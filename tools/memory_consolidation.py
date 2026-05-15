"""Memory consolidation — nightly cleanup of long_term_facts.

Without consolidation, long_term_facts is append-only and gets noisy fast:
duplicate facts, stale one-off task notes, redundant entries from the same
event captured multiple times. After a few weeks, recall(query=...) starts
returning low-signal results.

The consolidator runs as a scheduled task at 04:00 EST nightly (after the
03:00 backup). On each run:

  1. Pull facts from the last N hours (default 24).
  2. Group by primary tag.
  3. For each group, find near-duplicates by content overlap.
  4. Mark duplicates with tag 'superseded' (don't delete — preserve history).
  5. Write a summary fact: 'Consolidation YYYY-MM-DD — N reviewed, M superseded'.
  6. Append a markdown line to workspace/memory/consolidation_log.md.

Charles can also call this on demand. Default is dry_run=False (real changes).
"""
from __future__ import annotations

import logging
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.tools import tool
from core import memory as _mem

log = logging.getLogger("charles.memory_consolidation")

DB_PATH = Path("/Users/home/charles/workspace/memory.db")
MEMORY_DIR = Path("/Users/home/charles/workspace/memory")
SIMILARITY_THRESHOLD = 0.65  # 65% Jaccard overlap on token sets = duplicate

# Hard cap on facts considered per single consolidation call. 2026-05-12: the
# prior implementation used difflib.SequenceMatcher in an O(N×G) grouping
# loop. With ~1800 facts in a 24h window post-CC, that pegged a CPU core for
# 5+ min while holding a write transaction — DB locked, services starved,
# CC runner thread crashed. Token-set Jaccard is O(N×G) but each comparison
# is microseconds instead of milliseconds. The cap is a defense-in-depth
# guard for runaway growth (e.g. a goal generating thousands of notes).
MAX_FACTS_PER_RUN = 2000

# Token-cache for the Jaccard pass within one consolidate call. Maps
# fact_id → frozenset of normalized tokens. Built once per fact, reused
# across O(N×G) comparisons.
_TOKEN_SPLIT = re.compile(r"[a-z0-9]+")


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH), timeout=30.0)
    con.row_factory = sqlite3.Row
    # Inherit the WAL setting (set on connect — sticky on the file, but the
    # busy_timeout is per-connection). 30s gives writers room when a long
    # transaction is in flight elsewhere.
    con.execute("PRAGMA busy_timeout=30000")
    return con


def _primary_tag(tags: str) -> str:
    """First non-trivial tag is the primary classifier."""
    parts = [t.strip() for t in (tags or "").split(",") if t.strip()]
    # Skip generic noise tags
    skip = {"reference", "priority", "fact"}
    for p in parts:
        if p.lower() not in skip and ":" not in p:
            return p
    return parts[0] if parts else "untagged"


def _tokens(s: str) -> frozenset[str]:
    """Lowercase, strip non-alphanumeric, return frozenset of tokens.
    Truncates to first 500 chars before tokenizing — most duplicate signal
    is in the opening of the fact, and capping bounds the comparison cost.
    """
    if not s:
        return frozenset()
    return frozenset(_TOKEN_SPLIT.findall(s[:500].lower()))


def _similar(a_tokens: frozenset[str], b_tokens: frozenset[str]) -> float:
    """Jaccard similarity on pre-computed token sets. O(min(|a|, |b|)).

    Was difflib.SequenceMatcher.ratio() before 2026-05-12 — that was
    O(min(|a|, |b|)²) per call and tanked the watchdog. Jaccard is
    looser (treats word order / phrasing as equivalent) but that's
    actually CLOSER to what consolidation wants: catch "same content,
    minor formatting drift" without burning cycles.
    """
    if not a_tokens or not b_tokens:
        return 0.0
    intersect = len(a_tokens & b_tokens)
    if not intersect:
        return 0.0
    union = len(a_tokens | b_tokens)
    return intersect / union


def _pick_canonical(group: list[sqlite3.Row]) -> tuple[int, list[int]]:
    """Pick which fact in the dup group to keep. Heuristic: longest content,
    most recent created_at as tiebreaker. Returns (keep_id, supersede_ids)."""
    if len(group) == 1:
        return group[0]["id"], []
    sorted_rows = sorted(
        group,
        key=lambda r: (-len(r["fact"] or ""), r["created_at"] or ""),
    )
    keep = sorted_rows[0]
    supersede = [r["id"] for r in sorted_rows[1:] if r["id"] != keep["id"]]
    return keep["id"], supersede


@tool(
    name="consolidate_memory",
    summary=(
        "Review long_term_facts saved in the last N hours, find near-duplicates, mark them "
        "superseded (NOT deleted — preserved with a tag), write a daily summary. "
        "Defaults: 24h window, real run. Run nightly via scheduled task; run manually any time "
        "the fact store feels noisy."
    ),
    triggers=("consolidate memory", "clean up facts", "deduplicate facts", "memory cleanup"),
    schema={
        "type": "object",
        "properties": {
            "window_hours": {"type": "integer", "description": "Look back N hours. Default 24.", "default": 24},
            "dry_run": {"type": "boolean", "description": "If true, don't write — just report what would happen.", "default": False},
        },
    },
)
def consolidate_memory(window_hours: int = 24, dry_run: bool = False) -> str:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")

    con = _conn()
    cur = con.cursor()
    rows = cur.execute(
        "SELECT id, fact, tags, created_at FROM long_term_facts "
        "WHERE created_at >= ? AND tags NOT LIKE '%superseded%' "
        "ORDER BY id DESC LIMIT ?",
        (cutoff, MAX_FACTS_PER_RUN),
    ).fetchall()

    if not rows:
        con.close()
        return f"(no facts in last {window_hours}h)"

    capped = len(rows) >= MAX_FACTS_PER_RUN

    # Pre-compute token sets ONCE per fact (was being re-tokenized on every
    # comparison before the 2026-05-12 fix — wasted ~95% of the wall time).
    token_cache: dict[int, frozenset[str]] = {
        r["id"]: _tokens(r["fact"]) for r in rows
    }

    # Group by primary tag
    by_tag: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for r in rows:
        by_tag[_primary_tag(r["tags"])].append(r)

    superseded_count = 0
    kept_count = 0
    by_tag_summary: list[str] = []

    for tag, facts in by_tag.items():
        # Quick prefix-bucket pass: facts whose first-60-char prefix matches
        # (case-insensitive) are auto-grouped. Catches near-exact duplicates
        # in O(N) instead of O(N×G).
        prefix_buckets: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for f in facts:
            prefix = (f["fact"] or "")[:60].lower()
            prefix_buckets[prefix].append(f)

        # Now fall through to Jaccard for facts that didn't match a prefix.
        # Each prefix bucket with len > 1 is its own group; singletons go
        # into the Jaccard pass to catch reworded duplicates.
        groups: list[list[sqlite3.Row]] = []
        singletons: list[sqlite3.Row] = []
        for _, bucket in prefix_buckets.items():
            if len(bucket) > 1:
                groups.append(bucket)
            else:
                singletons.append(bucket[0])

        # Jaccard pass over singletons only — bounded by |singletons|×|groups|
        for f in singletons:
            f_tok = token_cache[f["id"]]
            placed = False
            for g in groups:
                rep_tok = token_cache[g[0]["id"]]
                if _similar(f_tok, rep_tok) >= SIMILARITY_THRESHOLD:
                    g.append(f)
                    placed = True
                    break
            if not placed:
                groups.append([f])

        for g in groups:
            keep_id, supersede_ids = _pick_canonical(g)
            kept_count += 1
            if not supersede_ids:
                continue
            superseded_count += len(supersede_ids)
            if not dry_run:
                for sid in supersede_ids:
                    # Append 'superseded:<keep_id>' to existing tags
                    row = cur.execute("SELECT tags FROM long_term_facts WHERE id=?", (sid,)).fetchone()
                    new_tags = f"{row['tags']},superseded,superseded_by:{keep_id}" if row else f"superseded,superseded_by:{keep_id}"
                    cur.execute("UPDATE long_term_facts SET tags=? WHERE id=?", (new_tags, sid))
        by_tag_summary.append(f"  {tag}: {len(facts)} facts → {sum(1 for g in groups if len(g) > 1)} dup-groups")

    if not dry_run:
        # Save a summary fact for posterity
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        summary_text = (
            f"MEMORY CONSOLIDATION {date_str} — {len(rows)} facts reviewed in last {window_hours}h, "
            f"{kept_count} kept, {superseded_count} superseded as duplicates. "
            f"Tags: {', '.join(sorted(by_tag.keys()))}"
        )
        # Route through canonical taxonomy — daily_summary is a leaf under system_health.
        _summary_embed = None
        try:
            from core import embeddings as _embed
            _summary_embed = _embed.encode(summary_text)
        except Exception:  # noqa: BLE001
            pass
        cur.execute(
            "INSERT INTO long_term_facts (fact, tags, topic, embedding) VALUES (?, ?, ?, ?)",
            (summary_text, "consolidation,daily_summary", "daily_summary", _summary_embed),
        )
        con.commit()

        # Append to markdown log so John can scan history
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        log_path = MEMORY_DIR / "consolidation_log.md"
        with log_path.open("a") as fp:
            fp.write(f"\n## {date_str} ({datetime.now(timezone.utc).strftime('%H:%M')}Z)\n")
            fp.write(f"- Reviewed {len(rows)} facts (last {window_hours}h), kept {kept_count}, superseded {superseded_count}\n")
            for line in by_tag_summary:
                fp.write(f"  -{line}\n")

    con.close()

    out = [
        f"Memory consolidation {'(DRY RUN) ' if dry_run else ''}— last {window_hours}h:",
        f"  Reviewed: {len(rows)} facts",
        f"  Kept: {kept_count}",
        f"  Superseded: {superseded_count}",
        "",
        "By tag:",
    ]
    out.extend(by_tag_summary)
    return "\n".join(out)
