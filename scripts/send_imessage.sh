#!/bin/bash
# Send an iMessage to John. Robust against special chars (em dashes, smart
# quotes, emojis, newlines) by passing the message as an osascript argv
# argument instead of via heredoc interpolation.
#
# Usage: send_imessage.sh "<message text>"

set -e
MSG="$1"
TARGET="${IMESSAGE_TARGET:-+16156637932}"

if [ -z "$MSG" ]; then
    echo "usage: $0 <message>" >&2
    exit 1
fi

# Pass $MSG as argv to osascript — AppleScript reads it as a clean string
# without bash variable expansion getting in the way.
osascript - "$MSG" "$TARGET" <<'APPLESCRIPT'
on run argv
    set messageText to item 1 of argv
    set targetHandle to item 2 of argv
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy targetHandle of targetService
        send messageText to targetBuddy
    end tell
end run
APPLESCRIPT
