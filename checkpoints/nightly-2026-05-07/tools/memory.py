"""Memory tools: remember(fact, tags) and recall(query)."""
from __future__ import annotations

from core import memory
from core.tools import tool


@tool(
    name="remember",
    summary="Save a fact to long-term memory. Use for things you want to recall in future conversations.",
    triggers=("remember", "note that", "save this", "memorize", "don't forget", "make a note"),
    schema={
        "type": "object",
        "properties": {
            "fact": {"type": "string", "description": "The fact to remember, written as a complete sentence."},
            "tags": {"type": "string", "description": "Optional comma-separated tags for retrieval (e.g. 'john,preference').", "default": ""},
        },
        "required": ["fact"],
    },
)
def remember(fact: str, tags: str = "") -> str:
    fact_id = memory.add_fact(fact, tags=tags)
    return f"remembered (id={fact_id}): {fact}"


@tool(
    name="recall",
    summary="Search long-term memory for facts matching a query. Returns up to 5 matches.",
    triggers=("recall", "remember", "what do you know about", "what did i tell you", "what was", "do you know"),
    schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Substring or tag to search for."},
        },
        "required": ["query"],
    },
)
def recall(query: str) -> str:
    hits = memory.search_facts(query, limit=5)
    if not hits:
        return f"(no facts match {query!r})"
    lines = [f"- [{h['created_at'][:10]}] {h['fact']}" + (f"  ({h['tags']})" if h["tags"] else "") for h in hits]
    return "\n".join(lines)
