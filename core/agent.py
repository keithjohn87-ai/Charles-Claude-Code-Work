"""Single-turn reasoning. M0: no tools, just text in / text out."""
from __future__ import annotations

from core.inference import complete
from core.prompts import build_system_prompt


def respond(message: str, conversation_id: str | None = None) -> str:
    system = build_system_prompt()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": message},
    ]
    total_chars = sum(len(m["content"]) for m in messages)
    print(f"[charles] prompt_chars={total_chars}")
    text, usage = complete(messages, max_tokens=600)
    print(f"[charles] usage={usage}")
    return text
