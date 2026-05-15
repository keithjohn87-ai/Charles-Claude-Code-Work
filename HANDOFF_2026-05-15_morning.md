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

---

## AFTERNOON BATCH (2026-05-15 ~10:54 EST onwards)

### GC suite — 8 documents, V1-GC-Complete

After John's 11:53 UTC correction ("I thought we were starting with the GC division?" — earlier I'd queued this as post-beta; he wanted forward motion now), I shipped a complete General Contractor suite at AIA-equivalent depth in `contrpro/files/packages/complete/gc/`:

1. ✅ **Application for Payment + SOV + Continuation Sheet** — 1,193L (commit `ac66646`). Industry-standard equivalent of AIA G702/G703. 18 CSI Division SOV with 40 spot-checked codes, 9-line cover-sheet calc with reconciliation check, full Continuation Sheet column definitions, retainage mechanics with state caps.
2. ✅ **Master Subcontract Agreement** — 751L (commit `8e33342`). 15 articles + Exhibit A Work Order template. Pay-when-paid with state-law alert (CA Wm. R. Clarke Corp. v. Safeco precedent + 7 other restricted states), comparative-fault indemnification with anti-indemnity statute citations, CGL with CG 20 10 + CG 20 37 endorsement combo, OSHA 29 CFR 1926, 3-step dispute resolution.
3. ✅ **RFI / Submittal / Transmittal templates** — 669L (commit `70e4668`). Three daily-use forms with use-case framing, sample log entries, and 10 discipline rules.
4. ✅ **Change Order Request + CCD + Change Order** — 547L (commit `33c35f1`). Three change-process instruments distinct from the existing Change_Order_Log XLSX. Pricing methodology comparison + 12 discipline rules.
5. ✅ **Closeout Suite** — 574L (commit `445ac66`). Substantial Completion Cert + Punch List + 40-item Closeout Document Checklist + Final Completion Cert + Retainage Release sequence with state prompt-payment statute citations.
6. ✅ **Schedule Baseline + 3-Week Look-Ahead** — 582L (commit `4583b67`). CPM activity list with sample 12-mo project + trade-by-trade Look-Ahead with sample week + monthly schedule update procedure + 12 discipline rules.
7. ✅ **GMP Agreement** — 716L (commit `089e76c`). 15 articles. Cost-plus-fee with GMP. Two-phase structure (Preconstruction + Construction). Cost of the Work definition, Contractor's Contingency, Allowance reconciliation, Open Book + Audit, Savings Sharing formula table.
8. ✅ **Cost-Plus Agreement + Delivery Method Selection Guide** — 454L (commit `2ee9341`). Three-method comparison (Lump Sum / Cost-Plus / GMP) + when-to-use guidance + Cost-Plus Owner-Contractor Agreement form.

**GC suite total: 8 documents / 5,486 lines / 425KB.** All committed.

### QA passes (two rounds)

**Round 1 — sub-agent QA (commit `ade28f5`):** Spawned a focused sub-agent to read all 8 GC docs + cross-references and produce a prioritized punch list. Returned 5 P0s, 11 P1s, 12 P2s. Auto-fixed 3 cleanly bounded items immediately:
- A.M. Best rating mismatch (master-sub VIII → VII to match prime contract)
- Schedule example A410 duration (90 → 108 days to reconcile with stated dates)
- RFI doc orphan `</p>` tag + AIA G716/G710 mapping correction (G716=RFI, G710=ASI)

**Round 2 — judgment-call dial-ins (commit `894a829`):** Per John's "wanna go ahead and dial them in?" greenlight, fixed the 6 remaining P0/P1 items requiring judgment:
- GA 60-day vs 90-day Affidavit of Nonpayment in `mechanics-lien.html` line 531 — corrected to 60 days per O.C.G.A. § 44-14-366(c)(1) as amended by HB 434 (effective Jan 1, 2021), with explicit "verify with GA construction counsel" note
- Master-Sub markup-stacking clarification (Sub markup capped at Owner-recoverable rate; GC adds on top per Prime Contract)
- Master-Sub 5.5 notice-to-proposal-clock chain explicitly tied (7-day notice → GC request → 10-day proposal clock)
- GMP Article 14.1 Savings formula reframed two-line to avoid double-counting
- GMP Article 14.4 added "as adjusted by all executed Change Orders" qualifier
- Change Order settlement language default flipped (Discrete-Scope preserves cumulative impact; Broad Settlement is opt-in alternative with red-bordered counsel-review note)
- Closeout SC silence-deemed-acceptance softened to state-counsel-dependent

**Agent finding that turned out to be wrong:** the agent flagged "FL pre-furnishing waiver $1M" at release-of-lien.html:673 as P0. Validated the line — it's actually about Pennsylvania (49 P.S. § 1401(b)), which is correctly stated. Agent crossed wires on state. No fix needed.

**Gap-analysis items I surfaced** (not in agent's punch list — for v1.1):
- CSI Divisions 11/12/13/14 missing from SOV (specialty equipment, furnishings, special construction, conveying systems / elevators)
- No Pencil Draft Agreement template (referenced in workflow as "single most important step")
- No Notice of Commencement template (required by FL/OH/MI/NJ for lien-rights flow)
- No Mutual Release at closeout (bilateral release between owner and contractor)
- Master Subcontract no occupied-buildings clauses (healthcare/institutional renovation)
- Closeout doesn't address LEED documentation
- Schedule doc has no visual Gantt rendering

### Complete tier zip + delivery to John

- ✅ **Complete tier zip rebuilt** (commit `913d473` first, then `ade28f5` and `894a829` for QA-fix rebuilds; final size 469KB).
- ✅ **Email delivered to John via Charles's Gmail** (Gmail message ID `19e2c81e0e867cd3`) at keith.john87@gmail.com from CharlesCreatorAI@gmail.com. Subject: "ContrPro Complete Tier — V1-GC-Complete build for SME review (15 May 2026)". Body includes inventory of zip contents + two-pass QA notes + focus areas for SME review + gap-analysis items for v1.1. Attachment: `contrpro-complete-v1-gc-complete-2026-05-15.zip` (469,437 bytes).

### Mid-day Charles harness fix #4 (commit `5569a8c`)

After John reported Charles felt incompetent in Telegram, diagnosed in Charles agent log conv 8455750177:
- Tightened cc_runner exec_shell guard from substring match to actual execute-pattern regex. Old guard false-positive'd on `grep "cc_runner.py"` etc.; new regex only blocks `python -m core.cc_runner` or `python core/cc_runner.py` patterns. Tested 9 should-block + 9 should-allow cases, all correct.

### Mid-day Charles harness fix #5 — set_goal mid-chain auto-nudge (commit `bac826e`)

After confirming Charles still didn't create a goal for the cc_runner work despite the MANDATORY rule in prompts.py:
- Added a harness nudge in `core/agent.py` round loop. When JOHN_CHARLES conv crosses round_n=4 with chain_tool_call_count >= 3 and no set_goal called yet, injects a one-time `[harness reminder]` synthetic user message into the chain. Audit-tagged for observation. Defaults: NUDGE_AFTER_ROUND=4, NUDGE_TOOL_CALL_THRESHOLD=3, fires at most once per chain.

### Late-afternoon — unattended-Mac recovery monitors

For John's upcoming travel home (Mac left at hotel office, needs auto-recovery on power-cycle):

**Audit findings:**
- ✅ pmset autorestart=1 (Mac auto-powers-on after AC restored)
- ✅ FileVault is OFF (no boot-time unlock needed)
- ✅ All 7 critical LaunchAgents have RunAtLoad=true + KeepAlive=true
- ✅ Tailscale Funnel config persistent (homes-mac-studio.tailc819f6.ts.net → 8090 survives reboot)
- ✅ Saved WiFi networks include MarriottBonvoy + 3 others
- ⚠️ **CRITICAL GAP:** No auto-login configured. LaunchAgents only fire AFTER user login. **Only John can fix** (System Settings → Users & Groups → Automatic login). John acknowledged 18:45 UTC: "I'll see if I can get it secured tonight."

**Defensive monitors shipped (commit pending — script files):**
- `scripts/boot_health_check.sh` + `~/Library/LaunchAgents/com.charles.boot-health-check.plist` — fires once per boot via RunAtLoad. Sleeps 90s then probes 7 LaunchAgents loaded + MLX/WarRoom/ContrPro local + Tailscale + Funnel public reachable + Internet clean (HTTP 204). iMessages John with full status.
- `scripts/captive_portal_watch.sh` + `~/Library/LaunchAgents/com.charles.captive-portal-watch.plist` — runs every 5 min via StartInterval=300. State machine in `workspace/captive_portal_state.txt` (CLEAN/CAPTIVE/OFFLINE). iMessages on state transitions + hourly reminder while still-captive (1hr cooldown). Marriott daily portal re-fires get caught.
- Both LaunchAgents loaded + verified registered. Captive-watch already ran one cycle (state=CLEAN, no alert sent).

**Pre-leave test plan (sent to John):** enable auto-login → confirm boot-health-check iMessage → hard power-cycle → wait 5 min → expect iMessage → from phone test WarRoom + Funnel URL.

### Commits today on Charles main (newest first)

```
894a829 GC suite QA round 2 — dial-in remaining P0/P1 items
ade28f5 GC suite QA fixes — auto-fix bounded items from QA pass
913d473 Rebuild complete-bundle-249.zip to include 8-doc GC suite
2ee9341 GC suite — Cost-Plus Agreement + Delivery Method Selection Guide
089e76c GC suite — GMP (Guaranteed Maximum Price) Agreement
4583b67 GC suite — Schedule Baseline + 3-Week Look-Ahead
445ac66 GC suite — Closeout (SC Cert + Punch List + Checklist + Final)
33c35f1 GC suite — Change Order Request + Authorization
70e4668 GC suite — RFI Log + Submittal Log + Transmittal templates
8e33342 GC suite — Master Subcontract Agreement
ac66646 GC suite — Application for Payment + SOV + Continuation Sheet
bac826e agent: auto-nudge Charles to set_goal mid-chain in JOHN_CHARLES
5569a8c tool_guards: tighten cc_runner block from substring to execute-pattern
7b02a18 Bring contrpro/ under version control
7f2e6b1 Charles harness: round-cap bump 5→15 + Plan-then-act rule
6faf498 Pre-Charles-self-edit baseline (2026-05-15)
```

Plus the recovery-monitor scripts commit (with the LaunchAgent plists noted but stored outside git at ~/Library/LaunchAgents/).

### Outstanding for John's call

- **Auto-login enablement** — only he can do this (his password). He committed to attempting "tonight" (18:45 UTC).
- **Steel Estimator rebuild** — ship-now vs v1.1 deferral (still pending; not blocking V1-GC).
- **Beta auth setup** — hash passwords + add `CONTRPRO_BETA_USERS` to `.env` + restart com.charles.contrpro. Only matters when ready to onboard real beta testers.
- **Optional: remote captive-portal-relogin tool** — I offered to draft this; John didn't say yes/no. Would let him SSH to the Mac from his phone and trigger Marriott portal re-login when away from the hotel. Build-on-request.

### SME review delivery

Complete zip emailed to John 16:48 UTC (Gmail msg `19e2c81e0e867cd3`). John will forward to his SME ("someone smarter than me, lol"). Punch list of focus areas + gap-analysis items included in email body so SME has a clear scope rather than a 5,486-line "tell me everything that's wrong" pass.

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
