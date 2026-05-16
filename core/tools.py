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
from typing import Any, Callable, Literal

log = logging.getLogger("charles.tools")


# ─────────────────────────────────────────────────────────────────────────────
# ToolResult envelope (added 2026-05-14 per Charles Harness Audit Fix #1).
#
# All dispatch() returns are now serialized JSON of this shape:
#   {"status": "ok"|"error"|"cancelled"|"blocked", "message": "...",
#    "data": <any, optional>, "category": "...optional..."}
#
# Why: the model previously saw bare prose strings (sometimes "[error] foo",
# sometimes plain content, sometimes JSON-dumped dicts) and had to GUESS
# whether a tool call succeeded. That ambiguity caused mid-chain cascades —
# tool A returns the word "error" inside a successful result, model
# misinterprets it as a failure, retries tool B uselessly. With a structured
# envelope, the model gets an explicit status flag every time.
#
# Backwards compatibility (critical):
#   • Tool HANDLERS still return strings (or dicts, or whatever). They don't
#     need to know about ToolResult. The dispatcher wraps them via
#     ToolResult.from_legacy_str() — preserving the existing convention that
#     "[error] X" / "[blocked] Y" / "[cancelled by user] Z" map to their
#     respective statuses, while everything else is treated as "ok" data.
#   • tool_guards.post_call() still receives the LEGACY string form (it does
#     regex matching on the body, e.g. _BLOCKED_HEADER_RE on browse_url
#     results). We feed it the pre-envelope string before serializing.
#   • Agent.respond() parses the envelope at dispatch return and renders a
#     human-readable form for history (e.g. "[ok] ...\n<data>" or
#     "[error:validation] foo"). The model sees a consistent prefix every
#     turn — status tag at the start, never buried.
# ─────────────────────────────────────────────────────────────────────────────

_STATUS_LITERAL = Literal["ok", "error", "cancelled", "blocked"]


@dataclass
class ToolResult:
    status: _STATUS_LITERAL
    message: str = ""
    data: Any = None
    # `category` is for status=error; Fix #2 will populate it
    # (validation / blocked / network / timeout / internal). Empty for now;
    # validation errors raised in dispatch are pre-tagged so the data path
    # is exercised end-to-end before Fix #2 fully arrives.
    category: str = ""

    def to_json(self) -> str:
        d: dict[str, Any] = {"status": self.status, "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        if self.category:
            d["category"] = self.category
        return json.dumps(d, default=str)

    @classmethod
    def from_legacy_str(cls, s: str) -> "ToolResult":
        """Promote a legacy handler-string into a ToolResult.

        Existing tool handlers historically prefix their string returns with
        "[error]" / "[blocked]" / "[cancelled by user]" or return plain
        content. This adapter preserves that convention so we can ship the
        envelope without touching any of the 78 individual tool handlers.
        """
        if not isinstance(s, str):
            return cls(status="ok", data=s, message="")
        if s.startswith("[error]"):
            return cls(status="error", message=s[len("[error]"):].strip())
        if s.startswith("[blocked]"):
            return cls(status="blocked", message=s[len("[blocked]"):].strip())
        if s.startswith("[cancelled"):
            close = s.find("]")
            tail = s[close + 1:].strip() if close != -1 else s
            return cls(status="cancelled", message=tail)
        return cls(status="ok", data=s, message="")

    @classmethod
    def parse(cls, s: str) -> "ToolResult":
        """Inverse of to_json — used by agent.py to read dispatch's return.

        Falls back to from_legacy_str() if the input isn't a valid envelope,
        so any future code path that bypasses dispatch (or any leftover
        legacy persisted result loaded from old conversation history) still
        renders cleanly.
        """
        if not isinstance(s, str):
            return cls(status="ok", data=s, message="")
        try:
            d = json.loads(s)
        except (json.JSONDecodeError, TypeError, ValueError):
            return cls.from_legacy_str(s)
        if not isinstance(d, dict) or "status" not in d:
            return cls.from_legacy_str(s)
        return cls(
            status=d.get("status", "ok"),
            message=d.get("message", ""),
            data=d.get("data"),
            category=d.get("category", ""),
        )

    def render(self) -> str:
        """Human-readable form for the model's tool-history view.

        The status tag ALWAYS appears at the start of the rendered text —
        even for status=ok with just data — so the model has an unambiguous
        success/failure signal on every tool result, no inference required.
        This is the whole point of Fix #1.
        """
        if self.status == "error" and self.category:
            prefix = f"[error:{self.category}]"
        else:
            prefix = f"[{self.status}]"
        head = f"{prefix} {self.message}".rstrip() if self.message else prefix
        if self.data is None:
            return head
        if isinstance(self.data, str):
            body = self.data
        else:
            try:
                body = json.dumps(self.data, default=str)
            except (TypeError, ValueError):
                body = str(self.data)
        # If there's no message and the body already starts with a status
        # marker (e.g. "[cached read_file]" from the guard cache hit, or
        # the legacy "[error]" prefix that from_legacy_str()'s caller may
        # have already stripped), avoid double-prefixing. Otherwise the
        # tag goes at the front of the body for an unambiguous status.
        if not self.message and isinstance(self.data, str) and body.startswith("["):
            return body
        return f"{head}\n{body}"


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
    # Lightweight session-scoped todo list (Claude Code's TodoWrite, ported
    # 2026-05-16). Distinct from set_goal/add_task — in-session planning
    # for the current chain only. CORE so it's always available to plan
    # before multi-step work fires off.
    "todo_set", "todo_get",
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


def _estimate_schema_tokens(schema: dict) -> int:
    """Rough token count for a tool's JSON schema.

    Anthropic / OpenAI tokenization is ~3.5–4 chars per token for code+JSON.
    We use 4 — slightly aggressive (under-counts) on average, which means
    actual prompt size lands a bit below budget. That's the safe direction.
    """
    try:
        return len(json.dumps(schema, default=str)) // 4
    except (TypeError, ValueError):
        return 200  # conservative fallback for un-serializable schemas


def select_tools(
    message: str,
    max_tools: int = 5,
    schema_token_budget: int | None = None,
) -> list[Tool]:
    """Pick up to N on-demand tools whose triggers appear in the message.

    Only ON_DEMAND tier is selectable — CORE is always sent (no need to
    select), SYSTEM_ONLY is never sent.

    v0 classifier: case-insensitive substring match on registered triggers.
    Score = number of distinct triggers that hit. Ties broken by registration
    order.

    `schema_token_budget` (added 2026-05-14 per Harness Fix #3): if supplied,
    drop tools from the tail of the ranked list once their cumulative schema
    size exceeds the budget. Without it, behavior is unchanged from the
    pre-Fix-#3 cap-by-count classifier — backwards-compatible default.

    The agent loop should pass a tighter budget for short / relational
    messages (e.g. 1500 tokens for <200-char user messages) and a looser
    budget for autonomous-channel chains (3000 tokens). The 78-tool
    registry was costing ~15.6k tokens of overhead per turn before this
    cap landed.
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

    selected: list[Tool] = []
    cumulative_tokens = 0
    dropped_to_budget: list[str] = []
    for _, _, t in scored:
        if len(selected) >= max_tools:
            break
        if schema_token_budget is not None:
            t_tokens = _estimate_schema_tokens(t.schema)
            if cumulative_tokens + t_tokens > schema_token_budget:
                dropped_to_budget.append(t.name)
                continue
            cumulative_tokens += t_tokens
        selected.append(t)

    if selected:
        log.info(
            "classifier selected on-demand: %s (~%d tokens, budget=%s)",
            [t.name for t in selected],
            cumulative_tokens,
            schema_token_budget,
        )
    if dropped_to_budget:
        log.info(
            "classifier dropped to fit token budget: %s",
            dropped_to_budget,
        )
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
        return ToolResult(
            status="cancelled",
            message=f"{name} was not run.",
        ).to_json()

    t = REGISTRY.get(name)
    if t is None:
        # Suggest the closest matching real tool name so Charles fixes the typo
        # instead of hallucinating it again next round.
        names = list(REGISTRY.keys())
        close = difflib.get_close_matches(name, names, n=3, cutoff=0.5)
        suggestion = f" Did you mean: {', '.join(close)}?" if close else ""
        return ToolResult(
            status="error",
            category="validation",
            message=(
                f"unknown tool: {name}.{suggestion} "
                f"Available tools: {', '.join(sorted(names))}"
            ),
        ).to_json()

    try:
        kwargs: dict[str, Any] = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        return ToolResult(
            status="error",
            category="validation",
            message=f"bad JSON arguments to {name}: {e}. Got: {arguments_json[:200]}",
        ).to_json()

    # Pre-flight: check required args BEFORE calling the handler. Catches the
    # Qwen3.6 failure mode where the model emits e.g. exec_shell() with no
    # args; better to surface 'missing command' than a Python TypeError.
    missing = _missing_required_args(t, kwargs)
    if missing:
        required_props = (t.schema.get("required") or [])
        all_props = list((t.schema.get("properties") or {}).keys())
        return ToolResult(
            status="error",
            category="validation",
            message=(
                f"{name}() missing required argument(s): {', '.join(missing)}. "
                f"Required: {required_props or 'none'}. "
                f"All accepted args: {all_props or 'none'}. "
                f"You called it with: {list(kwargs.keys()) or 'no arguments'}. "
                f"Re-emit the tool_call with the missing arg(s) filled in."
            ),
        ).to_json()

    # Behavioral guards — short-circuit on blocked URLs / repeat calls /
    # sqlite-as-memory anti-pattern / same-chain re-reads.
    #
    # check_pre_call now returns (message, category) per Harness Fix #2
    # (2026-05-14). For real guard blocks, category="blocked" — we tag
    # the ToolResult so the model can distinguish retriable from non-
    # retriable on its own. Cached-read hits return category="" because
    # they are NOT errors; from_legacy_str maps them to status=ok via
    # the absence of an "[error]" prefix.
    guard_result = tool_guards.check_pre_call(name, kwargs)
    if guard_result is not None:
        guard_msg, guard_category = guard_result
        log.info("guard short-circuit on %s: %s", name, guard_msg[:120])
        envelope = ToolResult.from_legacy_str(guard_msg)
        # Attach category only when it would carry signal (guard says
        # "blocked" / "validation" etc.). Successful cache hits get no
        # category — the model reads them as plain success.
        if guard_category and envelope.status == "error":
            envelope.category = guard_category
        elif guard_category == "blocked" and envelope.status == "blocked":
            # legacy "[blocked]" prefix already conveys status; surface
            # category too in case the message body has more nuance later.
            envelope.category = guard_category
        return envelope.to_json()
    tool_guards.mark_in_flight(name, kwargs)

    # If the handler accepts a `cancel_event` parameter, plumb the caller's
    # event through. Handlers that don't accept it are unaffected — the
    # Stop click will fire on the next between-rounds check in agent.respond.
    if cancel_event is not None:
        handler_sig = inspect.signature(t.handler)
        if "cancel_event" in handler_sig.parameters and "cancel_event" not in kwargs:
            kwargs["cancel_event"] = cancel_event

    handler_raw: Any
    try:
        handler_raw = t.handler(**kwargs)
    except TypeError as e:
        # Defensive — schema-validation may pass but handler signature can
        # still mismatch. category=validation tells the model "fix args and
        # retry" rather than "give up" or "retry blindly."
        sig = inspect.signature(t.handler)
        handler_raw = ToolResult(
            status="error",
            category="validation",
            message=(
                f"{name}() rejected the args: {e}. "
                f"Handler signature: {name}{sig}. "
                f"You passed: {list(kwargs.keys())}."
            ),
        )
    except Exception as e:  # noqa: BLE001 — surface anything to the model
        # category=internal tells the model "the tool is broken; report it
        # to John rather than retrying." Per Harness Fix #2 system prompt.
        handler_raw = ToolResult(
            status="error",
            category="internal",
            message=f"{type(e).__name__} in {name}: {e}",
        )

    # tool_guards.post_call() does regex matching on the result (e.g.
    # _BLOCKED_HEADER_RE on browse_url output, "[error]"/"[cached" prefix
    # checks on read_file). Feed it the LEGACY string form before we wrap
    # in an envelope, so its existing logic keeps working unchanged.
    legacy_str = (
        handler_raw
        if isinstance(handler_raw, str)
        else (
            handler_raw.render()
            if isinstance(handler_raw, ToolResult)
            else json.dumps(handler_raw, default=str)
        )
    )
    tool_guards.post_call(name, kwargs, legacy_str)

    # Wrap into envelope on the way out. Handlers that already produce a
    # ToolResult (future ones — none today) pass through; legacy strings
    # are promoted; everything else is treated as "ok" with the value in
    # data so the model can introspect.
    if isinstance(handler_raw, ToolResult):
        return handler_raw.to_json()
    if isinstance(handler_raw, str):
        return ToolResult.from_legacy_str(handler_raw).to_json()
    return ToolResult(status="ok", data=handler_raw, message="").to_json()


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

