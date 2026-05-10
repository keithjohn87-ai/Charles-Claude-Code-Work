"""John-preferences ledger tools.

Settled doctrine in queryable form. When Charles isn't sure how John wants
something handled, call `john_says(category)` instead of guessing. Examples:
- 'comms' → how to address John, what channel, what register
- 'tooling' → which tools to prefer, which to avoid
- 'autonomy' → when to ask vs when to drive
"""
from __future__ import annotations

from core import memory as _mem
from core.tools import tool


@tool(
    name="john_says",
    summary=(
        "Return John's settled doctrine on a category. Use this whenever you're "
        "unsure how he'd want something handled — instead of guessing. Categories: "
        "comms, autonomy, technical, personal, scheduling, tooling. Returns the "
        "active rules in that category."
    ),
    triggers=("john says", "john's rule", "what does john want", "john's preference", "doctrine"),
    schema={
        "type": "object",
        "properties": {
            "category": {"type": "string", "description": "Category (comms / autonomy / technical / personal / scheduling / tooling). Empty = all categories."},
        },
    },
)
def john_says(category: str = "") -> str:
    rows = _mem.john_prefs_by_category(category or None)
    if not rows:
        return f"(no John-prefs found{' in category=' + category if category else ''})"
    lines = []
    current_cat = None
    for r in rows:
        if r["category"] != current_cat:
            current_cat = r["category"]
            lines.append(f"\n## {current_cat.upper()}")
        lines.append(f"- {r['rule']}")
        if r.get("why"):
            lines.append(f"    Why: {r['why']}")
        if r.get("how_to_apply"):
            lines.append(f"    How to apply: {r['how_to_apply']}")
    return "\n".join(lines).strip()


@tool(
    name="john_pref_add",
    summary=(
        "Add a new John-preference rule. Call this when John says something "
        "directive like 'from now on...', 'always do X', 'never do Y'. The rule "
        "becomes queryable via john_says(category)."
    ),
    triggers=("save john pref", "remember john's rule", "doctrine add"),
    schema={
        "type": "object",
        "properties": {
            "category": {"type": "string", "description": "Category (comms / autonomy / technical / personal / scheduling / tooling)."},
            "rule": {"type": "string", "description": "The rule in imperative form ('use X, not Y')."},
            "why": {"type": "string", "description": "Optional reason / context.", "default": ""},
            "how_to_apply": {"type": "string", "description": "Optional: when/how this rule fires.", "default": ""},
            "source": {"type": "string", "description": "Where it came from (session date / memory file).", "default": ""},
        },
        "required": ["category", "rule"],
    },
)
def john_pref_add(category: str, rule: str, why: str = "", how_to_apply: str = "", source: str = "") -> str:
    pid = _mem.john_pref_add(category, rule, why, how_to_apply, source)
    return f"saved John-pref (id={pid}, category={category!r})"


@tool(
    name="john_pref_categories",
    summary="List all John-preference categories with rule counts. Use to see the shape of John's doctrine.",
    triggers=("john categories", "doctrine categories", "prefs categories"),
    schema={"type": "object", "properties": {}},
)
def john_pref_categories() -> str:
    cats = _mem.john_pref_categories()
    if not cats:
        return "(no John-prefs registered)"
    lines = ["John-pref categories:"]
    for cat, n in cats:
        lines.append(f"  {cat}: {n} rules")
    return "\n".join(lines)
