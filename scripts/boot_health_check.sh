#!/bin/bash
# boot_health_check.sh — runs once shortly after boot/login, verifies that
# every critical Charles + ContrPro service came up cleanly, and iMessages
# John with the result. Designed for unattended operation when John is
# offsite (e.g., Mac left at hotel office while traveling home).
#
# Wiring: registered as a LaunchAgent (com.charles.boot-health-check.plist)
# with RunAtLoad=true. Fires once per boot. Waits ~90s for services to settle
# before checking, so KeepAlive-driven service starts have a chance to
# actually start their workers.

set -uo pipefail

LOG="/Users/home/charles/logs/boot_health_check.log"
JOHN_NUMBER="+16156637932"
WAIT_SECONDS=90
WEBHOOK_URL="http://localhost:8090/health"
WARROOM_URL="http://localhost:8765/api/state/now"
MLX_URL="http://127.0.0.1:8080/v1/models"
PUBLIC_FUNNEL="https://homes-mac-studio.tailc819f6.ts.net/health"

mkdir -p "$(dirname "$LOG")"
echo "================ boot_health_check $(date '+%Y-%m-%d %H:%M:%S %Z') ================" >> "$LOG"

# Wait for services to settle after boot/login
sleep "$WAIT_SECONDS"

# Helper: HTTP probe with timeout
probe() {
    local url="$1"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "$url" 2>/dev/null)
    [ "$code" = "200" ] && return 0
    [ "$code" = "401" ] && return 0  # warroom returns 401 without auth — still alive
    return 1
}

# Helper: launchctl-loaded check
service_running() {
    launchctl list 2>/dev/null | awk '{print $3}' | grep -qx "$1"
}

# Run all checks
declare -a problems=()
declare -a verified=()

# 1. LaunchAgents loaded
for svc in com.mlx.server com.charles.agent com.charles.warroom com.charles.contrpro com.charles.behavior_watchdog com.charles.watchdog com.charles.caffeinate; do
    if service_running "$svc"; then
        verified+=("loaded:$svc")
    else
        problems+=("DOWN: launchagent $svc not loaded")
    fi
done

# 2. MLX server reachable
if probe "$MLX_URL"; then
    verified+=("mlx:reachable")
else
    problems+=("DOWN: MLX server (port 8080) not responding")
fi

# 3. Charles WarRoom reachable
if probe "$WARROOM_URL"; then
    verified+=("warroom:reachable")
else
    problems+=("DOWN: WarRoom (port 8765) not responding")
fi

# 4. ContrPro webhook reachable (local)
if probe "$WEBHOOK_URL"; then
    verified+=("contrpro:reachable-local")
else
    problems+=("DOWN: ContrPro webhook (port 8090) not responding locally")
fi

# 5. Tailscale up
if /Applications/Tailscale.app/Contents/MacOS/Tailscale status >/dev/null 2>&1; then
    verified+=("tailscale:up")
else
    problems+=("DOWN: Tailscale not running")
fi

# 6. ContrPro webhook reachable from public internet (via Tailscale Funnel)
# This catches captive-portal blocks too
if probe "$PUBLIC_FUNNEL"; then
    verified+=("funnel:reachable-public")
else
    problems+=("DOWN: ContrPro webhook NOT reachable via public Funnel — Stripe webhooks will fail")
fi

# 7. Internet alive (HTTP 204 endpoint — fast captive-portal detector)
INTERNET_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 http://www.gstatic.com/generate_204 2>/dev/null)
if [ "$INTERNET_CODE" = "204" ]; then
    verified+=("internet:clean")
elif [ "$INTERNET_CODE" = "200" ] || [ "$INTERNET_CODE" = "302" ]; then
    problems+=("WARN: Internet behind captive portal (HTTP $INTERNET_CODE — needs WiFi re-login)")
else
    problems+=("WARN: Internet check returned HTTP $INTERNET_CODE")
fi

# Build status text
TIMESTAMP=$(TZ=America/New_York date '+%Y-%m-%d %H:%M EST')
UPTIME=$(uptime | awk -F'up ' '{print $2}' | awk -F',' '{print $1}')

if [ ${#problems[@]} -eq 0 ]; then
    STATUS="✅ Mac back up clean"
    BODY="${STATUS} at ${TIMESTAMP}.

Uptime: ${UPTIME}
All ${#verified[@]} checks passed:
  • MLX server reachable
  • Charles agent + WarRoom + ContrPro webhook running
  • Tailscale + Funnel reachable from public internet
  • Behavior watchdog + caffeinate up
  • Internet clean (no captive portal)

You're good. — Claude Code (boot health check)"
else
    STATUS="⚠️ Mac up but ${#problems[@]} issue(s)"
    BODY="${STATUS} at ${TIMESTAMP}.

Uptime: ${UPTIME}

Issues:"
    for p in "${problems[@]}"; do
        BODY+="
  • ${p}"
    done
    BODY+="

Verified clean:"
    for v in "${verified[@]}"; do
        BODY+="
  • ${v}"
    done
    BODY+="

— Claude Code (boot health check)"
fi

# Log to disk
{
    echo "STATUS: $STATUS"
    echo "Verified: ${verified[*]}"
    echo "Problems: ${problems[*]}"
    echo "Body:"
    echo "$BODY"
    echo "---"
} >> "$LOG"

# Send iMessage to John (use AppleScript via the existing send-imessage script)
osascript <<APPLESCRIPT
tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy "${JOHN_NUMBER}" of targetService
    send "${BODY//$'\n'/\\n}" to targetBuddy
end tell
APPLESCRIPT

EXIT_CODE=$?
echo "iMessage send exit code: $EXIT_CODE" >> "$LOG"
exit 0
