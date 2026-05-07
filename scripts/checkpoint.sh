#!/bin/bash
# Charles master checkpoint — snapshot everything irreplaceable.
#
# Usage:
#   bash scripts/checkpoint.sh                    # standard checkpoint
#   bash scripts/checkpoint.sh master-day0        # tagged checkpoint
#
# Includes: source tree, identity files, memory.db, self-modify backups.
# Excludes: models (re-downloadable), venv, __pycache__, /tmp leftovers.
#
# Destination, in priority order:
#   1. /Volumes/CharlesMemory/checkpoints/<tag>/   (external SSD per migration spec)
#   2. ~/charles/checkpoints/<tag>/                (internal fallback)

set -e
TAG="${1:-checkpoint-$(date +%Y%m%dT%H%M%S)}"
SRC="/Users/home/charles"

if [ -d /Volumes/CharlesMemory ]; then
    DEST="/Volumes/CharlesMemory/checkpoints/$TAG"
    LOC="external SSD"
else
    DEST="$SRC/checkpoints/$TAG"
    LOC="internal SSD (no external mounted)"
fi

mkdir -p "$DEST"
echo "[*] checkpointing to $DEST ($LOC)"

# rsync the live tree, excluding what's regenerable
rsync -a \
    --exclude='.venv' \
    --exclude='models' \
    --exclude='logs' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git/objects' \
    --exclude='workspace/voice_reference_short.wav' \
    "$SRC/" "$DEST/"

# Lightweight metadata
cat > "$DEST/CHECKPOINT_INFO.txt" <<EOF
Tag: $TAG
Created: $(date)
Host: $(hostname)
Git HEAD: $(cd "$SRC" && git rev-parse --short HEAD 2>/dev/null || echo "n/a")
Source: $SRC
Destination: $DEST
Location: $LOC

Charles process: $(pgrep -f "python.*charles.py" | head -1 || echo "(not running)")

Sizes:
  workspace: $(du -sh "$SRC/workspace" 2>/dev/null | awk '{print $1}')
  memory.db: $(ls -lh "$SRC/workspace/memory.db" 2>/dev/null | awk '{print $5}' || echo "n/a")
  source code: $(du -sh --exclude=.venv --exclude=models "$SRC" 2>/dev/null | awk '{print $1}')

NOTES:
  - models/ excluded (re-downloadable from HF / direct curl)
  - .venv excluded (re-installable via pip install -r requirements.txt)
  - logs/ excluded
  - .git/objects excluded (use git push for full git history backup)
  - voice_reference_short.wav excluded (deprecated, voice_reference.wav is canonical)
EOF

# Optionally tarball for archival
TAR="$DEST.tar.gz"
echo "[*] creating tarball $TAR"
tar -C "$(dirname "$DEST")" -czf "$TAR" "$(basename "$DEST")"

echo "[+] checkpoint complete"
echo "    dir:    $DEST"
echo "    tar:    $TAR ($(ls -lh "$TAR" | awk '{print $5}'))"
