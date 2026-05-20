"""ContrPro post-payment backend — Stripe webhook + signed download tokens.

This closes the gap in ContrPro.com that's been blocking revenue since the
v1 era. Site is static on GitHub Pages, so without a backend:
  - Stripe payments succeed but nothing tells the customer's email
  - "Delivery email" relies on the customer's browser loading success.html
    after paying. If they close the tab — no email, no delivery, support
    ticket.
  - "Download tokens" are client-side base64(email:tier:paymentId:ts) —
    anyone can fabricate a valid one in their browser console.

This service runs on the Mac Studio (alongside Charles), exposes:
  POST /webhook/stripe       — receives Stripe checkout.session.completed
  GET  /download/{token}     — verifies HMAC-signed token + redirects to file
  GET  /download/{token}.json — verifies + returns file list as JSON
  GET  /health               — liveness check

Exposed publicly via Cloudflare Tunnel (cloudflared) at a stable subdomain.
Stripe's webhook URL points at https://<tunnel>/webhook/stripe.

Token security: HMAC-SHA256 over (email|tier|paymentId|expires_at) using a
server-side secret. Verifier checks signature + expiration. Tokens are
single-use (recorded in SQLite; second use returns 410 Gone).

Email delivery: Gmail SMTP with an app password. Sender is configured via
env. Plain text + HTML alternative; download link expires in 72h.

Setup steps for John (in the AM):
  1. Pip install already done (stripe, fastapi, uvicorn in .venv).
  2. Set env vars in ~/charles/.env (see SETUP.md):
       CONTRPRO_STRIPE_SECRET_KEY = sk_live_xxx (from Stripe dashboard)
       CONTRPRO_STRIPE_WEBHOOK_SECRET = whsec_xxx (set after webhook
         configured in Stripe dashboard)
       CONTRPRO_TOKEN_SECRET = random_64_byte_hex (generate once with
         `python -c "import secrets; print(secrets.token_hex(32))"`)
       CONTRPRO_SMTP_USER = your_gmail@gmail.com
       CONTRPRO_SMTP_PASS = google_app_password (NOT your gmail password —
         generate at https://myaccount.google.com/apppasswords)
       CONTRPRO_PUBLIC_BASE = https://<cloudflare-tunnel-subdomain>/
       CONTRPRO_SUPPORT_EMAIL = support@contrpro.com (or wherever)
  3. Start: `bash scripts/contrpro_start.sh` (or via launchd plist).
  4. Set up cloudflared tunnel: `cloudflared tunnel create contrpro-webhook`
     then `cloudflared tunnel route dns <name> contrpro-webhook.contrpro.com`.
     (Detailed steps in SETUP.md once we set it up.)
  5. In Stripe dashboard → Webhooks → Add endpoint:
       URL:    https://<tunnel>/webhook/stripe
       Events: checkout.session.completed
     Copy the signing secret → put in env as CONTRPRO_STRIPE_WEBHOOK_SECRET.
  6. Update success.html and download.html on the contrpro repo to point at
     the new backend (a one-line code change — done in a follow-up commit).

The current download.html does CLIENT-SIDE base64 token verify. That stays
working for backward compat (existing customers with old tokens), but new
tokens issued by this server use the signed scheme and verify against /
download/.
"""
from __future__ import annotations

import base64
import hmac
import hashlib
import json
import logging
import os
import sqlite3
import time
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional

import stripe
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, HTMLResponse

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = Path("/Users/home/charles/contrpro/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / "webhook_server.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("contrpro.webhook")

# ---------------------------------------------------------------------------
# Config — read from env on import. Missing values do NOT crash startup so
# John can boot the server to test routes without setting up Stripe first;
# instead, each handler refuses politely if the relevant config is absent.
# ---------------------------------------------------------------------------

CFG = {
    "stripe_secret_key": os.environ.get("CONTRPRO_STRIPE_SECRET_KEY", ""),
    "stripe_webhook_secret": os.environ.get("CONTRPRO_STRIPE_WEBHOOK_SECRET", ""),
    "token_secret": os.environ.get("CONTRPRO_TOKEN_SECRET", ""),
    # Email delivery uses Charles's existing Gmail OAuth (token at
    # ~/charles/workspace/gmail_token.json, scope https://mail.google.com/).
    # Refactored from SMTP+app-password 2026-05-13 — John has OAuth already
    # wired so this is one less env var + one less setup step.
    "gmail_sender": os.environ.get("CONTRPRO_GMAIL_SENDER", "CharlesCreatorAI@gmail.com"),
    "gmail_token_path": os.environ.get(
        "CONTRPRO_GMAIL_TOKEN_PATH",
        "/Users/home/charles/workspace/gmail_token.json",
    ),
    "support_email": os.environ.get("CONTRPRO_SUPPORT_EMAIL", "support@contrpro.com"),
    "public_base": os.environ.get("CONTRPRO_PUBLIC_BASE", "https://contrpro.com"),
    "site_root": os.environ.get(
        "CONTRPRO_SITE_ROOT",
        "/Users/home/charles/contrpro/files",  # files served from here
    ),
    "token_ttl_seconds": int(os.environ.get("CONTRPRO_TOKEN_TTL", "259200")),  # 72h
    # Max successful landing-page downloads per token before the link is
    # locked. Customer must email support to re-issue. Tunable via env.
    "max_downloads_per_token": int(os.environ.get("CONTRPRO_MAX_DOWNLOADS", "3")),
}

if CFG["stripe_secret_key"]:
    stripe.api_key = CFG["stripe_secret_key"]

# Tier delivery resolution. As of 2026-05-18 the deliverable is state-tailored
# (per John's directive — "tailored to TN, not CA"). The buyer's state arrives
# via Stripe's client_reference_id query param on the Payment Link URL. The
# Complete tier is forked into complete-gc and complete-sub-steel by SKU.
#
# Pre-built state-tailored zips live under
#   /Users/home/charles/contrpro/files/packages/built/{STATE}-{tier_variant}.zip
# generated by contrpro/scripts/build_tailored_zip.py.
#
# tier_variant values:
#   essential | professional | business | complete-gc | complete-sub-steel | sba
#
# Falls back to the legacy non-tailored zip when the tailored zip doesn't
# exist yet (e.g. an order from before the state-tailoring deploy, or a
# state whose profile is still in the depth-pass queue).

_BUILT_DIR_REL = "packages/built"
_LEGACY_TIER_FALLBACK: dict[str, str] = {
    "essential": "packages/essential-forms-79.zip",
    "professional": "packages/professional-package-149.zip",
    "business": "packages/business-system-199.zip",
    "complete-gc": "packages/complete-bundle-249.zip",
    "complete-sub-steel": "packages/complete-bundle-249.zip",
    "complete-sub-plumbing": "packages/complete-bundle-249.zip",
    "complete-sub-electrical": "packages/complete-bundle-249.zip",
    "complete-sub-mechanical": "packages/complete-bundle-249.zip",
}


_SUB_TRADES = ("steel", "plumbing", "electrical", "mechanical")


def _parse_state_trade_ref(raw: str) -> tuple[str | None, str | None]:
    """Parse the client_reference_id into (state, trade).

    Accepted formats:
      "TN"               → state TN, no trade
      "TN__plumbing"     → state TN, trade plumbing
      "TN_PLUMBING"      → state TN, trade plumbing  (case-insensitive single underscore)
      "TN-plumbing"      → state TN, trade plumbing  (dash separator)

    Empty / malformed → (None, None).
    """
    raw = (raw or "").strip()
    if not raw:
        return (None, None)
    # Try the canonical double-underscore first
    for sep in ("__", "-", "_"):
        if sep in raw:
            head, _, tail = raw.partition(sep)
            head = head.upper().strip()
            tail = tail.lower().strip()
            if len(head) == 2 and head.isalpha() and tail in _SUB_TRADES:
                return (head, tail)
    # No separator → state only
    if len(raw) == 2 and raw.isalpha():
        return (raw.upper(), None)
    return (None, None)


def _resolve_tier_variant(tier: str, session: dict | None = None) -> str:
    """For Complete tier we need to disambiguate GC vs the four Sub-Trade
    variants. The Stripe payment link gives us the side (GC vs Sub-Steel);
    when the buyer selected a non-Steel sub trade, that intent rides in the
    client_reference_id as STATE__TRADE — we use that to upgrade the variant.

    For lower tiers the tier IS the variant.
    """
    if tier in ("essential", "professional", "business", "sba"):
        return tier
    if tier == "complete-gc":
        return tier
    if tier in ("complete-sub-steel", "complete-sub-plumbing",
                "complete-sub-electrical", "complete-sub-mechanical"):
        # If the Stripe link is the sub-steel one but the client_reference_id
        # encodes a different trade, prefer the client_reference_id intent.
        if session:
            raw_ref = (session.get("client_reference_id") or "").strip()
            _, trade = _parse_state_trade_ref(raw_ref)
            if trade and trade in _SUB_TRADES:
                return f"complete-sub-{trade}"
        return tier
    if tier == "complete" and session:
        line_items = (session.get("line_items") or {}).get("data") or []
        desc = ""
        if line_items:
            desc = ((line_items[0].get("description") if isinstance(line_items[0], dict) else None) or "").lower()
        if "gc" in desc or "general contractor" in desc:
            return "complete-gc"
        # Sub variant — let the client_reference_id pick the trade.
        raw_ref = (session.get("client_reference_id") or "").strip()
        _, trade = _parse_state_trade_ref(raw_ref)
        if trade and trade in _SUB_TRADES:
            return f"complete-sub-{trade}"
        # Description hints
        if "steel" in desc:
            return "complete-sub-steel"
        if "plumb" in desc:
            return "complete-sub-plumbing"
        if "electric" in desc:
            return "complete-sub-electrical"
        if "mechan" in desc or "hvac" in desc:
            return "complete-sub-mechanical"
        if "sub" in desc:
            return "complete-sub-steel"
    return "complete-gc"


def _tier_files(tier_variant: str, state: str | None = None) -> list[str]:
    """Resolve the on-disk file list for (tier_variant, state). Tries the
    state-tailored zip first; falls back to the legacy non-tailored zip."""
    if tier_variant == "sba":
        return [
            "downloads/sba-guides/SBA_Guide.pdf",
            "downloads/sba-guides/SBA_Guide.docx",
        ]
    if state:
        tailored = f"{_BUILT_DIR_REL}/{state.upper()}-{tier_variant}.zip"
        tailored_abs = Path(CFG["site_root"]) / tailored
        if tailored_abs.exists():
            return [tailored]
    fallback = _LEGACY_TIER_FALLBACK.get(tier_variant)
    return [fallback] if fallback else []


# Back-compat alias for endpoints that still read a static map.
# Treated as the legacy fallback list — state-aware code paths should use
# _tier_files(variant, state) instead.
TIER_FILES: dict[str, list[str]] = {
    k: [v] for k, v in _LEGACY_TIER_FALLBACK.items()
}
TIER_FILES["sba"] = [
    "downloads/sba-guides/SBA_Guide.pdf",
    "downloads/sba-guides/SBA_Guide.docx",
]
# Legacy "complete" key — older orders may reference it; keep pointing to the
# pre-fork bundle so reissue from the admin panel still works.
TIER_FILES["complete"] = ["packages/complete-bundle-249.zip"]


TIER_NAMES: dict[str, str] = {
    "essential": "Essential Forms",
    "professional": "Professional Package",
    "business": "Business System",
    "complete": "Complete Bundle",
    "complete-gc": "Complete Bundle — General Contractor",
    "complete-sub-steel": "Complete Bundle — Sub: Steel Erection",
    "complete-sub-plumbing": "Complete Bundle — Sub: Plumbing",
    "complete-sub-electrical": "Complete Bundle — Sub: Electrical",
    "complete-sub-mechanical": "Complete Bundle — Sub: Mechanical / HVAC",
    "sba": "SBA Funding Guide",
}

# Stripe Payment Link metadata mapping. When Stripe sends a webhook for a
# checkout.session.completed, we get the line items + the payment_link id
# but NOT directly the tier name. Map by the Stripe price IDs OR by
# pattern-matching the product name in the line item.
# This dict gets populated automatically on first webhook hit if missing,
# but can also be pre-seeded by John if he knows his Stripe price IDs.
STRIPE_PRICE_TO_TIER: dict[str, str] = {
    # populated dynamically; see _resolve_tier_from_session
}

# ---------------------------------------------------------------------------
# Persistence: SQLite for issued tokens + delivery records
# ---------------------------------------------------------------------------

DB_PATH = Path("/Users/home/charles/contrpro/contrpro.db")


def _db() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _db() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                stripe_session_id TEXT UNIQUE NOT NULL,
                customer_email    TEXT NOT NULL,
                tier              TEXT NOT NULL,
                amount_paid       INTEGER,
                currency          TEXT,
                token             TEXT NOT NULL,
                expires_at        INTEGER NOT NULL,
                delivery_status   TEXT NOT NULL DEFAULT 'pending',
                created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                last_download_at  TEXT,
                download_count    INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_orders_token ON orders(token);
            CREATE INDEX IF NOT EXISTS idx_orders_email ON orders(customer_email);

            -- 2026-05-18 state-tailored delivery: capture buyer's state and the
            -- resolved tier_variant (essential/.../complete-gc/complete-sub-steel).
            -- Both nullable for back-compat with pre-deploy orders.


            CREATE TABLE IF NOT EXISTS webhook_events (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                stripe_event_id TEXT UNIQUE NOT NULL,
                event_type    TEXT NOT NULL,
                handled_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                payload       TEXT
            );
            """
        )
        # Forward-only migration for state-tailored delivery (2026-05-18)
        cols = {row[1] for row in c.execute("PRAGMA table_info(orders)")}
        if "state" not in cols:
            c.execute("ALTER TABLE orders ADD COLUMN state TEXT")
        if "tier_variant" not in cols:
            c.execute("ALTER TABLE orders ADD COLUMN tier_variant TEXT")


# ---------------------------------------------------------------------------
# Token: HMAC-signed, expirable, single-resource. Format:
#   <hex_payload>.<hex_signature>
# Payload is JSON: {"e": email, "t": tier, "p": stripe_session_id, "x": exp_ts}
# ---------------------------------------------------------------------------


def _sign_token(payload: dict) -> str:
    if not CFG["token_secret"]:
        raise RuntimeError("CONTRPRO_TOKEN_SECRET not set")
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(CFG["token_secret"].encode(), raw, hashlib.sha256).hexdigest()
    return raw.hex() + "." + sig


def _verify_token(token: str) -> tuple[bool, dict | str]:
    """Return (True, payload_dict) on success; (False, reason) on failure."""
    if "." not in token:
        return False, "malformed"
    try:
        hex_payload, sig = token.split(".", 1)
        raw = bytes.fromhex(hex_payload)
    except ValueError:
        return False, "decode_failed"
    expected = hmac.new(CFG["token_secret"].encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False, "bad_signature"
    try:
        payload = json.loads(raw.decode())
    except json.JSONDecodeError:
        return False, "bad_json"
    if int(time.time()) > int(payload.get("x", 0)):
        return False, "expired"
    return True, payload


# ---------------------------------------------------------------------------
# Beta tester auth — server-side gate (replaces client-side JS gate that
# used to ship the password as a constant in beta.html). 2026-05-15.
#
# Threat model:
#   - Old gate: BETA_USER constant inline in beta.html JS source. Anyone with
#     view-source could read the password. localStorage flag also bypassable
#     in browser dev tools. Effectively no protection.
#   - New gate: server-side validation against PBKDF2-hashed credentials
#     stored in env. Successful login returns an HMAC-signed session token
#     (7-day expiry by default). Browser stores the token; subsequent loads
#     verify against /beta/verify.
#
# Env var format:
#   CONTRPRO_BETA_USERS = "email1@example.com:saltHex$iterations$hashHex,email2@example.com:..."
#
# Hash format follows _hash_password() output below. To add a new beta user,
# run: python3 scripts/contrpro_hash_password.py <password>
# Then append "<email>:<output>" to the env var.
# ---------------------------------------------------------------------------

import secrets

BETA_SESSION_TTL_SECONDS = int(os.environ.get("CONTRPRO_BETA_SESSION_TTL", str(7 * 24 * 3600)))


def _hash_password(password: str, salt: bytes | None = None, iterations: int = 200_000) -> str:
    """Return 'saltHex$iterations$hashHex' string. Uses PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{salt.hex()}${iterations}${h.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    """Constant-time verify a password against a stored hash."""
    try:
        salt_hex, iter_str, hash_hex = stored.split("$")
        salt = bytes.fromhex(salt_hex)
        iterations = int(iter_str)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(h, expected)


def _load_beta_users() -> dict[str, str]:
    """Parse CONTRPRO_BETA_USERS env var into {email_lowercase: password_hash}."""
    raw = os.environ.get("CONTRPRO_BETA_USERS", "").strip()
    if not raw:
        return {}
    out: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" not in pair:
            continue
        email, pw_hash = pair.split(":", 1)
        email = email.strip().lower()
        pw_hash = pw_hash.strip()
        if email and pw_hash:
            out[email] = pw_hash
    return out


# Loaded at import time. To add or remove users, update env + restart.
BETA_USERS: dict[str, str] = _load_beta_users()
log.info("beta auth: loaded %d configured beta users", len(BETA_USERS))


def _make_beta_session_token(email: str) -> str:
    """Issue a signed beta-session token. Distinct from download tokens by 'k' field."""
    payload = {
        "k": "beta_session",
        "e": email.lower(),
        "x": int(time.time()) + BETA_SESSION_TTL_SECONDS,
    }
    return _sign_token(payload)


def _verify_beta_session_token(token: str) -> tuple[bool, str | dict]:
    """Return (True, {email, exp}) on valid beta session; (False, reason) otherwise."""
    ok, payload = _verify_token(token)
    if not ok:
        return False, payload  # reason string
    if not isinstance(payload, dict):
        return False, "bad_payload"
    if payload.get("k") != "beta_session":
        return False, "wrong_kind"
    return True, {"email": payload.get("e", ""), "exp": int(payload.get("x", 0))}


# ---------------------------------------------------------------------------
# Stripe session → tier resolution
# ---------------------------------------------------------------------------


def _resolve_tier_from_session(session: dict) -> Optional[str]:
    """Inspect a Stripe checkout session and figure out which tier was bought.

    Strategy:
      1. If session.metadata has 'tier', use that (cleanest if Stripe Payment
         Link was configured with metadata).
      2. Otherwise, look at the first line item's price.id; check if we've
         mapped it already.
      3. Fallback: pattern-match against product name (e.g. "Essential" →
         "essential", "Bundle" → "complete").

    Returns the tier key or None.
    """
    md = session.get("metadata") or {}
    if md.get("tier") in TIER_FILES:
        return md["tier"]

    line_items = (session.get("line_items") or {}).get("data") or []
    if not line_items and session.get("id") and CFG["stripe_secret_key"]:
        # Stripe doesn't include line_items in checkout.session.completed
        # by default — need to fetch separately. Stripe SDK objects do not
        # expose dict-style .get(); use subscript with try/except.
        try:
            full = stripe.checkout.Session.retrieve(
                session["id"], expand=["line_items"]
            )
            li_obj = full["line_items"] if "line_items" in full else None
            line_items = (li_obj["data"] if li_obj and "data" in li_obj else []) or []
        except Exception as e:  # noqa: BLE001
            log.warning("could not fetch line_items for session %s: %s",
                        session.get("id"), e)

    # PATTERN-MATCH KEYWORDS — used in both the line_items path AND the
    # payment_link fallback below.
    _TIER_KEYWORDS = [
        ("general contractor", "complete-gc"),
        ("steel erection", "complete-sub-steel"),
        ("plumbing", "complete-sub-plumbing"),
        ("electrical", "complete-sub-electrical"),
        ("mechanical", "complete-sub-mechanical"),
        ("hvac", "complete-sub-mechanical"),
        ("complete bundle", "complete"),
        ("business system", "business"),
        ("professional", "professional"),
        ("essential", "essential"),
        ("sba", "sba"),
    ]

    if line_items:
        first = line_items[0]
        price_obj = first["price"] if "price" in first else None
        price_id = price_obj["id"] if price_obj and "id" in price_obj else None
        if price_id and price_id in STRIPE_PRICE_TO_TIER:
            return STRIPE_PRICE_TO_TIER[price_id]

        desc = ((first["description"] if "description" in first else "") or "").lower()
        for keyword, tier in _TIER_KEYWORDS:
            if keyword in desc:
                if price_id:
                    STRIPE_PRICE_TO_TIER[price_id] = tier
                return tier

    # FALLBACK 1: free-checkout (100% coupon) — Stripe returns empty line_items
    # on $0 sessions. Retrieve the Payment Link object directly to get the
    # product behind it.
    plink_field = session.get("payment_link")
    plink_id = plink_field if isinstance(plink_field, str) else (
        plink_field.get("id") if isinstance(plink_field, dict) else None
    )
    if plink_id and CFG.get("stripe_secret_key"):
        try:
            pl = stripe.PaymentLink.retrieve(
                plink_id, expand=["line_items", "line_items.data.price.product"]
            )
            pl_li = (pl.line_items.data if hasattr(pl, "line_items") else None) or []
            if pl_li:
                first = pl_li[0]
                desc = (first.description or "").lower() if hasattr(first, "description") else ""
                if not desc:
                    prod = getattr(first.price, "product", None) if hasattr(first, "price") else None
                    prod_name = getattr(prod, "name", None) if prod else None
                    desc = (prod_name or "").lower()
                for keyword, tier in _TIER_KEYWORDS:
                    if keyword in desc:
                        log.info("session %s: resolved via payment_link fallback → %s",
                                 session.get("id"), tier)
                        return tier
        except Exception as e:  # noqa: BLE001
            log.warning("payment_link fallback failed for session %s: %s",
                        session.get("id"), e)

    # FALLBACK 2: client_reference_id encodes the trade (STATE__trade format).
    # If buyer picked a Sub trade, that tells us complete-sub-{trade}.
    raw_ref = (session.get("client_reference_id") or "").strip()
    if raw_ref:
        try:
            _state, _trade = _parse_state_trade_ref(raw_ref)
            if _trade in ("steel", "plumbing", "electrical", "mechanical"):
                log.info("session %s: resolved via client_reference_id trade → complete-sub-%s",
                         session.get("id"), _trade)
                return f"complete-sub-{_trade}"
        except Exception as e:  # noqa: BLE001
            log.warning("client_reference_id fallback failed: %s", e)

    return None


# ---------------------------------------------------------------------------
# Email send (Gmail SMTP)
# ---------------------------------------------------------------------------


def _gmail_service():
    """Authorized Gmail API service using Charles's existing OAuth token.

    Token + refresh credentials live at CFG['gmail_token_path']. If the
    token's expired, google-auth's Request() flow refreshes it
    transparently using the stored refresh_token. This is the same
    pattern tools/gmail.py uses; both processes can share the same
    token file safely (google-auth writes atomically).
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_path = CFG["gmail_token_path"]
    if not os.path.exists(token_path):
        raise RuntimeError(
            f"Gmail token not found at {token_path}. "
            "Run any Charles gmail tool once to do the OAuth handshake."
        )
    creds = Credentials.from_authorized_user_file(
        token_path, ["https://mail.google.com/"]
    )
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Persist the refreshed token
            with open(token_path, "w") as fh:
                fh.write(creds.to_json())
        else:
            raise RuntimeError(
                "Gmail credentials invalid and no refresh token available — "
                "re-run the OAuth handshake via Charles's gmail tool."
            )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _send_delivery_email(
    to_email: str, tier: str, download_url: str, customer_name: str = ""
) -> bool:
    tier_name = TIER_NAMES.get(tier, tier)
    greeting = customer_name or to_email.split("@")[0].title()

    text_body = f"""Hi {greeting},

Thank you for purchasing the {tier_name} from ContractorPro.

Your download is ready. Click below to access your files:

  {download_url}

This link is valid for 72 hours. After that, just reply to this email and
we'll re-issue it.

If you have any questions about the documents, the SBA process, or anything
else, hit reply — real humans answer.

— ContractorPro
{CFG['support_email']}
"""

    html_body = f"""<!DOCTYPE html>
<html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2 style="color: #1e3a5f;">ContractorPro — Order Complete</h2>
  <p>Hi {greeting},</p>
  <p>Thank you for purchasing the <strong>{tier_name}</strong> from ContractorPro.</p>
  <p>Your download is ready:</p>
  <p style="margin: 30px 0;">
    <a href="{download_url}" style="background:#1e3a5f;color:#fff;padding:14px 32px;
       border-radius:8px;text-decoration:none;font-weight:bold;">
      Download Your Files
    </a>
  </p>
  <p style="color: #666; font-size: 14px;">
    This link is valid for 72 hours. If it expires, reply to this email and
    we'll re-issue it.
  </p>
  <p style="color: #666; font-size: 14px;">
    Questions? Just hit reply — real humans answer.
  </p>
  <p style="color: #999; font-size: 12px; margin-top: 40px;">
    ContractorPro · {CFG['support_email']}
  </p>
</body></html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your ContractorPro {tier_name} — download ready"
    msg["From"] = CFG["gmail_sender"]
    msg["To"] = to_email
    msg["Reply-To"] = CFG["support_email"]
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        svc = _gmail_service()
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = svc.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        log.info(
            "delivery email sent to %s (tier=%s) gmail_msg_id=%s",
            to_email, tier, sent.get("id"),
        )
        return True
    except Exception as e:  # noqa: BLE001
        log.exception("Gmail send failed for %s: %s", to_email, e)
        return False


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="ContrPro Webhook + Download Backend")

# CORS — beta.html is served from the static contrpro.com site; the auth
# endpoints below are called cross-origin from that page. Lock the allow-list
# tightly: production site + localhost for dev.
_CORS_ORIGINS = [
    "https://contrpro.com",
    "https://www.contrpro.com",
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    _init_db()
    log.info("contrpro webhook server starting; site_root=%s db=%s",
             CFG["site_root"], DB_PATH)


@app.get("/health")
def health() -> dict:
    gmail_token_ok = os.path.exists(CFG["gmail_token_path"])
    return {
        "ok": True,
        "ts": int(time.time()),
        "stripe_configured": bool(CFG["stripe_secret_key"]),
        "stripe_webhook_secret_configured": bool(CFG["stripe_webhook_secret"]),
        "gmail_token_present": gmail_token_ok,
        "token_secret_configured": bool(CFG["token_secret"]),
        "public_base": CFG["public_base"],
        "beta_users_configured": len(BETA_USERS),
    }


# ---------------------------------------------------------------------------
# Beta tester auth — POST /beta/login + GET /beta/verify
# ---------------------------------------------------------------------------
#
# In-memory rate-limit: per-email failed-attempt counter with 60-second window.
# After 5 failures in 60s, the email is locked for 5 minutes. This is a
# best-effort defense against credential stuffing; for stronger protection,
# put the public endpoint behind Cloudflare Turnstile or a similar challenge.
_BETA_FAIL_WINDOW_SECONDS = 60
_BETA_FAIL_LIMIT = 5
_BETA_LOCK_SECONDS = 300
# {email_lowercase: [(ts1, ts2, ...), unlock_until_ts]}
_beta_fail_state: dict[str, dict] = {}


def _beta_check_rate_limit(email: str) -> tuple[bool, str]:
    """Return (allowed, reason). Cleans up expired records as a side effect."""
    now = int(time.time())
    state = _beta_fail_state.get(email)
    if not state:
        return True, ""
    # Honor active lock first
    if state.get("locked_until", 0) > now:
        wait = state["locked_until"] - now
        return False, f"too_many_attempts_wait_{wait}s"
    # Drop expired failures from the window
    cutoff = now - _BETA_FAIL_WINDOW_SECONDS
    state["fails"] = [t for t in state.get("fails", []) if t >= cutoff]
    if len(state["fails"]) >= _BETA_FAIL_LIMIT:
        state["locked_until"] = now + _BETA_LOCK_SECONDS
        return False, f"too_many_attempts_wait_{_BETA_LOCK_SECONDS}s"
    return True, ""


def _beta_record_failure(email: str) -> None:
    now = int(time.time())
    state = _beta_fail_state.setdefault(email, {"fails": [], "locked_until": 0})
    state["fails"].append(now)


def _beta_clear_failures(email: str) -> None:
    _beta_fail_state.pop(email, None)


@app.post("/beta/login")
async def beta_login(request: Request) -> JSONResponse:
    """Validate beta credentials, return a 7-day signed session token.

    Body: {"email": "...", "password": "..."}
    Response (200): {"token": "...", "expires_in": <seconds>, "email": "..."}
    Response (401): {"error": "invalid_credentials"} or {"error": "too_many_attempts_wait_<n>s"}
    Response (503): {"error": "beta_auth_not_configured"} when no CONTRPRO_BETA_USERS set
    """
    if not CFG["token_secret"]:
        return JSONResponse({"error": "server_token_secret_not_configured"}, status_code=503)
    if not BETA_USERS:
        return JSONResponse({"error": "beta_auth_not_configured"}, status_code=503)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "bad_json"}, status_code=400)

    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        return JSONResponse({"error": "missing_credentials"}, status_code=400)

    allowed, reason = _beta_check_rate_limit(email)
    if not allowed:
        log.warning("beta_login: rate-limited email=%s reason=%s", email, reason)
        return JSONResponse({"error": reason}, status_code=429)

    pw_hash = BETA_USERS.get(email)
    # Always perform a PBKDF2 hash (even on email-not-found) so timing leaks
    # don't reveal whether an email is in the allow-list.
    if pw_hash is None:
        # Run a dummy verify against a known-fake hash to keep the timing
        # roughly comparable to a real verify.
        _verify_password(password, _hash_password("dummy"))
        _beta_record_failure(email)
        log.info("beta_login: unknown email %s", email)
        return JSONResponse({"error": "invalid_credentials"}, status_code=401)

    if not _verify_password(password, pw_hash):
        _beta_record_failure(email)
        log.info("beta_login: bad password for %s", email)
        return JSONResponse({"error": "invalid_credentials"}, status_code=401)

    _beta_clear_failures(email)
    token = _make_beta_session_token(email)
    log.info("beta_login: success for %s", email)
    return JSONResponse({
        "token": token,
        "expires_in": BETA_SESSION_TTL_SECONDS,
        "email": email,
    })


@app.get("/beta/verify")
def beta_verify(token: str) -> JSONResponse:
    """Verify a beta session token. Used by beta.html on page load.

    Query: ?token=<jwt-like-token>
    Response (200): {"valid": true, "email": "...", "exp": <ts>}
    Response (401): {"valid": false, "reason": "..."}
    """
    if not token:
        return JSONResponse({"valid": False, "reason": "missing_token"}, status_code=401)
    ok, payload = _verify_beta_session_token(token)
    if not ok:
        return JSONResponse({"valid": False, "reason": str(payload)}, status_code=401)
    return JSONResponse({"valid": True, **payload})


@app.post("/webhook/stripe")
async def webhook_stripe(request: Request) -> JSONResponse:
    """Receive Stripe webhook events. Verifies signature, processes
    checkout.session.completed: issue token + email customer."""
    if not CFG["stripe_webhook_secret"]:
        log.error("webhook hit but CONTRPRO_STRIPE_WEBHOOK_SECRET not set")
        raise HTTPException(503, "Webhook secret not configured on server")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        stripe.Webhook.construct_event(
            payload, sig_header, CFG["stripe_webhook_secret"]
        )
    except stripe.SignatureVerificationError as e:
        log.warning("stripe webhook bad signature: %s", e)
        raise HTTPException(400, "Invalid signature")
    except ValueError as e:
        log.warning("stripe webhook bad payload: %s", e)
        raise HTTPException(400, "Invalid payload")

    # Signature verified — parse as plain dict so .get() works at every
    # nesting level. Stripe SDK objects do not support dict-style .get().
    event = json.loads(payload)
    event_id = event["id"]
    event_type = event["type"]
    log.info("stripe webhook received: id=%s type=%s", event_id, event_type)

    # Dedup — Stripe retries; we should be idempotent
    with _db() as c:
        prior = c.execute(
            "SELECT 1 FROM webhook_events WHERE stripe_event_id=?", (event_id,)
        ).fetchone()
    if prior:
        return JSONResponse({"received": True, "deduped": True})

    handler_succeeded = False
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        try:
            await _handle_checkout_complete(session)
            # If we got here without raising, _handle_checkout_complete either
            # created+delivered the order OR found a prior order (idempotent
            # reissue). Either way the event is "done" and safe to dedup.
            handler_succeeded = True
        except Exception as e:  # noqa: BLE001
            log.exception("unhandled error in _handle_checkout_complete for session %s: %s",
                          session.get("id"), e)
    else:
        # Non-checkout events (subscription, refund, etc.) — accept + dedup so
        # we don't reprocess them on Stripe retries.
        handler_succeeded = True

    # Only mark the event as "processed" if the handler actually completed.
    # Failed events stay UN-deduped so a Stripe resend (manual or auto) gets a
    # fresh shot at processing them. This was the 2026-05-19 bug — failed events
    # were silently deduped, so resends after a code fix never fired.
    if handler_succeeded:
        with _db() as c:
            c.execute(
                "INSERT OR IGNORE INTO webhook_events (stripe_event_id, event_type, payload) VALUES (?, ?, ?)",
                (event_id, event_type, json.dumps(event)[:50_000]),
            )
    else:
        log.warning("event %s NOT inserted into webhook_events — handler failed; "
                    "Stripe will retry (or you can manually resend)", event_id)
    return JSONResponse({"received": True})


async def _handle_checkout_complete(session: dict) -> None:
    session_id = session.get("id")
    customer_email = session.get("customer_email") or session.get(
        "customer_details", {}
    ).get("email")
    amount = session.get("amount_total")
    currency = session.get("currency", "usd")

    if not customer_email:
        log.error("session %s: no customer_email present, cannot deliver", session_id)
        return

    tier = _resolve_tier_from_session(session)
    if not tier:
        # Dump safe diagnostic info so we can fix the resolver — no secrets.
        line_items = (session.get("line_items") or {}).get("data") or []
        line_diag = []
        for li in line_items[:3]:
            li_get = (lambda obj, k: (obj.get(k) if isinstance(obj, dict) else getattr(obj, k, None)))
            desc = li_get(li, "description")
            price = li_get(li, "price") or {}
            price_id = li_get(price, "id")
            prod = li_get(price, "product")
            prod_name = li_get(prod, "name") if isinstance(prod, dict) else (str(prod)[:30] if prod else None)
            line_diag.append({"desc": desc, "price_id": price_id, "product_name": prod_name})
        log.error(
            "session %s: could not resolve tier — amount_total=%s currency=%s "
            "client_reference_id=%r metadata=%s line_items=%s",
            session_id, session.get("amount_total"), session.get("currency"),
            session.get("client_reference_id"),
            dict(session.get("metadata") or {}),
            line_diag,
        )
        return

    # State-tailored delivery: buyer's USPS state code arrives via the Stripe
    # Payment Link's ?client_reference_id=XX query parameter. The buyer's
    # trade choice (plumbing/electrical/mechanical/steel) arrives in the
    # same field as STATE__TRADE (e.g. "TN__plumbing") when Sub side is
    # selected. _parse_state_trade_ref handles both shapes.
    raw_ref = (session.get("client_reference_id") or "").strip()
    state, _ = _parse_state_trade_ref(raw_ref)
    tier_variant = _resolve_tier_variant(tier, session)

    # Idempotency on session_id
    with _db() as c:
        prior = c.execute(
            "SELECT token FROM orders WHERE stripe_session_id=?", (session_id,)
        ).fetchone()
    if prior:
        log.info("session %s already has order; resending email with existing token",
                 session_id)
        token = prior["token"]
    else:
        expires_at = int(time.time()) + CFG["token_ttl_seconds"]
        token = _sign_token({
            "e": customer_email,
            "t": tier_variant,           # variant (complete-gc / complete-sub-steel) — keeps download path tight
            "s": state,                  # state code or None
            "p": session_id,
            "x": expires_at,
        })
        with _db() as c:
            c.execute(
                "INSERT INTO orders "
                "(stripe_session_id, customer_email, tier, amount_paid, currency, "
                "token, expires_at, state, tier_variant) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, customer_email, tier, amount, currency, token,
                 expires_at, state, tier_variant),
            )
        log.info("session %s: created order tier=%s variant=%s state=%s email=%s",
                 session_id, tier, tier_variant, state or "(none)", customer_email)

    download_url = f"{CFG['public_base'].rstrip('/')}/download/{token}"
    sent = _send_delivery_email(customer_email, tier, download_url)

    with _db() as c:
        c.execute(
            "UPDATE orders SET delivery_status=? WHERE stripe_session_id=?",
            ("sent" if sent else "queued", session_id),
        )


@app.get("/download/{token}")
def download_landing(token: str) -> Response:
    """Landing page customer hits from the delivery email. Shows a soft-auth
    gate: visitor must enter the buyer-of-record email to proceed. Does NOT
    increment the download counter — only successful POST verifications do.
    """
    ok, payload = _verify_token(token)
    if not ok:
        return HTMLResponse(_error_page("Invalid or expired link", str(payload)), status_code=410)

    email = payload["e"]
    session_id = payload["p"]
    max_downloads = CFG["max_downloads_per_token"]

    with _db() as c:
        row = c.execute(
            "SELECT download_count FROM orders WHERE token=?", (token,)
        ).fetchone()
    if row is None:
        log.warning("landing hit with valid signature but no order row: session=%s",
                    session_id)
        return HTMLResponse(_error_page("Link not recognized", ""), status_code=410)
    if row["download_count"] >= max_downloads:
        return HTMLResponse(
            _limit_reached_page(email, max_downloads), status_code=429
        )

    return HTMLResponse(_email_gate_page(token, error_msg=""))


@app.post("/download/{token}")
async def download_verify(token: str, request: Request) -> Response:
    """Email-gate verification. Customer enters their buyer email; if it
    matches the token's e-claim, we increment the download counter and
    serve the file (single-tier) or the index page (multi-file tiers like
    sba). On mismatch we re-render the form with a polite error. The cap
    check still runs here in case it was hit between landing and submit.
    """
    ok, payload = _verify_token(token)
    if not ok:
        return HTMLResponse(_error_page("Invalid or expired link", str(payload)), status_code=410)

    tier = payload["t"]
    email = payload["e"]
    session_id = payload["p"]
    max_downloads = CFG["max_downloads_per_token"]

    form = await request.form()
    entered = (form.get("email") or "").strip().lower()
    expected = email.strip().lower()

    if entered != expected:
        log.info("email gate mismatch for session %s (entered=%s expected=%s)",
                 session_id, entered or "(empty)", expected)
        return HTMLResponse(
            _email_gate_page(
                token,
                error_msg="That email doesn't match the buyer of record. "
                          "Use the address you bought with.",
            ),
            status_code=403,
        )

    # Check + bump download counter atomically. Cap is per-token: cleanly
    # enforces "3 downloads of this bundle" while the cryptographic token
    # binds the link to the buyer's email. Anything past the cap → email
    # support and Charles re-issues.
    with _db() as c:
        row = c.execute(
            "SELECT download_count FROM orders WHERE token=?", (token,)
        ).fetchone()
        if row is None:
            log.warning("verify hit with valid signature but no order row: session=%s",
                        session_id)
            return HTMLResponse(_error_page("Link not recognized", ""), status_code=410)
        if row["download_count"] >= max_downloads:
            log.info("download cap hit for session %s email %s count=%s",
                     session_id, email, row["download_count"])
            return HTMLResponse(
                _limit_reached_page(email, max_downloads), status_code=429
            )
        c.execute(
            "UPDATE orders SET last_download_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), "
            "download_count=download_count+1 WHERE token=?",
            (token,),
        )

    state = payload.get("s")
    files = _tier_files(tier, state)
    if not files:
        files = TIER_FILES.get(tier, [])  # back-compat with pre-tailoring tokens
    if len(files) == 1:
        return _serve_file(files[0], token)
    return HTMLResponse(_index_page(tier, files, token, email))


@app.get("/download/{token}/file/{idx}")
def download_file_by_index(token: str, idx: int) -> Response:
    ok, payload = _verify_token(token)
    if not ok:
        return HTMLResponse(_error_page("Invalid or expired link", str(payload)), status_code=410)
    state = payload.get("s")
    files = _tier_files(payload["t"], state)
    if not files:
        files = TIER_FILES.get(payload["t"], [])
    if not 0 <= idx < len(files):
        raise HTTPException(404, "file index out of range")
    return _serve_file(files[idx], token)


def _serve_file(rel_path: str, token: str) -> Response:
    abs_path = Path(CFG["site_root"]) / rel_path
    if not abs_path.is_file():
        log.error("download requested for missing file: %s", abs_path)
        raise HTTPException(404, f"file not on disk: {rel_path}")
    return FileResponse(
        str(abs_path),
        filename=abs_path.name,
        media_type="application/octet-stream",
    )


def _index_page(tier: str, files: list[str], token: str, email: str) -> str:
    tier_name = TIER_NAMES.get(tier, tier)
    rows = []
    for i, f in enumerate(files):
        name = Path(f).name
        rows.append(
            f'<li style="margin: 12px 0;"><a href="/download/{token}/file/{i}" '
            f'style="color: #1e3a5f; text-decoration: none; font-weight: 600;">📄 {name}</a></li>'
        )
    return f"""<!DOCTYPE html>
<html><head><title>Your ContractorPro Download</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 700px; margin: 40px auto; padding: 20px; }}
  h1 {{ color: #1e3a5f; }}
  ul {{ list-style: none; padding: 0; }}
  .meta {{ color: #666; font-size: 14px; }}
</style></head>
<body>
  <h1>Your {tier_name} files are ready</h1>
  <p class="meta">Delivered to {email}. Click any file to download:</p>
  <ul>{''.join(rows)}</ul>
  <p class="meta" style="margin-top: 40px;">
    Link expires 72 hours after purchase. Need it re-issued? Reply to the
    email we sent you.
  </p>
</body></html>"""


def _error_page(title: str, detail: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><title>{title}</title>
<style>body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 60px auto; padding: 20px; text-align: center; }}
h1 {{ color: #b91c1c; }}</style></head>
<body>
  <h1>⏰ {title}</h1>
  <p>{detail}</p>
  <p style="color: #666;">If this link should still work, email
    <a href="mailto:{CFG['support_email']}">{CFG['support_email']}</a> and
    we'll re-issue.
  </p>
  <p><a href="https://contrpro.com">← Back to ContractorPro</a></p>
</body></html>"""


def _email_gate_page(token: str, error_msg: str = "") -> str:
    err_html = (
        f'<p style="color:#b91c1c; font-size:14px; margin-top:12px;">{error_msg}</p>'
        if error_msg else ""
    )
    return f"""<!DOCTYPE html>
<html><head><title>Confirm your email — ContractorPro</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 480px; margin: 60px auto; padding: 24px; }}
  h1 {{ color: #1e3a5f; }}
  label {{ display: block; margin-top: 16px; font-weight: 600; color: #1e3a5f; }}
  input[type=email] {{ width: 100%; padding: 12px; font-size: 16px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }}
  button {{ margin-top: 20px; width: 100%; background: #1e3a5f; color: #fff; padding: 14px; border: 0; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; }}
  .meta {{ color: #666; font-size: 14px; margin-top: 24px; }}
</style></head>
<body>
  <h1>Confirm your email</h1>
  <p>Enter the email address you used to purchase. We send this once to
  the buyer of record — it keeps the link from being passed around.</p>
  <form method="POST" action="/download/{token}">
    <label for="email">Purchase email</label>
    <input type="email" id="email" name="email" required autofocus
           placeholder="you@example.com" autocomplete="email">
    {err_html}
    <button type="submit">Access my download</button>
  </form>
  <p class="meta">Trouble? Email
    <a href="mailto:{CFG['support_email']}">{CFG['support_email']}</a>
    and we'll sort it out.</p>
</body></html>"""


def _limit_reached_page(email: str, cap: int) -> str:
    support = CFG["support_email"]
    subject = "ContractorPro re-issue request"
    body = (
        f"Hi, I bought a ContractorPro bundle (purchased under {email}) and "
        "I'd like my download link re-issued. Thanks."
    )
    mailto = (
        f"mailto:{support}?subject={urllib.parse.quote(subject)}"
        f"&body={urllib.parse.quote(body)}"
    )
    return f"""<!DOCTYPE html>
<html><head><title>Download limit reached</title>
<style>body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 60px auto; padding: 20px; text-align: center; }}
h1 {{ color: #1e3a5f; }}
.btn {{ display: inline-block; background:#1e3a5f; color:#fff; padding:14px 28px; border-radius:8px; text-decoration:none; font-weight:bold; margin-top: 16px; }}
.meta {{ color: #666; font-size: 14px; }}</style></head>
<body>
  <h1>Download limit reached</h1>
  <p>This link has already been used <strong>{cap}</strong> times — the cap
  per purchase. The bundle was delivered to <strong>{email}</strong>.</p>
  <p class="meta">If you need it again — switched computers, lost the file,
  whatever — just email support from that same address and we'll re-issue
  within a few hours.</p>
  <p><a class="btn" href="{mailto}">Email support to re-issue</a></p>
  <p class="meta" style="margin-top: 24px;">
    Or write us directly: <a href="mailto:{support}">{support}</a>
  </p>
</body></html>"""


# ---------------------------------------------------------------------------
# Admin (local-only): list recent orders, manually re-issue a token.
# ---------------------------------------------------------------------------


@app.get("/admin/orders")
def admin_recent_orders(limit: int = 30) -> dict:
    with _db() as c:
        rows = c.execute(
            "SELECT id, stripe_session_id, customer_email, tier, amount_paid, "
            "delivery_status, created_at, download_count "
            "FROM orders ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return {"orders": [dict(r) for r in rows]}


@app.post("/admin/reissue/{order_id}")
def admin_reissue(order_id: int) -> dict:
    with _db() as c:
        row = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        raise HTTPException(404, "order not found")
    expires_at = int(time.time()) + CFG["token_ttl_seconds"]
    new_token = _sign_token({
        "e": row["customer_email"],
        "t": row["tier"],
        "p": row["stripe_session_id"],
        "x": expires_at,
    })
    with _db() as c:
        c.execute(
            "UPDATE orders SET token=?, expires_at=?, delivery_status='reissued' "
            "WHERE id=?",
            (new_token, expires_at, order_id),
        )
    download_url = f"{CFG['public_base'].rstrip('/')}/download/{new_token}"
    sent = _send_delivery_email(row["customer_email"], row["tier"], download_url)
    return {"reissued": True, "sent": sent, "download_url": download_url}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.environ.get("CONTRPRO_HOST", "127.0.0.1"),
        port=int(os.environ.get("CONTRPRO_PORT", "8090")),
        log_level="info",
    )
