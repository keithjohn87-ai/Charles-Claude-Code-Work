"""Common Crawl ingestion runner — drives the end-to-end build.

Per CC build directive 2026-05-11 sections 9-11:
  - Serial only (Phase 1 → Phase 2, branch by branch, config by config)
  - tree_validator runs after each branch/config; pause + surface to John on fail
  - Hard stops: low RAM, backlog overflow, uncategorized > 10%/batch,
    3 consecutive batch failures, supersede rate > 80%/branch

State persisted to workspace/cc_state.json so the runner is resumable across
restarts (in particular if Charles is restarted mid-build).

Surface progress via:
  - Per-batch IngestStats logged to charles.cc_runner
  - workspace/cc_state.json periodically flushed (every batch)
  - daily_log entries via memory.add_fact for milestones
  - Existing system_status display reads the JSON state file

Usage from CLI / scheduler:
    python -m core.cc_runner [--config NAME] [--max-batches N] [--dry-run]

Usage from a tool (`run_cc_build`):
    from core import cc_runner
    cc_runner.run(config_name=None, max_batches=None)
"""
from __future__ import annotations

import json
import logging
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("charles.cc_runner")

STATE_PATH = Path("/Users/home/charles/workspace/cc_state.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception as e:  # noqa: BLE001
            log.warning("cc_state load failed (%s) — starting fresh", e)
    return {"version": 1, "configs": {}, "started_at": _now_iso()}


def _save_state(state: dict) -> None:
    state["last_updated"] = _now_iso()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, default=str))


def _ram_headroom_gb() -> float:
    """Return free RAM in GB. Per directive: pause if < 4GB."""
    try:
        import psutil
        return psutil.virtual_memory().available / (1024 ** 3)
    except Exception:  # noqa: BLE001
        # psutil not installed — fall back to vm_stat (macOS)
        try:
            import subprocess
            out = subprocess.check_output(["vm_stat"], text=True)
            free_pages = inactive_pages = 0
            for line in out.splitlines():
                if "Pages free" in line:
                    free_pages = int(line.rsplit(":", 1)[1].strip().rstrip("."))
                elif "Pages inactive" in line:
                    inactive_pages = int(line.rsplit(":", 1)[1].strip().rstrip("."))
            return (free_pages + inactive_pages) * 4096 / (1024 ** 3)
        except Exception:  # noqa: BLE001
            return 999.0  # fail-open if we can't measure


def _check_hard_stops(stats_window: list, branch: str) -> str | None:
    """Return reason string if a hard-stop fires; else None."""
    from core.cc_configs import HARD_STOPS
    ram = _ram_headroom_gb()
    if ram < HARD_STOPS["min_ram_gb"]:
        return f"hard_stop_ram_low: {ram:.1f}GB < {HARD_STOPS['min_ram_gb']}GB"
    # 3 consecutive failed batches
    if len(stats_window) >= HARD_STOPS["max_consecutive_batch_failures"]:
        recent = stats_window[-HARD_STOPS["max_consecutive_batch_failures"]:]
        if all(s.pages_ingested == 0 for s in recent):
            return f"hard_stop_consecutive_failures: {len(recent)}"
    return None


def _backup_tree() -> Path:
    """Snapshot memory.db before Phase 1 begins — directive prereq."""
    db = Path("/Users/home/charles/workspace/memory.db")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = Path(f"/Users/home/charles/workspace/memory.db.pre-cc-{ts}")
    shutil.copy2(db, backup)
    log.info("backed up memory.db → %s", backup.name)
    return backup


def _mark_pending_supersede(config: dict, stamp: str) -> int:
    """Pre-ingest pass: mark existing non-CC facts in this config's branch as
    `pending_supersede:<stamp>` so we know which ones to commit/rollback later.

    Conservative: only touches facts whose tags include the config's `branch`
    name AND whose source is from the URL sprint (auto_finding / url_corpus
    / part:<branch>). Doctrine, John-curated, watchdog, and CC-sourced facts
    are NOT touched.

    Returns the number of facts marked.
    """
    from core.memory import _conn
    branch = config.get("branch") or ""
    if not branch:
        return 0
    pending_tag = f"pending_supersede:{stamp}"
    routing_tag = config.get("routing_tag") or f"phase1/{branch}"
    # Match facts that:
    #   - have the branch name in tags (e.g. "human_context")
    #   - look URL-sprint-sourced (auto_finding / url_corpus / "part:<branch>")
    #   - are NOT already CC-sourced (routing_tag absent)
    #   - are NOT already pending_supersede / superseded
    sql = """
        UPDATE long_term_facts
           SET tags = tags || ',' || ?
         WHERE tags LIKE ?
           AND (tags LIKE '%auto_finding%' OR tags LIKE '%url_corpus%' OR tags LIKE ?)
           AND tags NOT LIKE ?
           AND tags NOT LIKE '%pending_supersede:%'
           AND tags NOT LIKE '%superseded%'
    """
    branch_like = f"%{branch}%"
    part_like = f"%part:{branch}%"
    routing_like = f"%{routing_tag}%"
    with _conn() as c:
        cur = c.execute(sql, (pending_tag, branch_like, part_like, routing_like))
        n = cur.rowcount
    log.info("supersede: marked %d existing facts in branch=%s as %s",
             n, branch, pending_tag)
    return n


def _commit_supersede(stamp: str) -> int:
    """Post-ingest success: promote `pending_supersede:<stamp>` → `superseded`
    + a final `superseded_by:cc_<stamp>` marker so the audit trail shows when
    and why. The pending tag is removed.
    """
    from core.memory import _conn
    pending_tag = f"pending_supersede:{stamp}"
    final_tag = f"superseded,superseded_by:cc_{stamp}"
    sql = """
        UPDATE long_term_facts
           SET tags = REPLACE(tags, ?, ?)
         WHERE tags LIKE ?
    """
    with _conn() as c:
        cur = c.execute(sql, (pending_tag, final_tag, f"%{pending_tag}%"))
        n = cur.rowcount
    log.info("supersede: committed %d facts → superseded (stamp=%s)", n, stamp)
    return n


def _rollback_supersede(stamp: str) -> int:
    """Post-ingest failure: undo the pending tag so the originals stay active.
    Called when the CC run hard-stops dirty or tree_validator fails.
    """
    from core.memory import _conn
    pending_tag = f"pending_supersede:{stamp}"
    # Strip the pending tag (and the comma in front, if any) cleanly.
    sql = """
        UPDATE long_term_facts
           SET tags = REPLACE(REPLACE(tags, ',' || ?, ''), ?, '')
         WHERE tags LIKE ?
    """
    with _conn() as c:
        cur = c.execute(sql, (pending_tag, pending_tag, f"%{pending_tag}%"))
        n = cur.rowcount
    log.info("supersede: rolled back %d pending tags (stamp=%s)", n, stamp)
    return n


def _ingest_one_config(config: dict, *, max_batches: int | None) -> dict:
    """Run a single config until target_records hit OR hard-stop fires.
    Returns a per-config summary dict that goes into cc_state.json."""
    from core import cc_ingestion
    from core import tree_validator

    name = config["name"]
    log.info("=== START config %s (target %d records) ===",
             name, config["target_records"])

    branch_started = _now_iso()
    # Stamp for supersede correlation — short, file-safe.
    supersede_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    supersede_enabled = bool(config.get("supersede_existing"))
    pending_marked = 0
    if supersede_enabled:
        pending_marked = _mark_pending_supersede(config, supersede_stamp)

    cdx_state: dict = {"seen_urls": set(), "domain_cursor": 0}
    summary = {
        "name": name,
        "branch": config.get("branch"),
        "started_at": branch_started,
        "target_records": config["target_records"],
        "ingested": 0,
        "batches_run": 0,
        "failures": 0,
        "skipped_dedup": 0,
        "stopped_reason": None,
        "supersede_enabled": supersede_enabled,
        "supersede_stamp": supersede_stamp if supersede_enabled else None,
        "supersede_pending_marked": pending_marked,
        "supersede_committed": 0,
    }

    stats_window: list = []
    batch_n = 0
    while summary["ingested"] < config["target_records"]:
        if max_batches is not None and batch_n >= max_batches:
            summary["stopped_reason"] = f"max_batches_reached:{max_batches}"
            break

        stop = _check_hard_stops(stats_window, name)
        if stop:
            summary["stopped_reason"] = stop
            log.error("HARD STOP for %s: %s", name, stop)
            break

        try:
            stats = cc_ingestion.ingest_batch(
                config, batch_size=100, cdx_state=cdx_state
            )
        except Exception as e:  # noqa: BLE001
            log.exception("batch crashed for %s", name)
            summary["failures"] += 1
            stats_window.append(cc_ingestion.IngestStats(failures=1))
            time.sleep(2)
            continue

        stats_window.append(stats)
        summary["ingested"] += stats.pages_ingested
        summary["failures"] += stats.failures
        summary["skipped_dedup"] += stats.skipped_dedup
        summary["batches_run"] = batch_n + 1
        batch_n += 1

        log.info(
            "batch %d done — queried=%d fetched=%d filtered=%d ingested=%d (cum %d/%d)",
            batch_n, stats.pages_queried, stats.pages_fetched,
            stats.pages_passed_filter, stats.pages_ingested,
            summary["ingested"], config["target_records"],
        )

        # If this batch ingested 0 records, give CDX/network a beat to settle.
        if stats.pages_ingested == 0:
            time.sleep(5)

    # Validate after this config completes
    report = tree_validator.validate_after_branch(
        branch_or_config=name,
        new_facts_since=branch_started,
        branch_topic=config.get("topic"),
    )
    summary["validation"] = {
        "passed": report.passed,
        "metrics": report.metrics,
        "failures": report.failures,
        "warnings": report.warnings,
    }
    log.info("=== END config %s ===\n%s", name, report.summary())
    if not report.passed:
        summary["stopped_reason"] = (
            (summary["stopped_reason"] or "")
            + f"|tree_validation_fail:{report.failures}"
        ).strip("|")

    # Supersede commit/rollback. Only fires if the config opted in.
    # Commit when: validation passed AND we actually ingested SOMETHING new
    # (a 0-ingest run shouldn't supersede anything — that's a CC failure, not
    # a real replacement). Otherwise: roll back so originals stay live.
    if supersede_enabled and pending_marked > 0:
        ingested_real_records = summary["ingested"] > 0
        if report.passed and ingested_real_records:
            committed = _commit_supersede(supersede_stamp)
            summary["supersede_committed"] = committed
        else:
            rolled = _rollback_supersede(supersede_stamp)
            summary["supersede_rolled_back"] = rolled
            reason = []
            if not report.passed:
                reason.append("validation_failed")
            if not ingested_real_records:
                reason.append("no_records_ingested")
            summary["supersede_skip_reason"] = ",".join(reason) or "unknown"
    return summary


def run_in_background(
    *,
    config_name: str | None = None,
    max_batches: int | None = None,
    skip_backup: bool = False,
) -> dict:
    """Spawn run() in a daemon thread + return immediately.

    For LLM-tool callers (Charles via run_cc_build) so the agent's respond()
    loop doesn't block for the full ingestion duration. Caller polls
    `status()` to track progress.

    Returns: {"started": True, "pid": int, "started_at": iso, "state_path": str}
    or {"started": False, "reason": "..."} if a runner is already in flight.
    """
    import os
    import threading
    from core.cc_configs import all_configs, by_name

    # Pre-validate config_name before spawning, so caller gets a useful error
    # synchronously instead of the thread silently no-op'ing on bad input.
    if config_name:
        cfg = by_name(config_name)
        if cfg is None:
            valid = [c["name"] for c in all_configs()]
            base = config_name.replace("p1_", "").replace("p2_", "")
            suggestions = [n for n in valid if base and base in n]
            return {
                "started": False,
                "reason": (
                    f"no config matched name={config_name!r}. "
                    f"Valid: {valid}. "
                    + (f"Did you mean {suggestions}?" if suggestions else "")
                ),
                "valid_configs": valid,
            }

    # Don't double-fire — check if a runner is already in this Python process
    if any(t.name == "cc_runner_bg" and t.is_alive() for t in threading.enumerate()):
        return {
            "started": False,
            "reason": "cc_runner already running in this process — call cc_status to check progress",
        }

    def _wrapper():
        try:
            run(
                config_name=config_name,
                max_batches=max_batches,
                skip_backup=skip_backup,
            )
        except Exception as e:  # noqa: BLE001
            log.exception("cc_runner background thread crashed: %s", e)

    t = threading.Thread(target=_wrapper, name="cc_runner_bg", daemon=True)
    t.start()
    log.info("cc_runner spawned in background thread (config=%s, max_batches=%s)",
             config_name, max_batches)
    return {
        "started": True,
        "thread": t.name,
        "pid": os.getpid(),
        "started_at": _now_iso(),
        "state_path": str(STATE_PATH),
        "note": "Runner is async. Call cc_status periodically to track progress.",
    }


def run(
    *,
    config_name: str | None = None,
    max_batches: int | None = None,
    skip_backup: bool = False,
) -> dict:
    """Run the Common Crawl build — the directive's top-level entry.

    SYNCHRONOUS — blocks until all configs finish or a hard stop fires.
    For LLM-tool callers, prefer run_in_background() so the agent's
    respond() loop doesn't block.

    `config_name` — run only this one config (for debug / partial reruns).
                    Default: run all in order (Phase 1 → Phase 2).
    `max_batches` — cap batches per config (for testing). Default: unlimited.
    `skip_backup` — skip the pre-Phase-1 memory.db snapshot. Default: take it.
    """
    from core.cc_configs import all_configs, by_name

    state = _load_state()
    if not skip_backup and "tree_backup_path" not in state:
        backup = _backup_tree()
        state["tree_backup_path"] = str(backup)
        _save_state(state)

    if config_name:
        cfg = by_name(config_name)
        if cfg is None:
            valid = [c["name"] for c in all_configs()]
            # Fuzzy suggest — common confusion is p1_/p2_ prefix
            base = config_name.replace("p1_", "").replace("p2_", "")
            suggestions = [n for n in valid if base and base in n]
            return {
                "error": (
                    f"no config matched name={config_name!r}. "
                    f"Valid names: {valid}. "
                    + (f"Did you mean {suggestions}?" if suggestions else "")
                ),
                "valid_configs": valid,
            }
        configs = [cfg]
    else:
        configs = all_configs()
    configs = [c for c in configs if c]
    if not configs:
        return {"error": "no configs available — check core/cc_configs.py"}

    for cfg in configs:
        if cfg["name"] in state["configs"] and state["configs"][cfg["name"]].get("ingested", 0) >= cfg["target_records"]:
            log.info("skipping %s — already at target (%d)",
                     cfg["name"], cfg["target_records"])
            continue
        summary = _ingest_one_config(cfg, max_batches=max_batches)
        state["configs"][cfg["name"]] = summary
        _save_state(state)

        # Surface as a fact for John's audit trail
        try:
            from core import memory as _memory
            _memory.add_fact(
                fact=(
                    f"CC build completed {cfg['name']}: "
                    f"{summary['ingested']}/{cfg['target_records']} records "
                    f"in {summary['batches_run']} batches "
                    f"(stop_reason={summary.get('stopped_reason') or 'target'}). "
                    f"Validation: {'PASS' if summary['validation']['passed'] else 'FAIL'}."
                ),
                tags=f"cc_build,milestone,{cfg['name']}",
                topic="charles_self",
            )
        except Exception as e:  # noqa: BLE001
            log.warning("milestone add_fact failed: %s", e)

        # Hard pause if validation failed — don't proceed to next config
        if not summary["validation"]["passed"]:
            log.error("PAUSING: tree validation failed for %s", cfg["name"])
            break

    state["finished_at"] = _now_iso()
    _save_state(state)
    return state


def status() -> dict:
    """Read-only status pull — for system_status display + chat queries."""
    return _load_state()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _cli() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Run the Common Crawl build")
    p.add_argument("--config", help="Run only this config (default: all)")
    p.add_argument("--max-batches", type=int, default=None,
                   help="Cap batches per config (default: unlimited)")
    p.add_argument("--skip-backup", action="store_true",
                   help="Skip pre-Phase-1 memory.db snapshot")
    p.add_argument("--status", action="store_true",
                   help="Show current state instead of running")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.status:
        print(json.dumps(status(), indent=2, default=str))
        return 0

    state = run(
        config_name=args.config,
        max_batches=args.max_batches,
        skip_backup=args.skip_backup,
    )
    print(json.dumps(state, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
