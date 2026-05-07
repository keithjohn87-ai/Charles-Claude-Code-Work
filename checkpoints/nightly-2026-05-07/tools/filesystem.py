"""File read / write tools. No sandboxing — Charles has full filesystem access."""
from __future__ import annotations

from pathlib import Path

from core.tools import tool

_READ_CAP = 64_000  # chars; truncate huge files to keep replies sane


@tool(
    name="read_file",
    summary="Read a UTF-8 text file from disk and return its contents.",
    triggers=("read", "cat", "open", "view", "show", "contents", "look at", "what's in"),
    schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or ~-expanded file path."},
        },
        "required": ["path"],
    },
)
def read_file(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"[error] no such file: {p}"
    if not p.is_file():
        return f"[error] not a file: {p}"
    data = p.read_text(errors="replace")
    if len(data) > _READ_CAP:
        return data[:_READ_CAP] + f"\n... [truncated, file is {len(data)} chars total]"
    return data


@tool(
    name="write_file",
    summary="Write text to a file. Creates parent directories. Overwrites by default.",
    triggers=("write", "save", "create file", "put", "dump", "overwrite"),
    schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute or ~-expanded file path."},
            "content": {"type": "string", "description": "Full file contents to write."},
            "append": {"type": "boolean", "description": "Append instead of overwrite.", "default": False},
        },
        "required": ["path", "content"],
    },
)
def write_file(path: str, content: str, append: bool = False) -> str:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with p.open(mode, encoding="utf-8") as f:
        f.write(content)
    return f"wrote {len(content)} chars to {p} ({'append' if append else 'overwrite'})"
