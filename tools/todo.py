"""Lightweight session-scoped todo list — Claude Code's TodoWrite, ported.

Purpose: a per-conversation in-flight task list separate from the heavyweight
set_goal / add_task infrastructure. Charles uses it to plan multi-step work
WITHIN a respond chain — write the plan once, mark items complete as he
goes, see at a glance what's left.

Distinct from existing Charles state:
  - set_goal / list_goals: long-running goals advanced by the heartbeat. Use
    when work spans many turns / sessions / hours.
  - add_task / list_open_tasks: persistent task records (often things John
    asked Charles to do later). Use when work is async, deferred, or needs
    to survive session end.
  - todo_set / todo_get (this module): in-session planning + tracking. Use
    when you have a multi-step task RIGHT NOW and need to track progress
    across the next few rounds in the same chain. Cleared when a new
    conversation_id is opened.

Storage: JSON file at workspace/todo_<conv_id>.json. Lifetime is one
conversation (clears when conv_id changes). Single source of truth — no
DB writes, no embeddings, no heartbeat. Cheap and fast.

Schema:
    [
        {"content": "Read core/agent.py to find the round loop",
         "activeForm": "Reading core/agent.py to find the round loop",
         "status": "completed"},
        {"content": "Add the new guard at line 350",
         "activeForm": "Adding the new guard at line 350",
         "status": "in_progress"},
        ...
    ]

status values: "pending", "in_progress", "completed"
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config import WORKSPACE
from core.tools import tool

log = logging.getLogger("charles.tools.todo")

_VALID_STATUSES = {"pending", "in_progress", "completed"}


def _todo_path(conv_id: str | None) -> Path:
    """File path for the todo list scoped to a conversation."""
    safe_conv = (conv_id or "default").replace("/", "_").replace(":", "_")
    return WORKSPACE / f"todo_{safe_conv}.json"


def _read(conv_id: str | None) -> list[dict]:
    path = _todo_path(conv_id)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return []


def _write(conv_id: str | None, items: list[dict]) -> None:
    path = _todo_path(conv_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2))


def _validate(items: Any) -> tuple[list[dict] | None, str | None]:
    """Validate and normalize the items list. Returns (clean_items, error_or_None)."""
    if not isinstance(items, list):
        return None, f"items must be a list, got {type(items).__name__}"
    if len(items) > 100:
        return None, f"too many items ({len(items)}); cap is 100. Trim to what's actually next."

    clean = []
    in_progress_count = 0
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            return None, f"item #{i} is not a dict (got {type(raw).__name__})"
        content = (raw.get("content") or "").strip()
        active = (raw.get("activeForm") or "").strip()
        status = (raw.get("status") or "pending").strip().lower()
        if not content:
            return None, f"item #{i} has empty 'content' (must describe the task)"
        if not active:
            # Soft-default to content if activeForm missing — not a hard error
            active = content
        if status not in _VALID_STATUSES:
            return None, (
                f"item #{i} has invalid status {status!r}; "
                f"must be one of {sorted(_VALID_STATUSES)}"
            )
        if status == "in_progress":
            in_progress_count += 1
        clean.append({"content": content, "activeForm": active, "status": status})

    if in_progress_count > 1:
        return None, (
            f"only ONE item may be in_progress at a time (found {in_progress_count}). "
            f"Mark the others as pending or completed before starting a new one."
        )

    return clean, None


# Read conv_id from the tool_guards module (set during respond_started).
def _current_conv_id() -> str | None:
    try:
        from core import tool_guards
        return tool_guards.current_conv_id()
    except Exception:  # noqa: BLE001
        return None


@tool(
    name="todo_set",
    summary=(
        "Replace the session-scoped todo list with the provided items. Use FIRST "
        "for any multi-step task (3+ steps) to plan, then call again as items "
        "transition status (pending → in_progress → completed). Each item: "
        "{content (imperative), activeForm (present-progressive), status}. Only "
        "ONE item may be in_progress at a time. List is cleared when a new "
        "conversation starts. Distinct from set_goal (long-running, heartbeat-"
        "advanced) and add_task (persistent, async)."
    ),
    triggers=("plan", "todo", "tasks", "next steps", "checklist"),
    schema={
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "description": (
                    "Full new list (replaces current). Each item is a dict with "
                    "content (the task in imperative form, e.g. 'Read agent.py'), "
                    "activeForm (the present-progressive form shown during "
                    "execution, e.g. 'Reading agent.py'), and status (one of "
                    "'pending', 'in_progress', 'completed')."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "activeForm": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                        },
                    },
                    "required": ["content", "status"],
                },
            },
        },
        "required": ["items"],
    },
)
def todo_set(items: list[dict]) -> str:
    clean, err = _validate(items)
    if err:
        return f"[error:validation] {err}"
    conv_id = _current_conv_id()
    _write(conv_id, clean)
    counts = {"pending": 0, "in_progress": 0, "completed": 0}
    for it in clean:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    return (
        f"todo list updated for conv={conv_id or 'default'!r}: "
        f"{counts['pending']} pending, {counts['in_progress']} in_progress, "
        f"{counts['completed']} completed (total {len(clean)})"
    )


@tool(
    name="todo_get",
    summary=(
        "Return the current session-scoped todo list. Use when you need to "
        "check what's planned vs done in this conversation, especially after "
        "several rounds of tool work."
    ),
    triggers=("show todo", "what's the plan", "what's next", "check tasks"),
    schema={
        "type": "object",
        "properties": {},
    },
)
def todo_get() -> str:
    conv_id = _current_conv_id()
    items = _read(conv_id)
    if not items:
        return f"(no todo list for conv={conv_id or 'default'!r} — call todo_set to create one)"
    lines = [f"todo list for conv={conv_id or 'default'!r}:"]
    for i, it in enumerate(items, 1):
        marker = {"pending": "☐", "in_progress": "⚡", "completed": "✓"}.get(it["status"], "?")
        text = it["activeForm"] if it["status"] == "in_progress" else it["content"]
        lines.append(f"  {i}. [{marker} {it['status']}] {text}")
    return "\n".join(lines)
