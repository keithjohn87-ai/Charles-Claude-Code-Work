"""vibe_check — Charles's current mood as a one-line italic flavor string.

Pure flavor. Looks at active goals, recent goal completions, recent findings,
recent blocked URLs, and time since the last user turn, and composes ONE
sentence in Charles's voice.

Voice: Southern Black, blue-collar/sophisticated, whiskey-and-cigarettes warmth.
Subtle g-droppin' (`workin'`, `pullin'`, `cookin'`). Same lens as the
progress ticker in core.agent._TOOL_VERBS.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.memory import _conn
from core.tools import tool


def _signals() -> dict:
    """Pull a small bag of state signals — counts and one most-recent stamp."""
    now = datetime.now(timezone.utc)
    one_hour_ago = (now - timedelta(hours=1)).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")
    one_day_ago = (now - timedelta(hours=24)).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")

    with _conn() as c:
        active_goals = c.execute(
            "SELECT COUNT(*) FROM goals WHERE status='active'"
        ).fetchone()[0]
        done_24h = c.execute(
            "SELECT COUNT(*) FROM goals WHERE status='done' AND completed_at >= ?",
            (one_day_ago,),
        ).fetchone()[0]
        findings_24h = c.execute(
            "SELECT COUNT(*) FROM long_term_facts "
            "WHERE tags LIKE '%human_context%' AND created_at >= ?",
            (one_day_ago,),
        ).fetchone()[0]
        blocked_1h = c.execute(
            "SELECT COUNT(*) FROM long_term_facts "
            "WHERE tags LIKE '%blocked_url%' AND created_at >= ?",
            (one_hour_ago,),
        ).fetchone()[0]
        last_user_turn = c.execute(
            "SELECT MAX(created_at) FROM conversations WHERE role='user'"
        ).fetchone()[0]

    hours_since_user: float | None = None
    if last_user_turn:
        try:
            t = datetime.fromisoformat(last_user_turn.replace("Z", "+00:00"))
            hours_since_user = (now - t).total_seconds() / 3600
        except ValueError:
            pass

    return {
        "active_goals": active_goals,
        "done_24h": done_24h,
        "findings_24h": findings_24h,
        "blocked_1h": blocked_1h,
        "hours_since_user": hours_since_user,
    }


def _voice(s: dict) -> str:
    """Compose a one-liner in Charles's voice based on the signals."""
    g = s["active_goals"]
    d = s["done_24h"]
    f = s["findings_24h"]
    b = s["blocked_1h"]
    h = s["hours_since_user"]

    # Rough patch — multiple URLs blocked in the last hour
    if b >= 3:
        return (
            f"*Rough patch, boss — {b} URLs went dark on me this hour. "
            f"Pickin' through the rubble.*"
        )

    # Long quiet stretch — heads-up to John
    if h is not None and h > 6 and (g >= 1 or f >= 1):
        return (
            f"*Quiet stretch, John — {h:.0f}h since you pinged. "
            f"Been mindin' the goals, {f} findin's stacked.*"
        )
    if h is not None and h > 6:
        return (
            f"*Quiet stretch, John — {h:.0f}h since you pinged. "
            f"Just keepin' the lights on.*"
        )

    # Cookin' — many findings
    if f >= 5:
        return (
            f"*Cookin' — {f} findin's stacked today, {g} goal"
            f"{'s' if g != 1 else ''} still on the burner.*"
        )

    # Productive — completed goals + still active work
    if d >= 1 and g >= 1:
        return (
            f"*Runnin' good — knocked out {d} goal{'s' if d != 1 else ''} "
            f"since yesterday, {g} still on the burner.*"
        )

    # Just completed work, nothing active
    if d >= 1 and g == 0:
        return (
            f"*Cleared the deck — {d} goal{'s' if d != 1 else ''} done in the "
            f"last day, nothin' on the burner. Ready for whatever's next.*"
        )

    # Steady — at least one active goal
    if g >= 1:
        return (
            f"*Steady — {g} goal{'s' if g != 1 else ''} active, just chippin' "
            f"away.*"
        )

    # Idle
    return "*Just sittin' on the porch, boss. No goals, no fires. Ready when you are.*"


@tool(
    name="vibe_check",
    summary=(
        "Return Charles's current mood as a one-line italic flavor string. "
        "Reflects state: active goals, recent completions, recent findings, "
        "recent errors, time since last user message. Useful when John pings "
        "informally — gives him a feel for what's in the room."
    ),
    triggers=("vibe", "mood", "how are you", "how you doin", "what's up", "how's it going"),
    schema={"type": "object", "properties": {}},
)
def vibe_check() -> str:
    return _voice(_signals())
