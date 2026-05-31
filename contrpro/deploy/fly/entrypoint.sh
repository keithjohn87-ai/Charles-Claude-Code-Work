#!/bin/sh
# Seed mutable state onto the /data volume on first boot, then run the server.
set -e

mkdir -p /data/logs

# Gmail OAuth token: seeded from the CONTRPRO_GMAIL_TOKEN_JSON secret on first
# boot. google-auth refreshes the access token in place on the volume, so the
# refresh_token survives restarts. Re-seed only happens if the file is missing.
if [ ! -f /data/gmail_token.json ] && [ -n "$CONTRPRO_GMAIL_TOKEN_JSON" ]; then
  printf '%s' "$CONTRPRO_GMAIL_TOKEN_JSON" > /data/gmail_token.json
fi

# Orders DB: copy the baked snapshot to the volume the first time only. After
# that the live volume DB is authoritative and is never overwritten.
if [ ! -f /data/contrpro.db ] && [ -f /app/seed/contrpro.db ]; then
  cp /app/seed/contrpro.db /data/contrpro.db
fi

exec python -m uvicorn webhook_server:app \
  --host 0.0.0.0 --port 8080 --no-access-log
