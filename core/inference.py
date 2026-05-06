"""MLX-LM client. Thinking mode is disabled at the chokepoint — never inline."""
from __future__ import annotations

from typing import Any

from openai import OpenAI

from config import MLX_BASE_URL, MLX_MODEL

_client = OpenAI(base_url=MLX_BASE_URL, api_key="not-needed")


def complete(
    messages: list[dict],
    *,
    max_tokens: int = 800,
    temperature: float = 0.7,
    tools: list[dict] | None = None,
) -> tuple[str, Any, dict]:
    """Send chat-completions to MLX-LM. Returns (text, message, usage_dict)."""
    kwargs: dict[str, Any] = {
        "model": MLX_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
    }
    if tools:
        kwargs["tools"] = tools

    resp = _client.chat.completions.create(**kwargs)
    msg = resp.choices[0].message
    text = (msg.content or "").strip()
    usage = resp.usage.model_dump() if resp.usage else {}
    return text, msg, usage
