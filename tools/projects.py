"""Project tools — structured per-project state.

Replaces the "ask Charles to count" pattern. Every long-running initiative
(URL corpus, code refactor, learning track) gets:
  - one `project` row with a slug, title, status
  - many `project_items` rows with status + attempt + fact counts

Status checks return the same number every time because they're SQL
aggregates over structured rows, not Charles re-grepping his own notes.
"""
from __future__ import annotations

import json

from core import memory as _mem
from core.tools import tool


@tool(
    name="project_create",
    summary=(
        "Create a project — a long-running initiative with item-level status. "
        "Use this for any goal that has discrete items (URLs to process, files "
        "to refactor, topics to master). Items get registered separately via "
        "project_register_items. Idempotent on slug."
    ),
    triggers=("create project", "new project", "start project"),
    schema={
        "type": "object",
        "properties": {
            "slug": {"type": "string", "description": "URL-safe identifier (e.g. 'url_corpus_part2'). Stable handle for all later operations."},
            "title": {"type": "string", "description": "Human-readable title."},
            "description": {"type": "string", "description": "What the project is about.", "default": ""},
            "goal_id": {"type": "integer", "description": "Optional link to an existing goal id.", "default": 0},
        },
        "required": ["slug", "title"],
    },
)
def project_create(slug: str, title: str, description: str = "", goal_id: int = 0) -> str:
    pid = _mem.project_create(slug, title, description, goal_id or None)
    return f"project created (id={pid}, slug={slug!r})"


@tool(
    name="project_register_items",
    summary=(
        "Bulk-register items in a project. Pass items as a JSON array of objects "
        "with 'key' (unique within project), optional 'title' and 'type'. "
        "Idempotent — re-running with the same keys skips existing items, so this "
        "is safe to call repeatedly when ingesting a source file."
    ),
    triggers=("register items", "load items", "ingest items"),
    schema={
        "type": "object",
        "properties": {
            "slug": {"type": "string", "description": "Project slug."},
            "items_json": {"type": "string", "description": "JSON array string. Example: '[{\"key\":\"https://X\",\"title\":\"X\",\"type\":\"url\"}, ...]'"},
        },
        "required": ["slug", "items_json"],
    },
)
def project_register_items(slug: str, items_json: str) -> str:
    try:
        items = json.loads(items_json)
    except json.JSONDecodeError as e:
        return f"[error] items_json must be a valid JSON array: {e}"
    if not isinstance(items, list):
        return "[error] items_json must be a JSON array"
    try:
        n = _mem.project_register_items(slug, items)
    except ValueError as e:
        return f"[error] {e}"
    return f"registered {n} item(s) in project {slug!r}"


@tool(
    name="project_status",
    summary=(
        "Return ONE deterministic status summary for a project: total, "
        "counts by status (pending/done/blocked/...), progress %, recent activity. "
        "USE THIS instead of counting from goal notes or recall() — it returns "
        "the same number every time."
    ),
    triggers=("project status", "how many done", "what is left", "progress on"),
    schema={
        "type": "object",
        "properties": {
            "slug": {"type": "string", "description": "Project slug."},
        },
        "required": ["slug"],
    },
)
def project_status(slug: str) -> str:
    s = _mem.project_status(slug)
    if not s:
        return f"[error] project {slug!r} not found"
    by_status = s["by_status"]
    parts = [
        f"Project: {s['title']} ({s['slug']}) — status={s['status']}",
        f"Progress: {by_status.get('done', 0)}/{s['total']} done ({s['progress_pct']}%)",
        "By status: " + ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())),
    ]
    if s.get("last_attempt_at"):
        parts.append(f"Last attempt: {s['last_attempt_at']}")
    if s.get("recent_done"):
        parts.append("Recent done: " + ", ".join(s["recent_done"][:3]))
    if s.get("recent_blocked"):
        parts.append("Recent blocked: " + ", ".join(s["recent_blocked"][:3]))
    return "\n".join(parts)


@tool(
    name="project_next_pending",
    summary=(
        "Return the next pending item in a project (lowest position with status "
        "= pending). Use during goal-tick chains to pick what to work on next "
        "without re-counting or re-reading source files."
    ),
    triggers=("next item", "what next", "next pending", "next url"),
    schema={
        "type": "object",
        "properties": {
            "slug": {"type": "string", "description": "Project slug."},
        },
        "required": ["slug"],
    },
)
def project_next_pending(slug: str) -> str:
    item = _mem.project_next_pending(slug)
    if not item:
        return f"(no pending items in {slug!r} — project may be complete)"
    parts = [f"#{item['position']} key={item['item_key']}"]
    if item.get("title"):
        parts.append(f"title={item['title']}")
    if item.get("item_type"):
        parts.append(f"type={item['item_type']}")
    if item.get("attempt_count"):
        parts.append(f"prior_attempts={item['attempt_count']}")
    return " | ".join(parts)


@tool(
    name="project_mark_item",
    summary=(
        "Update a single item's status. Use this immediately after attempting an "
        "item — set status=done/blocked/skipped/etc., record fact_count_delta if "
        "the item produced facts, and last_error if blocked. ALWAYS update an "
        "item after working on it — that's how the project's status stays accurate."
    ),
    triggers=("mark item", "mark done", "mark blocked", "mark item status"),
    schema={
        "type": "object",
        "properties": {
            "slug": {"type": "string", "description": "Project slug."},
            "item_key": {"type": "string", "description": "Unique key of the item (the URL / file path / etc. you registered)."},
            "status": {"type": "string", "description": "pending | in_progress | done | blocked | skipped | paywalled | 404", "enum": ["pending", "in_progress", "done", "blocked", "skipped", "paywalled", "404"]},
            "last_error": {"type": "string", "description": "Short reason for non-success statuses (e.g. 'cloudflare_block').", "default": ""},
            "fact_count_delta": {"type": "integer", "description": "How many new facts were derived from this attempt. 0 for blocked/skipped.", "default": 0},
            "notes": {"type": "string", "description": "Optional free-text note to append.", "default": ""},
        },
        "required": ["slug", "item_key", "status"],
    },
)
def project_mark_item(
    slug: str,
    item_key: str,
    status: str,
    last_error: str = "",
    fact_count_delta: int = 0,
    notes: str = "",
) -> str:
    ok = _mem.project_mark_item(
        slug,
        item_key,
        status=status,
        last_error=last_error or None,
        fact_count_delta=fact_count_delta,
        notes=notes or None,
    )
    if not ok:
        return f"[error] item not found: project={slug!r} key={item_key!r}"
    return f"marked {item_key!r} as {status} in {slug!r}"


@tool(
    name="project_list_items",
    summary=(
        "List items in a project, optionally filtered by status. Returns "
        "position-ordered with key, title, status. Use to see what's pending "
        "or what's been done."
    ),
    triggers=("list items", "show items", "project items"),
    schema={
        "type": "object",
        "properties": {
            "slug": {"type": "string", "description": "Project slug."},
            "status": {"type": "string", "description": "Optional filter: pending | done | blocked | etc.", "default": ""},
            "limit": {"type": "integer", "description": "Max items to return.", "default": 50},
        },
        "required": ["slug"],
    },
)
def project_list_items(slug: str, status: str = "", limit: int = 50) -> str:
    items = _mem.project_list_items(slug, status=status or None, limit=int(limit))
    if not items:
        return f"(no items in {slug!r}" + (f" with status={status!r}" if status else "") + ")"
    lines = []
    for it in items:
        parts = [f"#{it['position']}", it["item_key"]]
        if it["title"]:
            parts.append(f"({it['title']})")
        parts.append(f"[{it['status']}]")
        if it["fact_count"]:
            parts.append(f"facts={it['fact_count']}")
        if it["last_error"]:
            parts.append(f"err={it['last_error'][:40]}")
        lines.append(" ".join(parts))
    return "\n".join(lines)
