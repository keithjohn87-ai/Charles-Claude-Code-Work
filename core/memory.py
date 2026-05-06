"""SQLite-backed memory.

Three tables, one file at workspace/memory.db:

  conversations      append-only log of (conversation_id, role, content). Used to
                     replay recent context into the prompt on each turn so Charles
                     stays continuous across Telegram messages.

  long_term_facts    facts Charles chooses to remember (name, place, decision,
                     habit). Added via the `remember` tool, queried via `recall`.
                     NOT auto-injected into every prompt — pulled on demand.

  daily_log          structured event log (kind, text). Used for daily summaries
                     and audits. Charles can query today's entries via tools.

Memory is QUERIED into prompts on demand, never dumped wholesale.
"""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from config import WORKSPACE

DB_PATH = WORKSPACE / "memory.db"

log = logging.getLogger("charles.memory")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT    NOT NULL,
    role            TEXT    NOT NULL,
    content         TEXT    NOT NULL,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_conversations_cid ON conversations(conversation_id, id);

CREATE TABLE IF NOT EXISTS long_term_facts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    fact         TEXT    NOT NULL,
    tags         TEXT    NOT NULL DEFAULT '',
    created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_used_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_facts_tags ON long_term_facts(tags);

CREATE TABLE IF NOT EXISTS daily_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_daily_log_created ON daily_log(created_at);
"""


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    with _conn() as c:
        c.executescript(_SCHEMA)


# ---------------- Conversations ----------------


def log_turn(conversation_id: str, role: str, content: str) -> None:
    """Persist one user/assistant message to the conversation log + daily log."""
    if not content.strip():
        return
    with _conn() as c:
        c.execute(
            "INSERT INTO conversations (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content),
        )
        c.execute(
            "INSERT INTO daily_log (kind, text) VALUES (?, ?)",
            (f"turn:{role}", f"[{conversation_id}] {content[:500]}"),
        )


def recent_history(conversation_id: str, max_chars: int = 4000, max_turns: int = 50) -> list[dict]:
    """Return the most recent turns (oldest first), trimmed to a char budget."""
    with _conn() as c:
        rows = c.execute(
            "SELECT role, content FROM conversations "
            "WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
            (conversation_id, max_turns),
        ).fetchall()

    out: list[dict] = []
    total = 0
    for r in rows:  # newest first
        size = len(r["content"])
        if total + size > max_chars:
            break
        out.append({"role": r["role"], "content": r["content"]})
        total += size
    out.reverse()
    return out


# ---------------- Long-term facts ----------------


def add_fact(fact: str, tags: str = "") -> int:
    fact = fact.strip()
    if not fact:
        raise ValueError("empty fact")
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO long_term_facts (fact, tags) VALUES (?, ?)",
            (fact, tags.strip()),
        )
        c.execute(
            "INSERT INTO daily_log (kind, text) VALUES (?, ?)",
            ("remembered", fact[:500]),
        )
        return cur.lastrowid or 0


def search_facts(query: str, limit: int = 5) -> list[dict]:
    """Substring search over fact text and tags. Newest first on ties."""
    q = f"%{query.strip()}%"
    with _conn() as c:
        rows = c.execute(
            "SELECT id, fact, tags, created_at FROM long_term_facts "
            "WHERE fact LIKE ? OR tags LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (q, q, limit),
        ).fetchall()
        if rows:
            ids = ",".join(str(r["id"]) for r in rows)
            c.execute(
                f"UPDATE long_term_facts SET last_used_at = strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                f"WHERE id IN ({ids})"
            )
    return [dict(r) for r in rows]


def all_facts(limit: int = 50) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, fact, tags, created_at FROM long_term_facts "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------- Daily log ----------------


def log_event(kind: str, text: str) -> None:
    with _conn() as c:
        c.execute("INSERT INTO daily_log (kind, text) VALUES (?, ?)", (kind, text))


def daily_log_for(date_iso: str | None = None) -> list[dict]:
    """All entries for a UTC date (YYYY-MM-DD). Defaults to today UTC."""
    if date_iso is None:
        date_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _conn() as c:
        rows = c.execute(
            "SELECT id, kind, text, created_at FROM daily_log "
            "WHERE substr(created_at, 1, 10) = ? "
            "ORDER BY id ASC",
            (date_iso,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------- Lifecycle ----------------

init_db()
