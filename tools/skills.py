"""Skill registry tools.

A skill is something Charles has learned to DO — a tool pattern, a
recovery procedure, a habit. Skills have evidence-based levels:
  - novice: first exposure, surface knowledge
  - practiced: 3+ successful uses
  - expert: 10+ successful uses, can apply broadly

Use to compound learning over time — when Charles hits the same
problem twice and solves it the same way, that's a skill he should
register so future Charles knows it's a settled approach.
"""
from __future__ import annotations

from core import memory as _mem
from core.tools import tool


@tool(
    name="skill_register",
    summary=(
        "Register a new skill or update one's metadata. Use when you've "
        "figured out a useful pattern (tool combo, recovery procedure, "
        "behavioral habit) and want to remember you can do it."
    ),
    triggers=("register skill", "new skill", "learned skill"),
    schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill slug (e.g. 'cloudflare_block_recovery')."},
            "title": {"type": "string", "description": "Human-readable name.", "default": ""},
            "description": {"type": "string", "description": "What the skill is and when to use it.", "default": ""},
        },
        "required": ["name"],
    },
)
def skill_register(name: str, title: str = "", description: str = "") -> str:
    sid = _mem.skill_upsert(name, title, description)
    return f"skill registered (id={sid}, name={name!r})"


@tool(
    name="skill_log_use",
    summary=(
        "Log a single use of a skill — was it a success or failure? "
        "Auto-promotes the skill's level when success counts cross thresholds "
        "(3 successes → practiced, 10 → expert). Charles becomes more "
        "confident at things he keeps doing right."
    ),
    triggers=("log skill", "used skill", "applied skill"),
    schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill slug."},
            "success": {"type": "boolean", "description": "True if the application worked, False if it didn't."},
            "evidence": {"type": "string", "description": "Short note describing what just happened.", "default": ""},
        },
        "required": ["name", "success"],
    },
)
def skill_log_use(name: str, success: bool, evidence: str = "") -> str:
    ok = _mem.skill_record_attempt(name, bool(success), evidence)
    row = _mem.skill_get(name)
    if not ok or not row:
        return f"[error] couldn't log skill use for {name!r}"
    return (
        f"logged ({'success' if success else 'failure'}). "
        f"Now: {row['level']} ({row['success_count']} successes, {row['failure_count']} failures)."
    )


@tool(
    name="skill_list",
    summary=(
        "List all registered skills with their level (novice/practiced/expert) "
        "and success counts. Optionally filter by level."
    ),
    triggers=("list skills", "what can i do", "my skills"),
    schema={
        "type": "object",
        "properties": {
            "level": {"type": "string", "description": "Optional filter: novice | practiced | expert.", "default": ""},
            "limit": {"type": "integer", "description": "Max to return.", "default": 50},
        },
    },
)
def skill_list(level: str = "", limit: int = 50) -> str:
    rows = _mem.skill_list(level=level or None, limit=int(limit))
    if not rows:
        return "(no skills registered)" if not level else f"(no skills at level={level!r})"
    lines = []
    for r in rows:
        title = r.get("title") or r["name"]
        lev = r["level"]
        wins = r["success_count"]
        losses = r["failure_count"]
        last = (r.get("last_used_at") or "")[:10]
        lines.append(f"  [{lev:9s}] {title} ({r['name']}) — {wins}W/{losses}L, last {last}")
    return "Skills:\n" + "\n".join(lines)


@tool(
    name="skill_get",
    summary="Return full info on one skill — level, evidence, success/failure counts, description.",
    triggers=("skill info", "skill detail", "show skill"),
    schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill slug."},
        },
        "required": ["name"],
    },
)
def skill_get(name: str) -> str:
    r = _mem.skill_get(name)
    if not r:
        return f"(no skill named {name!r})"
    return (
        f"{r.get('title') or r['name']} ({r['name']})\n"
        f"Level: {r['level']}\n"
        f"Counts: {r['success_count']} successes, {r['failure_count']} failures\n"
        f"Last used: {r.get('last_used_at') or '(never)'}\n"
        f"Description: {r.get('description') or '(none)'}\n"
        f"Latest evidence: {r.get('evidence') or '(none)'}"
    )
