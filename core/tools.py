"""Tool registry, classifier, and dispatcher.

Architectural point of M1: lean prompt by default. Only the SUMMARIES of all
tools go in the system prompt every turn (one line each). Full JSON schemas
are loaded ONLY for the 0-3 tools the classifier matches against the user's
current message. This is the dynamic-loading model that lets us keep
hundreds of tools without OpenClaw-scale prompt bloat.
"""
from __future__ import annotations

import difflib
import inspect
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

log = logging.getLogger("charles.tools")


@dataclass
class Tool:
    name: str
    summary: str
    schema: dict
    triggers: tuple[str, ...]
    handler: Callable[..., str]

    def openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.summary,
                "parameters": self.schema,
            },
        }


REGISTRY: dict[str, Tool] = {}

_SMART_QUOTES = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
})

# ─────────────────────────────────────────────────────────────────────────────
# Tool tiering (added 2026-05-11 audit). Three tiers control where a tool's
# schema and summary appear in the LLM context, so prompt cost stays bounded
# as the toolset grows past ~10:
#
#   CORE        — always sent every turn. Stable across all calls so the MLX
#                 prompt cache stays warm. The set Charles uses in normal
#                 conversation + critical safety + frequent project ops.
#   ON_DEMAND   — sent only when the user message OR recent CHARLES_LOG
#                 chatter triggers a keyword in the tool's `triggers` field.
#                 Loaded on top of CORE on the first round of a chain.
#   SYSTEM_ONLY — never sent to the LLM. Called by scheduler / heartbeat /
#                 watchdog code paths only. The handler is registered for
#                 dispatch but the schema and summary are excluded from
#                 prompts entirely.
#
# A tool name not listed in CORE_TOOLS or SYSTEM_ONLY_TOOLS defaults to
# ON_DEMAND.
# ─────────────────────────────────────────────────────────────────────────────

CORE_TOOLS: set[str] = {
    # Top 10 actually-invoked via LLM (per audit 2026-05-11)
    "project_mark_item", "browse_url", "project_next_pending", "exec_shell",
    "project_list_items", "recall", "project_status", "read_file",
    "remember", "complete_goal",
    # Critical safety / state-management (must always be available)
    "reset_my_conversation", "recall_keyword",
    # Proactive iMessage to John (legacy notify_john lives in on_demand)
    "send_imessage", "recent_imessages",
    # Goal + task ops Charles needs in normal chat
    "list_goals", "append_goal_note", "list_open_tasks", "add_task",
    # New learning-tree surfaces (Charles is gradually adopting them)
    "recall_topic", "topic_list", "john_says", "john_pref_categories",
    "skill_log_use",
    # Async-tool plumbing — Charles always needs to be able to check on or
    # cancel a job he kicked off. The async-tool handlers themselves are
    # ON_DEMAND by default (they declare their own triggers).
    "async_tool_status", "async_tool_cancel",
    # System status + vibe
    "system_status", "vibe_check", "current_time",
    # Common Crawl build (2026-05-11) — John will ask Charles to run/check it
    "run_cc_build", "cc_status",
}

SYSTEM_ONLY_TOOLS: set[str] = {
    # Scheduler-invoked, not LLM-facing
    "consolidate_memory", "reflect_now", "get_weather", "notify_john",
}


def tool_tier(name: str) -> str:
    """Return 'core', 'system', or 'on_demand' for a registered tool name."""
    if name in CORE_TOOLS:
        return "core"
    if name in SYSTEM_ONLY_TOOLS:
        return "system"
    return "on_demand"


def tool(*, name: str, summary: str, schema: dict, triggers: tuple[str, ...] = ()):
    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        if name in REGISTRY:
            raise ValueError(f"tool {name!r} already registered")
        REGISTRY[name] = Tool(
            name=name,
            summary=summary.strip(),
            schema=schema,
            triggers=tuple(t.lower() for t in triggers),
            handler=fn,
        )
        return fn

    return decorator


def summary_block() -> str:
    """One-line summary per tool — CORE tier only.

    On-demand tool summaries are NOT included in the always-on system prompt;
    they're surfaced as schemas via select_tools() when their triggers fire.
    System-only tools never appear in the prompt. This caps the always-on
    summary block at ~25-30 entries regardless of total registry size.
    """
    if not REGISTRY:
        return ""
    lines = [f"- {t.name}: {t.summary}" for t in REGISTRY.values() if tool_tier(t.name) == "core"]
    if not lines:
        return ""
    return "Tools you can call (core; more available on-demand via triggers):\n" + "\n".join(lines)


def select_tools(message: str, max_tools: int = 5) -> list[Tool]:
    """Pick up to N on-demand tools whose triggers appear in the message.

    Only ON_DEMAND tier is selectable — CORE is always sent (no need to
    select), SYSTEM_ONLY is never sent.

    v0 classifier: case-insensitive substring match on registered triggers.
    Score = number of distinct triggers that hit. Ties broken by registration
    order.
    """
    text = (message or "").lower().translate(_SMART_QUOTES)
    scored: list[tuple[int, int, Tool]] = []
    for idx, t in enumerate(REGISTRY.values()):
        if tool_tier(t.name) != "on_demand":
            continue
        hits = sum(1 for trig in t.triggers if trig in text)
        if hits:
            scored.append((-hits, idx, t))
    scored.sort()
    selected = [t for _, _, t in scored[:max_tools]]
    if selected:
        log.info("classifier selected on-demand: %s", [t.name for t in selected])
    return selected


def core_tools() -> list[Tool]:
    """Return all CORE-tier tools. Always-on for every LLM call."""
    return [t for t in REGISTRY.values() if tool_tier(t.name) == "core"]


def dispatch(
    name: str,
    arguments_json: str,
    cancel_event: threading.Event | None = None,
) -> str:
    """Run a tool by name with JSON-string arguments. Always returns a string.

    cancel_event (optional): a threading.Event that, when set, signals the
    user clicked Stop in the WarRoom UI mid-call. Behavior:
      - Pre-flight: if already set when dispatch is entered, returns a
        synthetic "[cancelled by user]" string WITHOUT calling the handler.
        Used to short-circuit a tool that was queued while the Stop click
        was still in flight.
      - Mid-tool: if the handler's signature accepts a `cancel_event` kwarg,
        the same event is passed through so the handler can honor it at
        its own checkpoints (exec_shell, browse_url, run_cc_build, etc.).
      - If the handler does NOT accept cancel_event, the dispatcher still
        runs it synchronously; the Stop click will fire on the NEXT round
        check inside agent.respond. Same behavior as before this parameter
        existed — additive, no regression.

    Hardened 2026-05-09 after forensic showed Charles repeatedly emitting
    tool_calls with missing required args (exec_shell() / self_patch() /
    append_goal_note() with no args), and trying tools that don't exist
    (append_file). All errors are returned as actionable strings so the
    model learns from them instead of looping.

    Hardened again 2026-05-09 evening after a 500-turn forensic showed the
    model doesn't remember what it already tried. The dispatcher now calls
    into core.tool_guards before and after each handler invocation:
      - blocks repeat browse_url calls to URLs that already returned
        access-denied / 404 / cloudflare-block / etc.,
      - blocks exact same-call duplicates within one respond() chain,
      - returns a content-hash signal for read_file re-reads in the same
        chain instead of re-dumping the file,
      - redirects exec_shell+sqlite3 against memory.db to recall().
    See core/tool_guards.py for the full guard set.
    """
    from core import tool_guards  # late import — avoids circular at module load

    # Pre-flight stop check — user clicked Stop while this tool call was in
    # the LLM's just-emitted message but before we got here. Short-circuit
    # without running the handler at all.
    if cancel_event is not None and cancel_event.is_set():
        return f"[cancelled by user] {name} was not run."

    t = REGISTRY.get(name)
    if t is None:
        # Suggest the closest matching real tool name so Charles fixes the typo
        # instead of hallucinating it again next round.
        names = list(REGISTRY.keys())
        close = difflib.get_close_matches(name, names, n=3, cutoff=0.5)
        suggestion = f" Did you mean: {', '.join(close)}?" if close else ""
        return f"[error] unknown tool: {name}.{suggestion} Available tools: {', '.join(sorted(names))}"

    try:
        kwargs: dict[str, Any] = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        return f"[error] bad JSON arguments to {name}: {e}. Got: {arguments_json[:200]}"

    # Pre-flight: check required args BEFORE calling the handler. Catches the
    # Qwen3.6 failure mode where the model emits e.g. exec_shell() with no
    # args; better to surface 'missing command' than a Python TypeError.
    missing = _missing_required_args(t, kwargs)
    if missing:
        required_props = (t.schema.get("required") or [])
        all_props = list((t.schema.get("properties") or {}).keys())
        return (
            f"[error] {name}() missing required argument(s): {', '.join(missing)}. "
            f"Required: {required_props or 'none'}. "
            f"All accepted args: {all_props or 'none'}. "
            f"You called it with: {list(kwargs.keys()) or 'no arguments'}. "
            f"Re-emit the tool_call with the missing arg(s) filled in."
        )

    # Behavioral guards — short-circuit on blocked URLs / repeat calls /
    # sqlite-as-memory anti-pattern / same-chain re-reads.
    guard_msg = tool_guards.check_pre_call(name, kwargs)
    if guard_msg is not None:
        log.info("guard short-circuit on %s: %s", name, guard_msg[:120])
        return guard_msg
    tool_guards.mark_in_flight(name, kwargs)

    # If the handler accepts a `cancel_event` parameter, plumb the caller's
    # event through. Handlers that don't accept it are unaffected — the
    # Stop click will fire on the next between-rounds check in agent.respond.
    if cancel_event is not None:
        handler_sig = inspect.signature(t.handler)
        if "cancel_event" in handler_sig.parameters and "cancel_event" not in kwargs:
            kwargs["cancel_event"] = cancel_event

    try:
        result = t.handler(**kwargs)
    except TypeError as e:
        # Defensive — schema-validation may pass but handler signature can
        # still mismatch. Give the model a cleaner error than a raw stack.
        sig = inspect.signature(t.handler)
        return (
            f"[error] {name}() rejected the args: {e}. "
            f"Handler signature: {name}{sig}. "
            f"You passed: {list(kwargs.keys())}."
        )
    except Exception as e:  # noqa: BLE001 — surface anything to the model
        return f"[error] {type(e).__name__} in {name}: {e}"

    out = result if isinstance(result, str) else json.dumps(result, default=str)
    tool_guards.post_call(name, kwargs, out)
    return out


def _missing_required_args(t: Tool, kwargs: dict[str, Any]) -> list[str]:
    """Return the names of required args the model didn't supply."""
    required = t.schema.get("required") or []
    return [r for r in required if r not in kwargs]


# ---------------------------------------------------------------------------
# @async_tool — fire-and-forget primitive.
#
# Generalizes the cc_runner background-thread pattern: a tool whose handler
# might take minutes to hours (CC ingest, long browse sweeps, multi-file
# refactors) shouldn't block agent.respond. The wrapped function runs in a
# daemon thread; the tool call returns a job_id immediately. Charles polls
# `async_tool_status` to check progress.
#
# Handler contract:
#   - Must accept the same kwargs as a regular @tool.
#   - MAY accept an optional `cancel_event: threading.Event` kwarg — if
#     present, the wrapper passes one in and the handler is expected to
#     check `cancel_event.is_set()` at safe checkpoints to bail early.
#   - Return value is captured into job.result. Exceptions are captured
#     into job.error and the job marked 'failed'.
#
# Jobs live in-process. After a process restart they're gone. Charles should
# treat job_ids as session-scoped, not durable across kickstarts.
# ---------------------------------------------------------------------------


@dataclass
class AsyncJob:
    job_id: str
    tool_name: str
    started_at: str
    status: str  # 'running' | 'done' | 'failed' | 'cancelled'
    result: str | None = None
    error: str | None = None
    finished_at: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)


_ASYNC_JOBS: dict[str, AsyncJob] = {}
_ASYNC_JOBS_LOCK = threading.Lock()
_ASYNC_JOB_TTL_SECONDS = 86400  # finished jobs reaped after 24h


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _reap_old_jobs() -> int:
    """Drop finished jobs whose started_at is older than the TTL."""
    cutoff = time.time() - _ASYNC_JOB_TTL_SECONDS
    dropped = 0
    with _ASYNC_JOBS_LOCK:
        for job_id, job in list(_ASYNC_JOBS.items()):
            if job.status == "running":
                continue
            try:
                started_ts = datetime.fromisoformat(
                    job.started_at.replace("Z", "+00:00")
                ).timestamp()
            except ValueError:
                continue
            if started_ts < cutoff:
                del _ASYNC_JOBS[job_id]
                dropped += 1
    return dropped


def list_async_jobs() -> list[AsyncJob]:
    """Snapshot of all known async jobs. Used by the WarRoom UI."""
    with _ASYNC_JOBS_LOCK:
        return list(_ASYNC_JOBS.values())


def async_tool(*, name: str, summary: str, schema: dict, triggers: tuple[str, ...] = ()):
    """Register a fire-and-forget tool.

    Same parameters as @tool. The wrapped function will run in a daemon
    thread; the tool call itself returns a short "started, job_id=..."
    string. Use async_tool_status to poll progress.

    Augmented summary: the registered summary is prefixed with
    "[ASYNC, returns job_id]" so Charles knows from the system prompt that
    the call won't block — he should expect a job_id back and poll, not
    wait for the result inline.
    """
    augmented_summary = f"[ASYNC, returns job_id] {summary.strip()}"

    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        sig = inspect.signature(fn)
        accepts_cancel = "cancel_event" in sig.parameters

        def wrapper(**kwargs: Any) -> str:
            _reap_old_jobs()
            job = AsyncJob(
                job_id=uuid.uuid4().hex[:8],
                tool_name=name,
                started_at=_now_iso(),
                status="running",
            )
            with _ASYNC_JOBS_LOCK:
                _ASYNC_JOBS[job.job_id] = job

            def _runner() -> None:
                call_kwargs = dict(kwargs)
                if accepts_cancel:
                    call_kwargs["cancel_event"] = job.cancel_event
                try:
                    out = fn(**call_kwargs)
                    text = out if isinstance(out, str) else json.dumps(out, default=str)
                    with _ASYNC_JOBS_LOCK:
                        # If cancel was requested mid-run, prefer that status
                        # over 'done' so the UI shows the user's intent.
                        if job.cancel_event.is_set():
                            job.status = "cancelled"
                            job.result = text
                        else:
                            job.status = "done"
                            job.result = text
                        job.finished_at = _now_iso()
                except Exception as e:  # noqa: BLE001
                    log.exception("async tool %s (job=%s) crashed", name, job.job_id)
                    with _ASYNC_JOBS_LOCK:
                        job.status = "failed"
                        job.error = f"{type(e).__name__}: {e}"
                        job.finished_at = _now_iso()

            t = threading.Thread(
                target=_runner,
                name=f"async-{name}-{job.job_id}",
                daemon=True,
            )
            t.start()
            return (
                f"started async tool {name!r}, job_id={job.job_id}. "
                f"Poll with async_tool_status(job_id='{job.job_id}'); "
                f"cancel with async_tool_cancel(job_id='{job.job_id}')."
            )

        # Mirror @tool's registration so dispatch routes through wrapper.
        return tool(
            name=name,
            summary=augmented_summary,
            schema=schema,
            triggers=triggers,
        )(wrapper)

    return decorator


@tool(
    name="async_tool_status",
    summary=(
        "Check the status of an async tool job. Returns running/done/failed/"
        "cancelled, the started/finished timestamps, and the result or error. "
        "Pass job_id from the original async tool call."
    ),
    schema={
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "The job_id returned by an async tool."},
        },
        "required": ["job_id"],
    },
    triggers=("job status", "async status", "check job", "is it done"),
)
def async_tool_status(job_id: str) -> str:
    with _ASYNC_JOBS_LOCK:
        job = _ASYNC_JOBS.get(job_id)
    if job is None:
        # Older job that aged out, or wrong id — surface known ids so Charles
        # can recover instead of looping with a stale handle.
        with _ASYNC_JOBS_LOCK:
            known = sorted(_ASYNC_JOBS.keys())[-5:]
        return (
            f"[error] no async job with id={job_id!r}. "
            f"Recent jobs in this process: {known or '(none)'}. "
            f"Jobs older than 24h are reaped, and a kickstart wipes the table."
        )
    parts = [
        f"job_id: {job.job_id}",
        f"tool: {job.tool_name}",
        f"status: {job.status}",
        f"started: {job.started_at}",
    ]
    if job.finished_at:
        parts.append(f"finished: {job.finished_at}")
    if job.error:
        parts.append(f"error: {job.error}")
    elif job.result is not None:
        snippet = job.result if len(job.result) < 800 else job.result[:800] + "…(truncated)"
        parts.append(f"result: {snippet}")
    return "\n".join(parts)


@tool(
    name="async_tool_cancel",
    summary=(
        "Request cancellation of a running async tool job. Sets the cancel "
        "flag; the job will stop at its next checkpoint IF the underlying "
        "handler honors cancel_event. If the handler doesn't check, this "
        "marks intent but the work runs to completion. Idempotent — calling "
        "twice is harmless."
    ),
    schema={
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "The job_id to cancel."},
        },
        "required": ["job_id"],
    },
    triggers=("cancel job", "stop job", "abort tool", "kill task"),
)
def async_tool_cancel(job_id: str) -> str:
    with _ASYNC_JOBS_LOCK:
        job = _ASYNC_JOBS.get(job_id)
    if job is None:
        return f"[error] no async job with id={job_id!r}."
    if job.status != "running":
        return f"job {job_id} is already {job.status} — nothing to cancel."
    job.cancel_event.set()
    return (
        f"cancellation flag set on job {job_id}. The handler will stop at "
        f"its next checkpoint if it honors cancel_event; otherwise the "
        f"thread runs to completion but will be marked 'cancelled'."
    )

