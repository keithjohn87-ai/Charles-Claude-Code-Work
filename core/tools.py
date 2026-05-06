"""Tool registry, classifier, and dispatcher.

Architectural point of M1: lean prompt by default. Only the SUMMARIES of all
tools go in the system prompt every turn (one line each). Full JSON schemas
are loaded ONLY for the 0-3 tools the classifier matches against the user's
current message. This is the dynamic-loading model that lets us keep
hundreds of tools without OpenClaw-scale prompt bloat.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("charles.tools")


@dataclass
class Tool:
    name: str
    summary: str
    schema: dict
    triggers: tuple[str, ...]
    handler: Callable[..., str]

    def openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.summary,
                "parameters": self.schema,
            },
        }


REGISTRY: dict[str, Tool] = {}


def tool(*, name: str, summary: str, schema: dict, triggers: tuple[str, ...] = ()):
    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        if name in REGISTRY:
            raise ValueError(f"tool {name!r} already registered")
        REGISTRY[name] = Tool(
            name=name,
            summary=summary.strip(),
            schema=schema,
            triggers=tuple(t.lower() for t in triggers),
            handler=fn,
        )
        return fn

    return decorator


def summary_block() -> str:
    """One-line summary per tool, for the lean default prompt."""
    if not REGISTRY:
        return ""
    lines = [f"- {t.name}: {t.summary}" for t in REGISTRY.values()]
    return "Tools you can call:\n" + "\n".join(lines)


def select_tools(message: str, max_tools: int = 3) -> list[Tool]:
    """Pick up to N tools whose triggers appear in the message.

    v0 classifier: case-insensitive substring match on registered triggers.
    Score = number of distinct triggers that hit. Ties broken by registration order.
    """
    text = (message or "").lower()
    scored: list[tuple[int, int, Tool]] = []
    for idx, t in enumerate(REGISTRY.values()):
        hits = sum(1 for trig in t.triggers if trig in text)
        if hits:
            scored.append((-hits, idx, t))
    scored.sort()
    selected = [t for _, _, t in scored[:max_tools]]
    if selected:
        log.info("classifier selected: %s", [t.name for t in selected])
    return selected


def dispatch(name: str, arguments_json: str) -> str:
    """Run a tool by name with JSON-string arguments. Always returns a string.

    Errors are caught and returned as text so the model can read them. YOLO
    mode: no confirmation gates.
    """
    t = REGISTRY.get(name)
    if t is None:
        return f"[error] unknown tool: {name}"
    try:
        kwargs: dict[str, Any] = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        return f"[error] bad JSON arguments: {e}"
    try:
        result = t.handler(**kwargs)
    except Exception as e:  # noqa: BLE001 — surface anything to the model
        return f"[error] {type(e).__name__}: {e}"
    return result if isinstance(result, str) else json.dumps(result, default=str)
