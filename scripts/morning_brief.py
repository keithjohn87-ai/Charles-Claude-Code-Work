#!/usr/bin/env python3
"""Morning brief — fires at 06:00 EST via LaunchAgent, iMessages John a
plain-English summary of the last 24h of Charles activity.

Deliberately deterministic Python: no MLX, no agent.respond. The brief
must work even when Charles is down. Inputs are pulled directly from
memory.db. Output is one iMessage, target = John's number (per
DEFAULT_TARGET in tools/imessage.py).

Layout (max ~300 words to keep iMessage readable):

  Morning brief — YYYY-MM-DD

  Overnight:
    - Goals advanced: <n>; completed: <n>; cancelled: <n>
    - Facts saved: <n>  (top 3 by recency)
    - Watchdog interventions: <n>  (top 1 by severity)

  Top learnings:
    1. <fact preview>
    2. <fact preview>
    3. <fact preview>

  Blockers:
    - <one line per real blocker; "none" if zero>

  In-flight:
    - <active goals, 1 line each, with last advance age>

  — Charles (auto-brief, no reply expected)

Fail-safe: if anything explodes, the script still tries to send a
1-line "morning brief generation failed: <error>" so John knows the
brief itself is broken, not that there was zero activity.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Logging — pure file, no console (LaunchAgent stdout/stderr captured separately)
LOG = Path("/Users/home/charles/logs/morning_brief.log")
LOG.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("morning_brief")

DB_PATH = Path("/Users/home/charles/workspace/memory.db")
JOHN = "+16156637932"


# ---------------------------------------------------------------------------
# Data pulls
# ---------------------------------------------------------------------------


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _ago_iso(seconds: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def pull_overnight_counts(since_iso: str) -> dict:
    """Return aggregate counts for the brief header."""
    out = {
        "goals_advanced": 0,
        "goals_completed": 0,
        "goals_cancelled": 0,
        "facts_saved": 0,
        "watchdog_interventions": 0,
        "tool_errors": 0,
    }
    with _conn() as c:
        # Goals: any with last_advanced_at >= since OR completed_at >= since OR cancelled_at
        r = c.execute(
            "SELECT COUNT(*) FROM goals WHERE last_advanced_at >= ?",
            (since_iso,),
        ).fetchone()
        out["goals_advanced"] = int(r[0])
        r = c.execute(
            "SELECT COUNT(*) FROM goals WHERE status='done' AND completed_at >= ?",
            (since_iso,),
        ).fetchone()
        out["goals_completed"] = int(r[0])
        r = c.execute(
            "SELECT COUNT(*) FROM goals WHERE status='cancelled' AND completed_at >= ?",
            (since_iso,),
        ).fetchone()
        out["goals_cancelled"] = int(r[0])
        # Facts: exclude superseded so we count active knowledge only
        r = c.execute(
            "SELECT COUNT(*) FROM long_term_facts "
            "WHERE created_at >= ? "
            "  AND COALESCE(tags, '') NOT LIKE '%superseded%'",
            (since_iso,),
        ).fetchone()
        out["facts_saved"] = int(r[0])
        # Watchdog interventions
        r = c.execute(
            "SELECT COUNT(*) FROM long_term_facts "
            "WHERE created_at >= ? AND tags LIKE '%intervention,auto%'",
            (since_iso,),
        ).fetchone()
        out["watchdog_interventions"] = int(r[0])
        # Tool errors: assistant turns with role='tool' content starting [error]
        r = c.execute(
            "SELECT COUNT(*) FROM conversations "
            "WHERE role='tool' AND content LIKE '[error]%' "
            "  AND created_at >= ?",
            (since_iso,),
        ).fetchone()
        out["tool_errors"] = int(r[0])
    return out


def pull_top_learnings(since_iso: str, n: int = 3) -> list[str]:
    """Return the top N facts saved in the window, by recency, that aren't
    bookkeeping noise. 120-char preview each.

    Filters: drop facts that are watchdog audit, consolidation summaries,
    prune logs, intervention records, "FINDING (auto-extracted)" auto-recall
    artifacts (those are summaries OF facts, not new learnings), and any
    fact tagged superseded. What's left should be the real new knowledge.
    """
    with _conn() as c:
        rows = c.execute(
            "SELECT fact, tags FROM long_term_facts "
            "WHERE created_at >= ? "
            "  AND COALESCE(tags, '') NOT LIKE '%consolidation%' "
            "  AND COALESCE(tags, '') NOT LIKE '%prune%' "
            "  AND COALESCE(tags, '') NOT LIKE '%intervention%' "
            "  AND COALESCE(tags, '') NOT LIKE '%superseded%' "
            "  AND COALESCE(tags, '') NOT LIKE '%audit%' "
            "  AND fact NOT LIKE 'FINDING (auto-extracted%' "
            "  AND fact NOT LIKE 'WATCHDOG SWEEP%' "
            "  AND fact NOT LIKE 'MEMORY CONSOLIDATION%' "
            "  AND length(fact) > 20 "
            "ORDER BY id DESC LIMIT ?",
            (since_iso, n * 3),  # over-fetch in case of more noise we should skip
        ).fetchall()
    out: list[str] = []
    for r in rows:
        line = r["fact"].strip().split("\n")[0]
        if not line:
            continue
        out.append(line[:120])
        if len(out) >= n:
            break
    return out


def pull_blockers(since_iso: str) -> list[str]:
    """Real signals John needs to know: watchdog interventions, big error
    storms, hard system_health flags. One line each, max 3."""
    blockers: list[str] = []
    with _conn() as c:
        # Watchdog interventions in window
        rows = c.execute(
            "SELECT fact FROM long_term_facts "
            "WHERE created_at >= ? AND tags LIKE '%intervention,auto%' "
            "ORDER BY id DESC LIMIT 5",
            (since_iso,),
        ).fetchall()
        for r in rows:
            line = r["fact"].split("\n")[0].strip()
            # Drop the "Behavioral watchdog: " prefix for readability
            line = line.replace("Behavioral watchdog: ", "")
            blockers.append(line[:140])
        # System health flags (e.g. "MLX down", disk low)
        rows = c.execute(
            "SELECT fact FROM long_term_facts "
            "WHERE created_at >= ? AND tags LIKE '%system_health%' "
            "ORDER BY id DESC LIMIT 3",
            (since_iso,),
        ).fetchall()
        for r in rows:
            blockers.append(r["fact"].split("\n")[0][:140])
    # Dedup-ish: drop near-identical prefixes
    seen = set()
    out: list[str] = []
    for b in blockers:
        key = b[:60].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(b)
        if len(out) >= 3:
            break
    return out


def pull_in_flight() -> list[str]:
    """One line per active goal — description (truncated) + age of last advance."""
    out: list[str] = []
    now = datetime.now(timezone.utc)
    with _conn() as c:
        rows = c.execute(
            "SELECT id, description, last_advanced_at "
            "FROM goals WHERE status='active' "
            "ORDER BY id DESC LIMIT 6"
        ).fetchall()
    for r in rows:
        desc = (r["description"] or "(no description)").split("\n")[0][:60]
        last = r["last_advanced_at"]
        if last:
            try:
                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                age_min = int((now - last_dt).total_seconds() // 60)
                if age_min < 60:
                    age = f"{age_min}m ago"
                elif age_min < 1440:
                    age = f"{age_min // 60}h ago"
                else:
                    age = f"{age_min // 1440}d ago"
            except ValueError:
                age = "?"
        else:
            age = "never"
        out.append(f"#{r['id']}: {desc} (last advance {age})")
    return out


# ---------------------------------------------------------------------------
# Compose
# ---------------------------------------------------------------------------


def fetch_weather(location: str = "Dundalk,MD") -> str:
    """Fetch today's detailed forecast from wttr.in JSON. No API key, no
    Charles dependency, no MLX.  Returns a multi-line weather block or ''
    on any error so the brief still composes.

    Output format:
      Weather (Dundalk,MD): High 97° / Low 64°  UV 9
      Morning  6-9am:  66-76°  hum 69-88%  rain 0%
      Lunch   9am-1pm:  76-91°  hum 46-69%  rain 0%
      Afternoon 1-5pm:  91-96°  hum 38-46%  rain 0%
    """
    import urllib.parse, urllib.request, json
    url = f"https://wttr.in/{urllib.parse.quote(location)}?format=j1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:  # noqa: BLE001
        log.warning("weather fetch failed: %s", e)
        return ""

    days = data.get("weather", [])
    if not days:
        return ""

    today = days[0]
    high_f = today.get("maxtempF", "?")
    low_f  = today.get("mintempF", "?")
    uv     = today.get("uvIndex", "?")
    hourly = today.get("hourly", [])

    # Bucket hours into Morning (6-9), Lunch (9-13), Afternoon (13-17)
    buckets = {"Morning  6-9am": [], "Lunch   9-1pm": [], "Afternoon 1-5pm": []}
    for h in hourly:
        t = int(h["time"])  # 0, 300, 600, 900, 1200, 1500, 1800, 2100
        hour = t // 60
        if 6 <= hour < 9:
            bucket = "Morning  6-9am"
        elif 9 <= hour < 13:
            bucket = "Lunch   9-1pm"
        elif 13 <= hour < 17:
            bucket = "Afternoon 1-5pm"
        else:
            continue  # skip overnight hours
        buckets[bucket].append(h)

    lines = [f"Weather ({location}): High {high_f}° / Low {low_f}°  UV {uv}"]
    for label, entries in buckets.items():
        if not entries:
            continue
        temps = [int(e["tempF"]) for e in entries]
        hums  = [e["humidity"] for e in entries]
        rains = [int(e["chanceofrain"]) for e in entries]
        mn_t, mx_t = min(temps), max(temps)
        mn_h, mx_h = min(hums), max(hums)
        mn_r, mx_r = min(rains), max(rains)
        lines.append(
            f"  {label}:  {mn_t}-{mx_t}°  hum {mn_h}-{mx_h}%  rain {mn_r}-{mx_r}%"
        )

    return "\n".join(lines)


def compose_brief() -> str:
    now = datetime.now(timezone.utc).astimezone()
    date_label = now.strftime("%Y-%m-%d")
    # 24h window from this morning back
    since = _ago_iso(24 * 3600)

    counts = pull_overnight_counts(since)
    learnings = pull_top_learnings(since, n=3)
    blockers = pull_blockers(since)
    in_flight = pull_in_flight()
    weather = fetch_weather()

    lines = [f"Morning brief — {date_label}"]
    if weather:
        # Weather is multi-line; indent each line so it nests under the brief
        for wline in weather.splitlines():
            lines.append(f"  {wline}")
    lines.append("")
    lines.append("Overnight:")
    lines.append(
        f"  Goals: {counts['goals_advanced']} advanced, "
        f"{counts['goals_completed']} done, "
        f"{counts['goals_cancelled']} cancelled."
    )
    lines.append(
        f"  Facts saved: {counts['facts_saved']}.  "
        f"Watchdog interventions: {counts['watchdog_interventions']}.  "
        f"Tool errors: {counts['tool_errors']}."
    )

    if learnings:
        lines.append("")
        lines.append("Top learnings:")
        for i, fact in enumerate(learnings, 1):
            lines.append(f"  {i}. {fact}")
    else:
        lines.append("")
        lines.append("Top learnings: nothing notable last 24h.")

    lines.append("")
    if blockers:
        lines.append("Blockers:")
        for b in blockers:
            lines.append(f"  - {b}")
    else:
        lines.append("Blockers: none.")

    if in_flight:
        lines.append("")
        lines.append("In-flight:")
        for line in in_flight:
            lines.append(f"  - {line}")
    else:
        lines.append("")
        lines.append("In-flight: no active goals.")

    lines.append("")
    lines.append("— Charles (auto-brief, no reply expected)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------


def send_imessage(text: str, target: str = JOHN) -> bool:
    """Send via AppleScript trampoline — same mechanism as tools/imessage.py
    but standalone (no Charles dependencies)."""
    safe = text.replace("\\", "\\\\").replace('"', '\\"')
    target_esc = target.replace("\\", "\\\\").replace('"', '\\"')
    script = (
        'tell application "Messages"\n'
        '  set targetService to 1st service whose service type = iMessage\n'
        f'  set targetBuddy to buddy "{target_esc}" of targetService\n'
        f'  send "{safe}" to targetBuddy\n'
        "end tell"
    )
    r = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        log.error("osascript send failed: %s", r.stderr.strip())
        return False
    return True


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def main() -> int:
    try:
        brief = compose_brief()
        log.info("composed brief (%d chars):\n%s", len(brief), brief)
        ok = send_imessage(brief)
        if ok:
            log.info("brief sent to %s", JOHN)
            print(brief)
            return 0
        log.error("send failed")
        return 2
    except Exception as e:  # noqa: BLE001
        log.exception("morning_brief blew up: %s", e)
        # Try a fail-safe one-liner so John knows the brief is broken
        try:
            send_imessage(
                f"morning brief generation failed: {type(e).__name__}: {e}. "
                f"Check {LOG}."
            )
        except Exception:  # noqa: BLE001
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
