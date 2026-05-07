"""Gmail tools for Charles.

OAuth setup is one-time per Gmail account: first call to any of these tools
spawns a browser to authorize. Token is saved to workspace/gmail_token.json
so subsequent calls use it silently. Refresh tokens auto-renew.

Capabilities:
  - list_emails(query, max_results)  — search Gmail with the standard query syntax
  - read_email(message_id)           — full body + headers
  - send_email(to, subject, body)    — send from authenticated account
  - archive_email(message_id)        — move out of inbox
  - delete_email(message_id)         — Tier-2 action (irreversible) — gated via request_approval

Per John's instruction: 'Enable everything Gmail related for him' — full scope:
https://mail.google.com/

Account context: Charles primarily uses CharlesCreatorAI@gmail.com. John may
later authorize his personal Gmail too (different token file).
"""
from __future__ import annotations

import base64
import logging
import os
import pickle
from email.mime.text import MIMEText
from pathlib import Path

from core.tools import tool

log = logging.getLogger("charles.gmail")

WORKSPACE = Path("/Users/home/charles/workspace")
TOKEN_PATH = WORKSPACE / "gmail_token.json"
SCOPES = [os.environ.get("GOOGLE_OAUTH_SCOPES", "https://mail.google.com/")]


def _get_service():
    """Return an authorized Gmail API service. First call opens a browser."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
            client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
            if not client_id or not client_secret:
                raise RuntimeError(
                    "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET missing from .env"
                )
            client_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            # Use a local server flow — opens a browser to authorize
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
        log.info("saved Gmail token to %s", TOKEN_PATH)

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


@tool(
    name="list_emails",
    summary="Search Gmail using the standard query syntax (e.g., 'from:noreply@stripe.com', 'is:unread', 'after:2026/05/01'). Returns up to N message IDs + subject lines + sender. First call opens browser for OAuth.",
    triggers=("list emails", "search gmail", "find emails", "check inbox", "unread emails"),
    schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Gmail query syntax. Empty string returns recent inbox."},
            "max_results": {"type": "integer", "description": "Max messages to return (default 20).", "default": 20},
        },
        "required": ["query"],
    },
)
def list_emails(query: str = "", max_results: int = 20) -> str:
    try:
        svc = _get_service()
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"
    try:
        results = svc.users().messages().list(
            userId="me", q=query or "in:inbox", maxResults=max_results
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            return f"(no messages match {query!r})"
        out = []
        for m in messages:
            full = svc.users().messages().get(userId="me", id=m["id"], format="metadata",
                                              metadataHeaders=["From", "Subject", "Date"]).execute()
            headers = {h["name"]: h["value"] for h in full.get("payload", {}).get("headers", [])}
            out.append(
                f"{m['id']} | {headers.get('Date', '?')[:25]} | {headers.get('From', '?')[:40]} | "
                f"{headers.get('Subject', '(no subject)')[:80]}"
            )
        return "\n".join(out)
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"


@tool(
    name="read_email",
    summary="Read the full body of a Gmail message by ID. Use list_emails first to find IDs.",
    triggers=("read email", "open email", "show email", "email body"),
    schema={
        "type": "object",
        "properties": {"message_id": {"type": "string", "description": "Gmail message ID from list_emails."}},
        "required": ["message_id"],
    },
)
def read_email(message_id: str) -> str:
    try:
        svc = _get_service()
        msg = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    body = _extract_body(msg["payload"])
    return (
        f"From: {headers.get('From', '?')}\n"
        f"To: {headers.get('To', '?')}\n"
        f"Date: {headers.get('Date', '?')}\n"
        f"Subject: {headers.get('Subject', '(no subject)')}\n"
        f"---\n{body[:8000]}"
    )


def _extract_body(payload: dict) -> str:
    """Walk MIME payload and pull the plain-text body (or HTML stripped)."""
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        for part in payload["parts"]:
            text = _extract_body(part)
            if text:
                return text
    elif payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    return ""


@tool(
    name="send_email",
    summary="Send an email from the authenticated Gmail account. Use this for autonomous email work (replies, outreach, unsubscribe-confirm flows). For external-party emails (Tier-2), call request_approval FIRST.",
    triggers=("send email", "email", "reply to email", "compose email"),
    schema={
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email address."},
            "subject": {"type": "string"},
            "body": {"type": "string", "description": "Plain-text body."},
            "reply_to_id": {"type": "string", "description": "Optional Gmail message ID to thread as a reply."},
        },
        "required": ["to", "subject", "body"],
    },
)
def send_email(to: str, subject: str, body: str, reply_to_id: str = "") -> str:
    try:
        svc = _get_service()
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"
    msg = MIMEText(body)
    msg["To"] = to
    msg["Subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    payload = {"raw": raw}
    if reply_to_id:
        try:
            orig = svc.users().messages().get(userId="me", id=reply_to_id, format="metadata").execute()
            payload["threadId"] = orig.get("threadId")
        except Exception:  # noqa: BLE001
            pass
    try:
        sent = svc.users().messages().send(userId="me", body=payload).execute()
        return f"sent: id={sent['id']} threadId={sent.get('threadId')}"
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"


@tool(
    name="archive_email",
    summary="Remove the INBOX label from a message (i.e., archive it). Reversible.",
    triggers=("archive email",),
    schema={
        "type": "object",
        "properties": {"message_id": {"type": "string"}},
        "required": ["message_id"],
    },
)
def archive_email(message_id: str) -> str:
    try:
        svc = _get_service()
        svc.users().messages().modify(
            userId="me", id=message_id, body={"removeLabelIds": ["INBOX"]}
        ).execute()
        return f"archived {message_id}"
    except Exception as e:  # noqa: BLE001
        return f"[error] {type(e).__name__}: {e}"
