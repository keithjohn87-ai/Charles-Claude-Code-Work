#!/bin/bash
# ContrPro webhook server launcher. Loads env from ~/charles/.env if present,
# then starts the FastAPI app via uvicorn. Default bind is 127.0.0.1:8090 —
# Cloudflare Tunnel (or ngrok) is what exposes it publicly.

set -u
cd /Users/home/charles/contrpro

# Pull config from main .env if it lives there (John keeps secrets there)
if [ -f /Users/home/charles/.env ]; then
  set -a
  source /Users/home/charles/.env 2>/dev/null
  set +a
fi

# Defaults the operator can override via env
: "${CONTRPRO_HOST:=127.0.0.1}"
: "${CONTRPRO_PORT:=8090}"

mkdir -p logs

exec /Users/home/charles/.venv/bin/python -m uvicorn \
  webhook_server:app \
  --host "$CONTRPRO_HOST" \
  --port "$CONTRPRO_PORT" \
  --no-access-log
