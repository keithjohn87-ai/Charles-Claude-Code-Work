"""Sub-agent spawning — Claude Code's Task tool, ported.

Lets Charles delegate a self-contained task to a fresh-context sub-agent
running on the same model. The sub-agent gets full max_rounds budget,
runs to completion in isolation, and returns the final reply text to
the parent chain.

Why this matters:
  - Context isolation: research-heavy work (read 10 files, summarize)
    bloats the parent's context. Delegating that to a subagent keeps
    the parent's context clean for the user-facing reply.
  - Recursion safety: the parent stays focused on the user's question;
    the subagent goes deep on the prerequisite.
  - Future-parallelization-ready: although MLX is single-threaded today
    (no actual parallelism benefit), the API is shaped so that when /
    if a multi-instance backend lands, parallel sub-agents become free.

Distinct from `call_claude` (the operator/consultant bridge):
  - call_claude → delegates to the Anthropic Claude API (different model,
    intelligence boost). Use when local Qwen isn't smart enough for the
    task. Costs API tokens.
  - delegate_subagent → delegates to a FRESH local Charles instance
    (same model, isolated context). Use when the task is well within
    Qwen's capability but you want context isolation. Free.

Recursion depth is capped at MAX_SUBAGENT_DEPTH (default 2) to prevent
runaway spawn chains. Each subagent's conv_id is namespaced as
"subagent:<parent_conv>:<depth>:<n>" for traceability in the
conversations table.
"""
from __future__ import annotations

import contextvars
import logging

from core.tools import tool

log = logging.getLogger("charles.tools.subagent")

MAX_SUBAGENT_DEPTH = 2

_subagent_depth: contextvars.ContextVar[int] = contextvars.ContextVar(
    "subagent_depth", default=0,
)
_subagent_counter: contextvars.ContextVar[int] = contextvars.ContextVar(
    "subagent_counter", default=0,
)


def _next_subagent_conv_id(parent_conv_id: str | None) -> str:
    n = _subagent_counter.get() + 1
    _subagent_counter.set(n)
    depth = _subagent_depth.get() + 1
    parent = parent_conv_id or "root"
    return f"subagent:{parent}:{depth}:{n}"


@tool(
    name="delegate_subagent",
    summary=(
        "Spawn a fresh-context sub-agent to handle a self-contained task. "
        "The sub-agent runs on the same local model with isolated history "
        "and returns its final reply text. Use when (a) the task is "
        "research-heavy and would bloat your context (e.g., 'read 10 files "
        "and summarize'); (b) the task is well-defined enough to specify "
        "in one prompt; (c) you don't need the sub-agent's intermediate "
        "tool calls in your own context. For tasks that need higher model "
        "intelligence than local Qwen provides, use `call_claude` instead "
        "(delegates to Anthropic Claude API). Recursion depth capped at "
        f"{MAX_SUBAGENT_DEPTH}; sub-agents cannot spawn their own sub-agents "
        "beyond that depth."
    ),
    triggers=("delegate", "subagent", "spawn", "research subtask"),
    schema={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": (
                    "The full self-contained task description for the "
                    "sub-agent. Must include all context the sub-agent "
                    "needs — sub-agent does NOT see your conversation "
                    "history. Be specific about what you want returned "
                    "(e.g., 'a 200-word summary' or 'a list of file paths' "
                    "or 'the dollar value found in the doc')."
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "Optional additional context to prepend to the task — "
                    "use for shared facts, file paths, conventions the "
                    "sub-agent should know but that aren't part of the task "
                    "itself."
                ),
                "default": "",
            },
        },
        "required": ["task"],
    },
)
def delegate_subagent(task: str, context: str = "") -> str:
    current_depth = _subagent_depth.get()
    if current_depth >= MAX_SUBAGENT_DEPTH:
        return (
            f"[error:blocked] sub-agent recursion depth cap reached "
            f"({current_depth}/{MAX_SUBAGENT_DEPTH}). The current chain is "
            f"already nested too deep. This guard prevents runaway spawn "
            f"chains. Either complete the task in this chain OR escalate "
            f"to John via notify_john if you need deeper delegation."
        )

    parent_conv_id: str | None = None
    try:
        from core import tool_guards
        parent_conv_id = tool_guards.current_conv_id()
    except Exception:  # noqa: BLE001
        pass

    sub_conv_id = _next_subagent_conv_id(parent_conv_id)

    if context.strip():
        sub_message = f"[CONTEXT]\n{context.strip()}\n\n[TASK]\n{task.strip()}"
    else:
        sub_message = task.strip()

    log.info(
        "delegate_subagent SPAWN parent=%s sub=%s depth=%d task_chars=%d",
        parent_conv_id, sub_conv_id, current_depth + 1, len(sub_message),
    )

    token = _subagent_depth.set(current_depth + 1)
    try:
        from core.agent import respond as agent_respond
        result = agent_respond(sub_message, conversation_id=sub_conv_id)
    except Exception as e:  # noqa: BLE001
        log.exception("delegate_subagent FAILED parent=%s sub=%s: %s",
                      parent_conv_id, sub_conv_id, e)
        _subagent_depth.reset(token)
        return (
            f"[error:internal] sub-agent {sub_conv_id} raised "
            f"{type(e).__name__}: {e}. Treat as if the sub-agent returned "
            f"nothing useful; consider an alternative approach."
        )
    finally:
        _subagent_depth.reset(token)

    if len(result) > 8000:
        head = result[:3000]
        tail = result[-5000:]
        result = (
            f"{head}\n\n"
            f"...[+{len(result) - 8000:,} chars truncated from middle of "
            f"sub-agent reply — head and tail preserved]...\n\n"
            f"{tail}"
        )

    log.info(
        "delegate_subagent RETURN parent=%s sub=%s depth=%d result_chars=%d",
        parent_conv_id, sub_conv_id, current_depth + 1, len(result),
    )

    return f"[sub-agent {sub_conv_id} reply]\n{result}"
