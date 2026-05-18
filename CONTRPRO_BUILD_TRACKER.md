# ContrPro Build Tracker

**Updated:** 2026-05-17 mid-day · Universal Sub Suite + Steel Erection trade pack + GC suite retrofit (3 working workbooks) all shipped. Older history is in git + memory files.

## Product scope (locked 2026-05-17)

ContrPro covers **5 trade buckets**, each at V1-GC-Complete depth:
1. **General Contractor** — V1-GC-Complete SHIPPED 2026-05-15 (8 docs / 5,486 lines); 3 working workbooks added 2026-05-17 (Bid Estimator, App for Payment, Project Operations — 25 tabs, 2,503 formulas)
2. **Steel Erection** — SHIPPED 2026-05-17 (6 trade-specific deliverables, field-only scope, on Universal Sub Suite foundation)
3. **Electrical** — pending
4. **Mechanical** — pending
5. **Plumbing** — pending

ICP: **startup/small GCs + subs**. 1-3 person shops. Not Procore territory.
Integration moat: **every doc ships in Word + Google Docs + PDF + XLSX + CSV-with-QB-headers**. "Your tools, our forms."

## Current shelf — what a buyer actually gets today

| Tier | Price | Zip size | Contents |
|---|---|---|---|
| Essential | $79 | 333 KB | 4 AIA-depth legal docs (HTML **+ DOCX**) + 50-state lien guide |
| Professional | $149 | 361 KB | Essential contents |
| Business | $199 | 544 KB | Pro + 8 XLSX trackers + refreshed SBA suite (Funding Mastery + Lender Matrix) |
| Complete | $249 | 1.9 MB | Business + 8 GC suite docs + **3 GC working workbooks (Bid Estimator + App for Payment + Project Operations)** + 8 Universal Sub Suite docs + 6 Steel Erection trade-pack deliverables (HTML + DOCX + XLSX + CSV) + full SBA suite (4 .md) + Marketing Playbook (11,259 words) |

## Active background work

- **Goal #10012** on Charles — 32-state audit grind at 30-min heartbeat. TN + CA prioritized at queue front (existing stub-quality audits being depth-passed). Pings John every 5 completed.
- **Goal #10011** on Charles — Part 1 URL ingestion, still active.

## Cleanup blockers — DONE 2026-05-17

- ✅ Steel Estimator v1 stripped from Pro/Business/Complete zips
- ✅ Business_Plan.txt 85-byte stub removed from Complete
- ✅ SBA file mismatch reconciled — Business tier upgraded to include Funding Mastery + Lender Matrix
- ✅ Stripe `(Copy)` test products deleted (John, via Stripe UI)
- ✅ HTML→DOCX integration pass on all 12 existing legal+GC docs — 24 .docx files generated, zips repacked
- ✅ **Universal Sub Suite shipped — 8 docs (6 HTML + 6 DOCX + 4 XLSX + 4 CSV) — 2026-05-17**
- ✅ **Steel Erection trade pack shipped — 6 deliverables (5 HTML + 5 DOCX + 4 XLSX + README) — 2026-05-17** — pending Leo Flynn SME review (email sent 10:39 EST)
- ✅ **GC suite architecture retrofit shipped — 3 working workbooks added (Bid Estimator, App for Payment, Project Operations) — 2026-05-17** — 25 tabs, 2,503 formulas, 0 issues on pressure test
- ⏳ TN + CA depth-passes — delegated to Charles via goal #10012

## What's missing (in priority order)

1. ~~Universal Sub Suite (8 docs)~~ ✅ SHIPPED 2026-05-17
2. ~~Steel Erection trade pack~~ ✅ SHIPPED 2026-05-17 (pending Leo Flynn SME review)
3. **Trade-specific deltas + bid estimators** — Electrical, Mechanical, Plumbing. 0 of 3 remaining. ~half-day to day each. Apply `project_trade_pack_architecture.md` pattern.
4. **State audits 19-50** — Charles grinding in background. 32 to go.
5. **Google Docs link delivery** — current pass only generates DOCX files, not the "one-click make-a-copy" Google Docs links per the integration strategy. Needs Google Drive API integration or manual upload step.

## Build sequence — status

1. ~~Cleanup blockers~~ ✅ done 2026-05-17
2. ~~Integration pass on existing 12 docs (HTML→DOCX)~~ ✅ done 2026-05-17
3. ~~Universal Sub Suite build (8 docs)~~ ✅ done 2026-05-17
4. State audits run in parallel on Charles (already running, 32 of 50 remaining)
5. ~~Steel Erection trade pack (6 deliverables, field-only)~~ ✅ done 2026-05-17 (Leo Flynn review pending)
6. **Electrical / Mechanical / Plumbing trade packs** ← NEXT (any order; same architecture pattern)

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
