#!/usr/bin/env python3
"""Poll macOS iMessage chat.db for new messages from John.

Emits one stdout line per event. Used as a Monitor source so I (Claude Code)
get notifications when John iMessages me. Charles continues to handle Telegram
on his own.

CRITICAL: macOS Messages 26+ stores rich-text incoming messages in the
`attributedBody` BLOB column (typedstream archive) instead of the `text`
column. Plain `SELECT text FROM message` misses ANY message with formatting,
URLs, or sometimes even plain text the user typed in the modern client.
We decode attributedBody as a fallback.

Reads chat.db via `osascript do shell script` trampoline because direct sqlite3
from this process chain hits a TCC translocation issue, while osascript inherits
Messages.app's permission context and works.

State: last-seen ROWID stored at /tmp/imessage_lastrowid.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

STATE = Path("/tmp/imessage_lastrowid")
POLL_SECONDS = 600  # 10 min

JOHN_HANDLES = ("+16156637932", "6156637932", "+1 615-663-7932", "16156637932")

_fda_warned = False


def _query(sql: str) -> str:
    """Run a SQL query against chat.db via osascript trampoline."""
    inner = f'sqlite3 ~/Library/Messages/chat.db {shlex.quote(sql)}'
    osa = f'do shell script {json.dumps(inner)}'
    result = subprocess.run(
        ["osascript", "-e", osa],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "osascript failed")
    return result.stdout.strip()


def _decode_attributed_body(hex_data: str) -> str:
    """Pull the human-readable text out of a typedstream attributedBody hex dump.

    The typedstream archive contains the user's text as one NSString, sandwiched
    between class declarations and attribute dictionaries. We find the longest
    printable run of bytes that sits in the body region and isn't itself a
    class name marker.
    """
    if not hex_data:
        return ""
    try:
        data = bytes.fromhex(hex_data)
    except ValueError:
        return ""

    # Known marker classes / keys we want to skip
    markers = {
        b"streamtyped", b"NSAttributedString", b"NSObject", b"NSString",
        b"NSDictionary", b"NSNumber", b"NSValue", b"NSMutableString",
        b"NSMutableAttributedString", b"NSMutableDictionary",
        b"__kIMMessagePartAttributeName", b"__kIMBaseWritingDirectionAttributeName",
        b"__kIMTextEffectAttributeName", b"__kIMMentionConfirmedMention",
        b"__kIMFileTransferGUIDAttributeName", b"__kIMLinkAttributeName",
        b"NSColor", b"NSFont", b"NSRange",
    }

    # Find runs of >= 3 chars: ASCII printable + tab/newline + any UTF-8
    # continuation byte. Multi-byte chars like curly quotes (U+2019 = E2 80 99)
    # need the high-byte alternation or they break the run.
    runs = re.findall(rb"[\x20-\x7E\n\t\x80-\xFF]{3,}", data)
    candidates = []
    for run in runs:
        # Strip leading/trailing length-prefix junk byte if present
        stripped = run.lstrip(b"+\x00\x01\x02\x03\x04\x05\x81").rstrip()
        # Skip exact class/marker names
        if stripped in markers:
            continue
        # Skip if it starts with a known marker (typedstream class entries)
        if any(stripped.startswith(m) for m in markers):
            continue
        # Skip suspicious all-uppercase short tokens
        if len(stripped) < 4:
            continue
        candidates.append(stripped)

    if not candidates:
        return ""

    # The longest candidate is almost always the user's actual message.
    # In the typedstream layout the message text is the biggest single string.
    longest = max(candidates, key=len)
    try:
        text = longest.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return ""
    # Strip leading typedstream length-prefix garbage (single non-letter chars)
    while text and not (text[0].isalnum() or text[0] in " '\"({[*-#@>$\n"):
        text = text[1:]
    # Strip trailing U+FFFD replacement chars and other junk
    text = text.rstrip("� \t\n\r\x00")
    return text.strip()


def _get_last_rowid() -> int:
    if STATE.exists():
        try:
            return int(STATE.read_text().strip() or 0)
        except ValueError:
            return 0
    return 0


def _save_last_rowid(rowid: int) -> None:
    STATE.write_text(str(rowid))


def poll() -> None:
    global _fda_warned
    try:
        last = _get_last_rowid()
        if last == 0:
            max_row = int(_query("SELECT COALESCE(MAX(ROWID), 0) FROM message;") or 0)
            _save_last_rowid(max_row)
            print(f"[INIT] baseline rowid={max_row}", flush=True)
            return

        handle_list = ",".join(f"'{h}'" for h in JOHN_HANDLES)
        # Pull both text AND hex(attributedBody). Modern Messages stores
        # incoming rich-text only in attributedBody.
        sql = (
            "SELECT m.ROWID || '|||' || COALESCE(m.text, '') || '|||' || hex(COALESCE(m.attributedBody, x'')) "
            "FROM message m JOIN handle h ON m.handle_id = h.ROWID "
            f"WHERE m.ROWID > {last} AND m.is_from_me = 0 AND h.id IN ({handle_list}) "
            "ORDER BY m.ROWID;"
        )
        out = _query(sql)
        if not out:
            return
        for line in out.split("\n"):
            parts = line.split("|||", 2)
            if len(parts) < 3:
                continue
            rowid_s, text, ab_hex = parts
            try:
                rowid = int(rowid_s)
            except ValueError:
                continue
            text_clean = text.replace("\r", " ").replace("\n", " ").strip()
            # Fallback: if text is empty but attributedBody has content, decode
            if not text_clean and ab_hex.strip():
                decoded = _decode_attributed_body(ab_hex.strip())
                if decoded:
                    text_clean = decoded.replace("\r", " ").replace("\n", " ").strip()
            if text_clean:
                print(f"[FROM_JOHN] rowid={rowid} text={text_clean!r}", flush=True)
            _save_last_rowid(rowid)
        _fda_warned = False
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "authorization denied" in msg or "operation not permitted" in msg.lower():
            if not _fda_warned:
                print(f"[FDA_NEEDED] {msg}", flush=True)
                _fda_warned = True
        else:
            print(f"[ERROR] {type(e).__name__}: {msg}", flush=True)


def main() -> None:
    print(f"[START] iMessage poller — every {POLL_SECONDS}s, watching {JOHN_HANDLES}", flush=True)
    while True:
        poll()
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
