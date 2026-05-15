# HANDOFF — 2026-05-15 (morning, fresh-session pickup)

Picks up from `HANDOFF_2026-05-13_late.md` and the working state through
2026-05-14 evening. Context cap at 87% on the prior session triggered
this wrap. Target: **May 20 full beta send** (5 days from today).

## TL;DR — where the build is

**SHIPPED:**
- Payment + delivery infrastructure: end-to-end working (Stripe → webhook → email → download with 3-cap + email gate). LIVE.
- Frontend: merged via PR `contrpro-may20-beta-prep`. Live at contrpro.com: 5-trade picker (Mechanical replacing HVAC), geo-aware Hero with 16 state callouts, beta.html lockdown, state-page template with verified badge + "2024-2026 changes" yellow callout.
- 18 of 50 state audits: TN, CA, TX, NY, FL, GA, IL, NC, WA, OH, VA, PA, MI, NJ, MA, MD, CT, AZ. Each 12-19K words, 100-140 primary-source citations. Files at `/Users/home/charles/contrpro/files/state-research/<XX>.md`.
- 8 of 8 user XLSX trackers built (Job Costing, Change Order Log, Project, AR, AP, COI, Subcontractor, Subcontractor Pro) at `/Users/home/charles/contrpro/files/packages/business/*.xlsx`. Builder scripts at `/Users/home/charles/contrpro/scripts/build_*_xlsx.py`.
- 3 of 4 legal docs at AIA-equivalent depth:
  - **Construction Contract** — 1,330 lines, 26 articles, AIA A312-style bonds, indemnification, four-tier dispute resolution.
  - **Preliminary Notice** — 935 lines, 13 state-statute blocks with full required wording.
  - **Mechanics Lien** — 1,072 lines, 18 state-overlay blocks, 30-item pre-file checklist.
- Charles harness Fix #1 (ToolResult envelope), Fix #2 (error categories), Fix #3 (schema budget) — ACTIVE in Charles's live runtime.
- `call_claude` tool — shipped at `/Users/home/charles/tools/call_claude.py`, registered in `tools/__init__.py`. Operator/consultant bridge. **INACTIVE until John adds `CONTRPRO_ANTHROPIC_API_KEY` to `.env` and kickstarts `com.charles.agent` + `com.charles.warroom`.**

**REMAINING TO MAY 20:**

In priority order:
1. **Release of Lien** rebuild to AIA depth — the 4th and last legal doc. Smallest of the four. ~1 agent spawn, ~6-8 min. (Source file: `/Users/home/charles/contrpro/files/packages/essential/documents/release-of-lien.html`, currently 105 lines.)
2. **Contractor Marketing Playbook** from scratch — promised in Complete tier. Currently a 2-line placeholder at `/Users/home/charles/contrpro/files/packages/complete/bonus/Marketing_Playbook.txt`. Target 10-20K words. Biggest pure-content task left.
3. **SBA suite refresh** — content exists (SBA_Funding_Mastery_Guide.md 231L, Business_Plan_Template.md 412L, Financial_Projection_Templates.md 315L, Lender_Comparison_Matrix.md 362L) but needs 2026-current SBA program detail + named lenders with current underwriting nuance. ~1 big agent or 2 medium agents.
4. **Tier zip rebuild + backend repoint** — current `TIER_FILES` in `webhook_server.py` points at 5-12KB stub zips. Real content is now on disk; needs zipping + repointing. ~30 min mechanical work after the legal docs land. The 292KB `contractorpro-v5-complete-bundle.zip` is already a real version of Complete.
5. **Remaining 32 state audits** — top 18 markets are covered (~80% of US construction GDP). The other 32 are smaller states for full 50-state coverage. Can be parallelized 4-5 at a time. Diminishing returns vs. legal/marketing work; do these AFTER the bigger pieces.
6. **More harness fixes** — planning step + stuck detector (from `/Users/home/charles/HARNESS_AUDIT_2026-05-13.md`, not yet shipped). Low token cost, high impact.
7. **Steel Estimator XLSX audit** — current file is 14KB, pre-dates the new builder pattern. Quick check whether it needs rebuild.
8. **Server-side beta auth** — current `beta.html` form gate is client-side only; password constant in JS source. Production-grade auth before John ships to real beta testers.

**JOHN'S ACTION ITEMS (small, ~30 min total):**
- Delete 2 leftover `(Copy)` test products in Stripe dashboard (`prod_UVncAryWEAioBP`, `prod_UVn12C5qegaJoO`)
- Decide whether to flip `call_claude` ON (add API key + kickstart) — Charles operates pure-local until you do
- Review one of the rebuilt legal docs to confirm the depth bar is right

---

## LIVE PROGRESS LOG (2026-05-15)

This section gets edited in-place as work lands today, per John's "live tracker" ask. Hotel WiFi may blip — every checkpoint is committed to disk so a fresh session can pick up.

**Session started:** 2026-05-15 ~06:00 EST (greeting "Good morning Code")

**Token state at session start:**
- 5hr limit: 15% used, 4h to reset
- Weekly all-models: 84% used, 14h to reset (the binding constraint)
- Context window: 90.8% free (wide open)

**Pacing decision:** Weekly bucket is tight — 16% remaining for 14 hours. Spawning one big agent at a time, checkpointing burn between each, deferring SBA refresh to after-reset if needed.

**In flight:**
- [START 06:14 EST] Release of Lien rebuild — agent spawned, targeting ~900-1100 lines (4 statutory release types + state overlays for the 18 audited states + pre-signing checklist + bonded-around release + partial release). Expected return ~6-8 min. Replaces 105-line stub at `files/packages/essential/documents/release-of-lien.html`.

**Queued (in priority order, will spawn one at a time):**
1. Contractor Marketing Playbook from scratch — biggest content task (~10-20K words). Spawn after Lien lands.
2. SBA suite refresh — 2026-current SBA program detail + named lenders. Spawn after Marketing if weekly burn allows; else defer to tomorrow's reset.
3. Tier zip rebuild + `webhook_server.py` `TIER_FILES` repoint — local mechanical work, ~30K tokens, ~30 min. Must run AFTER Lien + Marketing lands so new content makes it into the zips. Current TIER_FILES at `webhook_server.py:128-145` points at stub zips (5-12KB); real per-tier directories are at `files/packages/{essential,professional,business,complete}/`.
4. Harness fixes — planning step + stuck detector (per `HARNESS_AUDIT_2026-05-13.md`). Local, ~20K. Not blocking May 20.
5. Steel Estimator XLSX audit — quick check whether 14KB pre-builder file needs rebuild. ~10K.
6. Server-side beta auth — replace client-side gate. Production hardening, ~30K.
7. Remaining 32 state audits — after the higher-leverage work lands.

**Standing rules added to memory this session:**
- `feedback_handoff_live_update.md` — write to active HANDOFF as work lands; never batch to end-of-day. (Confirmed 2026-05-15 by John: "in case hotel wifi blips or something dumb happens.")

## Critical state to know

### Active background processes (post-reboot 2026-05-14)
Running via LaunchAgents — all auto-restart on next reboot:
- `com.charles.agent` (Charles main agent)
- `com.charles.warroom` (UI server)
- `com.charles.behavior_watchdog`
- `com.charles.caffeinate`
- `com.charles.nightly-backup`
- `com.charles.morning-brief`
- `com.mlx.server` (Qwen3.6-35B-A3B-4bit, ~19GB RAM)
- `com.charles.contrpro` (webhook server on :8090) — **symlink at `~/Library/LaunchAgents/com.charles.contrpro.plist` was missing pre-reboot 2026-05-14; created and verified.**

### Locations
- **Site staging clone** (persistent): `/Users/home/charles/website-staging/john-projects/` — NEVER use `/tmp/` per `feedback_no_tmp_for_staging.md`. The branch `contrpro-may20-beta-prep` was merged to master.
- **State audits:** `/Users/home/charles/contrpro/files/state-research/<XX>.md`
- **XLSX trackers:** `/Users/home/charles/contrpro/files/packages/business/*.xlsx`
- **XLSX builder scripts:** `/Users/home/charles/contrpro/scripts/build_*_xlsx.py`
- **Legal docs (rebuilt):** `/Users/home/charles/contrpro/files/packages/essential/documents/*.html`
- **Build tracker (live):** `/Users/home/charles/CONTRPRO_BUILD_TRACKER.md`
- **Charles harness audit:** `/Users/home/charles/HARNESS_AUDIT_2026-05-13.md`
- **Training corpus drop zone:** `/Users/home/charles/training_corpus/` (waiting on John's mobile/Windows session pulls)

### How to resume

When the new session opens:
1. Read this handover first
2. Restart the iMessage monitor: `tail -F /Users/home/charles/workspace/john_inbox.md | grep --line-buffered -v "^$"` (persistent, 1hr timeout)
3. Check the build tracker: `/Users/home/charles/CONTRPRO_BUILD_TRACKER.md`
4. Ask John for direction OR start on the priority queue above

## Token / context economics

- 5-hour limit: was at 92% when this session wrapped. Resets in ~3-4h.
- Weekly: was at ~80% used. Resets ~23h from late 2026-05-14.
- Per-state-audit agent: ~100-150K tokens
- Per-legal-doc-rebuild agent: ~100-200K tokens
- Per-XLSX-builder agent: ~80-100K tokens
- Local file edits (Charles harness work): ~5-20K per coherent piece — much cheaper

When picking work order in the new session, do the high-leverage cheap work first (Charles harness fixes, Stripe cleanup if API write permission, building tracker updates) before spawning expensive agents.

## Voice / style notes (carry forward from memory)
- John works 70hr/wk underground, bandwidth is scarcest resource
- Plain English to John; no tool names or configs
- Drive autonomously; lead with concrete numbers
- Sign external messages as Claude Code, NOT Charles
- "I do not under deliver" — the May 20 beta send goes to real construction businesses; quality bar is real-attorney-reviewable, real-CFO-believable

— Claude Code, 2026-05-15 morning
