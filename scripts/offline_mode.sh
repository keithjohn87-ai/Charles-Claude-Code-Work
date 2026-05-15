#!/bin/bash
# offline_mode.sh — graceful offline-mode toolkit for unattended Mac
# operation when internet will be unavailable for a known period
# (e.g., John traveling home over the weekend, hotel WiFi dies on
# checkout). Can be invoked locally or via Tailscale SSH if Tailscale
# is still up.
#
# Usage:
#   offline_mode.sh enable [duration_hours]
#       Mark Mac as intentionally offline. Logs the event. Sends one
#       last iMessage to John (if internet still up) confirming the
#       offline window. Tells the captive-portal-watch and boot-
#       health-check monitors to suppress alarm iMessages while
#       offline-mode is enabled (otherwise we'd queue dozens of
#       "internet down" alerts that all flush at once when WiFi
#       returns). Optional duration_hours arg auto-schedules a
#       disable; default is no auto-disable (manual disable on return).
#
#   offline_mode.sh disable
#       Resume normal monitoring. Sends "Mac back online" iMessage.
#
#   offline_mode.sh status
#       Print current state.
#
# Flag file at /Users/home/charles/workspace/offline_mode.flag is the
# single source of truth. The two monitor scripts check this file
# before sending alarm iMessages.

set -uo pipefail

FLAG_FILE="/Users/home/charles/workspace/offline_mode.flag"
LOG="/Users/home/charles/logs/offline_mode.log"
JOHN_NUMBER="+16156637932"

mkdir -p "$(dirname "$FLAG_FILE")"
mkdir -p "$(dirname "$LOG")"

ts() { TZ=America/New_York date '+%Y-%m-%d %H:%M EST'; }

send_imessage() {
    local body="$1"
    osascript <<APPLESCRIPT 2>>"$LOG"
tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy "${JOHN_NUMBER}" of targetService
    send "${body//$'\n'/\\n}" to targetBuddy
end tell
APPLESCRIPT
}

cmd="${1:-status}"

case "$cmd" in
enable)
    duration_hours="${2:-0}"
    enabled_at=$(ts)
    if [ "$duration_hours" -gt 0 ]; then
        # Compute auto-disable timestamp (POSIX seconds for at-job scheduling)
        auto_disable_unix=$(( $(date +%s) + duration_hours * 3600 ))
        auto_disable_human=$(TZ=America/New_York date -r $auto_disable_unix '+%Y-%m-%d %H:%M EST')
    else
        auto_disable_unix=0
        auto_disable_human="(manual disable on return — no auto)"
    fi

    cat > "$FLAG_FILE" <<EOF
ENABLED|$(date +%s)|${enabled_at}|${auto_disable_unix}|${auto_disable_human}
EOF
    echo "[$enabled_at] OFFLINE MODE ENABLED. Auto-disable: ${auto_disable_human}" >> "$LOG"

    body="🌙 Mac entering OFFLINE MODE at ${enabled_at}.

Boot-health-check + captive-portal-watch alarms suppressed during this window so you don't get hit with a flood of \"internet down\" alerts the moment WiFi returns.

Auto-disable: ${auto_disable_human}

To resume monitoring manually when you're back:
  ssh home@<mac-tailscale-ip>
  /Users/home/charles/scripts/offline_mode.sh disable

Or just let the auto-disable fire (if scheduled). The Mac will keep running locally — Charles agent + WarRoom + ContrPro webhook stay up via launchd KeepAlive — but external API calls will fail until WiFi returns. Stripe webhooks queue + retry on Stripe's side for 3 days, so any sales during the offline window will deliver when you're back online (assuming ≤3 day window).

Safe travels. — Claude Code (offline mode)"
    send_imessage "$body"
    echo "[$enabled_at] iMessage sent" >> "$LOG"

    # Schedule auto-disable if duration was specified
    if [ "$duration_hours" -gt 0 ]; then
        # Use 'at' to schedule the disable; falls back gracefully if 'at' isn't enabled
        disable_at_human=$(TZ=America/New_York date -r $auto_disable_unix '+%H:%M %m/%d/%Y')
        echo "/Users/home/charles/scripts/offline_mode.sh disable" | at -t "$(TZ=America/New_York date -r $auto_disable_unix '+%Y%m%d%H%M.%S')" 2>/dev/null && \
            echo "[$enabled_at] auto-disable scheduled via at(1) for ${auto_disable_human}" >> "$LOG" || \
            echo "[$enabled_at] WARNING: at(1) unavailable; auto-disable NOT scheduled. Manual disable required." >> "$LOG"
    fi
    ;;

disable)
    if [ ! -f "$FLAG_FILE" ]; then
        echo "OFFLINE MODE was not enabled. No action taken."
        exit 0
    fi

    enabled_at=$(awk -F'|' '{print $3}' "$FLAG_FILE" 2>/dev/null)
    rm -f "$FLAG_FILE"
    disabled_at=$(ts)
    echo "[$disabled_at] OFFLINE MODE DISABLED. Was enabled at: $enabled_at" >> "$LOG"

    body="☀️ Mac OFFLINE MODE disabled at ${disabled_at}.

Was enabled at: ${enabled_at}

Boot-health-check + captive-portal-watch alarms resumed. Charles + ContrPro back to normal monitoring.

Quick check: any Stripe webhook deliveries that queued during the offline window should now be processing on Stripe's retry schedule. Visit the Stripe dashboard webhook log to confirm successful redelivery.

— Claude Code (offline mode)"
    send_imessage "$body"
    echo "[$disabled_at] iMessage sent" >> "$LOG"
    ;;

status)
    if [ -f "$FLAG_FILE" ]; then
        IFS='|' read -r state enabled_unix enabled_human auto_unix auto_human < "$FLAG_FILE"
        echo "OFFLINE MODE: ${state}"
        echo "  Enabled at: ${enabled_human}"
        echo "  Auto-disable: ${auto_human}"
        if [ "$auto_unix" -gt 0 ]; then
            now_unix=$(date +%s)
            remaining_sec=$(( auto_unix - now_unix ))
            if [ "$remaining_sec" -gt 0 ]; then
                remaining_h=$(( remaining_sec / 3600 ))
                remaining_m=$(( (remaining_sec % 3600) / 60 ))
                echo "  Time remaining: ${remaining_h}h ${remaining_m}m"
            else
                echo "  Time remaining: OVERDUE — auto-disable should have fired"
            fi
        fi
    else
        echo "OFFLINE MODE: NOT ENABLED — normal monitoring active"
    fi
    ;;

*)
    cat <<USAGE
Usage:
  $(basename "$0") enable [duration_hours]   # enter offline mode (suppress monitor alerts)
  $(basename "$0") disable                   # exit offline mode (resume alerts)
  $(basename "$0") status                    # report current state

Examples:
  $(basename "$0") enable 72       # enable for 72 hours then auto-disable
  $(basename "$0") enable          # enable indefinitely (manual disable required)
  $(basename "$0") disable
  $(basename "$0") status
USAGE
    exit 1
    ;;
esac

exit 0
