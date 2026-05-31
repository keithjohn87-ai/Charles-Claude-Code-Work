# ContrPro webhook+delivery backend — Fly.io lift-and-shift.
# Build context is the contrpro/ dir (the repo subtree), NOT deploy/fly.
# Deploy with:  cd ~/charles/contrpro && fly deploy --config deploy/fly/fly.toml --dockerfile deploy/fly/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY deploy/fly/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Application code (unchanged from the Mac — only path env vars differ)
COPY webhook_server.py /app/webhook_server.py

# Served payload: state-tailored packages + SBA guides. The build-input dirs
# (state-research, sme-review) are intentionally NOT shipped — they aren't served.
COPY files/packages /app/files/packages
COPY files/downloads /app/files/downloads

# First-boot seed of the orders DB (copied to the volume only if absent)
COPY deploy/fly/seed/contrpro.db /app/seed/contrpro.db
COPY deploy/fly/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Container paths point at the baked files + the mounted /data volume.
# Secrets (Stripe keys, token secret, Gmail token JSON, public base) come from
# `fly secrets set` at runtime — never baked into the image.
ENV CONTRPRO_SITE_ROOT=/app/files \
    CONTRPRO_DB_PATH=/data/contrpro.db \
    CONTRPRO_LOG_DIR=/data/logs \
    CONTRPRO_GMAIL_TOKEN_PATH=/data/gmail_token.json \
    CONTRPRO_HOST=0.0.0.0 \
    CONTRPRO_PORT=8080

EXPOSE 8080
ENTRYPOINT ["/app/entrypoint.sh"]
