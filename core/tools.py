"""Tool registry, classifier, and dispatcher.

Architectural point of M1: lean prompt by default. Only the SUMMARIES of all
tools go in the system prompt every turn (one line each). Full JSON schemas
are loaded ONLY for the 0-3 tools the classifier matches against the user's
current message. This is the dynamic-loading model that lets us keep
hundreds of tools without OpenClaw-scale prompt bloat.
"""
from __future__ import annotations

import difflib
import inspect
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

_SMART_QUOTES = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
})


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
    text = (message or "").lower().translate(_SMART_QUOTES)
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

    Hardened 2026-05-09 after forensic showed Charles repeatedly emitting
    tool_calls with missing required args (exec_shell() / self_patch() /
    append_goal_note() with no args), and trying tools that don't exist
    (append_file). All errors are returned as actionable strings so the
    model learns from them instead of looping.

    Hardened again 2026-05-09 evening after a 500-turn forensic showed the
    model doesn't remember what it already tried. The dispatcher now calls
    into core.tool_guards before and after each handler invocation:
      - blocks repeat browse_url calls to URLs that already returned
        access-denied / 404 / cloudflare-block / etc.,
      - blocks exact same-call duplicates within one respond() chain,
      - returns a content-hash signal for read_file re-reads in the same
        chain instead of re-dumping the file,
      - redirects exec_shell+sqlite3 against memory.db to recall().
    See core/tool_guards.py for the full guard set.
    """
    from core import tool_guards  # late import — avoids circular at module load

    t = REGISTRY.get(name)
    if t is None:
        # Suggest the closest matching real tool name so Charles fixes the typo
        # instead of hallucinating it again next round.
        names = list(REGISTRY.keys())
        close = difflib.get_close_matches(name, names, n=3, cutoff=0.5)
        suggestion = f" Did you mean: {', '.join(close)}?" if close else ""
        return f"[error] unknown tool: {name}.{suggestion} Available tools: {', '.join(sorted(names))}"

    try:
        kwargs: dict[str, Any] = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        return f"[error] bad JSON arguments to {name}: {e}. Got: {arguments_json[:200]}"

    # Pre-flight: check required args BEFORE calling the handler. Catches the
    # Qwen3.6 failure mode where the model emits e.g. exec_shell() with no
    # args; better to surface 'missing command' than a Python TypeError.
    missing = _missing_required_args(t, kwargs)
    if missing:
        required_props = (t.schema.get("required") or [])
        all_props = list((t.schema.get("properties") or {}).keys())
        return (
            f"[error] {name}() missing required argument(s): {', '.join(missing)}. "
            f"Required: {required_props or 'none'}. "
            f"All accepted args: {all_props or 'none'}. "
            f"You called it with: {list(kwargs.keys()) or 'no arguments'}. "
            f"Re-emit the tool_call with the missing arg(s) filled in."
        )

    # Behavioral guards — short-circuit on blocked URLs / repeat calls /
    # sqlite-as-memory anti-pattern / same-chain re-reads.
    guard_msg = tool_guards.check_pre_call(name, kwargs)
    if guard_msg is not None:
        log.info("guard short-circuit on %s: %s", name, guard_msg[:120])
        return guard_msg
    tool_guards.mark_in_flight(name, kwargs)

    try:
        result = t.handler(**kwargs)
    except TypeError as e:
        # Defensive — schema-validation may pass but handler signature can
        # still mismatch. Give the model a cleaner error than a raw stack.
        sig = inspect.signature(t.handler)
        return (
            f"[error] {name}() rejected the args: {e}. "
            f"Handler signature: {name}{sig}. "
            f"You passed: {list(kwargs.keys())}."
        )
    except Exception as e:  # noqa: BLE001 — surface anything to the model
        return f"[error] {type(e).__name__} in {name}: {e}"

    out = result if isinstance(result, str) else json.dumps(result, default=str)
    tool_guards.post_call(name, kwargs, out)
    return out


def _missing_required_args(t: Tool, kwargs: dict[str, Any]) -> list[str]:
    """Return the names of required args the model didn't supply."""
    required = t.schema.get("required") or []
    return [r for r in required if r not in kwargs]
