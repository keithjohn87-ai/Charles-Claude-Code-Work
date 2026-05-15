#!/bin/bash
# captive_portal_watch.sh — runs every 5 min via LaunchAgent. Detects
# when the Mac's WiFi gets intercepted by a hotel/captive-portal redirect
# and iMessages John so he can re-authenticate the portal from his phone
# (via Tailscale SSH or Screen Sharing). Critical for unattended hotel
# operation where Marriott et al force daily re-login.
#
# Detection strategy: probe http://www.gstatic.com/generate_204 — clean
# internet returns HTTP 204 (no body). Captive portals return HTTP 200
# with HTML, or HTTP 302 with redirect to the portal login. Any non-204
# is treated as captive intercept.
#
# Alert dedup: writes a state file with the last-alert timestamp. Will
# not alert again for 1 hour (avoids spamming John during a brief
# outage). On recovery from captive-state to clean-state, sends an
# "internet back" all-clear so he knows when it's fixed.

set -uo pipefail

LOG="/Users/home/charles/logs/captive_portal_watch.log"
STATE_FILE="/Users/home/charles/workspace/captive_portal_state.txt"
JOHN_NUMBER="+16156637932"
ALERT_COOLDOWN_SECONDS=3600  # 1 hour between alerts

mkdir -p "$(dirname "$LOG")"
mkdir -p "$(dirname "$STATE_FILE")"

NOW=$(date +%s)
TIMESTAMP=$(TZ=America/New_York date '+%Y-%m-%d %H:%M EST')

# Read prior state (CLEAN | CAPTIVE | UNKNOWN, last-alert timestamp)
prior_state="UNKNOWN"
last_alert=0
if [ -f "$STATE_FILE" ]; then
    prior_state=$(awk -F'|' 'NR==1{print $1}' "$STATE_FILE" 2>/dev/null || echo "UNKNOWN")
    last_alert=$(awk -F'|' 'NR==1{print $2}' "$STATE_FILE" 2>/dev/null || echo "0")
fi

# Probe
http_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 \
    -H "Cache-Control: no-cache" \
    "http://www.gstatic.com/generate_204" 2>/dev/null)

if [ "$http_code" = "204" ]; then
    new_state="CLEAN"
elif [ -z "$http_code" ] || [ "$http_code" = "000" ]; then
    new_state="OFFLINE"  # no network at all (cable unplugged, WiFi dropped)
else
    new_state="CAPTIVE"  # 200, 302, or other — captive portal intercepting
fi

# Decide whether to alert
should_alert=0
alert_body=""

if [ "$new_state" = "CAPTIVE" ] && [ "$prior_state" != "CAPTIVE" ]; then
    # Newly captive — always alert (and reset cooldown)
    should_alert=1
    alert_body="🚨 Mac WiFi behind captive portal at ${TIMESTAMP}.

HTTP probe returned ${http_code} (expected 204). The Mac is connected to WiFi but a captive portal is intercepting requests — which means:
  • Tailscale Funnel may be unreachable from public internet
  • Stripe webhooks may fail to reach ContrPro
  • Any outbound API calls from Charles will hang or fail

Fix: re-authenticate the WiFi captive portal. If you can Tailscale-SSH or Screen Share to the Mac, open Safari and visit any HTTP site to trigger the portal page; complete the captive form (accept ToS, etc.). If you can't reach the Mac remotely, the hotel office staff would need to do this physically.

— Claude Code (captive portal watch)"
elif [ "$new_state" = "OFFLINE" ] && [ "$prior_state" != "OFFLINE" ]; then
    # Newly offline
    should_alert=1
    alert_body="🚨 Mac internet OFFLINE at ${TIMESTAMP}.

HTTP probe to gstatic.com returned no response. WiFi may have dropped, the cable may be unplugged, or the network is down. Cannot tell from here whether it's a brief outage or a real disconnect.

Mac is still up locally (you're getting this iMessage via the Messages app, which queues until network returns). The hotel WiFi may have re-issued a captive portal that's blocking everything.

— Claude Code (captive portal watch)"
elif [ "$new_state" = "CLEAN" ] && [ "$prior_state" = "CAPTIVE" ]; then
    # Recovered from captive — send all-clear
    should_alert=1
    alert_body="✅ Mac WiFi recovered at ${TIMESTAMP}.

HTTP probe returned 204 — internet clean, no captive portal interception. Tailscale Funnel + Stripe webhook delivery should work normally now.

— Claude Code (captive portal watch)"
elif [ "$new_state" = "CLEAN" ] && [ "$prior_state" = "OFFLINE" ]; then
    # Recovered from offline
    should_alert=1
    alert_body="✅ Mac internet back online at ${TIMESTAMP}.

— Claude Code (captive portal watch)"
fi

# Apply cooldown to repeat-state alerts only (CAPTIVE → CAPTIVE without recovery in between)
if [ "$should_alert" = "0" ] && [ "$new_state" = "CAPTIVE" ] && [ "$prior_state" = "CAPTIVE" ]; then
    if [ $((NOW - last_alert)) -ge $ALERT_COOLDOWN_SECONDS ]; then
        should_alert=1
        elapsed=$(( (NOW - last_alert) / 60 ))
        alert_body="🚨 Mac STILL behind captive portal (last alert ${elapsed}m ago) at ${TIMESTAMP}.

WiFi captive portal still intercepting. HTTP probe: ${http_code}. Re-flagging hourly until cleared.

— Claude Code (captive portal watch)"
    fi
fi

# Send iMessage if needed
if [ "$should_alert" = "1" ]; then
    osascript <<APPLESCRIPT 2>>"$LOG"
tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy "${JOHN_NUMBER}" of targetService
    send "${alert_body//$'\n'/\\n}" to targetBuddy
end tell
APPLESCRIPT
    last_alert=$NOW
    echo "[$TIMESTAMP] ALERT SENT — state=${prior_state}→${new_state} http=${http_code}" >> "$LOG"
else
    # Quiet log — just record the probe
    echo "[$TIMESTAMP] state=${new_state} http=${http_code} (no alert)" >> "$LOG"
fi

# Persist state for next run
echo "${new_state}|${last_alert}" > "$STATE_FILE"
exit 0
