"""Deterministic guards that prevent Charles from re-trying things he's
already tried, re-reading files he just read, or using exec_shell as a
memory-query tool.

Built 2026-05-09 evening after a 500-turn forensic showed Charles:
  - re-reading the same source file 55 times in one goal,
  - retrying ResearchGate "Access denied" pages 48 times,
  - running 167 sqlite3 queries against his own memory.db via exec_shell,
  - emitting the same `[BLOCKED]` browse_url 13× across ticks.

Qwen's tool-call format is fine. The model is fine. The dispatcher just
had no enforcement of "don't repeat what already failed." This module
adds that enforcement, deterministically, without re-training anything.

State model:
  • _BLOCKED_URLS — per conv_id, set of URLs that returned a blocked-page
    signal. Persists across `respond()` calls (ticks) so a goal that
    spans dozens of ticks doesn't re-try the same dead URLs.
  • _IN_FLIGHT — per `respond()` call, set of (tool_name, args_signature)
    tuples seen so far. Reset at the start of each respond. Catches the
    "blast 8 browse_urls in one turn, then blast same 8 again" pattern.
  • _RECENT_READS — per `respond()` call, dict of file_path → content_hash
    so re-reads of the same file in the same chain return a short signal
    instead of re-dumping the file.

The guards are applied by `core/tools.dispatch()` before invoking the
handler. They short-circuit with `[error] ...` strings the model will
read in its next round.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import re
from collections import defaultdict
from typing import Any

log = logging.getLogger("charles.tool_guards")

# ---------------------------------------------------------------------------
# Per-conversation state (persists across respond() calls within one process)
# ---------------------------------------------------------------------------

# conv_id → set of blocked URLs. Bounded by python's natural memory; if it
# grows unbounded for a single conv, that conv has its own bigger problems
# (the watchdog will trim repeating replies / cancel the goal).
_BLOCKED_URLS: dict[str, dict[str, str]] = defaultdict(dict)  # conv → {url: reason}

# ---------------------------------------------------------------------------
# Per-respond() state (reset every call). Lives in a contextvar so concurrent
# respond() calls (different conv_ids served in parallel) don't trample each
# other's in-flight tracking.
# ---------------------------------------------------------------------------

_in_flight: contextvars.ContextVar[set[str] | None] = contextvars.ContextVar(
    "tool_guards_in_flight", default=None,
)
_recent_reads: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    "tool_guards_recent_reads", default=None,
)
_current_conv: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tool_guards_current_conv", default=None,
)


def respond_started(conv_id: str | None) -> None:
    """Called by agent.respond() at the start of every call."""
    _in_flight.set(set())
    _recent_reads.set({})
    _current_conv.set(conv_id)


def respond_finished() -> None:
    """Called by agent.respond() in its finally block."""
    _in_flight.set(None)
    _recent_reads.set(None)
    _current_conv.set(None)


def current_conv_id() -> str | None:
    return _current_conv.get()


# ---------------------------------------------------------------------------
# Tool-call signature (used for both in-flight dedup and blocked-URL lookup)
# ---------------------------------------------------------------------------

def _signature(name: str, args: dict[str, Any]) -> str:
    """Stable hashable signature of (tool_name, args). Sorted keys so arg
    re-orderings don't fool the dedup."""
    try:
        return name + "|" + json.dumps(args, sort_keys=True, default=str)[:400]
    except Exception:  # noqa: BLE001
        return name + "|" + repr(sorted(args.items()))[:400]


# ---------------------------------------------------------------------------
# Pre-call guards: return an [error] string to short-circuit, or None to proceed
# ---------------------------------------------------------------------------

# exec_shell + sqlite3 against the agent's own memory.db is never the right
# tool — Charles has `recall()` and `search_facts()` for that. Detect and
# redirect.
_OWN_DB_PATTERN = re.compile(
    r"sqlite3\b.*?\bmemory\.db\b",
    re.IGNORECASE | re.DOTALL,
)


def check_pre_call(name: str, args: dict[str, Any]) -> str | None:
    """Return a short-circuit error string, or None to let the call proceed."""

    # 1) Self-querying memory via shell — redirect.
    if name == "exec_shell":
        cmd = (args.get("command") or "")
        if _OWN_DB_PATTERN.search(cmd):
            return (
                "[error] this is your own memory database. NEVER query "
                "workspace/memory.db via shell — it's slow, error-prone, and "
                "the schema can change. Use the dedicated tools instead:\n"
                "  - recall(query='...') for fact lookups\n"
                "  - search_facts(query='...') for keyword search across facts\n"
                "  - list_goals() / append_goal_note() for goal state\n"
                "Re-emit your tool_call with one of those instead of sqlite3."
            )

    # 2) URL block-list (browse_url, browser_screenshot).
    conv_id = current_conv_id()
    if conv_id and name in ("browse_url", "browser_screenshot"):
        url = (args.get("url") or "").strip()
        if url:
            blocked = _BLOCKED_URLS.get(conv_id, {})
            reason = blocked.get(url)
            if reason:
                return (
                    f"[error] you already tried this URL earlier in this "
                    f"conversation and it failed: reason={reason}, url={url}. "
                    f"Move on — pick a different source or skip this item. "
                    f"Do NOT retry it; the result will be the same."
                )

    # 3) In-flight duplicate (same tool + same args within ONE respond chain).
    in_flight = _in_flight.get()
    if in_flight is not None:
        sig = _signature(name, args)
        if sig in in_flight:
            return (
                f"[error] you already called {name}() with these exact "
                f"arguments earlier in this same response chain. Calling it "
                f"twice in one round won't change the result. Use the result "
                f"you already have, or call a different tool."
            )
        # Will mark this signature as seen AFTER pre-checks pass — see mark_in_flight().

    # 4) read_file de-dup within a respond chain — return cached content
    #    fingerprint instead of the full file.
    if name == "read_file":
        path = (args.get("path") or "").strip()
        recent = _recent_reads.get()
        if path and recent is not None and path in recent:
            cached_hash = recent[path]
            return (
                f"[cached read_file] you read {path!r} earlier in this same "
                f"response chain — content hash sha256={cached_hash[:12]}. "
                f"It hasn't changed since you read it 2 seconds ago. Use the "
                f"content you already have in context. If you genuinely need "
                f"to re-read because you suspect the file changed, call "
                f"exec_shell with `stat {path!r}` first to verify the mtime."
            )

    return None


def mark_in_flight(name: str, args: dict[str, Any]) -> None:
    """Record a successful pre-check pass so the next call with same sig short-circuits."""
    in_flight = _in_flight.get()
    if in_flight is not None:
        in_flight.add(_signature(name, args))


# ---------------------------------------------------------------------------
# Post-call hooks: read tool results and update the block-lists / cache
# ---------------------------------------------------------------------------

# When browse_url returns a "page is blocked / dead" result, we want to record
# the URL so future calls short-circuit. The browse_url tool itself emits a
# structured `[BLOCKED reason=... url=...]` header (see tools/browser.py) that
# we parse here. Falls back to substring matching for results from older
# code paths.
_BLOCKED_HEADER_RE = re.compile(
    r"\[BLOCKED\s+reason=([a-z_0-9]+)\s+url=(\S+?)\]",
    re.IGNORECASE,
)
_LEGACY_BLOCK_PHRASES = (
    ("Access denied", "access_denied"),
    ("Access Denied", "access_denied"),
    ("Forbidden", "forbidden"),
    ("Just a moment", "cloudflare_block"),
    ("Temporarily Unavailable", "site_unavailable"),
    ("Page not found", "404"),
    ("Page Not Found", "404"),
    ("404 Error", "404"),
    ("403 ERROR", "forbidden"),
    ("Sorry, the page you requested was not found", "404"),
    ("File Not Found", "404"),
)


def _classify_legacy_blocked(result: str) -> str | None:
    """Best-effort: scan the raw page text for known block-page phrases."""
    snippet = result[:1500]  # only the head matters
    for phrase, reason in _LEGACY_BLOCK_PHRASES:
        if phrase in snippet:
            return reason
    return None


def post_call(name: str, args: dict[str, Any], result: str) -> None:
    """Update guards' state from the tool's result. Never raises."""
    try:
        conv_id = current_conv_id()

        # Update URL block-list from browse_url / browser_screenshot results.
        if conv_id and name in ("browse_url", "browser_screenshot"):
            url = (args.get("url") or "").strip()
            if url:
                m = _BLOCKED_HEADER_RE.search(result[:300])
                if m:
                    reason = m.group(1).lower()
                    _BLOCKED_URLS[conv_id][url] = reason
                    log.info("URL blocked for conv=%s: %s (%s)", conv_id, url, reason)
                else:
                    legacy_reason = _classify_legacy_blocked(result)
                    if legacy_reason:
                        _BLOCKED_URLS[conv_id][url] = legacy_reason
                        log.info(
                            "URL legacy-blocked for conv=%s: %s (%s)",
                            conv_id, url, legacy_reason,
                        )

        # Cache successful read_file by path (only if it didn't error).
        if name == "read_file":
            path = (args.get("path") or "").strip()
            recent = _recent_reads.get()
            if path and recent is not None and not result.startswith("[error]") and not result.startswith("[cached"):
                recent[path] = hashlib.sha256(result.encode("utf-8", errors="replace")).hexdigest()
    except Exception as e:  # noqa: BLE001 — guards must never break the dispatcher
        log.warning("post_call hook failed for %s: %s", name, e)


# ---------------------------------------------------------------------------
# Inspection / debug helpers (for tests + watchdog visibility)
# ---------------------------------------------------------------------------

def blocked_urls_for(conv_id: str) -> dict[str, str]:
    """Return a copy of {url: reason} for a conv (empty dict if none)."""
    return dict(_BLOCKED_URLS.get(conv_id, {}))


def clear_blocked_urls(conv_id: str) -> int:
    """Drop the block-list for a conv (e.g. on reset_conversation)."""
    n = len(_BLOCKED_URLS.get(conv_id, {}))
    _BLOCKED_URLS.pop(conv_id, None)
    return n


def reset_all() -> None:
    """For tests."""
    _BLOCKED_URLS.clear()
    _in_flight.set(None)
    _recent_reads.set(None)
    _current_conv.set(None)
