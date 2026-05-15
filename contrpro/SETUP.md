# ContrPro Webhook Backend — Setup

What this is: the server piece that closes the post-payment gap in
ContrPro.com. Static GitHub Pages can't take Stripe webhooks; this server
can. It runs on your Mac Studio alongside Charles.

**Status as of 2026-05-13 ~10:40 EDT (this morning, after refactor):**

  ✓ Stripe live secret key in .env
  ✓ Gmail OAuth (Charles's existing token, refactored away from SMTP)
  ✓ Token signing secret generated + in .env
  ✓ LaunchAgent bootstrapped + server running at 127.0.0.1:8090
  ✗ Stripe webhook secret — pending, needs the Cloudflare Tunnel URL first
  ✗ Cloudflare Tunnel — needs your hand (cloudflared install + auth)

What's left for you: the Cloudflare Tunnel (step 3 below) and registering
the webhook in Stripe (step 4). Everything else is done.

---

## What's already done

- `webhook_server.py` — FastAPI app. Routes:
  - `POST /webhook/stripe` — receives Stripe `checkout.session.completed`
  - `GET  /download/{token}` — verifies token, serves file or file-list page
  - `GET  /download/{token}/file/{idx}` — individual file in a multi-file tier
  - `GET  /admin/orders` — local-only, lists recent orders
  - `POST /admin/reissue/{order_id}` — local-only, reissue an expired link
  - `GET  /health` — config check
- HMAC-SHA256 signed download tokens with expiration. Tampering returns 410.
- SQLite tables (`orders`, `webhook_events`) auto-created on startup.
- Plain text + HTML delivery email via Gmail SMTP.
- Idempotent webhook handling (Stripe retries are deduped).
- Product file mapping (`TIER_FILES`) matches ContrPro's existing tiers.
- Product files staged at `~/charles/contrpro/files/`:
  - packages/essential-forms-79.zip
  - packages/professional-package-149.zip
  - packages/business-system-199.zip
  - packages/complete-bundle-249.zip
  - downloads/sba-guides/SBA_Guide.pdf + .docx
- LaunchAgent plist at `~/charles/launchd/com.charles.contrpro.plist`.
- Tested: server boots, all 4 endpoints respond correctly to good + bad input.

---

## Already done (don't redo these)

### ~~1. Set env vars~~ — DONE this morning

In `~/charles/.env`:
- `CONTRPRO_STRIPE_SECRET_KEY` — your live key (added 2026-05-13 from iMessage)
- `CONTRPRO_TOKEN_SECRET` — generated 64-byte hex
- `CONTRPRO_GMAIL_SENDER` — `CharlesCreatorAI@gmail.com`
- `CONTRPRO_SUPPORT_EMAIL` — `support@contrpro.com`

Gmail OAuth (refactored from the original SMTP plan): uses Charles's
existing token at `~/charles/workspace/gmail_token.json`. Already
authenticated as charlescreatorai@gmail.com. No app password needed.

Still pending: `CONTRPRO_STRIPE_WEBHOOK_SECRET` and `CONTRPRO_PUBLIC_BASE`
— both come from step 3 + step 4 below.

### ~~2. Activate the LaunchAgent~~ — DONE

```bash
launchctl list | grep contrpro    # com.charles.contrpro should have a PID
curl -s http://127.0.0.1:8090/health
```

Currently `/health` returns:
- `stripe_configured: true` ✓
- `gmail_token_present: true` ✓
- `token_secret_configured: true` ✓
- `stripe_webhook_secret_configured: false` ← will flip to true after step 4

## What YOU still have to do (2 steps, ~15 minutes)

### 3. Expose the webhook with Tailscale Funnel (no Cloudflare needed)

You already have Tailscale running for the WarRoom iOS app. Tailscale
Funnel reuses that infrastructure to expose a port from the Mac Studio to
the public internet at a stable URL. Free for personal use. Better than
Cloudflare because no new account / no new install / no DNS config —
the URL is already provisioned.

**3a. Enable Funnel on your tailnet (one-time, browser, ~10 seconds):**

  https://login.tailscale.com/admin/settings/funnel

Toggle Funnel ON. Sign in with your Apple ID.

**3b. Start the Funnel from the Mac terminal (one command):**

```bash
/Applications/Tailscale.app/Contents/MacOS/Tailscale funnel --bg 8090
```

This binds the public URL `https://homes-mac-studio.tail09ce02.ts.net/`
to localhost:8090. The `--bg` flag runs it in the background so it stays
alive after the shell exits.

Test from anywhere:

```bash
curl https://homes-mac-studio.tail09ce02.ts.net/health
```

Should return the same JSON as `curl http://127.0.0.1:8090/health`.

**3c. Update CONTRPRO_PUBLIC_BASE in `~/charles/.env`:**

```bash
CONTRPRO_PUBLIC_BASE=https://homes-mac-studio.tail09ce02.ts.net
```

Then kickstart so the webhook server picks up the new public URL (used
in the download link it emails to customers):

```bash
launchctl kickstart -k gui/$(id -u)/com.charles.contrpro
```

### 4. Configure Stripe webhook

In the Stripe dashboard (the ContractorPro account — acct_1T8L22FVfLIjIEWB):
- Developers → Webhooks → Add endpoint
- Endpoint URL: `https://homes-mac-studio.tail09ce02.ts.net/webhook/stripe`
- Events to listen to: `checkout.session.completed` (just that one for now)
- Click "Add endpoint"
- Click into the new endpoint → "Signing secret" → "Reveal" → copy it

Put it in `~/charles/.env`:
```bash
CONTRPRO_STRIPE_WEBHOOK_SECRET=whsec_...
```

Kickstart the service:
```bash
launchctl kickstart -k gui/$(id -u)/com.charles.contrpro
```

Confirm `/health` now shows `stripe_webhook_secret_configured: true`.

### 5. Test end-to-end with a real $0.50 purchase

- Visit ContrPro.com
- Add Essential ($79) to cart, but DON'T pay yet
- In Stripe dashboard, temporarily create a $0.50 test Payment Link OR use
  the existing one with a 100% off promo code (Stripe → Products → Coupons)
- Make a real purchase to your own email
- Watch `~/charles/contrpro/logs/webhook_server.log` for the webhook
- Check your inbox for the delivery email
- Click the download link → confirm you get the zip file
- Check `curl -s http://127.0.0.1:8090/admin/orders` shows the order

If anything fails, the log will tell you why. Common issues:
- "no customer_email present" — Stripe Payment Link wasn't configured to
  collect email. In dashboard, edit the Payment Link → "Customer
  information" → check "Always collect email."
- "could not resolve tier" — Payment Link's product name doesn't match the
  pattern matcher. Fix: in Stripe dashboard, add metadata `tier=essential`
  (or whichever) to the Payment Link.
- SMTP auth fails — Gmail app password is wrong. Regenerate.

---

## Front-end changes still needed on ContrPro.com (the repo)

These are tiny but they have to happen for the public site to use the new
backend. We'll do this together in the AM:

1. `js/stripe-config.js` — remove the `prompt('Please enter your email')`
   calls. Stripe Payment Links collect email natively. The browser doesn't
   need to handle it anymore.
2. `js/delivery-config.js` — delete the client-side `generateDownloadToken`
   and `verifyDownloadToken` functions. They're insecure and replaced.
3. `download.html` — replace the `ProductDelivery.verifyDownloadToken(token)`
   call with a fetch to `${CONTRPRO_PUBLIC_BASE}/download/{token}`. Simpler:
   just redirect the customer there. The new backend renders its own page.
4. `success.html` — strip the EmailDelivery code. Just say "Check your
   email, link's on the way."

I'll write the exact diffs in the AM.

---

## Manual operation (until we automate it)

To see recent orders:
```bash
curl -s http://127.0.0.1:8090/admin/orders | python3 -m json.tool
```

To reissue a download link for an order that's expired or the customer lost:
```bash
curl -X POST http://127.0.0.1:8090/admin/reissue/<order_id>
```

To watch live webhooks as they come in:
```bash
tail -F ~/charles/contrpro/logs/webhook_server.log
```

---

## What's NOT in scope here

- Subscription / recurring billing — current tiers are one-time only.
- Refunds — Stripe dashboard handles those; the order row stays as audit.
- VAT / tax — Stripe Tax can be enabled in the dashboard.
- Multi-product cart — ContrPro's current cart redirects to highest-tier
  Payment Link. Multi-item orders fold into one charge.

Once revenue is flowing we revisit.
