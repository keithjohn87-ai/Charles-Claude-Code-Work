#!/bin/bash
# Install (or refresh) the Charles + watchdog LaunchAgents.
#
# Usage:
#   bash scripts/install_launchd.sh enable    # symlink plists + launchctl load
#   bash scripts/install_launchd.sh disable   # launchctl unload + remove symlinks
#   bash scripts/install_launchd.sh status    # show current state
#
# This is reversible. The plists live in /Users/home/charles/launchd/ and are
# symlinked into ~/Library/LaunchAgents/ when enabled.

set -e
ACTION="${1:-status}"
SRC_DIR="/Users/home/charles/launchd"
DST_DIR="$HOME/Library/LaunchAgents"
PLISTS=("com.charles.agent.plist" "com.charles.watchdog.plist" "com.charles.nightly-backup.plist" "com.charles.caffeinate.plist")

mkdir -p "$DST_DIR"

case "$ACTION" in
    enable)
        # First, kill any non-launchd Charles to avoid getUpdates 409 conflicts
        if pgrep -f "python.*charles.py" >/dev/null 2>&1; then
            echo "[*] killing existing foreground charles.py (avoid Telegram conflict)"
            pgrep -f "python.*charles.py" | xargs kill 2>/dev/null || true
            sleep 2
        fi
        for p in "${PLISTS[@]}"; do
            ln -sf "$SRC_DIR/$p" "$DST_DIR/$p"
            launchctl unload "$DST_DIR/$p" 2>/dev/null || true
            launchctl load -w "$DST_DIR/$p"
            echo "[+] loaded $p"
        done
        ;;
    disable)
        for p in "${PLISTS[@]}"; do
            if [ -L "$DST_DIR/$p" ] || [ -f "$DST_DIR/$p" ]; then
                launchctl unload -w "$DST_DIR/$p" 2>/dev/null || true
                rm "$DST_DIR/$p"
                echo "[-] unloaded + removed $p"
            fi
        done
        ;;
    status)
        echo "=== launchctl state ==="
        for p in "${PLISTS[@]}"; do
            label="${p%.plist}"
            if launchctl list | grep -q "$label"; then
                echo "[ON]  $label"
                launchctl list | grep "$label"
            else
                echo "[OFF] $label"
            fi
        done
        echo ""
        echo "=== plists in ~/Library/LaunchAgents/ ==="
        ls -la "$DST_DIR" | grep -E "charles" || echo "(none installed)"
        ;;
    *)
        echo "usage: $0 {enable|disable|status}"
        exit 1
        ;;
esac
