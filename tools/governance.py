"""Tier-2 approval governance + system status.

Per MOM Section 9 (Permission Architecture):

  Tier 1 — Full autonomy (no approval): development, research, self-improvement,
           memory organization, internal experimentation, email triage/drafting.
  Tier 2 — Approval-gated: financial transactions, account creation, external
           commitments, legal commitments, identity-bearing actions.

Tier 2 actions go through `request_approval` which:
  1. Sends a formatted iMessage with action/reason/cost.
  2. Records the request as a long_term_fact tagged 'approval-pending'.
  3. Returns IMMEDIATELY without blocking — Charles continues other work.
  4. John replies later (👍 = approve, anything else = halt).
  5. Future ticks check `recent_imessages` to see John's response and
     update the request status via `resolve_approval`.

This avoids blocking the heartbeat / agent loop on a human reply.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from core import memory
from core.tools import tool
from tools.imessage import send_imessage as _send_imessage
from tools.notify import notify_john as _notify_john

log = logging.getLogger("charles.governance")


@tool(
    name="request_approval",
    summary="Request John's approval for a Tier-2 action (financial txns, account creation, external messages, contracts, identity actions). Sends a formatted iMessage and records the request. Returns immediately — does NOT block waiting for response. Check back via recent_imessages on a later tick to see John's reply.",
    triggers=("request approval", "ask john", "tier 2", "need approval", "permission needed"),
    schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "What you want to do, in one clear sentence.",
            },
            "reason": {
                "type": "string",
                "description": "Why this action — what outcome or value it delivers.",
            },
            "cost_risk": {
                "type": "string",
                "description": "Money cost, time cost, or downside risk if it goes wrong. Be honest.",
            },
        },
        "required": ["action", "reason", "cost_risk"],
    },
)
def request_approval(action: str, reason: str, cost_risk: str) -> str:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    msg = (
        "📋 APPROVAL NEEDED\n\n"
        f"Action: {action}\n"
        f"Reason: {reason}\n"
        f"Cost/risk: {cost_risk}\n\n"
        f"Reply 👍 to approve, anything else halts.\n"
        f"(req {timestamp})"
    )
    send_result = _send_imessage(msg)

    # Record the request as a fact so Charles can find it later
    fact = (
        f"APPROVAL PENDING [{timestamp}]: action={action!r} reason={reason!r} "
        f"cost_risk={cost_risk!r}. Awaiting John's response (👍 to approve, else halt). "
        f"DO NOT proceed with this action until status changes to APPROVED."
    )
    fact_id = memory.add_fact(fact, tags="approval-pending,tier2")
    return (
        f"approval request sent (fact #{fact_id}, ts={timestamp}). "
        f"iMessage status: {send_result}. "
        f"Action is BLOCKED until John replies 👍 — check recent_imessages on a later tick."
    )


@tool(
    name="resolve_approval",
    summary="Mark a pending Tier-2 approval as approved or halted. Call this AFTER reading John's iMessage reply. Updates the fact with the outcome.",
    triggers=("resolve approval", "approval received", "approval granted", "approval denied"),
    schema={
        "type": "object",
        "properties": {
            "fact_id": {"type": "integer", "description": "The fact id from request_approval."},
            "approved": {"type": "boolean", "description": "True if John replied with 👍 (approved), False otherwise (halt)."},
            "note": {"type": "string", "description": "Optional one-line about John's exact reply."},
        },
        "required": ["fact_id", "approved"],
    },
)
def resolve_approval(fact_id: int, approved: bool, note: str = "") -> str:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    status = "APPROVED" if approved else "HALTED"
    resolution_fact = (
        f"APPROVAL {status} [{timestamp}]: parent_fact_id={fact_id}. "
        f"John's reply: {note or '(see iMessage thread)'}."
    )
    new_id = memory.add_fact(resolution_fact, tags=f"approval-{status.lower()},tier2")
    return f"recorded: parent fact #{fact_id} → {status} (new fact #{new_id})"


@tool(
    name="system_status",
    summary="Return your own system health snapshot: process uptime, memory.db sizes, active goals/scheduled tasks count, recent fact count, last successful Telegram poll. Use to self-check or to answer 'how are you' questions accurately.",
    triggers=("system status", "your status", "are you ok", "health check", "how are you"),
    schema={"type": "object", "properties": {}},
)
def system_status() -> str:
    import os
    import subprocess
    from pathlib import Path

    # Charles process info
    try:
        out = subprocess.check_output(["pgrep", "-fa", "python.*charles.py"], text=True).strip()
        charles_pid_line = out.split("\n")[0] if out else "(not running?)"
    except subprocess.CalledProcessError:
        charles_pid_line = "(not running)"

    # Memory.db stats
    db = Path("/Users/home/charles/workspace/memory.db")
    db_size = db.stat().st_size if db.exists() else 0

    # Counts
    from core import goals as _goals, scheduler as _sched
    active_goals = len(_goals.list_goals("active"))
    pending_tasks = len(_sched.list_tasks("pending"))
    recent_facts = len(memory.all_facts(limit=50))

    # Active LaunchAgents
    try:
        la_out = subprocess.check_output(
            ["launchctl", "list"], text=True
        ).strip()
        agents = [line for line in la_out.split("\n") if "com.charles" in line]
    except subprocess.CalledProcessError:
        agents = []

    parts = [
        f"=== Charles system status [{datetime.now(timezone.utc).isoformat(timespec='seconds')}Z] ===",
        f"Process: {charles_pid_line}",
        f"LaunchAgents: {len(agents)} active — {[a.split()[2] if len(a.split()) >= 3 else a for a in agents]}",
        f"memory.db: {db_size:,} bytes",
        f"Active goals: {active_goals}",
        f"Pending scheduled_tasks: {pending_tasks}",
        f"Long-term facts (recent 50): {recent_facts}",
    ]
    return "\n".join(parts)
