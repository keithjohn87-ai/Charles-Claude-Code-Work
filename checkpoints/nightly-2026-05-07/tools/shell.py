"""Shell exec. Full power, no allowlist, no confirmation gate (YOLO mode)."""
from __future__ import annotations

import subprocess

from core.tools import tool

_OUTPUT_CAP = 8_000  # chars; truncate huge outputs so replies stay legible


@tool(
    name="exec_shell",
    summary="Run a shell command (zsh on macOS) and return stdout/stderr and exit code.",
    triggers=(
        "run", "execute", "exec", "command", "shell", "ls", "list", "find",
        "grep", "ps", "kill", "npm", "pip", "brew", "git", "mkdir", "rm",
        "mv", "cp", "curl", "what files", "what's in /",
    ),
    schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to run via /bin/zsh -c."},
            "timeout": {"type": "number", "description": "Max seconds before killing the command.", "default": 60},
        },
        "required": ["command"],
    },
)
def exec_shell(command: str, timeout: float = 60) -> str:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            executable="/bin/zsh",
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"[error] timed out after {timeout}s: {command!r}"

    parts = [f"exit={proc.returncode}"]
    if proc.stdout:
        parts.append("[stdout]\n" + proc.stdout.rstrip())
    if proc.stderr:
        parts.append("[stderr]\n" + proc.stderr.rstrip())
    out = "\n".join(parts)
    if len(out) > _OUTPUT_CAP:
        out = out[:_OUTPUT_CAP] + f"\n... [truncated, full output was {len(out)} chars]"
    return out
