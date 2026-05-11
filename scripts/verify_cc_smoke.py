#!/usr/bin/env python3
"""Post-CC-smoke verification — Step 3 of RAPID_FIRE_2026-05-11.md.

Run AFTER `python -m core.cc_runner --config p2_qwen36 --max-batches 2`.
Surfaces:
  1. cc_state.json contents (per-config progress + validation verdict)
  2. Topic distribution diff vs the pre-CC baseline (saved at /tmp/cc_pre.snapshot.json
     by the FIRST run of this script — second run shows what changed)
  3. Sample 10 newly-ingested facts tagged 'cc' for quality eyeball
  4. Standalone tree_validator run against current state
  5. Pre/post fact count + supersede rate per branch

Idempotent. Safe to re-run. No DB writes.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

DB = Path("/Users/home/charles/workspace/memory.db")
STATE = Path("/Users/home/charles/workspace/cc_state.json")
SNAP = Path("/tmp/cc_pre.snapshot.json")


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB))
    con.row_factory = sqlite3.Row
    return con


def _topic_distribution() -> dict[str, int]:
    with _conn() as c:
        rows = c.execute(
            "SELECT topic, COUNT(*) AS n FROM long_term_facts "
            "WHERE topic IS NOT NULL AND topic != '' "
            "AND tags NOT LIKE '%superseded%' "
            "GROUP BY topic"
        ).fetchall()
    return {r["topic"]: r["n"] for r in rows}


def _save_snapshot() -> dict[str, Any]:
    snap = {"topics": _topic_distribution()}
    with _conn() as c:
        snap["total_facts"] = c.execute(
            "SELECT COUNT(*) FROM long_term_facts"
        ).fetchone()[0]
        snap["cc_facts"] = c.execute(
            "SELECT COUNT(*) FROM long_term_facts WHERE tags LIKE '%cc,%'"
        ).fetchone()[0]
    SNAP.write_text(json.dumps(snap, indent=2))
    return snap


def _load_snapshot() -> dict[str, Any] | None:
    if SNAP.exists():
        return json.loads(SNAP.read_text())
    return None


def _print_state() -> None:
    print("\n=== 1. cc_state.json ===")
    if not STATE.exists():
        print("  (no state file — CC has not run)")
        return
    state = json.loads(STATE.read_text())
    print(f"  started:  {state.get('started_at')}")
    print(f"  finished: {state.get('finished_at', '(running or paused)')}")
    print(f"  backup:   {state.get('tree_backup_path', '(none)')}")
    for name, cfg in state.get("configs", {}).items():
        ingested = cfg.get("ingested", 0)
        target = cfg.get("target_records", 0)
        pct = (ingested / target * 100) if target else 0
        v = cfg.get("validation", {})
        verdict = "PASS" if v.get("passed") else "FAIL"
        stop = cfg.get("stopped_reason") or "target_reached"
        print(f"  {name}: {ingested:,}/{target:,} ({pct:.0f}%) "
              f"validation={verdict} stop={stop} batches={cfg.get('batches_run', 0)}")


def _print_distribution_diff() -> None:
    print("\n=== 2. Topic distribution (current) ===")
    dist = _topic_distribution()
    for topic, n in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"  {n:5d}  {topic}")
    pre = _load_snapshot()
    if pre is None:
        print("\n  (no pre-snapshot found at /tmp/cc_pre.snapshot.json)")
        print("  Saving current state as baseline for the NEXT verify run.")
        _save_snapshot()
        return
    print("\n=== Diff vs pre-snapshot ===")
    pre_topics = pre.get("topics", {})
    all_keys = sorted(set(dist) | set(pre_topics))
    for k in all_keys:
        delta = dist.get(k, 0) - pre_topics.get(k, 0)
        if delta != 0:
            sign = "+" if delta > 0 else ""
            print(f"  {sign}{delta:+5d}  {k}  ({pre_topics.get(k, 0)} → {dist.get(k, 0)})")
    print(f"\n  TOTAL Δ: {dist and sum(dist.values()) - sum(pre_topics.values())}")


def _print_sample_facts() -> None:
    print("\n=== 3. Sample of newly-ingested CC facts (latest 10) ===")
    with _conn() as c:
        rows = c.execute(
            "SELECT id, fact, tags, topic, source, created_at "
            "FROM long_term_facts "
            "WHERE tags LIKE '%cc,%' "
            "ORDER BY id DESC LIMIT 10"
        ).fetchall()
    if not rows:
        print("  (no CC facts found — tag 'cc,' not present)")
        return
    for r in rows:
        print(f"\n  id={r['id']} topic={r['topic']!r}")
        print(f"  tags={r['tags']}")
        print(f"  src={r['source']}")
        print(f"  fact: {r['fact'][:200]}{'...' if len(r['fact']) > 200 else ''}")


def _print_validator() -> None:
    print("\n=== 4. tree_validator (read-only) ===")
    sys.path.insert(0, "/Users/home/charles")
    try:
        from core import tree_validator
        report = tree_validator.validate_after_branch(
            branch_or_config=f"verify_run_post_smoke",
            new_facts_since=None,
        )
        print(report.summary())
    except Exception as e:  # noqa: BLE001
        print(f"  validator failed to run: {e}")


def _print_supersede_rate_by_branch() -> None:
    print("\n=== 5. Supersede rate by branch (CC vs old facts) ===")
    branches = ["business_corpus", "human_context", "training_corpus", "external"]
    with _conn() as c:
        for b in branches:
            cc_n = c.execute(
                "SELECT COUNT(*) FROM long_term_facts "
                "WHERE topic IN (SELECT name FROM topics WHERE parent_topic_id IN "
                "                (SELECT id FROM topics WHERE name=?)) "
                "AND tags LIKE '%cc,%'",
                (b,),
            ).fetchone()[0]
            sup_n = c.execute(
                "SELECT COUNT(*) FROM long_term_facts "
                "WHERE topic IN (SELECT name FROM topics WHERE parent_topic_id IN "
                "                (SELECT id FROM topics WHERE name=?)) "
                "AND tags LIKE '%superseded%'",
                (b,),
            ).fetchone()[0]
            print(f"  {b}: cc-tagged={cc_n}, superseded-tagged={sup_n}")


def main() -> int:
    print(f"=== CC verify @ {sys.argv[0]} ===")
    print(f"DB: {DB}")
    print(f"State: {STATE}")
    print(f"Snapshot: {SNAP}")
    _print_state()
    _print_distribution_diff()
    _print_sample_facts()
    _print_validator()
    _print_supersede_rate_by_branch()
    print("\n=== DONE ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
