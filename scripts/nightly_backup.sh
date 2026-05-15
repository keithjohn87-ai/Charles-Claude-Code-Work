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

# 4. Rotate large logs. Anything > 10MB gets gzipped with date suffix.
#    Keeps 7 days of rotated logs, deletes older.
echo "[*] log rotation pass"
LOGDIR=/Users/home/charles/logs
for f in "$LOGDIR"/charles.launchd.err.log "$LOGDIR"/charles.launchd.out.log "$LOGDIR"/warroom.err.log "$LOGDIR"/warroom.out.log "$LOGDIR"/behavior_watchdog.log; do
    [ -f "$f" ] || continue
    size=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null)
    if [ "${size:-0}" -gt 10485760 ]; then
        ts=$(date +%Y%m%d-%H%M%S)
        gzip -c "$f" > "${f}.${ts}.gz" && : > "$f"
        echo "[*] rotated $(basename "$f") ($((size / 1024 / 1024))MB -> ${f}.${ts}.gz)"
    fi
done
# Drop rotated logs older than 7 days
find "$LOGDIR" -name "*.gz" -mtime +7 -delete 2>/dev/null

echo "[$(date)] nightly_backup done"
