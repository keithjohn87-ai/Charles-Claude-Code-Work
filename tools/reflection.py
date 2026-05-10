"""Reflection-loop tools.

Daily self-review: aggregates fact ingestion by topic, refreshes summaries
for topics that grew, identifies thin/cold topics, auto-supersedes stale
facts. Persists a digestible "what I learned today" fact.

Run via scheduled_task daily (suggested 04:00 EST during the prune sweep
window). Charles can also call it manually with `reflect_now`.
"""
from __future__ import annotations

from core import memory as _mem
from core.tools import tool


@tool(
    name="reflect_now",
    summary=(
        "Run a daily reflection pass: count new facts by topic, refresh "
        "summaries for topics with >=3 new facts, identify thin/cold topics, "
        "auto-supersede stale facts (>30 days unused). Persists a digest "
        "fact tagged 'reflection,daily,system'."
    ),
    triggers=("reflect", "daily reflection", "self review", "what did i learn"),
    schema={"type": "object", "properties": {}},
)
def reflect_now() -> str:
    digest = _mem.reflect_daily()
    by_topic = digest["new_facts_by_topic"]
    top_topics = sorted(by_topic.items(), key=lambda kv: -kv[1])[:5]
    parts = [
        f"Daily reflection ({digest['date']})",
        f"New facts (24h): {digest['new_facts_total']}",
    ]
    if top_topics:
        parts.append("Top topics today: " + ", ".join(f"{t} ({n})" for t, n in top_topics))
    if digest["topics_with_new_summaries"]:
        parts.append("Refreshed summaries: " + ", ".join(digest["topics_with_new_summaries"]))
    if digest["thin_topics"]:
        parts.append("Thin topics (need content): " + ", ".join(digest["thin_topics"][:5]))
    if digest["cold_topics"]:
        parts.append("Cold topics (14d+ untouched): " + ", ".join(digest["cold_topics"][:5]))
    if digest["cold_facts_marked"]:
        parts.append(f"Auto-superseded {digest['cold_facts_marked']} stale facts.")
    return "\n".join(parts)
