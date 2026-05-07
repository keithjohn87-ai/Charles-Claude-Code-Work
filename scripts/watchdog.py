#!/usr/bin/env python3
"""Charles watchdog.

Runs as a separate LaunchAgent (com.charles.watchdog). Every 30 seconds:
1. Checks if charles.py is alive (via pgrep).
2. Checks if Charles is making progress (heartbeat log appended within last 5 min).
3. If dead OR stale: launchctl kickstart the Charles agent (which forces a
   clean restart through the LaunchAgent system; KeepAlive will respawn it).
4. After N consecutive failed restarts, send John a Telegram alert.

State: /tmp/charles_watchdog_state.json — restart count + last alert.

Logs to /Users/home/charles/logs/watchdog.log.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

LOG_PATH = Path("/Users/home/charles/logs/watchdog.log")
STATE_PATH = Path("/tmp/charles_watchdog_state.json")
# Charles's logging.basicConfig writes to stderr, so the err.log is what gets
# touched on every heartbeat tick / Telegram poll. The .out.log stays empty.
HEARTBEAT_LOG = Path("/Users/home/charles/logs/charles.launchd.err.log")
CHARLES_LABEL = "com.charles.agent"

CHECK_SECONDS = 30
STALE_AFTER_SECONDS = 300       # 5 min without heartbeat log = stale
MAX_FAILED_RESTARTS = 5         # after N consecutive failures, page John
ALERT_COOLDOWN_SECONDS = 1800   # don't spam alerts more than once per 30 min

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("watchdog")


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state))


def charles_pid() -> int | None:
    try:
        out = subprocess.check_output(["pgrep", "-f", "python.*charles.py"], text=True).strip()
        if out:
            # If multiple, return first
            return int(out.split("\n")[0])
    except subprocess.CalledProcessError:
        return None
    return None


def heartbeat_fresh() -> bool:
    if not HEARTBEAT_LOG.exists():
        return False
    age = time.time() - HEARTBEAT_LOG.stat().st_mtime
    return age < STALE_AFTER_SECONDS


def kickstart_charles() -> bool:
    """Use launchctl kickstart to force a clean restart via the LaunchAgent."""
    try:
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{uid}/{CHARLES_LABEL}"],
            check=True, capture_output=True,
        )
        log.info("kickstarted %s", CHARLES_LABEL)
        return True
    except subprocess.CalledProcessError as e:
        log.error("kickstart failed: %s", e.stderr.decode() if e.stderr else e)
        return False


def alert_john(message: str) -> None:
    """Send a Telegram alert via the bot. Used for runaway-failure escalation."""
    try:
        # Lazy load to avoid circulars and only require config when alerting
        sys.path.insert(0, "/Users/home/charles")
        from dotenv import load_dotenv
        load_dotenv("/Users/home/charles/.env")
        import httpx
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        owner = int(os.environ.get("OWNER_TELEGRAM_ID", "0"))
        if not token or not owner:
            log.error("missing TELEGRAM_BOT_TOKEN or OWNER_TELEGRAM_ID for alert")
            return
        httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": owner, "text": f"🚨 CHARLES WATCHDOG: {message}"},
            timeout=10,
        )
        log.info("alerted John: %s", message[:80])
    except Exception as e:  # noqa: BLE001
        log.error("alert failed: %s", e)


def tick() -> None:
    state = _load_state()
    pid = charles_pid()
    fresh = heartbeat_fresh()

    if pid and fresh:
        if state.get("failed_restarts", 0):
            log.info("recovered: pid=%d, heartbeat fresh", pid)
        state["failed_restarts"] = 0
        _save_state(state)
        return

    if not pid:
        log.warning("charles is dead (no pid) — kickstarting")
    elif not fresh:
        log.warning("charles pid=%d but heartbeat is stale — kickstarting", pid)

    if kickstart_charles():
        state["failed_restarts"] = 0
        state["last_kickstart"] = time.time()
    else:
        state["failed_restarts"] = state.get("failed_restarts", 0) + 1
        log.error("failed_restarts=%d", state["failed_restarts"])
        if state["failed_restarts"] >= MAX_FAILED_RESTARTS:
            now = time.time()
            last_alert = state.get("last_alert", 0)
            if now - last_alert > ALERT_COOLDOWN_SECONDS:
                alert_john(
                    f"Charles dead, {state['failed_restarts']} restart attempts failed. "
                    f"Manual intervention needed."
                )
                state["last_alert"] = now
    _save_state(state)


def main() -> None:
    log.info("watchdog starting (check every %ds)", CHECK_SECONDS)
    while True:
        try:
            tick()
        except Exception:  # noqa: BLE001
            log.exception("tick failed")
        time.sleep(CHECK_SECONDS)


if __name__ == "__main__":
    main()
