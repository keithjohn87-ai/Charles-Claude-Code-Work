#!/bin/bash
# Charles master checkpoint — snapshot everything irreplaceable.
#
# Usage:
#   bash scripts/checkpoint.sh                    # standard checkpoint
#   bash scripts/checkpoint.sh master-day0        # tagged checkpoint
#
# Includes: source tree, identity files, memory.db, self-modify backups.
# Excludes: models (re-downloadable), venv, __pycache__, prior checkpoints,
#           LoRA adapter checkpoints (re-trainable), corpus JSONL (regen-able
#           from source extraction).
#
# Destination, in priority order:
#   1. /Volumes/CharlesMemory/checkpoints/<tag>/   (external SSD per migration spec)
#   2. ~/charles/checkpoints/<tag>/                (internal fallback)
#
# ROTATION: tarballs older than RETENTION_DAYS are deleted, extracted dirs
# are deleted if a matching tarball exists. Prevents fractal duplication that
# bit us 2026-05-16 (485 GB consumed by overlapping nightlies).

set -e
TAG="${1:-checkpoint-$(date +%Y%m%dT%H%M%S)}"
SRC="/Users/home/charles"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

if [ -d /Volumes/CharlesMemory ]; then
    DEST_ROOT="/Volumes/CharlesMemory/checkpoints"
    LOC="external SSD"
else
    DEST_ROOT="$SRC/checkpoints"
    LOC="internal SSD (no external mounted)"
fi

DEST="$DEST_ROOT/$TAG"
mkdir -p "$DEST"
echo "[*] checkpointing to $DEST ($LOC)"

# rsync the live tree, excluding what's regenerable
# IMPORTANT: 'checkpoints' and 'training_corpus/_normalized/*_adapter' are
# the two largest sources of fractal duplication. Always exclude them.
rsync -a \
    --exclude='.venv' \
    --exclude='models' \
    --exclude='logs' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git/objects' \
    --exclude='workspace/voice_reference_short.wav' \
    --exclude='checkpoints' \
    --exclude='training_corpus/_normalized/*_adapter' \
    --exclude='training_corpus/_normalized/**/*_adapter' \
    --exclude='training_corpus/_normalized/**/*.jsonl' \
    --exclude='training_corpus/_normalized/**/_ab_staged' \
    --exclude='training_corpus/_normalized/**/*.log' \
    --exclude='training_corpus/manual_drops' \
    --exclude='*.safetensors' \
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
  workspace: $(du -sh "$SRC/workspace" 2>/dev/null | awk '{print \$1}')
  memory.db: $(ls -lh "$SRC/workspace/memory.db" 2>/dev/null | awk '{print \$5}' || echo "n/a")
  this checkpoint: $(du -sh "$DEST" 2>/dev/null | awk '{print \$1}')

NOTES:
  - models/ excluded (re-downloadable from HF / direct curl; fused models live in models/)
  - .venv excluded (re-installable via pip install -r requirements.txt)
  - logs/ excluded
  - .git/objects excluded (use git push for full git history backup)
  - voice_reference_short.wav excluded (deprecated, voice_reference.wav is canonical)
  - checkpoints/ excluded (prevents fractal duplication of prior nightlies)
  - training_corpus/_normalized/**/*_adapter/ excluded (LoRA checkpoints, re-trainable)
  - training_corpus/_normalized/**/*.jsonl excluded (corpus data, re-extractable)
  - *.safetensors excluded (model weight artifacts, regenerable)
EOF

# Tarball for archival
TAR="$DEST.tar.gz"
echo "[*] creating tarball $TAR"
tar -C "$(dirname "$DEST")" -czf "$TAR" "$(basename "$DEST")"

# Rotation pass: delete tarballs older than RETENTION_DAYS, and delete
# extracted dirs once a tarball exists for the same tag.
echo "[*] rotation pass (retention: $RETENTION_DAYS days)"
find "$DEST_ROOT" -maxdepth 1 -name 'nightly-*.tar.gz' -mtime +$RETENTION_DAYS -print -delete 2>/dev/null || true
find "$DEST_ROOT" -maxdepth 1 -name 'checkpoint-*.tar.gz' -mtime +$RETENTION_DAYS -print -delete 2>/dev/null || true
# For each extracted dir, if a tarball exists, drop the dir (tar is the canonical artifact)
for d in "$DEST_ROOT"/nightly-*/ "$DEST_ROOT"/checkpoint-*/; do
    [ -d "$d" ] || continue
    base=$(basename "${d%/}")
    if [ -f "$DEST_ROOT/${base}.tar.gz" ] && [ "$base" != "$TAG" ]; then
        echo "[-] removing extracted dir (tarball exists): $d"
        rm -rf "$d"
    fi
done

echo "[+] checkpoint complete"
echo "    dir:    $DEST"
echo "    tar:    $TAR ($(ls -lh "$TAR" | awk '{print $5}'))"
