"""Single-conversation reasoning with multi-round tool calls.

M1: tools available. The classifier picks 0-3 tools per inbound user message
and only those tools' full JSON schemas are sent to the model. The
multi-round loop keeps going until the model stops emitting tool_calls or
the iteration cap is hit.
"""
from __future__ import annotations

import logging

import tools  # noqa: F401  — import side-effect: registers all tools

from core.inference import complete
from core.prompts import build_system_prompt
from core.tools import dispatch, select_tools

log = logging.getLogger("charles.agent")

MAX_TOOL_ROUNDS = 5


def respond(message: str, conversation_id: str | None = None) -> str:
    system = build_system_prompt()
    history: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": message},
    ]

    selected = select_tools(message)
    api_tools = [t.openai_schema() for t in selected] if selected else None

    total_chars = sum(len(m.get("content") or "") for m in history)
    log.info(
        "respond start: prompt_chars=%d tools=%s",
        total_chars,
        [t.name for t in selected] or "none",
    )

    final_text = ""
    for round_n in range(MAX_TOOL_ROUNDS):
        text, msg, usage = complete(history, tools=api_tools, max_tokens=800)
        log.info("round=%d usage=%s tool_calls=%d", round_n, usage, len(msg.tool_calls or []))

        if not msg.tool_calls:
            final_text = text
            break

        history.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            result = dispatch(tc.function.name, tc.function.arguments)
            log.info("tool=%s args=%r result_chars=%d", tc.function.name, tc.function.arguments[:200], len(result))
            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
    else:
        final_text = text or "(max tool rounds reached)"

    return final_text
