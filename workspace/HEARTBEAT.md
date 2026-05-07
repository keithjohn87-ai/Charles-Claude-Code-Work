# HEARTBEAT — Autonomous Tick Operations

A 15-second tick runs in the background of every Charles process (PID under `com.charles.agent`). Each tick does two things, in order:

1. **Fire any due scheduled tasks** (`scheduler.due_tasks()`)
2. **Advance one ripe goal** (`goals.ripe_goals(limit=1)`)

Both produce a synthetic prompt routed through the full agent. You decide what concrete action to take.

## When a scheduled task fires

The synthetic prompt looks like:
```
[heartbeat task #N] {description}

This is an autonomous tick — not John talking. Decide if this requires action.
Use notify_john ONLY if John actually needs to know.
```

Conversation id: `heartbeat:<task_id>` (isolated from John's main thread).

## When a goal advances

The synthetic prompt looks like:
```
[goal advance #N] {description}

## Progress so far
{notes}

## Your job this tick
Take ONE concrete step toward this goal right now: read a file, write a file,
schedule a subtask, save a fact, anything actionable. Then call
append_goal_note(goal_id=N, note=...) with one sentence describing what
you did and what the next step is. If the goal is fully complete, call
complete_goal(goal_id=N, summary=...). Do NOT call notify_john unless
the goal actually finished — silent ticks are correct.
```

Conversation id: `goal:<goal_id>` (stable across ticks for that goal — you can build on prior context).

## Discipline on heartbeat ticks

- **Silence is the default.** If a tick produces nothing material, don't ping John. The migration says: passive heartbeats are failures only when there's pending work and you don't execute. A correctly empty tick is fine.
- **No narration in notify_john.** "Still working" is noise. "Builds passing" is noise. Only ping for: deliverable done, hard blocker, financial decision, time-sensitive event.
- **Use append_goal_note every advance.** Future-you (next tick) reads those notes to know where you were. If you don't log progress, every tick starts from scratch.
- **Mark goals complete.** Goals that drift forever clog the queue. When a goal is done, call `complete_goal` with a one-sentence summary.

## When to set a goal vs schedule a task

| Use case | Tool |
|---|---|
| One-off action at a specific time | `schedule_task(in_seconds=X)` |
| Recurring action on cadence | `schedule_task(cadence_seconds=X)` |
| Open-ended objective spanning many turns | `set_goal(advance_minutes=X)` |
| One-shot work that doesn't need timing | Just do it now in conversation |

## Watchdog

`com.charles.watchdog` runs separately. Every 30s it checks:
- Is `python.*charles.py` alive? (pgrep)
- Has `logs/charles.launchd.out.log` been touched in the last 5 min? (heartbeat freshness)

If either fails: `launchctl kickstart -k` forces a clean restart. After 5 consecutive failed restarts, watchdog escalates to John via Telegram alert.

You don't need to do anything for the watchdog. It's outside your process. Just don't wedge for 5+ minutes.

## Scheduled task examples

```python
# Daily 6 AM Dundalk weather report (already scheduled — task #9)
schedule_task(
    description="Send John a morning weather report for Dundalk, MD via notify_john.",
    at_iso="2026-05-08T10:00:00Z",
    cadence_seconds=86400,
)

# Hourly self-health log
schedule_task(
    description="Append a one-line health summary to workspace/health.log: process uptime, memory.db size, active goals count.",
    in_seconds=3600,
    cadence_seconds=3600,
)
```

## Goal examples

```python
# A multi-week build goal
set_goal(
    description="Read MASTER_OPERATING_MANUAL.md once a week and summarize what's drifted vs current state. Save observations as remembered facts tagged 'mom-drift'.",
    advance_minutes=10080,  # weekly
)
```

🌊
