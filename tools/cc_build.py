"""Tool wrappers for the Common Crawl ingestion runner.

Per CC build directive 2026-05-11. The actual orchestration logic lives in
core/cc_runner.py — these are the chat-surface entry points so Charles can:
  - kick off a build (typically John triggers from chat)
  - check current progress without invoking the runner
  - peek at config catalog

Tool tiering note (added per 2026-05-11 audit M):
  - run_cc_build: CORE — John will ask Charles to run it
  - cc_status: CORE — frequent progress checks
  - cc_list_configs: ON_DEMAND — rarely needed once configs are stable
"""
from __future__ import annotations

import json
import logging

from core.tools import tool

log = logging.getLogger("charles.cc_build_tool")


@tool(
    name="run_cc_build",
    summary=(
        "Kick off a Common Crawl ingestion build IN THE BACKGROUND. Returns "
        "immediately with a 'started' confirmation — does NOT block. The runner "
        "ingests in a background thread; call `cc_status` to poll progress. "
        "Replaces the live-web URL sprint with archived/frozen Common Crawl. "
        "Phase 1 re-runs 4 existing branches (business/human/training/external). "
        "Phase 2 adds 3 stack-specific configs (qwen36, mlx, agent_architecture). "
        "Serial only — branch by branch, config by config. tree_validator runs "
        "between each. Backs up memory.db before Phase 1. Resumable across "
        "restarts via workspace/cc_state.json. Idempotent — calling again continues "
        "from where it left off. Long-running (hours per config at MLX speed) but "
        "non-blocking from your perspective."
    ),
    triggers=(
        "common crawl", "cc build", "run cc", "ingest cc",
        "foundation knowledge", "phase 1", "phase 2 ingestion",
    ),
    schema={
        "type": "object",
        "properties": {
            "config_name": {
                "type": "string",
                "description": "Run only this specific config (e.g. 'p2_qwen36'). "
                               "Default: run all in directive order.",
            },
            "max_batches": {
                "type": "integer",
                "description": "Cap batches per config for testing. Default: unlimited.",
            },
            "skip_backup": {
                "type": "boolean",
                "description": "Skip the pre-Phase-1 memory.db snapshot. Default: false "
                               "(always take it).",
                "default": False,
            },
        },
    },
)
def run_cc_build(
    config_name: str | None = None,
    max_batches: int | None = None,
    skip_backup: bool = False,
) -> str:
    from core import cc_runner
    result = cc_runner.run_in_background(
        config_name=config_name,
        max_batches=max_batches,
        skip_backup=skip_backup,
    )
    if not result.get("started"):
        return f"CC runner did NOT start. Reason: {result.get('reason', 'unknown')}"
    return (
        "CC runner started in background thread.\n"
        f"  Thread: {result['thread']}\n"
        f"  Started at: {result['started_at']}\n"
        f"  State file: {result['state_path']}\n"
        f"  Note: {result['note']}\n"
        "Call cc_status periodically to track progress. Runner takes hours "
        "per config; first batch usually shows ingest counts within 5-15 min."
    )


@tool(
    name="cc_status",
    summary=(
        "Show current Common Crawl build state. Read-only — does not run the "
        "ingester. Returns: per-config ingest counters (pages queried/fetched/"
        "filtered/ingested), validation verdict per branch, any hard-stop "
        "reasons, and the on-disk backup path of the pre-Phase-1 memory.db "
        "snapshot. Use this to peek at progress without triggering more work."
    ),
    triggers=(
        "cc status", "common crawl status", "cc progress", "cc state",
        "ingestion progress",
    ),
    schema={"type": "object", "properties": {}},
)
def cc_status() -> str:
    from core import cc_runner
    state = cc_runner.status()
    if not state.get("configs"):
        return "CC has not run yet. State file: workspace/cc_state.json (empty)."
    lines = [
        f"CC state (last updated {state.get('last_updated', '?')}):",
        f"  started: {state.get('started_at')}",
        f"  finished: {state.get('finished_at', '(running or paused)')}",
        f"  tree backup: {state.get('tree_backup_path', '(none)')}",
        "",
    ]
    for name, cfg_state in state["configs"].items():
        ingested = cfg_state.get("ingested", 0)
        target = cfg_state.get("target_records", 0)
        pct = (ingested / target * 100) if target else 0
        v = cfg_state.get("validation", {})
        verdict = "PASS" if v.get("passed") else "FAIL"
        stop = cfg_state.get("stopped_reason") or "target_reached"
        lines.append(
            f"  {name}: {ingested:,}/{target:,} ({pct:.0f}%) "
            f"validation={verdict} stop={stop}"
        )
        if v.get("failures"):
            for f in v["failures"]:
                lines.append(f"    ❌ {f}")
        if v.get("warnings"):
            for w in v["warnings"][:3]:
                lines.append(f"    ⚠️  {w}")
    return "\n".join(lines)


@tool(
    name="cc_list_configs",
    summary=(
        "List all Common Crawl ingestion configs (Phase 1 + Phase 2). Returns "
        "the name, target record count, routing tag, and domain list for each. "
        "Read-only catalog; use cc_status for progress, run_cc_build to execute."
    ),
    triggers=("cc configs", "cc list", "ingestion configs"),
    schema={"type": "object", "properties": {}},
)
def cc_list_configs() -> str:
    from core import cc_configs
    lines = ["Phase 1 (re-run existing branches):"]
    for c in cc_configs.PHASE_1_CONFIGS:
        lines.append(
            f"  {c['name']}: target {c['target_records']:,} records — "
            f"domains: {', '.join(c['domains'][:3])}{'...' if len(c['domains']) > 3 else ''}"
        )
    lines.append("")
    lines.append("Phase 2 (stack-specific gap fills):")
    for c in cc_configs.PHASE_2_CONFIGS:
        lines.append(
            f"  {c['name']}: target {c['target_records']:,} records — "
            f"routing={c['routing_tag']}"
        )
    total = sum(c["target_records"] for c in cc_configs.all_configs())
    lines.append("")
    lines.append(f"Total target across all 7 configs: {total:,} records.")
    return "\n".join(lines)
