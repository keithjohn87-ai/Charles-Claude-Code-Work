"""Goal tools: set_goal / list_goals / complete_goal / cancel_goal / append_goal_note."""
from __future__ import annotations

from core import goals as _goals
from core.tools import tool


@tool(
    name="set_goal",
    summary="Create a long-running open-ended goal that the heartbeat advances periodically. Use for multi-step objectives that span many turns (e.g. 'review the MOM and build the missing tools', 'rewrite SOUL.md based on what you learn this week'). The heartbeat fires a [goal advance] turn every advance_minutes (default 5) where you take one concrete step.",
    triggers=("set goal", "create goal", "new goal", "track goal"),
    schema={
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "What the goal is. Be specific enough that you (the future-tick version of you) can take a concrete next step from just reading this string + the notes column.",
            },
            "advance_minutes": {
                "type": "integer",
                "description": "How often the heartbeat advances this goal, in minutes. Default 5. Use 1-2 for fast iteration, 15-60 for slow long-burn work.",
                "default": 5,
            },
        },
        "required": ["description"],
    },
)
def set_goal(description: str, advance_minutes: int = 5) -> str:
    info = _goals.add_goal(description, advance_seconds=int(advance_minutes) * 60)
    return f"goal #{info['id']} set (every {advance_minutes}m): {description}"


@tool(
    name="list_goals",
    summary="List goals. Default returns active goals only.",
    triggers=("list goals", "what goals", "active goals", "my goals"),
    schema={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "active|paused|done|cancelled, or 'all'.", "default": "active"},
        },
    },
)
def list_goals(status: str = "active") -> str:
    rows = _goals.list_goals(None if status == "all" else status)
    if not rows:
        return f"(no goals with status={status!r})"
    out = []
    for g in rows:
        line = f"#{g['id']} [{g['status']}] every {g['advance_seconds'] // 60}m — {g['description']}"
        if g["notes"]:
            tail = g["notes"].splitlines()[-3:]
            line += "\n  recent notes:\n    " + "\n    ".join(tail)
        out.append(line)
    return "\n\n".join(out)


@tool(
    name="append_goal_note",
    summary="Append a progress note to a goal. Use during a [goal advance] tick to record what you did, what's next, what you learned. Future ticks see these notes.",
    triggers=("note on goal", "log goal progress", "update goal notes"),
    schema={
        "type": "object",
        "properties": {
            "goal_id": {"type": "integer"},
            "note": {"type": "string", "description": "One concrete sentence. What you did or what's next."},
        },
        "required": ["goal_id", "note"],
    },
)
def append_goal_note(goal_id: int, note: str) -> str:
    if not _goals.get_goal(goal_id):
        return f"[error] goal #{goal_id} not found"
    _goals.append_note(goal_id, note)
    return f"note appended to goal #{goal_id}"


@tool(
    name="complete_goal",
    summary="Mark a goal done with a one-line summary of the outcome. The summary becomes a permanent fact via remember.",
    triggers=("complete goal", "finish goal", "goal done", "goal complete"),
    schema={
        "type": "object",
        "properties": {
            "goal_id": {"type": "integer"},
            "summary": {"type": "string", "description": "One-sentence outcome — what you accomplished."},
        },
        "required": ["goal_id", "summary"],
    },
)
def complete_goal(goal_id: int, summary: str) -> str:
    if not _goals.complete(goal_id, summary):
        return f"[error] goal #{goal_id} not found or not active"
    # Also stamp it into long-term memory so it's discoverable via recall
    from core import memory as _mem
    _mem.add_fact(f"Completed goal #{goal_id}: {summary}", tags=f"goal,goal:{goal_id}")
    return f"goal #{goal_id} marked done"


@tool(
    name="cancel_goal",
    summary="Cancel an active goal. Use when the goal is no longer relevant or was misconfigured.",
    triggers=("cancel goal", "drop goal", "abandon goal"),
    schema={
        "type": "object",
        "properties": {"goal_id": {"type": "integer"}},
        "required": ["goal_id"],
    },
)
def cancel_goal(goal_id: int) -> str:
    if not _goals.cancel(goal_id):
        return f"[error] goal #{goal_id} not found or not active"
    return f"goal #{goal_id} cancelled"
