# HANDOFF — 2026-05-13 (late-evening, picks up from HANDOFF_2026-05-13.md)

For the next Claude Code session. This is the canonical state as of ~21:50 EST / 01:50 UTC May 14.

A reboot is scheduled for 03:30 EST tonight via `~/Library/LaunchAgents/com.charles.scheduled-reboot.plist`. The plist self-removes on fire. After reboot every Charles service auto-recovers via existing LaunchAgents. **My own session ends at the reboot** — John will resume here in the morning.

## What got done tonight

### 1. ContrPro webhook backend — bug fix + hardening
- **Root-cause fixed:** Stripe SDK objects do NOT support dict-style `.get()`. The handler was failing silently because every `.get()` call (on `session`, `customer_details`, etc.) raised AttributeError. Fixed at `/Users/home/charles/contrpro/webhook_server.py` line ~459: now parses the raw payload as plain JSON via `event = json.loads(payload)` AFTER signature verify. All downstream `.get()` calls work cleanly.
- **Top-level try/except** wraps `_handle_checkout_complete` so any future silent crash logs a real traceback via `log.exception` instead of returning 500 with no log line.
- **`_resolve_tier_from_session`** uses subscript access (with `if 'k' in obj` guards) on Stripe SDK objects when fetching line_items fresh — `.get()` would blow up on those.

### 2. New backend features shipped
- **3-download cap** (`CONTRPRO_MAX_DOWNLOADS=3` env, default 3). Implemented in `download_landing` + new `POST /download/{token}` handler.
- **Email gate**: visitor must enter buyer email to access download. POST-only flow, no cookie (re-verify each landing). Mismatches return 403 + re-rendered form with error. Successful match increments counter + serves file or index.
- **Limit-reached page** (`_limit_reached_page` in webhook_server.py): friendly 429 with a pre-filled mailto to support@contrpro.com for re-issue.
- **Email confirm page** (`_email_gate_page`): clean form, autofocus on input.

### 3. Stripe state
- Webhook fully tested end-to-end. 2 orders in DB (`/Users/home/charles/contrpro/contrpro.db`), both delivered email to keith.john87@gmail.com.
- **John deleted JOHN100 coupon** (100% off, was vulnerable). 0 active coupons remain.
- **Still need to delete:** 2 `(Copy)` test products in Stripe (`prod_UVncAryWEAioBP`, `prod_UVn12C5qegaJoO`). John deactivated the associated payment links; the products themselves should be archived.

### 4. Frontend PR merged
- Branch `webhook-backend-integration` merged to `master` via PR #1 (commit `5fd38de`). GitHub Pages auto-rebuilt. Live site at contrpro.com now uses the Tailscale backend for delivery — no more client-side EmailJS / base64 token forgery flow.

### 5. Local site changes staged (NOT YET PUSHED — needs John's merge auth)
All changes are in `/tmp/john-projects-clone/`. Branch: still on `master`, ahead of origin by 1 commit (the merge), but with **uncommitted edits** to:
- `index.html` — Hero rebuild + contractor picker swap (HVAC card → Mechanical card)
- `css/styles.css` — new `.hero-eyebrow`, `.hero-callout*` classes
- `beta.html` — visible password removed, real form gate, noindex meta
- `data/states.json` — CA + TN entries upgraded with audit-verified content
- New file `WEBHOOK_INTEGRATION_README.md` (still untracked from earlier session)

**To ship:** John needs to commit these to a new branch + merge through GitHub UI (harness blocks direct push to master).

### 6. Hero rebuild — Option A (geo-aware)
Per John's choice: kill fake stats ("10K+ Documents Generated" etc.), use geolocation to surface state-specific value. Lives in `index.html` `<section class="hero">` + script at bottom.
- Detects state via `https://ipapi.co/json/` with 1.5s hard timeout
- `HERO_STATE_FACTS` map currently populated for **TN, CA, TX**
- Other US states: soft "📍 [State] contractor — rolling out" eyebrow
- Non-US / fail: silent default

### 7. State audits completed (the format reference + 2 more)
All three files under `/Users/home/charles/contrpro/files/state-research/`:
- **TN.md** — 5,175 words, 55 citations. Nov 18 2025 CPA-compiled rule change, workers' comp construction trap (no 5-emp threshold), Structural Steel = "S" classification, HB0271 secondary-source trap caught.
- **CA.md** — 8,907 words, 72 citations. $500→$1,000 unlicensed threshold (AB 2622), SB 61 retainage cap (Jan 1 2026), SB 440 change-order procedure (Jan 1 2026), SB 1455 WC universal mandate punted to 2028, $25K bond (raised by SB 607 Jan 2023).
- **TX.md** — 11,371 words, 88 citations. Construction Trust Fund Act criminal liability (Tex. Prop. Code Ch. 162), monthly pre-lien notice schedule (15th day of 2nd month residential, 3rd month commercial), HB 2237 mail requirements, 2025 89th Legislature changes (SB 929/SB 947/HB 2960/HB 3005), Texas non-subscriber WC unique.

47 states still need audits. Priority queue per the homepage "Popular": FL, NY, GA, IL, NC, WA next.

### 8. Charles harness diagnostic
File: `/Users/home/charles/HARNESS_AUDIT_2026-05-13.md` — 2,800 words.

**Top 3 fixes ranked for next session:**
1. **ToolResult envelope** (4-5h). Tools currently return bare strings; model can't tell "error" string from "successful result containing the word error". Wrap all tool returns in a `ToolResult` dataclass with `{status, data, message}`. Update `dispatch()` + top 5 high-volume tools (shell, filesystem, cc_build, memory, goals).
2. **Error categories for smart retry** (2-3h). Blocked URLs get retried like network timeouts → infinite loops. Validation errors never bail out. Add `category` enum (validation/blocked/network/timeout/internal) to ToolResult. Tag every guard and exception handler. Add an error-handling docstring to the system prompt.
3. **Schema budget + adaptive tool selection** (2h). 78 tools × 200 tokens/schema = 15.6K overhead per message. `_estimate_schema_tokens()`. Budget-respecting `select_tools()` (3K normal, 1.5K short). Drop low-score tools when over budget.

Total: 8-10 hours to ship all three. Each is mechanical and observable.

### 9. Mac maintenance
- **1.2GB dead-weight purged** to `/Users/home/_trash_2026-05-13/` (REVERSIBLE — anything that breaks tomorrow, move it back):
  - `models--mlx-community--Qwen2.5-32B-Instruct-4bit` (203MB, unused by any code)
- **NEAR MISS:** I almost trashed the working voice-clone model. `/Users/home/charles/models/chatterbox-tts-4bit/` (976MB) looked like a duplicate of the HF cache entry but was actually the *active* model pointed at by `CHARLES_CLONE_MODEL` env var in `.env`. **Restored.** The HF cache entries (both fp16 AND 4bit) have `.incomplete` blobs — partial downloads. The local path is what actually works. **Lesson: check env vars for non-obvious dependencies before purging anything that looks duplicated.**
- **speak.py default updated** (`/Users/home/charles/core/speak.py` line 32): now defaults to the local path instead of the broken HF id, so if `.env` is ever lost, the fallback still works.
- **Scheduled reboot:** `~/Library/LaunchAgents/com.charles.scheduled-reboot.plist` fires `/Users/home/charles/scripts/scheduled_reboot.sh` at 03:30 local time. Script unloads + deletes the plist (one-shot), then sends Apple Event restart via `osascript`. Log at `/Users/home/charles/logs/scheduled_reboot.log`.

### 10. Training-corpus drop zone (per John's "ship my sessions to Charles" iMessage)
- `/Users/home/charles/training_corpus/` with subdirs: `mac_claude_code/`, `mobile_claude/`, `windows_cowork/`, `manual_drops/`, `_processed/`
- README documents the pipeline: drop file → sanitize → embed (MiniLM) → store in memory DB → move to `_processed/`
- **The indexer itself is not built yet** — that's a Phase 1 task. The dirs are ready for John to start dropping files.
- John mentioned he'll consolidate Mobile Claude + Windows Cowork sessions tomorrow.

## Foundational architecture decisions captured tonight (in memory)

These were the night's most important conversations and are now in `/Users/home/.claude/projects/-Users-home-charles/memory/`:

- **`project_charles_vs_claude_architecture.md`** — Charles is operator, Claude is consultant. Don't pitch swapping Claude for Charles or vice versa. Build the delegation interface.
- **`feedback_harness_not_model.md`** — When Charles fails, first hypothesis is harness drag (loop, tools, state, recovery), NOT model intelligence. Per `feedback_model_choice_settled.md` model is settled.
- **`project_charles_harness_in_claude_code_image.md`** — Strategic north star: port Claude Code's harness patterns (agent loop, structured tool returns, error visibility, planning step, stuck detection) into Charles's Python runtime.
- **`feedback_imessage_polling.md`** — When John says "iMessage", spin a 10s-cadence Monitor on `~/charles/workspace/john_inbox.md`.
- **`project_scheduled_reboot_2026-05-14.md`** — Tonight's reboot setup details.

MEMORY.md was updated to point to all five.

## Open todos (for the next session)

Priority order:
1. **Verify post-reboot state** — `cat /Users/home/charles/logs/scheduled_reboot.log`, `launchctl list | grep -E "charles|mlx"`, `curl http://127.0.0.1:8090/health`, `tailscale serve status`. All should be green.
2. **Restart the iMessage Monitor** (`tail -F /Users/home/charles/workspace/john_inbox.md | grep --line-buffered -v "^$"`, persistent, 10s cadence)
3. **Push the staged website changes** when John gives merge auth: 5-trade picker, geo Hero, states.json upgrades, beta lockdown
4. **Generate remaining state audits** — FL, NY, GA, IL, NC, WA next priority; can be batched as parallel agents
5. **Implement the top-3 Charles harness fixes** (ToolResult envelope → error categories → schema budget). 8-10h total. Per `feedback_two_processes_run_agent.md` — kickstart both `com.charles.agent` and `com.charles.warroom` after touching core/.
6. **Build the training_corpus indexer** — file watcher → sanitizer → MiniLM embedder → memory DB writer. Wire to Charles's recall pipe.
7. **Audit 4 legal docs for AIA-equivalent depth** (multi-day lift)
8. **Rebuild spreadsheet trackers as real XLSX with formulas + dashboards**
9. **Refresh SBA suite with 2026 program detail + named lenders**
10. **Write Contractor Marketing Playbook from scratch** (~10-20K words)
11. **Repackage tier zips** with real content + repoint backend `TIER_FILES`
12. **Delete 2 Stripe `(Copy)` test products** (`prod_UVncAryWEAioBP`, `prod_UVn12C5qegaJoO`)
13. **Build server-side beta auth** (replaces client-side localStorage flow; current beta.html has password constant visible in source)
14. **CC sweep** still paused (PID 22440 was killed by the reboot). State at `~/charles/workspace/cc_state.json`. p2_qwen36 last at ~140/12000. Resume when on better wifi.

## What needs manual restart after reboot

LaunchAgents auto-recover. These do NOT:
- **My Claude Code session** (obvious — start a new one)
- **The iMessage inbox Monitor** I set up (`tail -F ~/charles/workspace/john_inbox.md`)
- **The MLX server** — actually IT WILL auto-load via `~/Library/LaunchAgents/com.mlx.server.plist`. Model takes ~30s to warm into RAM after boot. Charles requests during that window will fail gracefully.
- **CC sweep PID 22440** — if you want to resume it: `cd ~/charles && python -m core.cc_runner --skip-backup`

## Voice / style notes (carry forward)

- Communicate with John in plain English; he speaks strategy not tech (per `feedback_john_is_strategic_not_technical.md`).
- Drive autonomously; don't ask permission for the obvious next step (`feedback_autonomy.md`).
- Lead with concrete numbers, not narration (`feedback_just_do_it.md`).
- When trading reliability vs charm, pick reliability (`feedback_operator_over_warmth.md`).
- Charles is being engineered, not vibe-coded. Don't dumb down the technical work to him; just translate the WHY into outcomes he can act on.
- John's been burned by demoware. Skepticism is calibrated, not pessimism. Honor it.

## Where we ended

John's last iMessage at 01:43 UTC: *"I will dive heavy into that tomorrow. I got you bro. Make sure everything comes up that needs to after the restart and I will fire you back up when I wake up."*

He's going to sleep. Reboot fires in ~2 hours. He wakes to a clean machine and resumes here.

— Claude Code, 2026-05-13 21:50 EST
