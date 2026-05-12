"""Autonomous heartbeat loop.

Three responsibilities every tick:
  1. Fire any due `scheduled_tasks` (one-shot or recurring time-based work).
  2. Advance one ripe `goal` (open-ended long-burn objectives).
  3. Poll the CLAUDE_CODE channel for builder dev-notes (throttled to 60s).

All three produce a synthetic prompt routed through the full agent. Charles
decides what concrete action to take and only notifies John when warranted.

Synthetic ticks (heartbeat tasks + goal advances) log into CHARLES_LOG —
the operational/autonomous channel. Builder dev-notes log into CLAUDE_CODE.
The goal_id / task_id is preserved in the message body so Charles knows which
scheduling event fired. Per-goal continuity is preserved via the goals table's
`notes` column, NOT a separate conv_id.
"""
from __future__ import annotations

import asyncio
import logging
import time

from core import channels, goals, scheduler

log = logging.getLogger("charles.heartbeat")

DEFAULT_TICK_SECONDS = 15

# Builder-note polling: every 60s, not every tick. Heartbeat default is 15s
# so without throttling we'd hammer the conversations table every tick for a
# channel that's quiet 99% of the time.
CLAUDE_CODE_POLL_SECONDS = 60
_last_claude_code_poll: float = 0.0


async def _run_blocking(prompt: str, conv_id: str) -> tuple[bool, str]:
    from core import agent  # late import — avoids circular at module load

    try:
        reply = await asyncio.to_thread(agent.respond, prompt, conv_id)
        return True, reply or ""
    except Exception as e:  # noqa: BLE001
        log.exception("conv=%s errored", conv_id)
        return False, f"{type(e).__name__}: {e}"


async def _fire_due_tasks() -> None:
    due = scheduler.due_tasks()
    if not due:
        return
    log.info("tick: firing %d task(s)", len(due))
    for task in due:
        scheduler.mark_running(task["id"])
        prompt = (
            f"[heartbeat task #{task['id']}] {task['description']}\n\n"
            f"This is an autonomous tick — not John talking. Decide if this "
            f"requires action. Use notify_john ONLY if John actually needs to know."
        )
        ok, result = await _run_blocking(prompt, channels.CHARLES_LOG)
        if ok:
            scheduler.mark_done(task["id"], result, task.get("cadence_seconds"))
        else:
            scheduler.mark_failed(task["id"], result)


_NARRATION_PHRASES = (
    "let me", "i'll", "i will", "i need to", "i'm going to",
    "going to write", "going to create", "going to start",
    "now i need", "now i'll", "writing the", "creating the",
    "ok, so", "alright, so", "now i have", "now let me",
    "let me check", "let me think", "let me extract", "let me try",
    "let me start by", "let me get",
)


def _count_narration_loop(notes: str) -> int:
    """Count how many recent notes look like 'I'll do X' without action.

    Only checks notes from the LAST 6 entries — older history doesn't matter.
    Lines marked with the GUARD_NOTICE marker are excluded so the guard
    doesn't trigger on its own warning text (2026-05-09 forensic showed the
    'HALLUCINATION GUARD tripped' string itself becoming a 56x loop pattern).
    """
    if not notes:
        return 0
    lines = [ln for ln in notes.split("\n") if ln.strip().startswith("[") and GUARD_NOTICE_MARKER not in ln]
    recent = lines[-6:]
    count = 0
    for line in recent:
        lower = line.lower()
        if any(phrase in lower for phrase in _NARRATION_PHRASES):
            count += 1
    return count


# Hallucination guard — known-bad terms Charles fabricates. Same logic as the
# 2026-05-08 patch but with self-marking so the guard's own prompt text
# doesn't re-trigger detection on next tick.
_HALLUCINATED_TERMS = (
    # Specific fabricated entities Charles invented in 2026-05-09 loop
    # episodes. NOT generic words like "ford" or "luxury car" — those
    # were dropped 2026-05-10 morning after a false positive on
    # legitimate psychology research mentioning the Ford Foundation.
    "tesla", "bugatti", "rivian", "larsonjuis", "larson juis",
)
GUARD_NOTICE_MARKER = "<<GUARD_NOTICE>>"


def _hallucinated_in_notes(notes: str) -> str | None:
    """Return the matched bad term if present in goal notes, ignoring guard text.

    Guard-issued lines (containing GUARD_NOTICE_MARKER) are skipped so we
    don't loop on the guard's own warning. Only checks Charles-authored notes.
    """
    if not notes:
        return None
    # Only inspect lines NOT issued by the guard itself
    lines = [ln for ln in notes.split("\n") if GUARD_NOTICE_MARKER not in ln]
    text = "\n".join(lines).lower()
    for term in _HALLUCINATED_TERMS:
        if term in text:
            return term
    return None


async def _advance_one_goal() -> None:
    ripe = goals.ripe_goals(limit=1)
    if not ripe:
        return
    goal = ripe[0]
    log.info("tick: advancing goal #%d (%s)", goal["id"], goal["description"][:60])
    notes_block = goal["notes"] or "(no notes yet — this is the first advance)"
    narration_count = _count_narration_loop(goal["notes"] or "")

    base_prompt = (
        f"[goal advance #{goal['id']}] {goal['description']}\n\n"
        f"## Progress so far\n{notes_block}\n\n"
        f"## Your job this tick\n"
    )

    hallucinated_term = _hallucinated_in_notes(goal["notes"] or "")

    if hallucinated_term:
        # Charles's own goal notes contain a known-bad term he keeps inventing.
        # Force a single-action tick: read source, log result, exit.
        log.warning("goal #%d hallucination detected (term=%r) — single-action guard tick",
                    goal["id"], hallucinated_term)
        action_prompt = (
            f"{GUARD_NOTICE_MARKER} HALLUCINATION GUARD: your goal notes contain "
            f"'{hallucinated_term}', which is NOT in any source file. This tick is "
            f"SINGLE-ACTION ONLY:\n"
            f"  Step 1: read_file the actual source path in your goal description.\n"
            f"  Step 2: pick one real numbered URL/item from that file.\n"
            f"  Step 3: process it OR log a real failure note.\n"
            f"  STOP after step 3. Do not chain 5 more tool calls. Do not say "
            f"'HALLUCINATION GUARD tripped' as your reply — just do the work and "
            f"summarize what you did in past tense (one sentence). Mention "
            f"{hallucinated_term} at your own peril; the guard re-triggers on it."
        )
    elif narration_count >= 3:
        # Charles is stuck saying "let me X" without doing X. Force the issue.
        log.warning("goal #%d narration loop detected (count=%d) — injecting strong-action prompt",
                    goal["id"], narration_count)
        action_prompt = (
            f"{GUARD_NOTICE_MARKER} NARRATION LOOP DETECTED: your last "
            f"{narration_count} notes are all 'I'll do X' or 'let me write Y' "
            f"WITHOUT actually doing it. THREE OPTIONS — pick one this tick:\n"
            f"  1. ACTUALLY DO IT NOW: call write_file/exec_shell/etc with the real content. "
            f"     If you have the content in your head, write it. If you don't, you're not "
            f"     ready to write — go to option 2 or 3.\n"
            f"  2. RESEARCH FIRST: call search_web, browse_url, or read_file ONCE, then "
            f"     summarize what you found in your final reply. NO 'let me' / 'I'll' phrases.\n"
            f"  3. CANCEL THE GOAL: call cancel_goal(goal_id={goal['id']}) — you don't have "
            f"     the runway for it right now.\n"
            f"Words like 'let me', 'I will', 'writing the', 'going to' are FORBIDDEN in your "
            f"reply this tick. Past-tense only ('I wrote', 'I read', 'I found') OR direct "
            f"action verbs in tool_calls. No more declarations of intent."
        )
    else:
        action_prompt = (
            f"Take ONE concrete step toward this goal right now: read a file, write a file, "
            f"schedule a subtask, save a fact, anything actionable. Your final plain-text reply "
            f"will be AUTO-LOGGED as the next progress note for this goal — so write it as ONE "
            f"sentence describing what you DID this tick (past tense) and what the next concrete "
            f"step is. If the goal is fully complete, call `complete_goal(goal_id={goal['id']}, "
            f"summary=...)` instead. Do NOT call notify_john unless the goal actually finished — "
            f"silent ticks are correct."
        )

    prompt = base_prompt + action_prompt
    goals.mark_advanced(goal["id"])  # mark before running so a slow run doesn't double-fire
    ok, reply = await _run_blocking(prompt, channels.CHARLES_LOG)

    # Auto-append the final reply as a progress note so progress survives even if
    # Charles forgets to call append_goal_note. Skip if the goal got completed/cancelled
    # this turn (status flipped) — its notes already got the completion summary.
    if ok and reply.strip():
        latest = goals.get_goal(goal["id"])
        if latest and latest["status"] == "active":
            note = reply.strip()
            if len(note) > 500:
                note = note[:500] + "…"
            goals.append_note(goal["id"], note)


def _unanswered_claude_code_turns(limit: int = 5) -> list[dict]:
    """Return user-role turns on the CLAUDE_CODE channel with no later assistant turn.

    A turn is "unanswered" if its id is greater than the most recent assistant
    turn on the same conv_id. This means after agent.respond fires on a note
    and appends an assistant turn, that note drops out of the result set
    automatically — no separate state file needed.

    Returned oldest-first so Charles processes builder notes in dispatch order.
    """
    from core.memory import _conn
    with _conn() as c:
        rows = c.execute(
            """
            SELECT id, content
              FROM conversations
             WHERE conversation_id = ?
               AND role = 'user'
               AND id > COALESCE(
                   (SELECT MAX(id) FROM conversations
                     WHERE conversation_id = ? AND role = 'assistant'),
                   0
               )
             ORDER BY id ASC
             LIMIT ?
            """,
            (channels.CLAUDE_CODE, channels.CLAUDE_CODE, limit),
        ).fetchall()
    return [{"id": r["id"], "content": r["content"]} for r in rows]


async def _poll_claude_code() -> None:
    """Dispatch any unread builder dev-notes on the CLAUDE_CODE channel.

    Throttled to CLAUDE_CODE_POLL_SECONDS so this query runs at most once a
    minute, even though the heartbeat ticks every 15s. Processes up to 5 notes
    per poll — if Claude Code stacked more, the next poll handles them.
    """
    global _last_claude_code_poll
    now = time.monotonic()
    if now - _last_claude_code_poll < CLAUDE_CODE_POLL_SECONDS:
        return
    _last_claude_code_poll = now

    try:
        pending = _unanswered_claude_code_turns(limit=5)
    except Exception:  # noqa: BLE001
        log.exception("claude_code poll: db query failed")
        return

    if not pending:
        return

    log.info("claude_code: processing %d builder note(s)", len(pending))
    for note in pending:
        prompt = (
            f"[builder dev-note from Claude Code, id={note['id']}]\n\n"
            f"{note['content']}\n\n"
            f"This is NOT John talking. It's a technical hand-off from Claude "
            f"Code (the harness AI that helps John build YOU). Read it, "
            f"integrate anything actionable (a memory fact, a behavior tweak, "
            f"a retry of something that failed), and reply with a SHORT "
            f"acknowledgment of what you took from it. Do NOT notify John "
            f"unless the note explicitly asks you to. Do NOT speak in voice "
            f"— this channel is silent."
        )
        ok, _result = await _run_blocking(prompt, channels.CLAUDE_CODE)
        if not ok:
            # Don't keep retrying the same note in a tight loop — stop the
            # batch and let the next poll re-attempt after 60s.
            log.warning("claude_code: respond failed on note id=%d; stopping batch", note["id"])
            break


async def _tick() -> None:
    await _fire_due_tasks()
    await _advance_one_goal()
    await _poll_claude_code()


async def loop(period_seconds: int = DEFAULT_TICK_SECONDS) -> None:
    log.info("heartbeat starting; period=%ds", period_seconds)
    while True:
        try:
            await _tick()
        except Exception:  # noqa: BLE001
            log.exception("heartbeat tick failed")
        await asyncio.sleep(period_seconds)
