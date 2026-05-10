"""Topic tools — hierarchical organization of facts.

Every fact has a `topic` field (set at save time, or backfilled from first tag).
This module exposes tools to:
  - list topics with fact counts
  - read the summary card for a topic
  - drill into facts under a topic
  - set parent/child relationships (hierarchy)
  - regenerate a topic's summary by composing from its top facts

Topic hierarchy is OPTIONAL — every topic starts as a root. Charles can
promote topics into a tree as patterns emerge (e.g., group "kahneman_tversky"
and "cialdini" under parent "behavioral_psychology").
"""
from __future__ import annotations

from core import memory as _mem
from core.tools import tool


@tool(
    name="topic_list",
    summary=(
        "List topics with their fact counts and last-activity timestamps. "
        "Use to see the shape of your knowledge — which topics are dense, "
        "which are thin. Sorted by fact count, biggest first."
    ),
    triggers=("topics", "list topics", "what topics", "knowledge map"),
    schema={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Max topics to return.", "default": 30},
            "min_facts": {"type": "integer", "description": "Skip topics with fewer than this many facts.", "default": 1},
        },
    },
)
def topic_list(limit: int = 30, min_facts: int = 1) -> str:
    rows = _mem.topic_list(limit=limit, min_facts=min_facts)
    if not rows:
        return "(no topics with facts yet)"
    lines = ["Topics (sorted by fact count):"]
    for r in rows:
        title = r.get("title") or r["name"]
        n = r["fact_count"]
        last = (r.get("last_fact_at") or "")[:10]
        summary_marker = "📝" if r.get("summary") else "  "
        lines.append(f"  {summary_marker} {title} ({r['name']}) — {n} facts, last {last}")
    return "\n".join(lines)


@tool(
    name="recall_topic",
    summary=(
        "Read a topic's cached summary card + its top recent facts. Use when "
        "you want a domain overview rather than searching by query. If the "
        "summary is empty/stale, call topic_recompute_summary to refresh."
    ),
    triggers=("recall topic", "topic summary", "what do I know about topic"),
    schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Topic name (e.g. 'cognitive_bias', 'human_context')."},
            "fact_limit": {"type": "integer", "description": "How many recent facts to include after the summary.", "default": 5},
        },
        "required": ["name"],
    },
)
def recall_topic(name: str, fact_limit: int = 5) -> str:
    name = (name or "").strip().lower().replace(" ", "_")
    if not name:
        return "[error] topic name required"
    rows = _mem.topic_list(limit=200)
    meta = next((r for r in rows if r["name"] == name), None)
    if not meta:
        return f"(no topic named {name!r}; try topic_list)"
    facts = _mem.topic_facts(name, limit=fact_limit)
    parts = [f"# Topic: {meta.get('title') or name} ({meta['fact_count']} facts)"]
    if meta.get("summary"):
        parts.append("")
        parts.append("## Summary")
        parts.append(meta["summary"])
    if facts:
        parts.append("")
        parts.append("## Recent facts:")
        for f in facts:
            text = f["fact"][:250]
            parts.append(f"- [{f['created_at'][:10]}] {text}")
    return "\n".join(parts)


@tool(
    name="topic_set_parent",
    summary=(
        "Wire a topic into a hierarchy by assigning a parent. Use when you "
        "notice related topics that belong under a common umbrella "
        "(e.g., 'kahneman_tversky' and 'gigerenzer' under 'behavioral_psychology'). "
        "Passing parent_name='' (empty) removes the parent link."
    ),
    triggers=("set parent", "topic hierarchy", "group topics"),
    schema={
        "type": "object",
        "properties": {
            "child_name": {"type": "string", "description": "Topic to be made a child."},
            "parent_name": {"type": "string", "description": "Parent topic name. Auto-created if it doesn't exist. Empty string unsets.", "default": ""},
        },
        "required": ["child_name"],
    },
)
def topic_set_parent(child_name: str, parent_name: str = "") -> str:
    ok = _mem.topic_set_parent(child_name, parent_name or None)
    if not ok:
        return f"[error] topic {child_name!r} not found"
    if parent_name:
        return f"set {child_name!r} → child of {parent_name!r}"
    return f"unset parent of {child_name!r}"


@tool(
    name="topic_recount",
    summary=(
        "Rebuild fact counts and last-activity timestamps for all topics by "
        "scanning long_term_facts. Also creates missing topic rows for any "
        "topic referenced in facts. Run this once after a bulk-ingestion or "
        "if counts look stale."
    ),
    triggers=("recount topics", "refresh topics"),
    schema={"type": "object", "properties": {}},
)
def topic_recount() -> str:
    n = _mem.topic_recount()
    return f"recomputed counts for {n} topic(s)"


@tool(
    name="topic_recompute_summary",
    summary=(
        "Regenerate a topic's cached summary by composing it from the topic's "
        "top facts. The summary is a one-paragraph synthesis John or you can "
        "read fast instead of scrolling through 30 facts. Run periodically on "
        "topics that have accumulated new facts since the last summary."
    ),
    triggers=("recompute summary", "refresh topic summary", "rebuild topic summary"),
    schema={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Topic name."},
        },
        "required": ["name"],
    },
)
def topic_recompute_summary(name: str) -> str:
    name = (name or "").strip().lower().replace(" ", "_")
    facts = _mem.topic_facts(name, limit=15)
    if not facts:
        return f"(no facts under topic {name!r})"
    # Synthesize a summary deterministically — first N chars from each top
    # fact, joined. Charles can later call this tool then improve the summary
    # via a follow-up `topic_set_summary` if he wants a richer LLM-written one.
    bullets = []
    for f in facts[:8]:
        text = f["fact"].strip()
        # Pull just the first sentence if it's long
        first_sentence = text.split(". ", 1)[0]
        if len(first_sentence) > 220:
            first_sentence = first_sentence[:217] + "..."
        bullets.append(f"- {first_sentence}.")
    summary = (
        f"Top facts under '{name}' ({len(facts)} sampled, {facts[0]['created_at'][:10]} latest):\n"
        + "\n".join(bullets)
    )
    ok = _mem.topic_set_summary(name, summary)
    if not ok:
        # Topic didn't exist yet — upsert and retry
        _mem.topic_upsert(name)
        _mem.topic_set_summary(name, summary)
    return f"summary set for {name!r} ({len(facts)} facts sampled, {len(summary)} chars)"


@tool(
    name="topic_tree",
    summary=(
        "Render the topic hierarchy as a tree. Shows parent → child "
        "relationships. Use to see how your knowledge is structured."
    ),
    triggers=("topic tree", "knowledge tree", "show hierarchy"),
    schema={"type": "object", "properties": {}},
)
def topic_tree() -> str:
    roots = _mem.topic_tree()
    if not roots:
        return "(no topics)"
    lines = []

    def render(node, depth=0):
        prefix = "  " * depth + ("└─ " if depth > 0 else "")
        title = node.get("title") or node["name"]
        lines.append(f"{prefix}{title} ({node['fact_count']} facts)")
        for child in node["children"]:
            render(child, depth + 1)

    for root in roots:
        render(root)
    return "\n".join(lines)
