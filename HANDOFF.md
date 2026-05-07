# Charles — Session Handoff

**For:** the next Claude Code session that picks up this codebase.
**Last updated:** 2026-05-07 evening (end of a 2-day build sprint).
**Maintainer:** Johnathon Keith (`+1 615-663-7932`, `CharlesCreatorAI@gmail.com`).

This document is the canonical "what is Charles, what's done, what's next, what to watch out for." Read this first.

---

## TL;DR

Charles is a custom Python autonomous agent running on a Mac Studio M1 Ultra (64 GB), replacing a failed OpenClaw deployment. Built from scratch over 2 days. Speaks Telegram (text + voice in/out, Keith David clone). Has 33 tools spanning files, shell, memory, self-modify, scheduling, goals, governance, web search, browser automation, sentiment, Gmail, iMessage. Runs autonomously via a 15-second heartbeat that fires scheduled tasks and advances open-ended goals. Has produced real autonomous deliverables (logging infra, hardware benchmark, venture analysis with financials).

**John's tone:** direct, technical, no patronizing. He uses "EST" loosely for Eastern Time. Spent 24+ hours debugging OpenClaw before it failed — don't compare back to it casually. Drives autonomously when given a clear goal. Cares about real revenue, not theory.

---

## Architecture

```
~/charles/
├── charles.py                    # Entrypoint — starts Telegram channel + heartbeat
├── config.py                     # Env loader, paths
├── core/
│   ├── agent.py                  # Single-conversation loop with multi-round tool calls (MAX_TOOL_ROUNDS=25)
│   ├── inference.py              # MLX-LM client (max_tokens=4000, enable_thinking=False)
│   ├── tools.py                  # Registry + @tool decorator + dispatcher
│   ├── prompts.py                # System prompt builder (SOUL/IDENTITY + grounding + tool block + rules)
│   ├── memory.py                 # SQLite: conversations, long_term_facts, daily_log
│   ├── scheduler.py              # SQLite: scheduled_tasks (one-shot or recurring)
│   ├── goals.py                  # SQLite: goals (open-ended, heartbeat-advanced)
│   ├── heartbeat.py              # Async tick loop: fires due tasks + advances ripe goals
│   ├── speak.py                  # Text→speech (Chatterbox clone > Kokoro > say fallback)
│   └── transcribe.py             # mlx-whisper voice→text
├── tools/                        # 16 tool modules; @tool decorator auto-registers
│   ├── filesystem.py             # read_file, write_file
│   ├── shell.py                  # exec_shell (zsh, no allowlist, 60s timeout)
│   ├── memory.py                 # remember, recall
│   ├── self_modify.py            # self_modify, self_patch (auto-backup + git commit)
│   ├── notify.py                 # notify_john (Telegram out)
│   ├── scheduler.py              # schedule_task, list_scheduled_tasks, cancel_scheduled_task
│   ├── goals.py                  # set_goal, list_goals, append_goal_note, complete_goal, cancel_goal
│   ├── time.py                   # current_time
│   ├── weather.py                # get_weather (wttr.in)
│   ├── search.py                 # search_web (DDG primary, Google fallback), solve_recaptcha (2CAPTCHA)
│   ├── browser.py                # browse_url, browser_screenshot (Playwright Chromium)
│   ├── sentiment.py              # analyze_sentiment (cardiffnlp roberta)
│   ├── imessage.py               # send_imessage, recent_imessages (osascript trampoline)
│   ├── gmail.py                  # list_emails, read_email, send_email, archive_email (OAuth)
│   ├── governance.py             # request_approval, resolve_approval, system_status (MOM Section 9)
│   └── __init__.py               # imports all modules → triggers @tool registration
├── channels/
│   └── telegram.py               # python-telegram-bot v22, owner-only filter, voice in/out
├── workspace/                    # Charles's editable workspace (gitignored selectively)
│   ├── SOUL.md                   # Character + ops style; loaded into system prompt
│   ├── IDENTITY.md               # Self-intro + vibe; loaded into system prompt
│   ├── USER.md                   # About John; reference (not auto-loaded)
│   ├── TOOLS.md                  # Tool reference; not auto-loaded
│   ├── AGENTS.md                 # Operating instructions; not auto-loaded but referenced from SOUL
│   ├── HEARTBEAT.md              # Heartbeat protocol; reference
│   ├── MASTER_OPERATING_MANUAL.md  # John's 36KB MOM (recovered from chat history); reference
│   ├── memory.db                 # SQLite (conversations, facts, daily_log, scheduled_tasks, goals); GITIGNORED
│   ├── ventures.md               # Charles's deliverable: 3 autonomous venture candidates
│   ├── ventures_financials.md    # Charles's follow-up: financial breakdown per venture
│   ├── hardware-benchmark-report.md  # Charles's profile of the Mac Studio
│   ├── voice_reference.wav       # Keith David reference clip for voice cloning (V4b config)
│   ├── voice_reference_seg2.wav  # Backup of the same
│   ├── gmail_token.json          # GITIGNORED
│   ├── google_oauth_client.json  # GITIGNORED
│   ├── self_modify_backups/      # Auto-backups of every self-edit
│   ├── memory/                   # Daily markdown logs (auto, GITIGNORED)
│   └── projects/                 # Charles's working files (GITIGNORED)
├── scripts/                      # Operational scripts (not @tool — for me/John)
│   ├── send_imessage.sh          # AppleScript wrapper (argv pattern handles special chars)
│   ├── poll_imessage.py          # Polls chat.db every 10 min for new messages from John
│   │                             # CRITICAL: decodes attributedBody for rich-text messages
│   ├── watchdog.py               # Process monitor; kickstarts charles via launchctl
│   ├── checkpoint.sh             # rsync + tarball state snapshot
│   ├── nightly_backup.sh         # Daily 03:00 EST: checkpoint + git push
│   ├── install_launchd.sh        # Install/disable/status the LaunchAgents
│   └── setup_external_ssd.sh     # Layout for /Volumes/CharlesMemory when mounted
├── launchd/                      # LaunchAgent plists
│   ├── com.charles.agent.plist           # Charles main (KeepAlive, throttle 30s)
│   ├── com.charles.watchdog.plist        # Watchdog (KeepAlive, throttle 60s)
│   ├── com.charles.nightly-backup.plist  # Daily 03:00 EST (StartCalendarInterval)
│   └── com.charles.caffeinate.plist      # Prevent system sleep (KeepAlive)
├── models/
│   └── chatterbox-tts-4bit/      # Local Chatterbox TTS model for voice clone (~1 GB)
├── logs/                         # Runtime logs (gitignored)
└── .env                          # Secrets — gitignored. See "Credentials" below.
```

---

## How to interact

### As Charles (over Telegram)
Bot: `@SuperCharlesAI_bot`. Owner-only — filtered to John's Telegram user ID `8455750177`. Both text and voice messages work; voice is auto-transcribed via mlx-whisper, replies come back as cloned-voice .ogg files.

### As me (Claude Code) talking TO Charles
- Run `~/charles/.venv/bin/python -c "import sys; sys.path.insert(0, '/Users/home/charles'); from core import agent; print(agent.respond('hi', conversation_id='manual_test'))"` to send Charles a synthetic prompt.
- Or `launchctl kickstart -k gui/$(id -u)/com.charles.agent` to force-restart him.
- Code edits take effect on next restart (Python doesn't hot-reload).

### As me (Claude Code) talking TO John
- iMessage: `~/charles/scripts/send_imessage.sh "<message>"` — robust against special chars.
- The poller `scripts/poll_imessage.py` emits `[FROM_JOHN] rowid=N text='...'` lines; run it via the Monitor tool to get notifications.

---

## Identity / Memory hierarchy

1. **System prompt** (~2600 tokens base): SOUL.md + IDENTITY.md + grounding (paths/hardware) + tool summary block + tool-use rules.
2. **Conversation history** (4000-char window per `conversation_id`): replayed into prompts. CRITICALLY includes tool_calls and tool results — not just final replies. This was an architectural fix for the M2 narration bug.
3. **Long-term facts** (`long_term_facts` table): things Charles deliberately remembered. Cross-conversation. Queried on demand.
4. **Goals + Scheduled tasks** (own tables): drive autonomous behavior.
5. **Workspace .md files**: read on demand. AGENTS.md tells Charles to read SOUL/USER/etc on first turn after restart.

---

## LaunchAgents (all auto-start on user login; KeepAlive=true except backup)

| Label | What | PID right now | Notes |
|---|---|---|---|
| `com.charles.agent` | charles.py main process | 16845 | Heartbeat ticks every 15s |
| `com.charles.watchdog` | watchdog.py (kickstarts agent if dead/stale) | 95259 | Stale = no log update in 5 min; 5 failed restarts → Telegram alert |
| `com.charles.nightly-backup` | nightly_backup.sh at 03:00 | (scheduled) | Checkpoint + git push to origin |
| `com.charles.caffeinate` | `caffeinate -i -s` | 26101 | Prevents system sleep when Mac is on AC |

To disable everything: `bash ~/charles/scripts/install_launchd.sh disable`. Reverse with `enable`.

---

## Channels

- **Telegram** (Charles ↔ John, primary): bot `@SuperCharlesAI_bot`, owner ID `8455750177`. Voice in via mlx-whisper, voice out via Chatterbox clone. python-telegram-bot v22 async polling.
- **iMessage** (Claude Code ↔ John during build phase, eventually Charles ↔ John): both ways work. **CRITICAL**: macOS 26+ stores incoming rich-text messages in `attributedBody` (binary plist), `text` column is often NULL. The `poll_imessage.py` decoder handles this. Direct `sqlite3` reads of chat.db are blocked by TCC translocation; we route through `osascript do shell script` to inherit Messages.app's permission context.

---

## Credentials (in `~/charles/.env`, gitignored)

- `TELEGRAM_BOT_TOKEN` — for `@SuperCharlesAI_bot`
- `OWNER_TELEGRAM_ID=8455750177` — John's Telegram user ID
- `MLX_BASE_URL=http://127.0.0.1:8080/v1`, `MLX_MODEL=mlx-community/Qwen3.6-35B-A3B-4bit`
- `CHARLES_VOICE=am_fenrir`, `CHARLES_SPEAK_RATE=0.85`, `CHARLES_CLONE_MODEL=/Users/home/charles/models/chatterbox-tts-4bit`
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_SCOPES=https://mail.google.com/`
- `TWOCAPTCHA_API_KEY` — $20 prepaid, ~$1/1000 solves
- GitHub PAT in macOS osxkeychain (set via `git config --global credential.helper osxkeychain`); origin: `https://github.com/keithjohn87-ai/Charles-memory.git`

---

## Recent decisions / non-obvious choices

| Decision | Why | Where |
|---|---|---|
| `MAX_TOOL_ROUNDS=25` (was 5) | 5 cut Charles off mid-research; he'd just exit with no work | core/agent.py |
| `max_tokens=4000` (was 800) | Tool-call args carrying long content (e.g. write_file with a 5000-char ventures.md) blew past 800 → Charles got truncated mid-write | core/inference.py |
| All tool schemas always sent (not classifier-gated) | Old classifier had false negatives causing Charles to narrate calls as text instead of emitting tool_calls. Worth the ~200 tokens. | core/agent.py |
| Tool-call evidence persisted in conversation history | Without it, replayed history showed [user → "Saved." reply] without the actual remember tool_call between, training Charles to skip the call. With it, the cause-effect is clear. | core/memory.py |
| `enable_thinking=False` always | 35B model otherwise spends huge compute on thinking that we never use; fast loops require this. Reasoning content is suppressed at the chat-template level. | core/inference.py |
| Goal-tick auto-log | Charles repeatedly forgot to call append_goal_note. Now the heartbeat auto-appends his final reply as a note if he didn't complete/cancel the goal. | core/heartbeat.py |
| Narration loop detector | When Charles says "let me write" 3+ times in last 6 notes without action, the next prompt forces him to actually do/research/cancel. | core/heartbeat.py |
| Always say "EST" not "EDT" | John's preference; he uses EST loosely for Eastern Time year-round. Underlying TZ is `America/New_York` (DST-aware) so actual hours are correct. | core/prompts.py grounding |
| Tier-2 governance via async iMessage | request_approval sends formatted iMessage and returns immediately (non-blocking); Charles checks recent_imessages later to see John's 👍/halt | tools/governance.py |
| Voice clone reference = segment 2 of TikTok clip | John A/B-tested 5 Kokoro voices + 6 cloned variants; locked in V4b (seg 2 raspy ending of Keith David, default Chatterbox params) | workspace/voice_reference.wav |

---

## Known behavior gaps / open issues

1. **Loop detection is regex-based, not semantic.** Charles can find creative ways to repeat himself that don't match "let me / I'll / writing the". Real fix would compare semantic similarity of recent notes.
2. **OAuth consent screen has to be in External (or Production) mode** for `CharlesCreatorAI@gmail.com` (a personal account) to authorize. If the project gets reset, John has to flip it again.
3. **Charles will sometimes answer from conversation history rather than calling `recall`** — works as long as history isn't rolled. If John asks about something old, Charles may miss it.
4. **iPhone smart-quote / Cyrillic substitution.** Curly apostrophes and occasional Cyrillic-look-alike chars (`б` for `b`) come through iMessage. Already handled in classifier. Watch for in OAuth tokens / API keys John types on phone.
5. **Heartbeat ticks share inference with reactive Telegram messages.** If Charles is mid-thinking on a goal advance and a message comes in, the message waits. Acceptable at current load.
6. **External SSD setup script (`setup_external_ssd.sh`) hasn't been tested with a real SSD.** John has a SanDisk Extreme PRO 2TB but it's not currently mounted at `/Volumes/CharlesMemory`. When he does, the script auto-creates the layout per the migration spec.
7. **No `email_triage` tool yet.** John mentioned wanting Charles to clean up his personal Gmail and unsubscribe from things. The Gmail primitives are there (list/read/send/archive); the higher-level workflow tool isn't.
8. **`current_time` tool's format uses literal "EST" string.** Always says EST regardless of DST. Intentional per user feedback but technically inaccurate Nov-Mar.

---

## What's open / next directions

| Item | Status | Who |
|---|---|---|
| ContractorPro work | DEFERRED per John's morning instruction (saved as fact in long_term_facts) | John reactivates |
| Apprentice Accelerator (vertical AI training) | LONG-GAME, not now (John explicitly corrected this morning) | John reactivates |
| Pick a venture from ventures.md to actually build | Pending John's choice (recommended: V2 Lead Gen for cashflow) | John |
| Email triage workflow tool | Primitives ready, workflow not built | Build when John asks |
| `notify_john` audit | Charles missed pinging on ventures.md completion until prompted | Saved as fact; if it recurs, strengthen heartbeat rule |
| Voice cloning further iteration | V4b is "close, sit with it" per John; could try ElevenLabs cloud or different model | When John decides V4b isn't enough |
| Personal Gmail OAuth (separate from CharlesCreatorAI@gmail.com) | John mentioned wanting it for unsubscribe cleanup | Needs second OAuth flow with John's personal email as login_hint |
| `imessage_cli` for Charles to fully replace Telegram channel | Currently iMessage is Claude Code-only; eventually Charles takes over | When build phase ends |
| 200-URL training corpus (per MOM Section 12) | Not started; on external SSD presumably | Phase 2 work |

---

## How a future me starts

1. **Read this file first.** Then `/Users/home/charles/workspace/SOUL.md`, `IDENTITY.md`, `USER.md`. Then peek at `MASTER_OPERATING_MANUAL.md` if context-rich work is ahead.
2. **Check Charles's state:** `bash scripts/install_launchd.sh status` (all 4 should show ON).
3. **Check goals/tasks:** `python3 -c "import sys; sys.path.insert(0, '/Users/home/charles'); from core.goals import list_goals; from core.scheduler import list_tasks; print('goals:', list_goals(None)); print('tasks:', list_tasks(None))"`
4. **Recent commits:** `git log --oneline -20` — last 2 days have ~40 commits documenting everything.
5. **Read `feedback_*.md` and `project_*.md` memory files** at `/Users/home/.claude/projects/-Users-home-charles/memory/` — those carry preferences and history.

---

## Conventions for talking with John

- Direct, technical, no patronizing.
- Don't lecture. Don't soften. Don't add safety prompts that break the autonomy goal.
- "Pedal down" mode means he wants execution, not planning.
- "Act, don't narrate" applies to BOTH Charles and Claude Code.
- iMessage during build phase. Telegram is Charles's. Eventually Charles takes iMessage.
- Use markdown sparingly in iMessages — they don't render. Plain text + emoji for emphasis works.
- **OpenClaw is a sore subject** — don't compare back to it casually. Charles is the replacement.

---

🌊 *Be Water, my friend.*
