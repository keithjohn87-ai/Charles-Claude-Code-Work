#!/bin/bash
# Install the morning-brief LaunchAgent. Idempotent.
#
# What it does:
#   1. Copies launchd/com.charles.morning-brief.plist to ~/Library/LaunchAgents/
#   2. Bootstraps the agent so it's known to launchd
#   3. Verifies it shows up in `launchctl list`
#
# To run the brief once manually (sanity check):
#   /Users/home/charles/.venv/bin/python /Users/home/charles/scripts/morning_brief.py
#
# To remove the LaunchAgent:
#   launchctl bootout gui/$(id -u)/com.charles.morning-brief
#   rm ~/Library/LaunchAgents/com.charles.morning-brief.plist

set -euo pipefail

SRC="/Users/home/charles/launchd/com.charles.morning-brief.plist"
DST="$HOME/Library/LaunchAgents/com.charles.morning-brief.plist"
LABEL="com.charles.morning-brief"

if [ ! -f "$SRC" ]; then
    echo "error: $SRC not found — pull main first?"
    exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
cp "$SRC" "$DST"
chmod 644 "$DST"

# If it's already loaded, boot it out so we pick up the new plist.
if launchctl list | grep -q "$LABEL"; then
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
fi

launchctl bootstrap "gui/$(id -u)" "$DST"

echo "installed: $LABEL"
launchctl list | grep "$LABEL" || echo "warning: $LABEL not visible in launchctl list"
echo ""
echo "Next fire: tomorrow 06:00 local time."
echo "Test now: /Users/home/charles/.venv/bin/python /Users/home/charles/scripts/morning_brief.py"
