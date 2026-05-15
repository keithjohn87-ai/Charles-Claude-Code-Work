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
        # Help Charles find the right path next try — show what's actually
        # in the parent directory + suggest closest matches. Cuts the
        # 7+ "no such file" loops where Charles invents paths.
        return _path_not_found_with_suggestions(p)
    if not p.is_file():
        return f"[error] not a file: {p}"
    data = p.read_text(errors="replace")
    if len(data) > _READ_CAP:
        return data[:_READ_CAP] + f"\n... [truncated, file is {len(data)} chars total]"
    return data


def _path_not_found_with_suggestions(missing: Path) -> str:
    """Return an error that includes a directory listing + closest-match hints."""
    import difflib
    parent = missing.parent
    out = [f"[error] no such file: {missing}"]
    # Walk up until we find a parent that DOES exist
    walked_up = False
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
        walked_up = True
    if walked_up:
        out.append(f"  (closest existing parent: {parent})")
    if parent.exists() and parent.is_dir():
        try:
            entries = sorted(p.name for p in parent.iterdir())
        except PermissionError:
            entries = []
        if entries:
            close = difflib.get_close_matches(missing.name, entries, n=3, cutoff=0.4)
            if close:
                out.append(f"  Did you mean: {', '.join(repr(c) for c in close)}?")
            shown = entries[:20]
            out.append(f"  Files in {parent}:")
            for e in shown:
                out.append(f"    - {e}")
            if len(entries) > 20:
                out.append(f"    …and {len(entries) - 20} more")
    return "\n".join(out)


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
