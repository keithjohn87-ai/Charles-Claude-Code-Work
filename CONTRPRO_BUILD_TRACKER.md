# ContrPro Build Tracker

**Updated:** 2026-05-17 ~10:50 PM EST · Tight current-state snapshot. Older history is in git + memory files.

## Product scope (locked 2026-05-17)

ContrPro covers **5 trade buckets**, each at V1-GC-Complete depth:
1. **General Contractor** — V1-GC-Complete SHIPPED 2026-05-15 (8 docs / 5,486 lines)
2. **Electrical** — pending
3. **Mechanical** — pending
4. **Plumbing** — pending
5. **Steel Erection** — pending (FIELD-ONLY scope — no fabrication)

ICP: **startup/small GCs + subs**. 1-3 person shops. Not Procore territory.
Integration moat: **every doc ships in Word + Google Docs + PDF + XLSX + CSV-with-QB-headers**. "Your tools, our forms."

## Current shelf — what a buyer actually gets today

| Tier | Price | Zip size | Contents |
|---|---|---|---|
| Essential | $79 | 333 KB | 4 AIA-depth legal docs (HTML **+ DOCX**) + 50-state lien guide |
| Professional | $149 | 361 KB | Essential contents |
| Business | $199 | 544 KB | Pro + 8 XLSX trackers + refreshed SBA suite (Funding Mastery + Lender Matrix) |
| Complete | $249 | 1.0 MB | Business + 8 GC suite docs (HTML **+ DOCX**) + full SBA suite (4 .md) + Marketing Playbook (11,259 words) |

## Active background work

- **Goal #10012** on Charles — 32-state audit grind at 30-min heartbeat. TN + CA prioritized at queue front (existing stub-quality audits being depth-passed). Pings John every 5 completed.
- **Goal #10011** on Charles — Part 1 URL ingestion, still active.

## Cleanup blockers — DONE 2026-05-17

- ✅ Steel Estimator v1 stripped from Pro/Business/Complete zips
- ✅ Business_Plan.txt 85-byte stub removed from Complete
- ✅ SBA file mismatch reconciled — Business tier upgraded to include Funding Mastery + Lender Matrix
- ✅ Stripe `(Copy)` test products deleted (John, via Stripe UI)
- ✅ HTML→DOCX integration pass on all 12 existing legal+GC docs — 24 .docx files generated, zips repacked
- ⏳ TN + CA depth-passes — delegated to Charles via goal #10012

## What's missing (in priority order)

1. **Universal Sub Suite** (8 docs sub-perspective: Bid Package, Subcontract Review, Sub SOV, T&M Tracker, Backcharge Dispute, Certified Payroll, Joint Check, Daily Field Report). 0 of 8 built. ~1-1.5 day at GC depth.
2. **Trade-specific Bid Estimators** — Electrical, Mechanical, Plumbing, Steel Erection. 0 of 4 built. ~half-day to day each.
3. **State audits 19-50** — Charles grinding in background. 32 to go.
4. **Google Docs link delivery** — current pass only generates DOCX files, not the "one-click make-a-copy" Google Docs links per the integration strategy. Needs Google Drive API integration or manual upload step.

## Build sequence for next session (per John's 5-step plan)

1. ~~Cleanup blockers~~ ✅ done
2. ~~Integration pass on existing 12 docs (HTML→DOCX)~~ ✅ done
3. **Universal Sub Suite build (8 docs)** ← START HERE NEXT SESSION
4. State audits run in parallel on Charles (already running)
5. Steel sub trade pack — last (Leo Flynn SME pipeline)

## Reference

- Strategic doctrines in memory:
  - `project_contrpro_integration_strategy.md` — output format requirements
  - `project_contrpro_5trade_roadmap.md` — 5-trade roadmap, depth standard
  - `project_charles_produces_claude_audits.md` — division of labor
  - `project_training_wheels_doctrine.md` — capability-building task shape
- Build scripts: `contrpro/scripts/build_*.py`
- Source content: `contrpro/files/packages/<tier>/`
- Delivered zips: `contrpro/files/packages/<tier>-<name>-<price>.zip`
- TIER_FILES wired in `contrpro/webhook_server.py`
