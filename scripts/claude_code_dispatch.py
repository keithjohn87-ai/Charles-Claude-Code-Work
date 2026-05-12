"""Dispatch a builder dev-note from Claude Code → Charles.

Usage:
    python scripts/claude_code_dispatch.py "your message here"
    echo "long body" | python scripts/claude_code_dispatch.py -
    python scripts/claude_code_dispatch.py --file path/to/note.md

This is NOT a Charles-callable @tool — it's a CLI entry point for the harness
(Claude Code) to leave Charles dev-notes that he'll pick up on his next
heartbeat poll (~60s, see core/heartbeat._poll_claude_code). The note is
written as a `user`-role turn to conv_id='claude_code' in memory.db; the
heartbeat dispatches each unread turn through agent.respond.

It lives in scripts/ rather than tools/ because tools/__init__.py eagerly
imports every @tool module at package-load time, which means a misnamed
branch could break the import. scripts/ stays cheap.

Why a separate channel: builder notes are technical (file paths, diffs,
reasoning about Charles's own code). Routing them through JOHN_CHARLES would
pollute John's relational thread with implementation detail and burn voice
synthesis on text he doesn't need to hear. Routing them through CHARLES_LOG
would mix them with Charles's own autonomous tick narration. They get their
own conv_id.

Exit codes:
    0 — note appended successfully
    1 — usage / read error
    2 — write error (DB locked, etc.)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# When invoked as `python scripts/claude_code_dispatch.py`, sys.path[0] is
# scripts/, not the project root — `from core import ...` would fail. Insert
# the project root so the imports resolve.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core import channels, memory  # noqa: E402


def _read_body(args: argparse.Namespace) -> str:
    if args.file:
        with open(args.file, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    if args.message == "-":
        return sys.stdin.read().strip()
    if args.message:
        return args.message.strip()
    raise SystemExit("error: provide a message, --file, or '-' for stdin")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="claude_code_dispatch",
        description="Append a builder dev-note to Charles's CLAUDE_CODE channel.",
    )
    parser.add_argument(
        "message",
        nargs="?",
        help="The note body. Use '-' to read from stdin.",
    )
    parser.add_argument(
        "--file",
        help="Read the note body from a file instead of argv/stdin.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the confirmation print on success.",
    )
    args = parser.parse_args()

    try:
        body = _read_body(args)
    except (FileNotFoundError, OSError) as e:
        print(f"read error: {e}", file=sys.stderr)
        return 1

    if not body:
        print("error: empty note body", file=sys.stderr)
        return 1

    try:
        memory.log_turn(channels.CLAUDE_CODE, "user", body)
    except Exception as e:  # noqa: BLE001
        print(f"db error: {e}", file=sys.stderr)
        return 2

    if not args.quiet:
        preview = body.replace("\n", " ")[:80]
        print(f"dispatched to claude_code channel: {preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
