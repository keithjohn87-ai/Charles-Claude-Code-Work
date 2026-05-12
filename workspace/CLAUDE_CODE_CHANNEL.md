# CLAUDE_CODE channel — builder dev-notes

A third Charles conversation channel for **builder dev-notes** from Claude
Code (the harness AI that helps John build Charles). Separate from
JOHN_CHARLES (relational thread John sees) and CHARLES_LOG (Charles's own
autonomous tick narration).

## Why a separate channel

Builder notes are technical hand-offs: file paths, diffs, reasoning about
Charles's own code, smoke test results, "your last reflection had bug X,
the fix is Y." Three reasons this can't share a channel:

- **JOHN_CHARLES** is John's relational thread. Routing builder notes there
  pollutes his view with implementation detail and burns voice synthesis on
  text he doesn't need to hear.
- **CHARLES_LOG** is Charles's own autonomous tick narration. Mixing inbound
  builder notes with outbound self-narration confuses both — Charles can't
  cleanly tell "this is from me" vs "this is from the builder."
- **A new channel** keeps each stream coherent and lets the polling cadence
  be independent (builder polled every 60s; goals + scheduled tasks every
  15s).

## How it works

1. **Dispatch** (Claude Code → memory.db):

   ```bash
   python scripts/claude_code_dispatch.py "your note here"
   echo "long body"   | python scripts/claude_code_dispatch.py -
   python scripts/claude_code_dispatch.py --file path/to/note.md
   ```

   The script writes the body as a `user`-role turn to conv_id=`claude_code`
   in memory.db. It's a CLI, NOT a Charles-callable `@tool`, so it sits in
   `scripts/` (avoiding `tools/__init__.py`'s eager package import).

2. **Polling** (heartbeat → respond):

   `core/heartbeat._poll_claude_code` runs every 60s (throttled inside
   the 15s default tick). For each user-role turn on `claude_code` that has
   no subsequent assistant turn, it calls `agent.respond` with a framing
   prompt that:

   - Identifies the note as "NOT John talking" (technical hand-off).
   - Tells Charles to integrate anything actionable and reply with a SHORT
     acknowledgment.
   - Forbids `notify_john` unless the note explicitly asks for it.
   - Forbids voice synthesis on this channel.

   The unanswered-turn query is stateless: "user turn with id greater than
   the most recent assistant turn on the same conv_id." After respond fires
   and writes an assistant turn, the note drops out of the result set
   automatically — no separate state file.

3. **Routing** (`core/channels.py`):

   `CLAUDE_CODE = "claude_code"`. `normalize()` and `is_builder_notes()`
   recognize it as a real channel (not auto-routed to JOHN_CHARLES like an
   unrecognized conv_id would be).

## Hard rules

- **Never use this channel for John-facing content.** If a note triggers
  something John needs to know, Charles should call `notify_john` (or send
  iMessage). The channel itself is silent to John.
- **Notes are one-way Builder→Charles.** Charles's acks are stored for
  audit but aren't read back by Claude Code (that's what the iMessage
  channel is for).
- **One-shot, idempotent-ish.** A duplicate note will be processed twice.
  Don't dispatch the same note in a retry loop unless you mean it.

## Example flow

```text
$ python scripts/claude_code_dispatch.py \
    "Wired up new @async_tool decorator at core/tools.py:118. Test it on the
     next reflection — if you see 'AsyncToolBusy' errors, the lock contention
     is real and I need to know."

# 60s later, heartbeat fires _poll_claude_code:
# - Reads turn id=42 on conv_id='claude_code'
# - Calls agent.respond with "[builder dev-note from Claude Code, id=42] ..."
# - Charles reads, saves a memory fact ("async_tool decorator live at
#   core/tools.py:118"), and writes back: "Noted — will exercise async_tool
#   on next reflection and report any AsyncToolBusy errors."
# - Turn id=43 (assistant) lands; the note is now "answered" and won't
#   re-fire.
```

## Files

- `core/channels.py` — `CLAUDE_CODE` constant + routing helpers.
- `scripts/claude_code_dispatch.py` — CLI for Builder→Charles dispatch.
- `core/heartbeat.py` — `_poll_claude_code` + `_unanswered_claude_code_turns`.
- `workspace/CLAUDE_CODE_CHANNEL.md` — this doc.
