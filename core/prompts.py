"""System prompt builder. Lean default, target ~500 tokens."""
from __future__ import annotations

from config import WORKSPACE

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

    if soul:
        return soul if not identity else f"{soul}\n\n{identity}"
    if identity:
        return identity
    return _DEFAULT_IDENTITY
