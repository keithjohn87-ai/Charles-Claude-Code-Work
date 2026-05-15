"""MLX-LM client. Per-channel thinking mode for the 2026-05-12 reliability bet.

Qwen3-class models support a chain-of-thought "thinking" mode via the
chat-template flag `enable_thinking`. When on, the model produces an
internal reasoning trace in `message.reasoning` before emitting the
final `message.content`. The reasoning is ~5-10× the token count of
the answer and adds latency, but it dramatically improves multi-step
reasoning — including the failure mode John keeps hitting where
Charles claims past-tense action without emitting the tool_call.

Policy (per-channel, set by caller):

  thinking=True   — autonomous channels (CHARLES_LOG, CLAUDE_CODE) and
                    goal-tick respond chains. Latency doesn't matter;
                    reliability does.
  thinking=False  — relational channel (JOHN_CHARLES). John waits on the
                    reply; snappy beats thorough for "are you awake".

The reasoning output is drained from `message.reasoning` and logged for
observability but NOT included in `text` (callers expect the final
answer there). The model's content path is unchanged: text returns the
same string shape whether thinking was on or off.
"""
from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from config import MLX_BASE_URL, MLX_MODEL

log = logging.getLogger("charles.inference")

_client = OpenAI(base_url=MLX_BASE_URL, api_key="not-needed")


def complete(
    messages: list[dict],
    *,
    max_tokens: int = 800,
    temperature: float = 0.7,
    tools: list[dict] | None = None,
    thinking: bool = False,
) -> tuple[str, Any, dict]:
    """Send chat-completions to MLX-LM. Returns (text, message, usage_dict).

    thinking: when True, sends `chat_template_kwargs.enable_thinking=True`
              to MLX. Model emits reasoning trace in `message.reasoning`
              before the final `content`. Caller should pass True for
              autonomous / reliability-sensitive paths and False for
              snappy relational replies. Default False to preserve
              prior behavior — callers must opt in.
    """
    kwargs: dict[str, Any] = {
        "model": MLX_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": thinking}},
    }
    if tools:
        kwargs["tools"] = tools

    resp = _client.chat.completions.create(**kwargs)
    msg = resp.choices[0].message
    text = (msg.content or "").strip()
    usage = resp.usage.model_dump() if resp.usage else {}

    # Drain + log the reasoning trace if thinking was on. Useful for
    # post-mortem ("did the model actually think through the tool call?")
    # and for measuring the latency / token cost of the experiment.
    if thinking:
        reasoning = getattr(msg, "reasoning", None)
        if reasoning:
            r_len = len(reasoning)
            log.info(
                "thinking=on reasoning_chars=%d content_chars=%d tokens=%s",
                r_len, len(text), usage.get("completion_tokens", "?"),
            )
            # Stash on usage dict so callers can inspect/log it without
            # changing the return tuple shape.
            usage["_reasoning_chars"] = r_len

    return text, msg, usage
