"""System prompt builder. Lean default, target ~500 tokens."""
from __future__ import annotations

from config import WORKSPACE
from core.tools import summary_block

_DEFAULT_IDENTITY = """\
You are Charles — an autonomous AI agent running locally on Johnathon Keith's Mac Studio.
Speak directly. No hedging. No patronizing. Technical depth is welcome.
You are Johnathon's partner in his construction-industry work and his AI buildout.
Keep replies tight unless he asks for detail."""


def build_system_prompt() -> str:
    soul_path = WORKSPACE / "SOUL.md"
    identity_path = WORKSPACE / "IDENTITY.md"

    soul = soul_path.read_text().strip() if soul_path.exists() else ""
    identity = identity_path.read_text().strip() if identity_path.exists() else ""

    if soul and identity:
        base = f"{soul}\n\n{identity}"
    elif soul:
        base = soul
    elif identity:
        base = identity
    else:
        base = _DEFAULT_IDENTITY

    tools_block = summary_block()
    if tools_block:
        base = f"{base}\n\n{tools_block}"
    return base
