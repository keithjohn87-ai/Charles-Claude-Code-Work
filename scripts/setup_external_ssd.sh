#!/bin/bash
# Initialize the external SSD layout per the migration spec — but only if
# /Volumes/CharlesMemory is actually mounted. Otherwise skip cleanly.

if [ ! -d /Volumes/CharlesMemory ]; then
    echo "[!] /Volumes/CharlesMemory not mounted — skipping external SSD setup"
    echo "    Mount your SanDisk Extreme PRO 2TB and re-run."
    exit 0
fi

DEST=/Volumes/CharlesMemory
mkdir -p "$DEST/archive" "$DEST/training" "$DEST/checkpoints/master" "$DEST/deliverables"
ls -la "$DEST" | head -10
echo ""
echo "[+] external SSD layout ready at $DEST"
