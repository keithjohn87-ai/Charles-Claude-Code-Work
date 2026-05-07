#!/bin/bash
# Charles nightly backup. Runs daily via launchd at 3 AM EST.
#
# Steps:
#   1. Take a checkpoint (rsync + tarball, internal fallback if no SSD)
#   2. Stage + commit any uncommitted changes in workspace/ identity files
#   3. Push to origin if a remote exists — fails silently if no remote
#
# Logs: /Users/home/charles/logs/nightly_backup.log

set -e
LOG=/Users/home/charles/logs/nightly_backup.log
SRC=/Users/home/charles
mkdir -p "$(dirname "$LOG")"
exec >> "$LOG" 2>&1

echo ""
echo "============================================"
echo "[$(date)] nightly_backup starting"

# 1. Checkpoint with date tag
TAG="nightly-$(date +%Y-%m-%d)"
bash "$SRC/scripts/checkpoint.sh" "$TAG" || echo "[!] checkpoint step had issues, continuing"

# 2. Commit any drift in workspace/ identity files
cd "$SRC"
if [ -n "$(git status --porcelain workspace/SOUL.md workspace/IDENTITY.md workspace/USER.md workspace/TOOLS.md 2>/dev/null)" ]; then
    echo "[*] committing workspace identity drift"
    git add workspace/SOUL.md workspace/IDENTITY.md workspace/USER.md workspace/TOOLS.md 2>/dev/null || true
    git -c user.name="Charles" -c user.email="charles@local" commit -m "nightly: identity drift $(date +%Y-%m-%d)" || true
fi

# 3. Push if origin exists. Exit cleanly if not (user hasn't set up remote yet).
if git remote get-url origin >/dev/null 2>&1; then
    echo "[*] pushing to origin"
    git push origin main 2>&1 || echo "[!] push failed (network? auth?) — non-fatal"
else
    echo "[~] no origin remote configured — skipping push (set one up to enable cloud backup)"
fi

echo "[$(date)] nightly_backup done"
