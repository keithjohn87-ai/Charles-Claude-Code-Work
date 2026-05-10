"""State readers — surface Charles's current state for the UI apps.

Read-only queries against the SQLite memory.db, plus runtime stats from
psutil and Charles's process. No writes. The command layer is in server.py.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

WORKSPACE = Path("/Users/home/charles/workspace")
DB_PATH = WORKSPACE / "memory.db"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def now_summary() -> dict[str, Any]:
    """Top-line state for the iPhone Now view + Lock Screen widget."""
    con = _conn()
    cur = con.cursor()
    active_goals = cur.execute(
        "SELECT id, description, advance_seconds, last_advanced_at "
        "FROM goals WHERE status='active' ORDER BY id"
    ).fetchall()
    pending_tasks = cur.execute(
        "SELECT COUNT(*) FROM scheduled_tasks WHERE status='pending'"
    ).fetchone()[0]
    pending_approvals = cur.execute(
        "SELECT COUNT(*) FROM long_term_facts WHERE tags LIKE '%approval-pending%' "
        "AND tags NOT LIKE '%resolved%'"
    ).fetchone()[0]
    # Count Charles-created tasks (and auto-extracted ones) so the Tasks tab
    # badge reflects the FULL unified view, not just approvals.
    try:
        open_tasks = cur.execute(
            "SELECT COUNT(*) FROM tasks WHERE status='open'"
        ).fetchone()[0]
    except sqlite3.OperationalError:
        open_tasks = 0  # tasks table not migrated yet (older DB)
    open_requests = cur.execute(
        "SELECT COUNT(*) FROM long_term_facts "
        "WHERE tags LIKE '%open_request%' AND tags NOT LIKE '%resolved%'"
    ).fetchone()[0]
    unified_pending = pending_approvals + open_tasks + open_requests
    last_turn = cur.execute(
        "SELECT created_at, conversation_id, role FROM conversations "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    con.close()

    return {
        "agent_running": _agent_alive(),
        "agent_pid": _agent_pid(),
        "uptime_seconds": _agent_uptime_seconds(),
        "active_goals": [
            {
                "id": g["id"],
                "description": (g["description"][:140] + "…") if len(g["description"]) > 140 else g["description"],
                "advance_seconds": g["advance_seconds"],
                "last_advanced_at": g["last_advanced_at"],
            }
            for g in active_goals
        ],
        "pending_tasks_count": pending_tasks,
        "open_tasks_count": open_tasks,
        "open_requests_count": open_requests,
        "unified_pending_count": unified_pending,
        "pending_approvals_count": pending_approvals,
        "last_activity_at": last_turn["created_at"] if last_turn else None,
        "last_activity_conv": last_turn["conversation_id"] if last_turn else None,
        "last_activity_role": last_turn["role"] if last_turn else None,
    }


def conversations_index(limit: int = 30) -> list[dict[str, Any]]:
    """List distinct conversation IDs with last-activity timestamp + turn count."""
    con = _conn()
    rows = con.execute(
        "SELECT conversation_id, MAX(created_at) AS last_at, COUNT(*) AS turn_count, "
        "       MAX(CASE WHEN role='user' THEN substr(content, 1, 120) END) AS last_user_msg "
        "FROM conversations "
        "GROUP BY conversation_id "
        "ORDER BY last_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def conversation_history(conv_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Full turns for a conversation. Newest last."""
    con = _conn()
    rows = con.execute(
        "SELECT id, role, content, tool_calls_json, tool_call_id, created_at "
        "FROM conversations WHERE conversation_id=? "
        "ORDER BY id DESC LIMIT ?",
        (conv_id, limit),
    ).fetchall()
    con.close()
    out = []
    for r in reversed(rows):
        entry: dict[str, Any] = {
            "id": r["id"],
            "role": r["role"],
            "content": r["content"],
            "tool_call_id": r["tool_call_id"],
            "created_at": r["created_at"],
        }
        if r["tool_calls_json"]:
            try:
                entry["tool_calls"] = json.loads(r["tool_calls_json"])
            except json.JSONDecodeError:
                entry["tool_calls"] = []
        out.append(entry)
    return out


def goals_state(status: str = "active") -> list[dict[str, Any]]:
    con = _conn()
    if status == "all":
        rows = con.execute(
            "SELECT id, description, status, notes, advance_seconds, "
            "       last_advanced_at, created_at, completed_at "
            "FROM goals ORDER BY id DESC"
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT id, description, status, notes, advance_seconds, "
            "       last_advanced_at, created_at, completed_at "
            "FROM goals WHERE status=? ORDER BY id DESC",
            (status,),
        ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def tasks_state(status: str = "pending") -> list[dict[str, Any]]:
    con = _conn()
    if status == "all":
        rows = con.execute(
            "SELECT id, description, due_at, cadence_seconds, status, last_run_at, last_result "
            "FROM scheduled_tasks ORDER BY due_at ASC"
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT id, description, due_at, cadence_seconds, status, last_run_at, last_result "
            "FROM scheduled_tasks WHERE status=? ORDER BY due_at ASC",
            (status,),
        ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def pending_approvals() -> list[dict[str, Any]]:
    """Approval-pending facts. The governance.request_approval tool tags these."""
    con = _conn()
    rows = con.execute(
        "SELECT id, fact, tags, created_at FROM long_term_facts "
        "WHERE tags LIKE '%approval-pending%' AND tags NOT LIKE '%resolved%' "
        "ORDER BY id DESC"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def activity_feed(limit: int = 50, conv_id: str | None = None) -> list[dict[str, Any]]:
    """Recent turns + tool calls flattened. Newest first.

    Optional conv_id filter — used by the Mac UI's Activity tab to scope to
    CHARLES_LOG only (the operational stream). When None, returns all turns
    interleaved (the default cross-channel feed)."""
    con = _conn()
    if conv_id:
        rows = con.execute(
            "SELECT id, conversation_id, role, substr(content, 1, 240) AS preview, "
            "       tool_calls_json, created_at "
            "FROM conversations WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
            (conv_id, limit),
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT id, conversation_id, role, substr(content, 1, 240) AS preview, "
            "       tool_calls_json, created_at "
            "FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    con.close()
    out = []
    for r in rows:
        entry: dict[str, Any] = {
            "id": r["id"],
            "conv_id": r["conversation_id"],
            "role": r["role"],
            "preview": r["preview"],
            "created_at": r["created_at"],
        }
        if r["tool_calls_json"]:
            try:
                tcs = json.loads(r["tool_calls_json"])
                entry["tool_call_names"] = [
                    tc.get("function", {}).get("name") for tc in tcs
                ]
            except json.JSONDecodeError:
                pass
        out.append(entry)
    return out


def system_stats() -> dict[str, Any]:
    """Mac Studio resource snapshot — RAM, CPU, model, voice, processes."""
    stats: dict[str, Any] = {
        "model": os.environ.get("MLX_MODEL", "unknown"),
        "voice": os.environ.get("CHARLES_VOICE", "unknown"),
        "agent_running": _agent_alive(),
        "agent_pid": _agent_pid(),
        "uptime_seconds": _agent_uptime_seconds(),
    }
    # Memory via vm_stat (Mac-native, no extra dep)
    try:
        out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=2).stdout
        page_size = 16384  # M1/M2/M3 default
        free = active = wired = 0
        for line in out.splitlines():
            if "Pages free" in line:
                free = int(line.split(":")[1].strip().rstrip("."))
            elif "Pages active" in line:
                active = int(line.split(":")[1].strip().rstrip("."))
            elif "Pages wired down" in line:
                wired = int(line.split(":")[1].strip().rstrip("."))
        stats["ram_free_gb"] = round(free * page_size / 1024 ** 3, 2)
        stats["ram_active_gb"] = round(active * page_size / 1024 ** 3, 2)
        stats["ram_wired_gb"] = round(wired * page_size / 1024 ** 3, 2)
    except Exception as e:  # noqa: BLE001
        stats["ram_error"] = str(e)
    # Charles process count
    try:
        ps = subprocess.run(
            ["pgrep", "-fl", "charles"], capture_output=True, text=True, timeout=2
        ).stdout
        stats["charles_processes"] = [line.strip() for line in ps.splitlines() if line.strip()][:10]
    except Exception:  # noqa: BLE001
        stats["charles_processes"] = []
    return stats


def tool_registry() -> list[dict[str, Any]]:
    """Tool registry list. Imports tools to populate REGISTRY."""
    import sys
    if "/Users/home/charles" not in sys.path:
        sys.path.insert(0, "/Users/home/charles")
    import tools  # noqa: F401  — side effect: registers tools
    from core.tools import REGISTRY

    return [
        {
            "name": t.name,
            "summary": t.summary,
            "triggers": list(t.triggers) if t.triggers else [],
        }
        for t in REGISTRY.values()
    ]


def _agent_alive() -> bool:
    try:
        out = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=2
        ).stdout
    except Exception:  # noqa: BLE001
        return False
    for line in out.splitlines():
        if "com.charles.agent" in line:
            parts = line.split("\t")
            return parts[0].isdigit() and int(parts[0]) > 0
    return False


def _agent_pid() -> int | None:
    try:
        out = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=2
        ).stdout
    except Exception:  # noqa: BLE001
        return None
    for line in out.splitlines():
        if "com.charles.agent" in line:
            parts = line.split("\t")
            if parts[0].isdigit():
                return int(parts[0])
    return None


def _agent_uptime_seconds() -> int | None:
    pid = _agent_pid()
    if not pid:
        return None
    try:
        # `ps -o etime= -p PID` returns elapsed time as [[dd-]hh:]mm:ss
        out = subprocess.run(
            ["ps", "-o", "etime=", "-p", str(pid)],
            capture_output=True, text=True, timeout=2,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return None
    return _parse_etime(out)


def _parse_etime(s: str) -> int | None:
    if not s:
        return None
    parts = s.split("-")
    days = 0
    if len(parts) == 2:
        days = int(parts[0])
        rest = parts[1]
    else:
        rest = parts[0]
    hms = rest.split(":")
    if len(hms) == 2:
        h, m, sec = 0, int(hms[0]), int(hms[1])
    elif len(hms) == 3:
        h, m, sec = int(hms[0]), int(hms[1]), int(hms[2])
    else:
        return None
    return days * 86400 + h * 3600 + m * 60 + sec


def latest_conversation_id() -> int:
    """For the WebSocket event stream — last conversations.id seen."""
    con = _conn()
    row = con.execute("SELECT MAX(id) FROM conversations").fetchone()
    con.close()
    return row[0] or 0


def conversation_rows_since(last_id: int, limit: int = 100) -> list[dict[str, Any]]:
    con = _conn()
    rows = con.execute(
        "SELECT id, conversation_id, role, substr(content, 1, 500) AS preview, "
        "       tool_calls_json, created_at "
        "FROM conversations WHERE id > ? ORDER BY id ASC LIMIT ?",
        (last_id, limit),
    ).fetchall()
    con.close()
    out = []
    for r in rows:
        entry: dict[str, Any] = {
            "id": r["id"],
            "conv_id": r["conversation_id"],
            "role": r["role"],
            "preview": r["preview"],
            "created_at": r["created_at"],
        }
        if r["tool_calls_json"]:
            try:
                tcs = json.loads(r["tool_calls_json"])
                entry["tool_call_names"] = [
                    tc.get("function", {}).get("name") for tc in tcs
                ]
            except json.JSONDecodeError:
                pass
        out.append(entry)
    return out
