# ContrPro Build Tracker — "ready to sell a real product"

**Last updated:** 2026-05-15 morning · *Claude Code keeps this file in sync as work lands.*

## STATE AS OF SESSION WRAP 2026-05-15 morning

**Shipped this run (2026-05-13 through 2026-05-14):**
- 18 state audits (TN, CA, TX, NY, FL, GA, IL, NC, WA, OH, VA, PA, MI, NJ, MA, MD, CT, AZ)
- 8 of 8 user XLSX trackers
- 3 of 4 legal docs at AIA depth (Construction Contract 1,330L, Preliminary Notice 935L, Mechanics Lien 1,072L)
- Charles harness Fix #1/#2/#3 active
- Geo-aware Hero (16 states) + 5-trade picker + state-page template + beta lockdown — LIVE on contrpro.com
- `call_claude` tool shipped (inactive — needs API key + kickstart)
- Build infrastructure: tracker, handover docs, builder scripts, persistent staging location at `/Users/home/charles/website-staging/`

**See `/Users/home/charles/HANDOFF_2026-05-15_morning.md` for full session-pickup brief.**

---


## TL;DR — how far are we?

| Bucket | Status | Effort to "ship-ready" |
|---|---|---|
| Payment & delivery infrastructure | ✅ **DONE** | 0 hrs |
| Charles harness Fix #1 (ToolResult envelope) | ✅ **STAGED, activates on next restart** | 0 hrs |
| Charles harness Fix #2 (Error categories) | ✅ **STAGED, activates on next restart** | 0 hrs |
| Charles harness Fix #3 (Schema budget + adaptive tool selection) | ✅ **STAGED, activates on next restart** | 0 hrs |
| Site frontend (the public-facing UX) | 🟡 **STAGED, needs merge** | 0 hrs (your merge auth) |
| State compliance content (50 states) | 🟡 **14 of 50 done** (TN, CA, TX, NY, FL, GA, IL, NC, WA, OH, VA, PA, MI, NJ) — all 8 "Popular" + top 6 next-tier states. MA + MD stalled on rate-limit re-engagement; queued to resume after ~18:19 UTC. | ~4 hrs (parallelized) |
| 4 legal documents at "real lawyer reviews and signs off" depth | 🔴 **STUB QUALITY** | ~12 hrs |
| Spreadsheet trackers as real working XLSX (formulas, dashboards) | ✅ **8 of 8 user trackers SHIPPED** — Job Costing, Change Order Log, Project, AR, AP, COI, Subcontractor, Subcontractor Pro. Steel Estimator still pre-dates new pattern; minor audit pending. | ~1 hr (Steel Estimator review) |
| SBA suite (guide + biz plan + projections + lender matrix) | 🟡 **MOSTLY REAL, needs 2026 refresh** | ~6 hrs |
| Marketing Playbook (Complete-tier bonus) | 🔴 **2-LINE PLACEHOLDER** | ~12 hrs |
| Tier zip rebuild + backend wire-up | 🔴 **OLD STUB ZIPS BEING SERVED** | ~1.5 hrs |
| Stripe cleanup (delete `(Copy)` test products) | 🔴 **NOT DONE** | 5 min (you, via Stripe UI) |

**Honest estimate to "first real customer can buy + receive substantive deliverables":**

- **Most aggressive (full days of parallel content work, no rework):** 3 days
- **Realistic with iteration:** 5–7 days
- **Beta-testable by regional GCs at the quality bar you set:** 7–10 days

Not light years. Days. But the days require focused execution, and you're rate-limited by:
1. The legal docs need real depth (each ~3 hrs of careful writing — no shortcuts)
2. The marketing playbook needs to be substantive enough to differentiate from generic AI slop
3. State audits at 5–10K words × 47 remaining states is the longest pole

---

## Current state, component by component

### 🟢 Payment + delivery (LIVE NOW)

- Stripe checkout → webhook → backend → email → download chain works end-to-end (tested 2026-05-13)
- 3-download cap per token, email gate before download, mailto re-issue flow
- Tailscale Funnel public URL is stable, backend `/health` is 4/4 green
- LaunchAgent auto-restarts the backend on Mac reboot
- Frontend `webhook-backend-integration` PR merged to master, GitHub Pages rebuilt

**Risk:** if the (Copy) test products are still active in Stripe, a confused customer could buy one and get a placeholder. → delete them when you have a sec.

### 🟡 Frontend (STAGED, your 1-click ship)

Local clone at `/tmp/john-projects-clone/` has uncommitted changes:
- 5-trade contractor picker (Mechanical replacing HVAC, Roofing dropped)
- Geo-aware Hero with TN/CA/TX live state callouts (other states show soft "rolling out" eyebrow)
- beta.html locked down (noindex + real form gate)
- states.json upgraded with TN/CA/TX audit-verified content
- New CSS for hero eyebrow + callout

**To ship:** push to a new branch, open PR, merge in GitHub UI (~2 min of your time).

### 🟡 State compliance content (3 of 50 done)

**Audited (with primary-source citations, current as of 2026-05-13):**
- `state-research/TN.md` — 5,175 words, 55 citations
- `state-research/CA.md` — 8,907 words, 72 citations
- `state-research/TX.md` — 11,371 words, 88 citations

**In progress (background agents):**
- FL.md
- NY.md

**Still needed (47 states):** AK, AL, AR, AZ, CO, CT, DC, DE, GA, HI, IA, ID, IL, IN, KS, KY, LA, MA, MD, ME, MI, MN, MO, MS, MT, NC, ND, NE, NH, NJ, NM, NV, OH, OK, OR, PA, RI, SC, SD, UT, VA, VT, WA, WI, WV, WY

**Cadence:** 1 agent run ≈ 6–10 min per state. Running 2–4 in parallel ≈ 12–18 hrs of agent runtime for all 47, but parallelized to your wall-clock time of ~3 hrs if we burn them all overnight.

### 🔴 Legal documents (the highest-stakes asset)

Currently on disk in `files/packages/essential/documents/`:
- `preliminary-notice.html` — 113 lines, generic skeleton with `[fillable]` placeholders
- `mechanics-lien.html` — 245 lines, same
- `release-of-lien.html` — 105 lines, generic
- `construction-contract.html` — 264 lines, has structure (Parties → Scope → Payment → Changes → Insurance → Lien → Warranty → Dispute → Termination) but each section is one paragraph

**Where the bar is:** AIA A101 + A201 territory — real indemnification clauses, real insurance specs (CGL minimums, additional insured wording, waiver of subrogation, builder's risk, umbrella), force majeure (post-pandemic-standard), notice provisions, integration, severability, state-overlay sections.

**Effort:** ~3 hrs per doc × 4 = ~12 hrs focused writing. Could be parallelized via agents but quality demands careful review.

### 🔴 Spreadsheet trackers (look real, aren't yet)

On disk as **CSV files with real headers but no formulas, no calculations, no dashboards:**
- Job_Costing_Spreadsheet.csv (182 lines of header + empty rows)
- Change_Order_Log.csv
- AR_Tracker.csv, AP_Tracker.csv, COI_Tracker.csv
- Project_Tracker.csv, Subcontractor_Tracker.csv, Subcontractor_Tracker_Pro.csv
- Steel_Estimator_CSI_MasterFormat.xlsx (this one IS a real XLSX, 14KB)

**Where the bar is:** working XLSX files with formulas (budget vs actual vs committed, percent-complete, retainage holding, aging buckets), conditional formatting, summary dashboards. What real GCs use Procore/Sage 300 for in mini form.

**Effort:** ~45 min per tracker × 8 = ~6 hrs.

### 🟡 SBA suite

On disk and substantive:
- `SBA_Guide.pdf` (24KB) + `SBA_Guide.docx` (14KB) — real content
- `SBA_Funding_Mastery_Guide.md` (231 lines)
- `Business_Plan_Template.md` (412 lines)
- `Financial_Projection_Templates.md` (315 lines)
- `Lender_Comparison_Matrix.md` (362 lines)

**What's missing:** 2026-current SBA program details (7(a) caps, 504, SBA Express, Community Advantage current numbers), named real lenders with current underwriting nuances (Live Oak, Newtek, Huntington, Wells Fargo SBA), construction-specific NAICS-23 guidance.

**Effort:** ~6 hrs.

### 🔴 Contractor Marketing Playbook (Complete-tier bonus)

Current state: 2-line placeholder file. Promised by the Complete bundle.

**Where the bar is:** 40–80 page playbook covering 2026 contractor marketing reality — Google Business Profile dominance, local-pack SEO, BuildZoom/Houzz/Angi mechanics, direct lead-gen platforms (Service Direct, Networx), commercial channel (Dodge, ConstructConnect), referral systems, reputation management, pricing strategy, estimating speed.

**Effort:** ~10–15 hrs (longest pure-content task).

### 🔴 Tier zip rebuild

Backend `TIER_FILES` currently points at:
- `essential-forms-79.zip` (5.9KB — trial stub)
- `professional-package-149.zip` (11.7KB — trial stub)
- `business-system-199.zip` (12KB — trial stub)
- `complete-bundle-249.zip` (12KB — trial stub)

The REAL 292KB `contractorpro-v5-complete-bundle.zip` exists but isn't wired. The real source content (CSVs, HTML legal docs, MD guides) exists but isn't packaged into per-tier zips.

**Effort:** 1.5 hrs once the content above is finalized — straightforward zip + backend repoint.

---

## Critical path to first real sale

In order of dependency:

1. **Stripe cleanup** (5 min, you) — delete (Copy) test products + archive their payment links
2. **Frontend merge** (2 min, you) — push the staged changes, open PR, merge
3. **Legal docs at real depth** (12 hrs me, in 4 sessions of ~3 hrs each)
4. **Spreadsheets as working XLSX** (6 hrs me)
5. **SBA suite refresh to 2026 data** (6 hrs me)
6. **Marketing playbook from scratch** (12 hrs me)
7. **State audits 4–50** (3 hrs wall-clock if parallelized aggressively)
8. **Generate 50 state pages from audited data** (1 hr me, mechanical from states.json)
9. **Repackage tier zips with real content** (1.5 hrs me)
10. **Backend `TIER_FILES` repoint** (10 min me)

**Steps 3–6 are the long pole.** They can run in parallel via agents but quality demands review. Steps 7–10 are mechanical once 3–6 land.

---

## What's running RIGHT NOW

- **FL.md state audit** — agent (running)
- **NY.md state audit** — agent (running)
- **Harness Fix #1 (ToolResult envelope)** — code shipped to disk, activates on tonight's manual reboot, all 13 smoke tests pass
- **Harness Fix #2 (Error categories)** — paused mid-implementation to write this tracker; resumes after

## What we lost overnight

- The auto-reboot at 3:30 AM failed (script killed itself before issuing restart — see HANDOFF). Fixed. Re-armed as a 7 PM iMessage reminder for John to manually reboot.

## Notes from John that shape priorities

- "I do not under deliver in the real world."
- "1,000,000% confidence to ship to real construction companies."
- "Quality always wins over cool."
- "We will reboot tonight so I have time to fix things if not all systems come online."
- "Charles is John's revenue + legacy path" (per memory).

— Claude Code
