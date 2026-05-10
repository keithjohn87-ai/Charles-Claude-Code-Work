"""Single-conversation reasoning with multi-round tool calls and persistent memory.

M2: every turn loads the last few user/assistant exchanges for the same
conversation_id from SQLite and prepends them to the prompt. Each user
message and final assistant reply is also persisted, so Charles is
continuous across Telegram messages — not a goldfish.
"""
from __future__ import annotations

import logging
import re
import threading

import tools  # noqa: F401  — import side-effect: registers all tools

from core import memory
from core.inference import complete
from core.prompts import build_system_prompt
from core.tools import REGISTRY, dispatch  # select_tools still in core.tools, kept for future

log = logging.getLogger("charles.agent")

# In-flight cancellation registry — keyed by conversation_id. When a user
# clicks "Stop" in the WarRoom UI, the server calls request_stop(conv_id),
# which sets the Event. The respond() loop checks between tool rounds and
# exits cleanly with a "stopped by user" marker.
#
# Note: this can't kill an in-progress MLX generation mid-token — the current
# round's complete() call has to finish. But it WILL prevent the next round
# from running, so a runaway tool chain stops within one round (~5-30 sec).
_in_flight_stops: dict[str, threading.Event] = {}
_in_flight_lock = threading.Lock()


def request_stop(conversation_id: str) -> bool:
    """Signal the in-flight respond() for this conv to exit at the next checkpoint.
    Returns True if a respond() was registered to receive it."""
    with _in_flight_lock:
        ev = _in_flight_stops.get(conversation_id)
        if ev:
            ev.set()
            return True
    return False


def is_stop_pending(conversation_id: str | None) -> bool:
    if not conversation_id:
        return False
    with _in_flight_lock:
        ev = _in_flight_stops.get(conversation_id)
    return bool(ev and ev.is_set())

MAX_TOOL_ROUNDS = 25
HISTORY_CHAR_BUDGET = 4000

# Intra-call repetition guard: if the assistant emits substantially identical
# content (>= this ratio) in 2 of the last 3 rounds within a SINGLE respond()
# call, exit the loop early and surface a clear breakage marker. Catches the
# 2026-05-09 "**Test** (after ~5 min):" 108x intra-call loops where the
# between-call trim never fires because the model never returns to the user.
_INTRA_CALL_REPETITION_THRESHOLD = 0.85
_INTRA_CALL_REPETITION_WINDOW = 3


def _intra_call_loop_detected(recent_assistant_texts: list[str]) -> str | None:
    """Return a description of the loop if 2+ of last N assistant texts are near-identical."""
    if len(recent_assistant_texts) < _INTRA_CALL_REPETITION_WINDOW:
        return None
    window = recent_assistant_texts[-_INTRA_CALL_REPETITION_WINDOW:]
    pairs_above = 0
    for i in range(len(window)):
        for j in range(i + 1, len(window)):
            a, b = window[i].strip(), window[j].strip()
            if not a or not b:
                continue
            if a == b:
                pairs_above += 1
                continue
            # Cheap similarity: shared first-50-char prefix is the strong signal
            if a[:50] == b[:50]:
                pairs_above += 1
                continue
            # Fall back to set-of-words Jaccard on first 200 chars
            sa, sb = set(a[:200].lower().split()), set(b[:200].lower().split())
            if sa and sb and len(sa & sb) / max(len(sa | sb), 1) >= _INTRA_CALL_REPETITION_THRESHOLD:
                pairs_above += 1
    return f"intra-call repetition: {pairs_above}/{len(window)} pairs near-identical" if pairs_above >= 1 else None


def respond(message: str, conversation_id: str | None = None) -> str:
    # Register a stop event for this conv so request_stop() can cancel us
    stop_event: threading.Event | None = None
    if conversation_id:
        with _in_flight_lock:
            stop_event = threading.Event()
            _in_flight_stops[conversation_id] = stop_event
    # Tell the tool-call guards a fresh respond chain is starting — clears
    # the in-flight dedup set + recent-reads cache for this call. The
    # per-conv URL block-list persists across calls (a goal that retries
    # ResearchGate across 5 ticks should still hit the block-list).
    from core import tool_guards
    tool_guards.respond_started(conversation_id)
    try:
        return _respond_impl(message, conversation_id, stop_event)
    finally:
        tool_guards.respond_finished()
        # Clean up the stop registration so it doesn't leak across calls
        if conversation_id:
            with _in_flight_lock:
                if _in_flight_stops.get(conversation_id) is stop_event:
                    del _in_flight_stops[conversation_id]


def _respond_impl(message: str, conversation_id: str | None, stop_event: threading.Event | None) -> str:
    system = build_system_prompt()
    history: list[dict] = [{"role": "system", "content": system}]

    if conversation_id:
        # Behavioral pre-flight: check the tail of the conversation for a
        # response loop (last 3 assistant turns near-identical). If found,
        # nuke the poisoned tail BEFORE loading history. Prevents the
        # 2026-05-09 "**Test**" loop from re-occurring in any conv.
        try:
            trimmed = memory.trim_repeating_replies(conversation_id)
            if trimmed:
                log.warning("loop-recovery: trimmed %d turns from conv=%s before this run", trimmed, conversation_id)
        except Exception as e:  # noqa: BLE001
            log.exception("loop-recovery check failed (continuing): %s", e)

        prior = memory.recent_history(conversation_id, max_chars=HISTORY_CHAR_BUDGET)
        history.extend(prior)
        log.info("loaded %d prior turns for conv=%s", len(prior), conversation_id)

    history.append({"role": "user", "content": message})

    if conversation_id:
        memory.log_turn(conversation_id, "user", message)

    # Send all registered tool schemas every turn. Total schema cost at M2 is
    # ~200 tokens — worth it to eliminate the "tool present but not loaded"
    # failure mode where the model narrates a call as text instead of emitting
    # a real tool_call. When the toolset grows past ~10, reintroduce
    # select_tools gating.
    api_tools = [t.openai_schema() for t in REGISTRY.values()] or None

    total_chars = sum(len(m.get("content") or "") for m in history)
    log.info(
        "respond start: prompt_chars=%d turns_in_prompt=%d tools=%s",
        total_chars,
        len(history) - 1,
        [t.name for t in REGISTRY.values()],
    )

    final_text = ""
    recent_assistant_texts: list[str] = []  # for intra-call loop detection
    for round_n in range(MAX_TOOL_ROUNDS):
        # User-initiated stop check — fires between rounds (covers multi-tool chains).
        if stop_event and stop_event.is_set():
            log.warning("respond() stopped by user request at round %d (conv=%s)", round_n, conversation_id)
            final_text = "(stopped by you)"
            if conversation_id:
                memory.log_turn(conversation_id, "assistant", final_text)
            return final_text
        # max_tokens=4000: tool_call args can carry long write_file content
        # (e.g., a multi-page analysis). 800 was truncating Charles mid-write.
        text, msg, usage = complete(history, tools=api_tools, max_tokens=4000)
        log.info(
            "round=%d usage=%s tool_calls=%d",
            round_n,
            usage,
            len(msg.tool_calls or []),
        )

        # Post-complete stop check — catches Stop button clicked DURING the
        # LLM generation. MLX call already finished (can't kill mid-token),
        # but we discard the result so the user gets a clean stop marker
        # rather than the unwanted reply.
        if stop_event and stop_event.is_set():
            log.warning("stop fired during round %d's complete() — discarding generated text", round_n)
            partial = (text or "").strip()[:120]
            final_text = (
                f"(stopped by you — partial reply discarded: \"{partial}…\")"
                if partial else "(stopped by you)"
            )
            if conversation_id:
                memory.log_turn(conversation_id, "assistant", final_text)
            return final_text

        # Track each round's assistant text for intra-call repetition guard
        round_text = (msg.content or "").strip()
        if round_text:
            recent_assistant_texts.append(round_text)

        if not msg.tool_calls:
            final_text = text
            break

        # Intra-call loop guard — abort early before logging dozens of
        # identical turns. The forensic showed Charles emitting "**Test**
        # (after ~5 min):" 108 times in one tool chain on 2026-05-09.
        loop_reason = _intra_call_loop_detected(recent_assistant_texts)
        if loop_reason and round_n >= _INTRA_CALL_REPETITION_WINDOW - 1:
            log.warning("intra-call loop ABORTED at round %d (%s)", round_n, loop_reason)
            final_text = (
                f"(loop-detected at round {round_n}: {loop_reason} — "
                f"breaking out so the next tick starts fresh)"
            )
            if conversation_id:
                memory.log_turn(conversation_id, "assistant", final_text)
                # Also save an audit fact so we can see how often this fires
                try:
                    memory.add_fact(
                        f"Intra-call loop guard fired in conv {conversation_id} at round {round_n}: "
                        f"{loop_reason}. Last text: {round_text[:200]}",
                        tags="incident,intra_call_loop,auto",
                    )
                except Exception:  # noqa: BLE001
                    pass
            return final_text

        tool_calls_payload = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
        history.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": tool_calls_payload,
        })
        if conversation_id:
            memory.log_assistant_tool_calls(conversation_id, msg.content or "", tool_calls_payload)

        for tc in msg.tool_calls:
            result = dispatch(tc.function.name, tc.function.arguments)
            log.info(
                "tool=%s args=%r result_chars=%d",
                tc.function.name,
                tc.function.arguments[:200],
                len(result),
            )
            history.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
            if conversation_id:
                memory.log_tool_result(conversation_id, tc.id, result)
    else:
        final_text = text or "(this tick used the full tool budget — work continues next tick)"

    if conversation_id and final_text:
        memory.log_turn(conversation_id, "assistant", final_text)
        # Auto-extract tasks from the reply so they surface in the Tasks tab.
        # Only fires for human-conv replies (not goal: or heartbeat: ticks).
        try:
            _autoextract_tasks(final_text, conversation_id)
        except Exception as e:  # noqa: BLE001
            log.warning("task auto-extract failed (non-fatal): %s", e)

    return final_text


# Patterns that indicate Charles is asking John to do something concrete.
# These run on his FINAL reply only (not tool-chain rounds), so we don't
# spam tasks for every "let me think about that" intermediate turn.
_TASK_PATTERNS = [
    # "I need you to X" — strong direct ask
    re.compile(r"(?:^|[\.!\?\n])\s*[Ii]\s+need\s+you\s+to\s+([^\.!\?\n]{6,140})", re.MULTILINE),
    # "You'll need to X" / "You need to X"
    re.compile(r"(?:^|[\.!\?\n])\s*[Yy]ou(?:'ll)?\s+need\s+to\s+([^\.!\?\n]{6,140})", re.MULTILINE),
    # "Please X" — start-of-sentence verb
    re.compile(r"(?:^|[\.!\?\n])\s*[Pp]lease\s+([a-z][^\.!\?\n]{6,140})", re.MULTILINE),
    # "Can you X?" — request form
    re.compile(r"(?:^|[\.!\?\n])\s*[Cc]an\s+you\s+([^\?\.\n]{6,140})\?", re.MULTILINE),
    # "Could you X?" — softer request
    re.compile(r"(?:^|[\.!\?\n])\s*[Cc]ould\s+you\s+([^\?\.\n]{6,140})\?", re.MULTILINE),
    # "Waiting on you to X" / "Waiting for you to X"
    re.compile(r"[Ww]aiting\s+(?:on|for)\s+you\s+(?:to\s+)?([^\.!\?\n]{6,140})", re.MULTILINE),
]
# Convs where auto-extract is allowed. Heuristic: human-named conv ids (numeric
# Telegram IDs, or anything not starting with goal:/heartbeat:/sunday_test_/
# warroom-).
_AUTOEXTRACT_SKIP_PREFIXES = ("goal:", "heartbeat:", "sunday_test_", "warroom-", "stress_", "smoketest", "post_patch")


def _autoextract_tasks(reply_text: str, conversation_id: str) -> int:
    """Scan a final assistant reply for task-language; create tasks for matches.
    Returns the count of tasks created. No-ops on goal/heartbeat conv_ids."""
    if any(conversation_id.startswith(p) for p in _AUTOEXTRACT_SKIP_PREFIXES):
        return 0
    if not reply_text or len(reply_text) < 6:
        return 0
    seen: set[str] = set()
    created = 0
    for pattern in _TASK_PATTERNS:
        for match in pattern.finditer(reply_text):
            phrase = match.group(1).strip().rstrip(",;:")
            phrase_key = phrase.lower()[:80]
            if phrase_key in seen:
                continue
            seen.add(phrase_key)
            # Drop trivially short or punctuation-only matches
            if len(phrase) < 6 or not any(c.isalpha() for c in phrase):
                continue
            title = phrase[:120].rstrip()
            try:
                memory.add_task(
                    title=title,
                    description=f"Auto-extracted from Charles's reply in conv {conversation_id}.",
                    urgency="normal",
                    source="auto_extracted",
                    source_conv=conversation_id,
                )
                created += 1
            except Exception as e:  # noqa: BLE001
                log.warning("add_task failed for phrase %r: %s", title, e)
    if created:
        log.info("auto-extracted %d task(s) from reply in conv=%s", created, conversation_id)
    return created
