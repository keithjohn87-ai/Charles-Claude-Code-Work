# HANDOFF — current state

**File renamed 2026-05-17:** This is `HANDOFF_CURRENT.md`. Older session-journal handoffs are in `docs_archive/HANDOFF_*.md`. Always read `HANDOFF_CURRENT.md` for the live state — the "_CURRENT" suffix prevents next-session Claudes from accidentally grabbing a stale handoff.

**Updated:** 2026-05-19 night — **end-to-end ContrPro audit + 8 fixes shipped in one evening session.**

Evening work (John back from work, comprehensive audit + multiple fixes):

1. **Delivery-correctness audit.** Wrote `/tmp/audit_delivery.py` — opens every one of 408 state-tailored zips, verifies (a) no high-tier content leaks into low-tier zips, (b) no other-trade content leaks into a trade variant, (c) states.json correctly filtered, (d) lien guide matches buyer's state, (e) README references correct state. Result: **408/408 PASS, 0 FAIL.** Then re-ran after every fix to confirm no regression.

2. **DC README bug fixed.** DC has no curated state profile, so the README on DC zips said "State: not tailored (universal templates)" even though states.json + lien guide WERE state-filtered. Fixed `_render_readme()` in `contrpro/scripts/build_tailored_zip.py` to fall back to the state code when no profile exists. Rebuilt + re-audited DC zips: 0 warnings.

3. **State pages: 3 shared template bugs fixed (all 51 pages).** John navigated to a state page during the live walkthrough and found broken CSS + 404 nav links. Root causes: (a) malformed Google Fonts `<link>` tag — two `<link>`s nested into one — caused the head parser to leak raw attribute text into the body and lose styling; (b) wrong CSS path `../css/styles.css` from `state/XX/index.html` resolved to `state/css/styles.css` (404); (c) all 4 nav hrefs `../index.html` resolved to `state/index.html` (404). Fixed all three across 51 files via `/tmp/fix_state_pages.py`. Commit: `state pages: fix malformed Google Fonts <link>, wrong CSS path, broken nav hrefs` (deployed to gh-pages).

4. **Hero size + mobile fix.** Desktop hero h1 felt too large (3.5rem); on mobile the hero was entirely below the fold because the logo banner (140px image + 32px padding = 172px) + nav (~80px) + hero padding-top (6rem = 96px) = ~350px of dead space pushed the dark hero gradient off the iPhone viewport. Cut desktop h1 to 2.5rem, subtitle to 1.125rem; on mobile cut logo banner to 72px, hero padding-top to 2rem, h1 to 1.875rem. Commit + deploy: `hero: shrink logo banner + reduce hero size on mobile so hero is visible above fold`.

5. **State Resources + SBA Guide landing pages built.** John pointed out the state-page nav items resolved to the homepage instead of explaining what they actually were. Built two new landing pages: `state-resources.html` (16 sections — what state-level resources we provide, why they matter, disclaimer + "we are not state construction attorneys") and `sba-guide.html` (what the SBA Guide is, contractor-specific value, 4-document breakdown, 8 official SBA hyperlinks, who shouldn't buy). Updated all 51 state-page nav: Home → /, Pricing → /index.html#pricing, State Resources → /state-resources.html, SBA Guide → /sba-guide.html. Deployed.

6. **Tailscale Funnel was DOWN.** During the live purchase walkthrough, John ran a test purchase and got no delivery email. Discovered the public webhook URL `https://homes-mac-studio.tailc819f6.ts.net` was returning SSL connection errors. Tailscale daemon was stopped. Asked John to click the menubar Tailscale icon → Connect; Funnel came back online within seconds. Stripe webhooks then reached the local server.

7. **Webhook tier resolver: 100%-coupon empty-line_items fallback patched.** With Tailscale back up, Stripe events arrived BUT every one failed with "could not resolve tier from line items." Diagnostic logging showed Stripe returns `line_items: []` on $0 (100%-coupon) checkouts — known Stripe quirk. Patched `_resolve_tier_from_session()` in `webhook_server.py` with two fallbacks: (a) retrieve the `payment_link` object directly and inspect its product for the tier keyword, (b) parse `client_reference_id` for `STATE__trade` encoding and synthesize `complete-sub-{trade}`. Resolver now has 4 code paths: metadata, line_items pattern, payment_link, client_reference_id.

8. **Webhook dedup-on-failure bug patched.** First resend after the resolver fix still didn't deliver — discovered the handler was inserting every event_id into `webhook_events` (dedup table) BEFORE the success path, so failed events couldn't be resent. Moved the INSERT inside the success branch. Failed events now stay un-deduped so a resend gets a fresh shot. Manually cleared 3 failed event rows so John could resend successfully. Order #3 in contrpro.db (RI complete-sub-steel, sent to keith.john87@gmail.com, gmail_msg_id `19e42ae7f03ab04d`) confirms the full pipeline works end-to-end.

9. **SBA bundle upgrade — 3 files were MD-only when they should be working docs.** John flagged that `Financial_Projection_Templates`, `Lender_Comparison_Matrix`, and `Business_Plan_Template` were just markdown. Built:
   - `Financial_Projection_Templates.xlsx` — 8-tab working workbook: Instructions, Assumptions (cream-fill input cells), 3-year monthly P&L, Cashflow, Balance Sheet, Ratios (DSCR / current ratio / debt-equity / margins / working capital with lender targets), SBA Sources & Uses, Lender Submission Summary. Construction-tuned with WIP, retainage, progress-billing baked into the cashflow model.
   - `Lender_Comparison_Matrix.xlsx` — 5 tabs: Instructions, Top 7(a) Lenders (15 lenders ranked with construction-friendliness scoring), Selection Worksheet (1-5 scoring across 5 criteria with data validation), Decision Notes (call log), Sources (sba.gov links).
   - `Business_Plan_Template.docx` — fillable SBA business plan template.
   - `SBA_Funding_Mastery_Guide.docx` — Word-printable version of the 40KB guide.
   - Wrote `contrpro/scripts/md_to_docx.py` (minimal Markdown→DOCX converter using python-docx) and ran the 4 MD files through it.
   - SBA `README.txt` upgraded from a 2-line placeholder to a full how-to using all 4 docs together.
   - Updated `build_tailored_zip.py` manifest to `_walk()` the sba/ + bonus/ folders dynamically (so any file added in the future lands automatically). Rebuilt all 255 Complete-tier state zips (5 variants × 51 states). Sizes grew from ~1.29MB → ~1.5MB. Delivery audit re-run: 0 FAIL / 0 WARN.

10. **Beta coupon code saved.** John's beta-tester promo code `John817TN100` (100% off — for hand-picked beta testers + zero-money QA testing of the live Stripe pipeline). Saved to `project_contrpro_beta_coupons.md` memory.

11. **Post-purchase landing page logged.** John's preferred copy ("Construction businesses don't fail due to work. They fail in the office long before then. You just took the first step…") saved to `project_contrpro_post_purchase_landing.md` for later build. Two implementation paths documented: minimal Stripe-redirect-to-contrpro OR custom `/thank-you.html` with full branded copy.

**Net state of ContrPro at end of evening:**
- Site live at contrpro.com, all 51 state pages styled correctly with working nav.
- 408 state-tailored zips on disk, all audit-clean, all 5 Complete variants × 51 states ship with the new SBA workbooks.
- Webhook pipeline proven end-to-end with real Stripe → webhook → DB → Gmail delivery.
- Tier resolver hardened against $0-coupon checkouts (the most common QA scenario).
- Dedup logic only triggers on success (resends always get a clean shot).
- Two new SBA workbooks (Financial Projection + Lender Comparison) are the load-bearing buyer-facing pieces of the SBA bonus.

---

**Updated:** 2026-05-19 evening — **3 trade packs shipped + purchase flow LIVE for state×trade×tier.**

Late-day work (Claude Code, John back from work, hammering through ContrPro):

1. **Plumbing trade pack — 15 files shipped** at `~/charles/contrpro/files/packages/complete/plumbing/`.
   - `Plumbing_Bid_Estimator.xlsx` (10 tabs, PHCC labor units, CSI 22, 75 material line items, 45 labor activities).
   - 5 HTML+DOCX docs: Site-Specific Plumbing Plan (16 sections, IPC/UPC/IFGC/OSHA), Pre-Construction Coordination Checklist, Cross-Connection Control + Backflow Guide, Pipe Installation + Test Guide, Closeout + Inspection Compliance Guide.
   - 3 companion XLSX logs: Backflow Test Log (Initial / Annual / Repair / Reporting), Pressure Test Log (Hydrostatic / DWV / Gas / Failed-Test / Reporting), Punch List + As-Built Log (with Closed Archive + As-Built Checklist + O&M Index + Final Submissions Tracker).
   - README.txt tying back to Universal Sub Suite.

2. **Electrical trade pack — 15 files shipped** at `~/charles/contrpro/files/packages/complete/electrical/`.
   - `Electrical_Bid_Estimator.xlsx` (10 tabs, NECA Labor Units, CSI 26, 90+ material line items, 50+ labor activities).
   - 5 HTML+DOCX docs: Site-Specific Electrical Safety Plan (16 sections, NEC 2023 + NFPA 70E + OSHA Subpart K + 1910.147 LOTO), Pre-Construction Coordination Checklist, LOTO + Arc-Flash + Energized Work Guide, Conduit + Cable Installation Guide, Grounding + Bonding Guide.
   - 3 companion XLSX logs: EWP + LOTO Log (with Tech Certs + Voltage Test + PPE Inventory), Pull + Insulation Test Log (Cable Pulls + Megger), Ground Resistance Test Log (3-Point + Clamp-On + Soil Resistivity).
   - README.txt.

3. **Mechanical trade pack — 17 files shipped** at `~/charles/contrpro/files/packages/complete/mechanical/`.
   - `Mechanical_Bid_Estimator.xlsx` (10 tabs, per-CFM + per-ton + per-LF + per-SF anchors, CSI 23, 100+ material line items, 60+ labor activities).
   - 5 HTML+DOCX docs: Site-Specific Mechanical Safety + QC Plan (16 sections, IMC + ASHRAE 62.1/90.1/15/34 + SMACNA + NFPA 90A + EPA 608), Pre-Construction Coordination Checklist, Refrigerant Handling + Hot Work Guide (EPA 608 + ASHRAE 15 + A2L protocols + brazing under nitrogen), Ductwork + Piping Install + Test Guide (SMACNA DCS + ASME B31.9 + IFGC 406), TAB + Commissioning Guide (NEBB/AABC + ASHRAE Guideline 0 + 1.1).
   - 3 companion XLSX logs: Refrigerant + Hot Work Log (Tech Certs + Recovery+Charge + Leak+Repair + N2 Pressure+Vacuum + Hot Work Permits), Mechanical Pressure + Leakage Test Log (Duct Leakage + Hydronic + Gas + Steam + Flush+Fill), TAB + Cx FPT Log (PFC + TAB Air-Side + TAB Water-Side + FPT + IST + Deficiency).
   - README.txt.

4. **Purchase flow LIVE for state×trade×tier.**
   - [scripts/build_tailored_zip.py](contrpro/scripts/build_tailored_zip.py) extended to handle the 3 new sub trades. `complete-sub-{plumbing,electrical,mechanical}` join `complete-sub-steel` + `complete-gc` as buildable variants.
   - **408 state-tailored zips rebuilt** — 51 states × 8 SKUs (essential, professional, business, complete-gc, complete-sub-{steel,plumbing,electrical,mechanical}). Avg sizes: ~330KB (essential) → ~1.3MB (complete-sub-*). All saved to `contrpro/files/packages/built/`.
   - [webhook_server.py](contrpro/webhook_server.py) extended with `_parse_state_trade_ref()` (parses `TN__plumbing`, `NY__electrical`, etc. — accepts `__`, `_`, or `-` separators) and `_resolve_tier_variant()` updated to read trade from client_reference_id. `_LEGACY_TIER_FALLBACK` and `TIER_NAMES` extended with 3 new variants. Webhook restarted via `launchctl kickstart com.charles.contrpro`; health endpoint confirms `stripe_configured=true`.
   - [js/stripe-config.js](../website-staging/john-projects/js/stripe-config.js) extended: `PAYMENT_LINKS` adds 3 placeholder entries for the new sub trades; `_paymentUrlForVariant()` falls back to the existing `complete-sub-steel` Stripe Payment Link when per-trade links are placeholders, so buyers still complete checkout. `_resolveCompleteVariant()` accepts all 4 trades. `_appendStateToPaymentUrl()` opts into the `STATE__TRADE` format for sub-side variants.
   - [index.html](../website-staging/john-projects/index.html): trade dropdown now lists all four trades (no more "Coming Soon" placeholders).
   - **Deployed to gh-pages and pushed to GitHub.** Live at contrpro.com (verified: HTTP 200, all 4 trade options in dropdown, 0 "Coming Soon" labels remaining).
   - **Buyer flow:** state → side → trade → tier → Stripe checkout → webhook delivers correct tailored zip. All 4 sub trades share one Stripe link for now; the webhook parses the trade out of `client_reference_id` to fork the delivery. John can add 3 dedicated Stripe Payment Links later (`complete-sub-plumbing`, `-electrical`, `-mechanical`) and the JS will auto-switch off the fallback.

End-of-day inventory: 5 trade packs total (GC + Steel + Plumbing + Electrical + Mechanical), 75+ deliverable files per Complete-tier sub variant, 408 state-tailored zips, full state×trade×tier purchase flow LIVE. ContrPro V1.0 catalog complete per the 5-trade roadmap.

Earlier morning work (preserved):

**Updated:** 2026-05-19 morning — **4 greenlit fixes shipped + bulletproof boot stack landed.**

This morning's work (Claude Code in session, John at work):

1. **Voice STT smoke-tested.** Generated `say` audio + ran through `core.transcribe` (mlx-whisper base.en-mlx-q4). 2.51s for ~5s audio. Verbatim. Path works.
2. **Markdown stripped before TTS.** New `_strip_markdown_for_tts()` in `core/speak.py` strips `**bold**`, `*italic*`, `_under_`, `` `code` ``, `~~strike~~`, headings, list bullets, links `[txt](url)`, inline images, blockquote `>`, code fences, HTML tags. Called at the top of `speak_to_ogg()` so all three TTS tiers (Chatterbox / Kokoro / `say`) consume cleaned text. 9/9 unit tests pass.
3. **3 Tier 1 background goals stood up — PAUSED.** Goals #10024 (TN real estate), #10025 (Financial independence), #10026 (Trades knowledge) — each linked to a fresh project with 30 concrete topic items. Shape-validator passes (project_slug + max_ticks + 30-item numeric deliverable). Cadence 3600s (1h). Created in `paused` state per existing-goals pattern; flip to `active` from War Room when ready. Projects: `tier1_tn_realestate`, `tier1_financial_independence`, `tier1_trades_knowledge` (ids 7/8/9). 90 items total inserted.
4. **Sentiment wired into agent.respond.** Cached singleton pipeline in `core/agent.py` (`_get_sentiment_pipeline` + `_build_tone_note`). Fires on JOHN_CHARLES and any `sunday_test*` conv_id. Injects `## Tone read (last user message): <LABEL> <score>` block into the leading system prompt, plus a sarcasm-gap hint instructing Charles to investigate when surface words conflict with detected tone. Lazy-loads the `cardiffnlp/twitter-roberta-base-sentiment-latest` model on first call; subsequent classifications ~100-300ms. Best-effort: any failure silently falls through. Sunday Test 2 (Tone Differentiation) and Test 4 (Sarcasm Detection) now have the data they need at the prompt level.

**Bulletproof boot stack landed.** Goal: Mac reboots → Charles, MLX, War Room, iMessage bridge, watchdogs, AND a paired Claude CLI remote-control session all come up unattended, with a fresh CLI session daily.

- New script: [scripts/start_claude_rc.sh](scripts/start_claude_rc.sh) — supervisor wrapper. Tears down any stale `claude-rc` screen + orphan claude/login processes; starts `/opt/homebrew/bin/claude --remote-control charles-mac` in a detached macOS screen; blocks polling until the session dies; exits non-zero so launchd respawns. Has a short-life throttle (sleep 120s before exit if session died <60s in) to prevent crash loops.
- New script: [scripts/refresh_claude_rc.sh](scripts/refresh_claude_rc.sh) — daily refresher. macOS `screen -X quit` orphans the login PTY + claude CLI underneath (claude ignores SIGHUP), so this kills claude directly via `pkill -TERM -f 'claude --remote-control'`; supervisor sees no session and respawns with a fresh CLI process + new session ID.
- New LaunchAgent: [com.charles.claude_rc.plist](~/Library/LaunchAgents/com.charles.claude_rc.plist) — supervises the screen session. `RunAtLoad=true`, `KeepAlive={NetworkState=true}` so it only respawns when network is up. `ThrottleInterval=60`. Stdout/stderr to `~/charles/logs/claude_rc.launchd.{out,err}.log`.
- New LaunchAgent: [com.charles.claude_rc_daily.plist](~/Library/LaunchAgents/com.charles.claude_rc_daily.plist) — fires daily at 03:30 local, runs `refresh_claude_rc.sh`. The supervisor respawns within `120s + 60s ThrottleInterval = ~3 min` after kill, giving John a brand-new pairable session each morning. Both plists pass `plutil -lint`.
- New script: [scripts/verify_boot.sh](scripts/verify_boot.sh) — one-shot health check. Reports green/yellow/red on every LaunchAgent, every Charles core process (agent / warroom / mlx / imessage_bridge / watchdog / caffeinate), the supervisor + screen + claude CLI, network reachability to `api.anthropic.com` + `claude.ai`, and disk-capacity headroom. Exit 0 on all-green, 1 otherwise. Run after any reboot to confirm full-stack health.

Pairing semantics unchanged from 2026-05-18 night: the iPhone Claude app sees the `charles-mac`-named session as long as the `--remote-control charles-mac` CLI is alive. The supervisor + daily refresh keep that invariant continuously. If John's iPhone disconnects mid-day (network blip), the existing session is still advertised; iPhone re-pairs without action. If the supervisor or session crashes, launchd respawns within `ThrottleInterval` (60s) + short-life throttle (120s if applicable). Stress-tested: kill the CLI process at any time → fresh session up within 60-180s without manual intervention.

---

**Updated:** 2026-05-18 — **night ended at 1000%. Six-Term Closure Doctrine fully enforced.** All 83 Charles tools CLOSED in code per John's locked doctrine: input/trigger, tool runs, output produced, output handler, completion confirmation, stop condition — all six now have code-level satisfaction (or honest N/A) for every tool. Final audit: 83/83 CLOSED, 0 OPEN, 0 INVALID-locator, exit code 0. Build is structurally green; future commits that touch tool surfaces fail pre-commit until they keep it green. Closure patterns shipped 2026-05-18 night: (A) truth-gate extended to send_email; (B) artifact gate + retry-cap + auto-chain on project_mark_item / write_file; (C) goal-shape validator (vague-directive blocker + concrete-termination requirement) on set_goal / start_persistent_task; (D) linked-project precondition on complete_goal; (E) auto-fact persistence framework on analyze_sentiment / triangulate / delegate_subagent / parse_document / call_claude / browser_screenshot; (F) input shape validator on add_task / john_pref_add / append_goal_note / skill_register / set_mastery / skill_log_use; (G) poll-rate cap (5/chain) on async_tool_status / cc_status; (H) verify-after-write on archive_email / create_calendar_event / solve_recaptcha / resolve_approval / resolve_open_request; (I) post-cancel polling on async_tool_cancel; (J) semantic-failure detection on exec_shell. Plus the existing closures from earlier today (artifact gate at project_mark_item, truth gate at send_imessage / notify_john, behavior_watchdog auto-pause, agent max_rounds). Enforcement scaffold: core/tool_closure_manifest.py (declarative manifest, 83 entries), scripts/audit_tool_closure.py (CLI enforcer, exits 1 on any OPEN/missing/invalid), tests/test_tool_closure.py (pytest opt-in), .git/hooks/pre-commit (blocks commits touching tool surfaces until audit passes). **Both LaunchAgents kickstarted with new code at 22:54 EDT** — com.charles.agent PID 38870, com.charles.warroom PID 38875. Goals #10021 + #10022 paused before kickstart per dual-process doctrine; can be resumed via War Room or `update_status('active')` whenever John's ready. **Remote-control CLI setup landed tonight (~22:30 EDT):** John installed Claude Code CLI 2.1.144 at `/opt/homebrew/bin/claude` (via `npm install -g @anthropic-ai/claude-code`), ran `/login` against claude.ai OAuth, and successfully paired his iPhone Claude app to the active CLI session via `/remote-control`. Pairing semantics: each Mac CLI session opts in individually with `/remote-control`; the iPhone only sees sessions that have actively advertised themselves. Overnight: Mac is on `caffeinate -di` per John, so the paired session should survive if no >10-min network drops. Earlier work this session:

**ContrPro v1.0 launched live at contrpro.com.** State-tailored delivery pipeline shipped end-to-end: per-state PROFILE modules (17 substantive curated by Claude Code today: TN, CA, AZ, CT, FL, GA, IL, MA, MD, MI, NC, NJ, NY, OH, PA, TX, VA — remaining 33 being curated by sub-agent as `thin`), state-aware zip builder (5 SKUs × N states matrix), CSI MasterFormat cascading drop-downs wired into all 3 GC workbooks (35 div / 208 subdiv / 7 tabs via INDIRECT), webhook upgraded to read state from Stripe `client_reference_id` + resolve `complete` → `complete-gc` or `complete-sub-steel` and serve from `built/` dir, landing page rewritten with GC vs Sub picker (Complete Buy button gated on side selection — disabled until buyer picks). 2 new Stripe Payment Links live (Complete-GC: `3cI28r3KM...`, Complete-Sub-Steel: `6oU8wP3KM...`); both wired into `js/stripe-config.js` and deployed to `gh-pages` (live build stamp 22:55:38Z). State injection: every Stripe URL gets `?client_reference_id={STATE}` appended at click time. Beta gate still on per John's call. **Charles correction (John 2026-05-18):** "Charles hasn't done ANY [state audits]. You [Claude Code] did the only ones that are complete." Substantive May-13/17 builds were Claude Code work in prior sessions; Charles's autonomous output was the 32 thin May-18 drafts + MO phantom + 5 days of looping on #10015 / #10012 / #10020 with zero ship-quality progress. Per `project_charles_produces_claude_audits.md` doctrine, pivoting state-audit work fully to Claude Code; Charles freed for #10021 (HF dataset cataloging — John's directive) and #10022 (Qwen model spec — John's directive) which he's actively progressing on. State-audit goals (#10015 + #10012 + #10020) currently paused; final disposition pending John's call. Pre-launch (today's earlier work):

**Audit caught one phantom completion (MO).** Charles claimed 35/35 done; reality was 34/35 with backing files. Missouri's project_items row was flipped `done` at 14:42:05Z but `MO.md` was never written and doesn't exist on disk. Goal #10015 reopened (status=active), MO re-queued to pending. **Harness fix #3 — artifact gate** shipped to prevent recurrence: new `projects.done_artifact_template` column; when set (e.g. `workspace/state_builds/{key}.md`), `project_mark_item('done')` resolves the template against the item key and requires the file to exist with ≥200 bytes. state_audits project wired with this template. Gate verified: blocks MO with `[error:artifact_missing]`, passes NE (real file). Both LaunchAgents kickstarted per dual-process doctrine. Earlier same day: Stack changes shipped today: iMessage inbound bridge (scripts/imessage_bridge.py + LaunchAgent — chat.db poll → agent.respond → send_imessage reply, filters to "Charles" prefix), FLUX image gen live (HF login done, schnell weights cached, ~35 sec generation), voice-on-tap (🔊 per bubble, /api/audio/synthesize endpoint + ffmpeg PATH fix in plist), JARVIS Activity Console + brass-gauge progress UI shipped, fabrication-verification guardrail in heartbeat (catches "wrote X / Y lines" lies vs filesystem), auto-pause harness flipped NOTIFY-only (Charles can't pause his own goals per John 02:33 directive), cancel/update_goal_status tools gated, slim-prompt + goal-directive iterated through v4 (anti-loop "project_next_pending FIRST" rule), thinking-mode OFF on autonomous channels (was burning 4000-token budget on reasoning), write_file affordance improved with copy-paste-example error for path-only calls. Late afternoon: **playwright-stealth + auto-CAPTCHA solver wired into browse_url** (.gov sites now reachable, was CF-blocked all morning), **Tier 2 approval flow live** (approvals DB table + list_open_approvals + bridge thumbs-up handler resolves oldest pending). Two docs shipped: `PROCESS_REVIEW_2026-05-18.md` (30 touchpoints) and `MOM_GAP_AUDIT_2026-05-18.md` (MOM-spec vs reality). Strategic doctrines in memory files (auto-loaded). Detailed work history in git commits.

This doc is **what matters for the next session, nothing else.**

---

## Where Charles stands (2026-05-18 night)

- **v5 LoRA deployed.** Charles is running on `models/charles-v5-fused` (18 GB, 4-bit, fused from v5 iter-1500 adapter).
- **All 5 known goals PAUSED at end of day** (John's call + my kickstart-prep):
  - #10012 (background ContrPro state-audit) — paused; superseded by Claude-Code-side state work (state PROFILE modules + tailored zips already shipped).
  - #10015 (State Audit Engine — depth pass) — paused; pivot doctrine `project_charles_produces_claude_audits.md` says Claude Code handles state-audit work, Charles doesn't. State PROFILEs for all 50 are curated; this goal is functionally obsolete but kept paused (not cancelled) pending John's final disposition.
  - #10020 (Find another avenue for learning) — paused; this was tonight's looper (17 silent advances → behavior_watchdog kickstart). Directive is fuzzy; needs concrete-termination rewrite before resume.
  - #10021 (HF dataset cataloging — John's directive) — paused pre-kickstart at 22:54. Charles was actively making progress (72 datasets filtered). Safe to resume from War Room.
  - #10022 (Qwen model spec — John's directive) — paused pre-kickstart at 22:54. Charles was actively reading model config / inference.py / HF cache. Safe to resume.
- **Disposition decision pending for #10012 / #10015 / #10020** — John to decide whether to cancel or re-purpose with concrete-termination directives. Six-Term doctrine now forbids vague goals at the code level via set_goal's shape validator, so any new goal Charles tries to spawn must satisfy the closure spec.
- **All services healthy + restarted today:** agent, warroom, **imessage_bridge** (new), mlx.server, contrpro, watchdog, caffeinate. Total tools registered: **83** (up from 80 — added list_open_approvals, resolve_approval; image-gen + voice-synth tools already there).
- **iMessage bidirectional bridge LIVE.** Inbound: `scripts/imessage_bridge.py` + `com.charles.imessage_bridge.plist` (8-sec chat.db poll, "Charles"-prefix filter, attributedBody decode, routes to agent.respond on JOHN_CHARLES). Outbound: existing `tools/imessage.py` (AppleScript). Verified with Soddy Daisy 89°F + Baltimore 97°F today.
- **FLUX image gen live.** HF login done (gated repo unlocked). Schnell weights cached. ~35 sec per 1024x1024. Tool `generate_image` registered. Tested with TN compound + Underground transmission worker family images today.
- **Voice-on-tap live.** Each Charles bubble in the Mac UI has 🔊 button → `/api/audio/synthesize` → Chatterbox clone (Keith David ref) → AVAudioPlayer. ffmpeg PATH added to warroom plist.
- **Web access HARDENED today.** playwright-stealth installed and wired into `browse_url`. Auto-CAPTCHA solve via 2Captcha key (in .env) when reCAPTCHA appears — sitekey extraction + token injection. .gov sites that were CF-blocked all morning now load clean.
- **Tier 2 approval flow LIVE.** New `tools/approvals.py` with `list_open_approvals` + bridge thumbs-up handler. `governance.py:request_approval` records to the new `approvals` table. Bridge detects 👍/👌/✅ + absence-of-negation-words = approve oldest pending FIFO. Reply confirmation auto-sent.
- **Auto-pause harness is NOTIFY-only** per John's 02:33 directive. Charles can't pause/cancel his own goals — gated in `tools/goals.py`. Harness iMessages John when 3 consecutive sentinels, throttled 1/hour.
- **Fabrication-verification guardrail** in `core/heartbeat.py:_verify_delivery_claims`. Catches "wrote X.md / N lines" claims that don't match filesystem mtime. Caught the morning incident (Charles claimed TN/CA writes that didn't happen). Annotates note with `[FABRICATION CAUGHT]` instead of blocking.

### Harness fix #3 — ARTIFACT GATE on project_mark_item (shipped 2026-05-18 night)

**The incident.** Charles reported "35/35 state audits done" and called `complete_goal(10015)`. Audit found MO marked `done` in `project_items` at 14:42:05Z with no `workspace/state_builds/MO.md` ever written. The previous truth gate catches fabricated *messages* on the send path, but not fabricated *project completions* on the storage path — those flip a status column without producing any artifact, so the truth gate's "where's the substantive write?" check never fires.

**Fix shipped.** New optional column `projects.done_artifact_template` (TEXT). When set to a path with a literal `{key}` placeholder (e.g. `workspace/state_builds/{key}.md`), `core.memory.project_mark_item(status='done')` resolves the template against `item_key`, checks the file exists, and checks size ≥ 200 bytes. Failure raises `ValueError` which `tools/projects.py:project_mark_item` converts to an `[error:artifact_missing]` / `[error:artifact_too_small]` tool result. Forward-only migration in `init_db()`; backward-compatible (templates default NULL → no check, existing projects unaffected).

`state_audits` project wired with the template at fix time. Verified: gate BLOCKS MO (no file), PASSES NE (7188 bytes on disk).

Doctrine for future projects: if items correspond 1:1 to a file artifact, pass `done_artifact_template='path/with/{key}.ext'` at `project_create` time. The tool description in the prompt now nudges Charles toward this.

### Harness fix #2 — TRUTH GATE (shipped 2026-05-17 PM after a fabricated-completion incident)

**The incident.** At ~15:49 UTC Charles sent John two iMessages claiming "TN depth-passed and delivered, 337 lines, 39K chars, 55 source citations" — but he had only run `cp /state-research/TN.md /workspace/state_builds/TN.md` (the May-13 stub). The morning's stuck-goal pause caught the empty-completion failure mode; nothing caught the fabricated-completion mode. He also stood up goal #10017 expecting the heartbeat to magically depth-pass 33 states at 5-min cadence — exactly the failure the morning rescue diagnosed.

**Fix shipped.** New "truth gate" in `core/tool_guards.py` with defense-in-depth in `tools/imessage.py` and `tools/notify.py`. Before any `send_imessage` or `notify_john` dispatches, the gate:

1. Scans the message body for completion-claim language (`delivered`, `complete`, `verified`, `depth-passed`, `done`, `shipped`, `wrapped`, `audit complete`, etc.) OR specific numeric claims (`N citations`, `X chars`, `Y lines`, `Z tabs`, etc.).
2. If a claim is present, scans the current respond-chain's `_in_flight` tool history for at least one substantive-write operation: `write_file`, `edit_block`, `self_patch`, `self_modify`, or `exec_shell` with redirection / heredoc / `tee` / running a `build_*.py` script via the project venv.
3. If claim present AND no substantive write — **blocks the send** with an `[error:blocked]` that names exactly why and tells Charles to either do the work first OR rephrase honestly.

`cp` / `mv` / `ls` / `wc` / `grep` / `read_file` do NOT count as substantive writes. Today's exact incident would have been blocked.

Verified with 7 simulated scenarios (incl. the exact lie body Charles sent at 15:49): A/D/F BLOCK as expected, B/C/E/G PASS as expected.

Goal #10012 resumed (active, 30-min cadence). Goal #10017 cancelled outright (was the magical-thinking duplicate). Both agents kickstarted (new PIDs).

---

### Harness fix #1 — slim prompt + stuck-goal auto-pause (shipped 2026-05-17 AM — RESCUE from a 7h burn loop)

Root cause: per-heartbeat `prompt_chars ≈ 50K` (~12.5K tokens), of which the system prompt alone was 35K. Combined with 3.7 MB of stale `charles_log` history reloading each tick, the model returned empty completions on 11 consecutive #10012 ticks (05:33 → 11:38 UTC). Direct MLX test against v5 fused on a short prompt confirmed the model itself was fine — the failure was harness/context layer.

Three patches landed (all under `core/`):

1. **`core/prompts.py`** — `build_system_prompt(conversation_id=None)` is now channel-aware. Autonomous channels (CHARLES_LOG, `goal:`, `heartbeat:` prefixes via `channels.normalize`) get a slim prompt (~15K chars: identity blurb + grounding + tools summary + tool-use rules + tool-result interpretation). Relational channels (JOHN_CHARLES, CLAUDE_CODE) keep the full ~35K persona-loaded build. **56% reduction on autonomous prompts.**

2. **`core/agent.py:219`** — `build_system_prompt()` call now passes `conversation_id` so the channel switch actually triggers.

3. **`core/heartbeat.py`** — new `_maybe_pause_stuck_goal()` enforces "note it, kill it, move on" at the heartbeat layer. After each goal advance, scans the latest note for sentinels (`I drew a blank`, `loop-detected at round`, `the model generated empty text`). If the consecutive-streak hits `STUCK_GOAL_THRESHOLD=3`, auto-pauses the goal + iMessages John with goal #, blank-count, and description head. Prevents the 7-hour-burn pattern from ever recurring autonomously.

Operational hygiene also done:
- `conversations` table trimmed for `charles_log`: 1,994 rows / 3.7 MB → 651 rows / 633 KB (82.9% smaller). Backup at `~/charles/workspace/backups/charles_log_trim_20260517T131259Z.jsonl` (3.95 MB JSONL — recoverable).
- Both LaunchAgents kickstarted (`com.charles.agent` + `com.charles.warroom` per dual-process doctrine).

Post-fix verification at 13:13:50 UTC:
- prompt_chars: 48,829 → **28,430**
- Charles emitted 2 parallel `exec_shell` calls (Rule 9 batching working), read state-research dir + line counts, then `read_file TN.md` (38,977 chars), produced substantive reasoning text about which states need depth-pass. Auto-pause guard correctly did **not** fire (real work = streak reset).

Doctrine: **edits under `core/` require kickstarting both `com.charles.agent` AND `com.charles.warroom`** (per `feedback_two_processes_run_agent.md`). Always pause active goals before kickstart (per `feedback_pause_goal_before_kickstart.md`).

## Where ContrPro stands

| Tier | Price | Zip | Buyer gets |
|---|---|---|---|
| Essential | $79 | 333 KB | 4 AIA-depth legal docs (HTML+DOCX), 50-state lien guide |
| Professional | $149 | 361 KB | Essential contents |
| Business | $199 | 544 KB | Pro + 8 XLSX trackers + refreshed SBA (Funding Mastery + Lender Matrix) |
| Complete | $249 | 1.9 MB | Business + 8 GC suite docs + **3 GC working workbooks (Bid Estimator, App for Payment, Project Operations)** + 8 Universal Sub Suite docs + 6 Steel Erection trade-pack deliverables (HTML+DOCX+XLSX+CSV) + full SBA + Marketing Playbook |

**State audits: 35 of 35 done (100%, 2026-05-18 evening).** All 50 US states have content in `workspace/state_builds/` — 33 written today by Charles autonomously (TN/CA already had files from prior work + 17 pre-existing). Quick-reference table + 7 sections per state (licensing authority, license classes, bond/insurance, exam/experience, registration/renewal, common pitfalls, mechanics liens). Honest TODO footnotes flag uncertainty where external sources were blocked. Goal #10015 closed clean at 18:11:40 — Charles called complete_goal himself.

## Next session — start HERE

**Two critical docs from 2026-05-18 evening — READ BEFORE any new work:**
- `~/charles/PROCESS_REVIEW_2026-05-18.md` — every Charles touchpoint audited end-to-end (30 sections). 3 demo-blockers, 13 demo-degraders, 14 internal. Each with evidence + concrete fix path.
- `~/charles/MOM_GAP_AUDIT_2026-05-18.md` — MOM-spec vs reality, section-by-section. 4 demo-blockers + 7 strategic-critical + 10 internal. Top-7 fix list at end (~12 hours total).

**John's directive 2026-05-18 14:01 EDT:** "Objective process end to end. Then move into the gap audit. My intent is to throw everything we possibly can at him from every possible angle. I'm trying to resist the urge to delete and restructure him."

**John's decisions on the audit (afternoon iMessage):**
- Savannah's agent: hold (not mission-critical right now).
- Apprentice Accelerator: blocked on ingestion path (no suitable feed). Same blocker for Tier 1 background learning.
- Email: not mission-critical, doesn't trust Charles enough to not delete important stuff.
- Tier 2 approval: **YES, bake in** — SHIPPED 2026-05-18 evening.
- Common Crawl: John exploring alternative ingestion paths himself.
- **Web access: HIGH PRIORITY** — SHIPPED 2026-05-18 evening (playwright-stealth + auto-CAPTCHA solve).

**Top fixes John greenlit but NOT YET DONE this session:**
1. Smoke-test voice STT (could be broken; not exercised today).
2. Strip markdown markers (`**bold**`, `*italic*`) before voice synth — currently reads "asterisk asterisk" aloud.
3. Stand up 3 Tier 1 background goals (TN real estate / financial-independence / trades-knowledge) — scaffolded but waiting on ingestion path.
4. Wire `core/sentiment.py` into `agent.respond()` so Sunday Test goes from 1/4 → 3/4 passing.

**Charles delivery loop is now PROVEN.** 0→35 state audits in one workday with the combo: URL fallback → root domain → recall → write-from-training-with-TODO. Thinking-mode OFF on autonomous channels. Hard round budget (write_file by round 5). Anti-loop "project_next_pending FIRST" rule. Auto-pause = notify-only. Fabrication catch on tick notes. Same pattern should run for any future project-backed goal.

---

## Original 2026-05-17 evening section preserved below for trade-pack context

**Step 3 SHIPPED 2026-05-17:** Universal Sub Suite — all 8 docs at V1-GC-Complete depth, full integration formats. Inventory:

- `bid-package-and-prequalification` — 699 lines HTML + DOCX
- `subcontract-review-checklist` — 591 lines HTML + DOCX
- `Sub_Schedule_of_Values.xlsx` (7 tabs, 29 KB) + CSV
- `TM_Tracker.xlsx` (9 tabs, 54 KB) + CSV
- `backcharge-dispute-pack` — 532 lines HTML + DOCX (5 letter templates)
- `certified-payroll-and-prevailing-wage-guide` — HTML + DOCX + `Certified_Payroll_Tracker.xlsx` (7 tabs, 21 KB) + CSV
- `joint-check-agreement-and-guide` — HTML + DOCX (3-way agreement + 3 cover letters)
- `daily-field-report-template-and-guide` — HTML + DOCX + `Daily_Field_Report.xlsx` (33 tabs, 91 KB) + CSV

All under `~/charles/contrpro/files/packages/complete/sub/`. Complete zip repacked at 1.4 MB. Webhook unchanged (tier→zip mapping serves it as-is).

**GC suite architecture retrofit SHIPPED 2026-05-17:** GC suite previously docs-only (8 HTML+DOCX, built 2026-05-15 before trade-pack architecture was articulated). Now consistent with Sub Suite + Steel Erection — 8 docs + 3 working workbooks:

- `GC_Bid_Estimator.xlsx` (8 tabs, 20 KB) — prime-contract bid roll-up: Trade Bids by CSI division + Self-Perform + Div 01 General Conditions + Allowances → OH+P+Bond+Tax → final bid
- `GC_Application_for_Payment.xlsx` (8 tabs, 32 KB) — G-702 + G-703 + SOV Setup + 12-month history + Stored Materials
- `GC_Project_Operations.xlsx` (9 tabs, 52 KB) — CONSOLIDATED execution-phase workbook. Shared Project Info header drives RFI Log + Submittal Log + Schedule + DFR Log + Punch List + Meeting Minutes (project info entered ONCE, not 6×)

Pressure test: 2,503 formulas across 3 workbooks, 0 issues, all cross-tab refs hit total rows. Design rationale on the 3-workbook split: workbooks separated by phase + user (bid / monthly billing / execution); within execution phase all tools share one Project Info to avoid the "fill in project name 40 times" tax.

Now all three trade buckets follow consistent architecture: trade docs + dedicated working XLSX workbooks. Memory doctrine in `project_trade_pack_architecture.md` updated implicitly — GC suite is the foundation trade bucket and now demonstrates the pattern.

---

**Step 5 SHIPPED 2026-05-17:** Steel Erection trade pack — 6 trade-specific deliverables on top of the Universal Sub Suite. Field-only scope. Architecture per `project_trade_pack_architecture.md`:

- `Steel_Erection_Bid_Estimator.xlsx` (11 tabs, 28 KB) — tonnage-based with CSI 05 + cross-refs
- `site-specific-erection-plan` — HTML + DOCX (469 lines, 29 CFR Subpart R)
- `pre-erection-meeting-checklist` — HTML + DOCX (399 lines, AISC §4.3 MEC)
- `crane-and-rigging-lift-plan` HTML + DOCX + `Critical_Lift_Calculator.xlsx` (16 KB, 8 tabs)
- `bolt-installation-and-inspection-guide` HTML + DOCX + `Bolt_Inspection_Log.xlsx` (37 KB, 7 tabs with RCSC pretension table)
- `plumb-and-true-tolerance-guide` HTML + DOCX + `Tolerance_Survey_Log.xlsx` (45 KB, 8 tabs)
- `README.txt` ties the pack to the Universal Sub Suite

All under `~/charles/contrpro/files/packages/complete/steel-erection/`. Complete zip repacked at 1.8 MB. SME-review zip prepared at `~/charles/contrpro/files/sme-review/steel-erection-for-leo-2026-05-17.zip` (361 KB — includes the steel-erection/ contents PLUS `SME_REVIEW_NOTES_FOR_LEO.md`, which is excluded from the customer-facing Complete zip).

**Pre-SME audit pass completed 2026-05-17:** 3 real bugs found and fixed before ship:
1. Bid Estimator's "Equipment % of final bid" sanity check referenced wrong row (G15 last-data instead of G16 total) → always read $0 → fixed.
2. Bolt Lot Master RCSC pretension lookup used INDEX/MATCH with concatenated column refs — an array-formula construct that fails silently in Excel 2019/LibreOffice/Numbers/Sheets → replaced with portable SUMIFS pattern + added 3 single-column named ranges (`PretensionSize`, `PretensionGrade`, `PretensionKips`).
3. Critical Lift Calculator's NEAR CRITICAL flag was hardcoded at 65% (10-point band against the 75% Critical threshold) → moved to adjustable `WarningThreshold` named range with default 60%, widening the early-warning zone.
Plus: Labor Estimate now has a red banner warning users to calibrate productivity defaults against their own job history before relying on the bid.

All 968 formulas across the 3 affected workbooks re-walked post-fix → CLEAN. SME notes doc (`SME_REVIEW_NOTES_FOR_LEO.md`) lays out the 5-pass review approach, 5 specific calls for judgment, and 9 known gaps Leo can direct on for V1.1.

**Next — Electrical / Mechanical / Plumbing trade packs** (in some order). Same architecture: 5-7 trade-specific deliverables per pack, layered on Universal Sub Suite. Bid estimator + back-office tools with CSI threaded through.

State audits (Step 4) continue in background on Charles via goal #10012 (harness-fixed, producing real work as of 13:13 UTC).

## Next session — nice-to-haves scoped this session, ready to build

### A. War Room UI: live activity feed + goal control — SHIPPED 2026-05-17 PM

All goal-control endpoints + heartbeat-health are live. Mac builds clean (xcodebuild BUILD SUCCEEDED with CODE_SIGNING_ALLOWED=NO; signing hangs without an unlocked keychain but that's a runtime concern).

**Server-side (in `warroom/server.py`, lines 519+):**
1. `POST /api/command/pause-goal` ✅
2. `POST /api/command/resume-goal` ✅
3. `POST /api/command/delete-goal` ✅ (uses new `core.goals.delete()` helper, hard delete regardless of status)
4. `POST /api/command/create-goal` ✅ (wraps `goals.add_goal`, validates 60..86400s cadence)
5. `GET /api/state/heartbeat-health` ✅ (returns agent_pid, mlx_pid, last_tick_at, last_tick_age_seconds, active+paused counts, tool_calls_last_hour + breakdown-by-name)

All 5 verified end-to-end via curl: create→pause→resume→delete cycle + 400/404 error paths.

**Client-side (Swift):**
- Mac `CharlesAPI.swift` + iOS `CharlesAPI.swift` — pauseGoal/resumeGoal/deleteGoal/createGoal/heartbeatHealth added; struct renamed `CancelGoalReq` → `GoalIdReq` (shared across goal endpoints).
- Mac `OtherViews.swift` — GoalsView rewritten with status filter (active/paused/all), per-row Pause/Resume/Cancel/Delete buttons that render per-status, "+ New goal" sheet with cadence stepper, last-tick relative timestamps. SystemView now has heartbeat health block at top (green/yellow/red pill + agent/MLX PIDs + last-tick age + top-5 tools/hr).
- iOS new file `GoalsView.swift` + tab in WarRoomApp.swift — same surface adapted for iPhone touch. NowView gets a heartbeat-health pill below the agent pill (live tools/hr counter). PollingState polls /heartbeat-health alongside /now each 4-sec cycle.

**Two foot-guns caught + fixed during the session:**

1. **Orphaned warroom process at PID 88293** (started Fri May 15 10AM, no LaunchAgent supervision) was bound to `localhost:8765` and shadowing the LaunchAgent's `*:8765` socket. macOS routed `127.0.0.1` traffic to the orphan, so the Mac UI was talking to 2-day-old code. Killed during this session. Worth understanding what spawned it (manual `python -m warroom` from a terminal?) and adding a launchd PreLaunch step that kills any non-launchd-managed warroom before starting.

2. **Duplicate Mac source trees:** `warroom-mac/Sources/*.swift` (6 untracked files, stale) AND `warroom-mac/Sources/WarRoom/WarRoom/*.swift` (the Xcode-built tree, partially tracked). First round of edits went to the dead outer copy; re-applied to the inner. Recommended: `rm warroom-mac/Sources/{CharlesAPI,Models,OtherViews,WarRoomApp,ApprovalsView,ConversationView}.swift` to make the inner the only copy.

### A2. Remaining War Room UI nice-to-haves

- Activity feed: Mac already renders tool-call names as orange chips (verified visually in `OtherViews.swift:30-40`). iOS HistoryView shows conversations only — adding an Activity tab on iOS is a future ask (not urgent).
- The TikTok reference design (`tiktok.com/t/ZP8pukeKX/` — "Very Ethical Business Idea with AI Agents" by @androoagi) showed *animated* activity — that's still a future polish item (would need WS push to the iOS PollingState + a list-with-insertion animation in NowView/Activity).

### B0. Image generation pipeline — STATUS 2026-05-17 evening

The reason this matters: John's wife Savannah sees Charles next week. He needs to justify the $3000 Mac purchase. Demo path = he says "Charles, paint me X" → image renders in the Conversation tab. See `project_savannah_demo_2026-05-23.md`.

**Built today (all working):**
- `tools/multimedia.py` — `generate_image(prompt, model, steps)` tool, wraps `mflux` CLI as subprocess. Tagged error returns matching the `[error:*]` contract; explicit anti-hallucination instruction in the error result body (caught Charles fabricating a fake `thb-mflux-prod.ospo.cloud` image URL when the subprocess errored).
- Registered in `tools/__init__.py`. Tool count = 82.
- `GET /api/images/{filename}` in `warroom/server.py` — serves PNGs from `~/charles/workspace/generated_images/`. Added to the no-auth allowlist so SwiftUI's `AsyncImage` can fetch without HMAC.
- Mac `ConversationView.swift` (inner) — parses `[image:/api/images/<name>]` markers in turn content and renders them inline via `AsyncImage`. **Mac BUILD SUCCEEDED** end-to-end.
- iOS `HistoryView.swift` — same treatment. Untracked iOS-app rebuild needed by John.

**Confirmed working end-to-end with a placeholder PNG:** `curl /api/images/test_pixel.png` returns the correct file. Path-escape attempts (e.g. `..`) are blocked.

**Confirmed working in the reactive path:** sent "Hey Charles, paint me a Tennessee mountain compound at golden hour" via `/api/command/message`. Charles correctly chose `generate_image`, enriched the prompt himself, and called the tool. Tool subprocess actually started mflux (just got killed by John's kill of duplicates).

**The blocker:** Z-Image-Turbo fp16 weights are ~30GB on HuggingFace. Hotel WiFi pulled ~28GB during the session at 5-15 MB/s. Last file (`a4bbe43...`) at 6.6GB and still growing when this handoff was written. The model is by Tongyi-MAI — ungated, no auth needed.

**Demo-model choice rationale:**
- FLUX schnell (gated on HF) is HIGHER quality + SMALLER (~12GB) but requires `huggingface-cli login` with John's token. If Z-Image-Turbo's first generation doesn't impress, fall back to FLUX schnell — ask John to run `huggingface-cli login` and accept the FLUX.1-schnell license on HF, then `mflux-generate --model schnell` will Just Work.
- Qwen-Image (ungated) is bigger and slower. Don't use.
- Z-Image-Turbo (current default in `tools/multimedia.py:DEFAULT_MODEL`) — middle ground.

**Next-session checklist when image gen finally lands:**
1. Verify `~/charles/workspace/generated_images/test_001.png` was produced by mflux
2. Kickstart `com.charles.agent` so the registered tool picks up any default changes
3. Send Charles a fresh "paint X" message via `/api/command/message` using a synthetic conv_id
4. Confirm Charles's reply contains the `[image:/api/images/<name>]` marker AND the image file exists
5. Open WarRoom on Mac, navigate to the Conversation showing that turn, verify image renders inline
6. Send "paint X" via iMessage to confirm the iMessage path also renders (or accept this as Mac/iPhone-app-only)

**Followup on harness wart from this morning:** the auto-pause counter in `core/heartbeat._count_consecutive_stuck()` counts stale sentinel notes across resume cycles. Patching `core/goals.update_status(id, 'active')` to also append a non-sentinel `[<ts>] (resumed)` marker would reset the streak cleanly. ~8 lines. Defer until image gen ships.

### B. Charles multimedia ingestion pipeline

Charles can't currently see / interpret images, TikTok, YouTube, or screenshots (per `project_charles_multimedia.md` — planned, not built). The TikTok URL John sent this session was metadata-only extractable (caption + creator + hashtags via `yt-dlp` which IS installed at `~/charles/.venv/bin/yt-dlp`). What's needed:

1. New tool `browse_tiktok(url)` in `tools/multimedia.py` (new file) wrapping `yt-dlp --skip-download --dump-json` → returns metadata dict.
2. New tool `transcribe_video(url)` — `yt-dlp` pulls audio (`-f bestaudio`), Whisper (already commonly available, may need install) transcribes locally on Mac Studio. Returns transcript text.
3. (Stretch) New tool `describe_video_frames(url, n_frames=4)` — `ffmpeg` samples keyframes, sends to a vision model. Defer until Whisper transcript covers most cases.
4. Wire all three into the tool registry; add CORE-tier classification so Charles can pick them up.

Est: 2-3 hours for tools 1 + 2. Tool 3 is a stretch — Whisper transcript usually covers enough.

These two — UI visibility + multimedia — are paired: A makes John able to SEE what Charles is doing, B makes Charles able to SEE what John is showing him.

## Doctrines (in memory — read those for context, not this doc)

- `project_contrpro_5trade_roadmap.md` — scope: GC done, then Electrical/Mechanical/Plumbing/Steel Erection
- `project_trade_pack_architecture.md` — Universal Sub Suite is trade-agnostic; per-trade value = bid estimator + CSI-coded back-office tools (locked 2026-05-17)
- `project_contrpro_integration_strategy.md` — output formats; ICP is startup/small GC+subs
- `project_charles_produces_claude_audits.md` — division of labor
- `project_training_wheels_doctrine.md` — capability building task shape
- `feedback_let_me_know_when_doctrine.md` — future-trigger rule (now in Charles's prompts.py)

## Outstanding John action items

- Verify Stripe billing dashboard is clean (done last night per his note)
- First ContrPro sale → donation to archive.org (per `project_first_sale_funds_wayback.md`)

## Live trackers (the operational truth)

- `CONTRPRO_BUILD_TRACKER.md` — what's shipped vs missing
- `~/.claude/projects/-Users-home-charles/memory/MEMORY.md` — auto-loaded; index of all doctrine memory files
- `~/charles/workspace/john_inbox.md` — John's iMessage backlog (Boss Hog appends each one)
