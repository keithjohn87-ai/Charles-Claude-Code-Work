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

**Shipped this session:**
- ✅ **Release of Lien (4th legal doc)** — 791 lines, 12 sections, all 4 statutory forms (CA Civ. §§ 8132/8134/8136/8138 model + state-conformed overlays for all 18 audited markets), 28-item pre-signing checklist, partial release, bonded-around release, joint-check flow-down, full Release of Recorded Lien form with notary blocks. Path: `contrpro/files/packages/essential/documents/release-of-lien.html`. **Method note:** background agent stalled at the 600s writing-watchdog after gathering statutory research; rebuild was finished in-conversation to save the weekly token bucket. John approved on preview.
- ✅ **Pre-Charles-self-edit baseline commit `6faf498`** — 28 files, +3233/-371. Captures harness Fix #1-3 deltas + this session's docs.
- ✅ **Charles refresh #1** — kickstart of `com.charles.agent` + `com.charles.warroom` after the baseline commit. PIDs 62202 / 62204.
- ✅ **JOHN_CHARLES round cap bump (`MAX_TOOL_ROUNDS_RELATIONAL` 5→15) in `core/agent.py`** — John approved on iMessage 10:34 UTC after the diagnosis at 10:30 UTC. Kicked the 2026-05-15 incident where Charles edited `cc_configs.py` successfully but hit round 5 before he could re-run cc_build to verify. The intra-call repetition guard + dispatch-guard still backstop runaways. Charles refresh #2 — PIDs 65594 / 65596.
- ✅ **Contractor Marketing Playbook** — 11,259 words, 721 lines, 19 sections. Foundation rules → positioning → 10 lead sources (referrals, LSA, GBP, Nextdoor, BNI/chambers, signage, direct mail, social organic, lead aggregators, permit data) → follow-up system → CRM comparison → social proof → seasonal cadences by trade → tiered budget framework + 90-day starter plan → 9 common mistakes → flywheel close. Path: `contrpro/files/packages/complete/bonus/Marketing_Playbook.md`. Cross-references the package's existing XLSX trackers. CSI MasterFormat awareness threaded throughout. **Method note:** sub-agent stalled at the writing stage (same pattern as Lien); written in-conversation. Saved as memory `feedback_agent_stall_at_write.md` for future sessions.

- ✅ **Harness Rule 7 (Plan-then-act)** in `core/prompts.py`. Forces a short `Plan:` preamble for multi-step engineering asks. Reduces wasted-round risk upstream of the round-cap fix shipped earlier. Stuck detector deferred — wanted to observe how Rule 7 + round cap interact before adding more layers (no clear concrete pattern to instrument).
- ✅ **SBA suite refresh** — Funding Mastery Guide (602L / 5,848 words / 38KB; was 231L / ~1.5K words). Lender Comparison Matrix (600L / 3,475 words / 24KB; was 362L). Both at `complete/sba/`. Funding guide covers all 7 SBA loan products incl. CAPLines + Working Capital Pilot (2024 launch), construction NAICS size standards table, FinCEN BOI 2024 compliance, 8 construction-specific denial reasons. Lender matrix has 15 SBA-7(a) lenders + 7 504 CDCs with current 2025 data + decision tree. Business Plan Template + Financial Projection Templates left for v1.1 (functional, not embarrassing). Complete zip rebuilt to 365KB.
- ✅ **Server-side beta auth** — replaces the client-side JS gate where the password used to live as a plaintext constant in `beta.html`. Implementation:
  - `webhook_server.py`: added `_hash_password` / `_verify_password` (PBKDF2-HMAC-SHA256, 200K iterations, stdlib only). Added POST `/beta/login` and GET `/beta/verify` endpoints. CORS middleware locked to `contrpro.com` + `localhost`. Rate-limit: 5 fails / 60s = 5-min lockout per email. Signed session tokens (7-day TTL) using existing `_sign_token` HMAC pattern with kind tag `beta_session`.
  - `scripts/contrpro_hash_password.py`: helper script John runs to hash a beta tester's password into the storage format.
  - `beta.html`: removed the BETA_USER constant. Login now POSTs to webhook server, stores signed session token in localStorage, page-load verifies token via /beta/verify. Cleaned up legacy `betaLoggedIn`/`betaUser` localStorage keys on logout.
  - **John's action item:** generate password hashes for each beta tester, add `CONTRPRO_BETA_USERS=email1:hash1,email2:hash2` to `.env`, restart `com.charles.contrpro`. Smoke test passed: all endpoints return correct codes for malformed/missing inputs; CORS preflight works for contrpro.com origin.
- ✅ **Tier zip rebuild (4 tiers)**.
  - **Bug fixed during rebuild:** previous session's AIA-depth legal docs only landed in `essential/`. Professional and Business still had 105-line stub release-of-lien (and similarly stub mechanics-lien / preliminary-notice / construction-contract). Complete had no `documents/` directory at all. Synced all 4 AIA-depth docs from `essential/documents/` to `professional/documents/`, `business/documents/`, and created `complete/documents/`. Backfilled Complete with `guides/` (50-state lien guide) and the XLSX trackers from Business.
  - Removed superseded `Marketing_Playbook.txt` placeholder.
  - Built zips: essential-forms-79.zip 111KB / professional-package-149.zip 152KB / business-system-199.zip 334KB / complete-bundle-249.zip 349KB. Each zip contents verified.
  - **No `TIER_FILES` code change needed** — zip filenames preserved; webhook continues serving the same paths, now with real content. Webhook health: HTTP 200.
  - SBA tier (downloads/sba-guides/SBA_Guide.pdf + .docx) untouched; will refresh in the SBA suite refresh task.

**In flight:**
- (None — picking next item from queue.)

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
