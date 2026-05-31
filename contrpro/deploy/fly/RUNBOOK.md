# ContrPro → Fly.io migration runbook

Lift-and-shift of the payment→delivery backend off the Mac. The storefront
(contrpro.com on GitHub Pages) does **not** move — only the webhook + download
+ email service does. Goal: it keeps working if the Mac is asleep, rebooting,
or dead.

**Framing:** one-month bridge. Single always-on machine, ~$5–10/mo. If ContrPro
doesn't perform / we close a buyer, tear it down (`fly apps destroy`).

What's already built in `deploy/fly/`:
- `Dockerfile` — packages the existing `webhook_server.py` + the 425MB of state
  zips + SBA guides, unchanged.
- `entrypoint.sh` — seeds the Gmail token + orders DB onto the volume on first boot.
- `fly.toml` — single always-on `shared-cpu-1x` / 512MB, 1GB `/data` volume.
- `requirements.txt` — pinned to the versions running on the Mac today.
- `seed/contrpro.db` — snapshot of the current 5 orders (seeded once, then the
  volume copy is authoritative).

The only code change to `webhook_server.py` was making the DB + log paths
env-overridable (same Mac defaults — local behavior is unchanged).

---

## Steps (run on the Mac — these need YOUR Fly account + secrets)

### 0. One-time: install + sign in
```sh
brew install flyctl          # if not already installed
fly auth login               # opens browser; creates/uses your Fly account
```

### 1. Create the app + volume
```sh
cd ~/charles/contrpro
fly launch --no-deploy --copy-config --config deploy/fly/fly.toml
#   - When prompted, accept the app name or pick one. If you change it,
#     update `app = ...` in deploy/fly/fly.toml to match.
fly volumes create contrpro_data --size 1 --region iad --yes
```

### 2. Set secrets (values come from ~/charles/.env and the Gmail token file)
The four real secrets + the public base. **Use the SAME `CONTRPRO_TOKEN_SECRET`
that's in your `.env`** — it signs download links, and reusing it keeps any
already-issued links valid.
```sh
# Pull these three values from ~/charles/.env:
fly secrets set \
  CONTRPRO_STRIPE_SECRET_KEY="sk_live_..." \
  CONTRPRO_STRIPE_WEBHOOK_SECRET="whsec_..." \
  CONTRPRO_TOKEN_SECRET="<same value as in .env>"

# Gmail OAuth token (whole file, as one secret):
fly secrets set CONTRPRO_GMAIL_TOKEN_JSON="$(cat ~/charles/workspace/gmail_token.json)"
```

### 3. First deploy
```sh
cd ~/charles/contrpro
fly deploy --config deploy/fly/fly.toml --dockerfile deploy/fly/Dockerfile
```
This uploads the ~425MB build context once — it can take a few minutes on home
upload. When it finishes, note the app URL, e.g. `https://contrpro-webhook.fly.dev`.

### 4. Point delivery links at the new home
```sh
fly secrets set CONTRPRO_PUBLIC_BASE="https://contrpro-webhook.fly.dev"
# (or your custom domain if you set one — see step 7)
```
> Download links in the customer email are built from `CONTRPRO_PUBLIC_BASE`.
> If this isn't set to the Fly URL, links will point at the wrong place.

### 5. Smoke-test before flipping Stripe
```sh
curl -s https://contrpro-webhook.fly.dev/health | python3 -m json.tool
```
Expect `"ok": true` and `stripe_configured`, `stripe_webhook_secret_configured`,
`gmail_token_present`, `token_secret_configured` all `true`.

### 6. Flip Stripe to the new webhook  ← the cutover
In the Stripe dashboard → **Developers → Webhooks**:
- **Edit the existing endpoint's URL** to `https://contrpro-webhook.fly.dev/webhook/stripe`
  (editing the URL keeps the same signing secret — no secret change needed).
- Confirm the event `checkout.session.completed` is still subscribed.
- Use **"Send test webhook"** → `checkout.session.completed` and confirm a 200
  in the Stripe UI and a log line via `fly logs`.

After this point, payments are delivered by Fly, not the Mac. You can stop the
Mac service once you've seen a clean test:
```sh
launchctl bootout gui/$(id -u)/com.charles.contrpro   # optional — frees the Mac
```

### 7. (Optional) custom domain
If you want `api.contrpro.com` instead of `*.fly.dev`:
```sh
fly certs add api.contrpro.com
# then add the CNAME/A records Fly prints, at your DNS provider
fly secrets set CONTRPRO_PUBLIC_BASE="https://api.contrpro.com"
```

### 8. Storefront follow-up (GitHub Pages repo — separate from this)
The static site's `beta.html` (login fetch) and any download/success pages that
call the backend currently point at the old Cloudflare-tunnel URL. Find/replace
that base URL with the new Fly URL (or `api.contrpro.com`) and push. The Stripe
**payment** flow itself doesn't need this — only the beta-login fetch does — but
do it so beta auth keeps working.

---

## Rollback
The Mac service is untouched and still works. To revert: re-point the Stripe
webhook URL back to the Cloudflare-tunnel address and re-start
`com.charles.contrpro` if you stopped it. Then `fly apps destroy <app>` when ready.

## Cost / teardown
One `shared-cpu-1x`/512MB always-on machine + 1GB volume ≈ $5–10/mo. Tear down
anytime with `fly apps destroy <app>` (also removes the volume).
