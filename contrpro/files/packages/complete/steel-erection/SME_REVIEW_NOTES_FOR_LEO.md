# Steel Erection Trade Pack — SME Pressure Test for Leo Flynn

**Reviewer:** Leo Flynn, Tennessee River Steel
**Pack version:** v1.0 (2026-05-17)
**Builder:** Johnathon Keith / ContrPro

---

## What this is

The ContrPro Steel Erection trade pack — 6 deliverables sitting on top of the Universal Sub Suite. Field-erection scope, commercial focus. We need a working erector's eyes on it before we put it in front of paying customers.

## What we're asking from you

Pressure-test the pack against the way your shop actually estimates, plans, executes, and closes out a job. Where it doesn't match reality, tell us. Where it's missing something a working PM would expect, tell us. Where we're being too conservative or too aggressive on a number, tell us.

We've already done a self-audit and fixed three bugs. The known calls for judgment are listed below — those are where your input matters most.

---

## How to pressure-test (suggested approach, 2-3 hours total)

### Pass 1 — Bid Estimator (45 min)
Open `Steel_Erection_Bid_Estimator.xlsx`. Walk these tabs in order:

1. **Project Info** — set up a sample project (one you actually bid recently, real or representative)
2. **Wage Rates** — replace the defaults with your real wage scale
3. **Material Takeoff** — enter your sample project's tonnage by CSI section
4. **Labor Estimate** — review the pre-loaded productivity rates (3.50 hrs/ton structural, 0.40 hrs/joist, 0.020 hrs/SF deck, etc.). Adjust to match your shop history.
5. **Bid Summary** — does the final bid number come out close to what you'd actually bid that job at?

If it's off by more than 10-15%, tell us where the drift is.

### Pass 2 — Site-Specific Erection Plan + Pre-Erection Meeting (30 min)
Open `site-specific-erection-plan.html` and `pre-erection-meeting-checklist.html` (or the `.docx` versions). Read with your safety officer's eyes — would you sign these as drafted? What sections feel thin? What standard items did we miss?

### Pass 3 — Crane & Rigging Lift Plan + Critical Lift Calculator (30 min)
Open `crane-and-rigging-lift-plan.html` + `Critical_Lift_Calculator.xlsx`. Walk a critical lift from your past experience through the calculator — does the math output match what your lift director would compute by hand? Does the permit summary look like a document you'd sign?

### Pass 4 — Bolt Installation Pack (20 min)
Open `bolt-installation-and-inspection-guide.html` + `Bolt_Inspection_Log.xlsx`. Test the lookup — enter a bolt size + grade on Bolt Lot Master; verify the RCSC minimum pretension auto-populates. Verify the daily roll-up totals when you populate a few sample connections.

### Pass 5 — Tolerance Survey Pack (20 min)
Open `plumb-and-true-tolerance-guide.html` + `Tolerance_Survey_Log.xlsx`. Enter a sample anchor rod survey + column plumb data; verify the OK/OUT flags fire correctly. Confirm the §7.13 tolerance limits match what you actually hold yourself to.

---

## Items from your prior Enterprise-Steel-Estimator critique — how we handled them

When you reviewed Johnathon's earlier estimator (March 9, 2026 email), you flagged several structural issues. We re-read your feedback before building this pack. Here's how the current Steel_Erection_Bid_Estimator.xlsx handles each of your prior points, so you can confirm we got it right or redirect us where we didn't:

| Your prior critique | How current pack handles it | Need your direction? |
|---|---|---|
| "Markup applied twice / three times" | Pack has line-level markup (Material 10%, Equip 8-10%, Sub 7%, Labor OH 15% + Profit 10%) AND summary-level (Project OH 13% + Project Profit 10%). Compound ~28-30% over direct cost. Your preference was single-stage markup at the OH+P summary step only. | **YES — should we strip all line-level markup so OH+P is applied only at the summary?** |
| "Decking priced by SQ (100 SF) not SF" | Pack uses SF as UOM with a separate $/SF line item. Easy to convert to SQ. | YES — flip to SQ for V1.1? |
| "Total hours not factoring crew size" | Labor Estimate has a Crew Composition column (count of workers) and a Productivity (hrs/UOM) column. The formula `qty × hrs/UOM × billed rate` gives crew-hours; we don't auto-multiply by crew size since productivity is already crew-based. Worth your verification this isn't doing what you saw before. | Confirm formula reads right or call out the gap |
| "Joist category missing" | ✓ 05 21 19 Open-Web Steel Joists + 05 21 23 Joist Girders are both in the takeoff seed list with productivity rates on the Labor Estimate tab. | Just verify present |
| "Plate priced by SF weight not EA" | Pack treats plate by TON in the Material Takeoff (under 05 12 23 Structural Steel — Plate / Bent Plate). | Confirm tonnage approach OK for plate |
| "Detailing in fabrication pricing" | Out of scope for THIS pack — Steel Erection is field-only; detailing is in the fabricator's scope. Want a note in the README clarifying that? | Confirm field-only scope OK |
| "Freight by the mile" | Pack does not include a freight line. Material delivery is typically fabricator's responsibility on FOB-jobsite contracts. | Should we add a freight category for FOB-shipping-point contracts? |
| "Engineering Calcs for misc + connections missing" | Pack does not include connection engineering. That's usually EOR scope or fabricator's delegated-design scope. | Confirm OK or should we add a placeholder? |
| "Bond default 0%, Retainage variable by location" | Pack defaults Bond to 1.2% (industry-typical commercial), Retainage NOT defaulted (it's in the Universal Sub Suite Sub_SOV workbook, not here). Your old guidance was 0% by default. | Should bond default to 0% and let user enter project-specific? |

The big one is the markup-applied-twice question. Tell us whether to strip the line-level layers and run pure summary-level OH+P, or whether the current two-stage structure makes sense for steel erection specifically (since labor really does carry distinct OH+P from project-level GCs).

---

## Specific calls for judgment — please weigh in

These are NEW items (not in your prior critique) that we deliberately left for your input rather than guess at.

### 1. Productivity defaults
We seeded the Labor Estimate with industry-average commercial-South non-union numbers:

| Activity | Default (hrs/UOM) | Your number? |
|---|---|---|
| Structural steel erection — typical | 3.50 hrs/ton | __________ |
| Structural steel erection — AESS | 6.50 hrs/ton | __________ |
| Open-web joists | 0.40 hrs/joist | __________ |
| Joist girders | 1.50 hrs/each | __________ |
| Floor decking install | 0.020 hrs/SF | __________ |
| Roof decking install | 0.018 hrs/SF | __________ |
| Shear stud welding | 0.08 hrs/stud | __________ |
| Embed/base plate setting | 0.50 hrs/each | __________ |
| Metal pan stairs | 0.60 hrs/riser | __________ |
| Pipe railings | 0.30 hrs/LF | __________ |
| Bolt-up (TOTN) | 0.08 hrs/bolt | __________ |
| Field welding (per joint) | 0.35 hrs/joint | __________ |
| Plumb-and-true survey | 0.75 hrs/bay | __________ |

A red banner now warns users to calibrate against their own history, but if your numbers are materially different from ours, send them — we'll update the defaults.

### 2. Anchor rod stickup tolerance
We cited ±1/8" per AISC §7.5.2 in the Plumb-and-True Tolerance Guide. Industry practice on the projects you've worked: is that the right number, or should it be ±1/4"? Concrete-sub trade practice in TN especially.

### 3. NEAR CRITICAL lift threshold
Default is 60% of crane capacity (between Routine and the 75% Critical threshold). Some firms run 50% or 65%. What's your shop's convention?

### 4. Crane operator certification language
We cited NCCCO prominently. There are 4-5 OSHA-recognized programs (NCCCO, CIC, ITAC, NCCER, audited-employer). Should we soften the language to be programs-neutral?

### 5. Davis-Bacon coverage of crane operators
Should the Certified Payroll guide (Universal Sub Suite) explicitly call out crane operator classifications on Davis-Bacon projects? Operating Engineers Local typically governs but it varies.

---

## Known gaps — what direction do you want us to take?

We held off on adding the following so you could weigh in on whether/how. Each can be added in V1.1 if you say go.

### A. Erection Sequence Diagram template
The SSEP references "Exhibit B (erection sequence diagram)" but we don't provide a template. Options:
- (i) A blank gridded template with sample sequence callouts
- (ii) A worked example for a typical 2-story commercial frame
- (iii) Leave it as a project-specific deliverable each user draws fresh

### B. Connection-type detail callouts
The pack treats connections generically. Should we add a section breaking down:
- Shear tab connections
- Double angle connections
- End plate (extended/flush) connections
- Seated connections
- Moment connections (welded, bolted, hybrid)
- Column splice details

Per-connection-type bolting/welding requirements, common errors, inspection emphasis.

### C. Hot work permit template
Field welding adjacent to other trades or occupied space typically requires a hot work permit (NFPA 51B). Should we add a template?

### D. Steel piece-marking / tagging workflow
Shop-fab piece marks → site receipt → bay stage → installation verification. Should we add a tracker workbook for this?

### E. Camber-up direction marking
Composite beams have a specified camber direction. Worth a separate guide?

### F. Column splice prep checklist
Mid-height column splices have specific prep / fit-up requirements. Worth a dedicated checklist?

### G. Plumb-and-True Tolerance Guide depth
This doc is 290 lines — the shortest in the pack. It treats AISC §7.13 fairly comprehensively but you could legitimately write a book about it. Are there sections you'd expand?

### H. OSHA injury reporting workflow
Recordable / serious injury reporting deadlines (8 hr fatality, 24 hr amputation/hospitalization) — should we add a one-page reporting workflow?

### I. Builder's Risk + equipment policy specifics
Currently covered generically in the Universal Sub Suite Bid Package. Should we add a steel-erection-specific insurance addendum?

---

## How to send feedback

Whatever's easiest for you. Suggested formats in order of speed:

1. **Mark up this file** — open in a text editor, add comments inline (`// LEO:` prefix or whatever)
2. **Annotated PDF** — print this doc, mark it up, scan/photo back
3. **Phone call** — Johnathon can record + transcribe
4. **Email reply** — bullet-point list of issues

Send to: Johnathon at <span style="font-style:italic">[John's email here]</span>

We'll incorporate your feedback into V1.1 and credit you in the README (if you want — say no if you'd rather stay off the byline).

---

## What we already fixed in pre-SME pass

Self-audit caught + corrected before sending to you:

1. Equipment % sanity check formula in Bid Estimator referenced wrong row → fixed (was reading $0 always)
2. Bolt Lot Master pretension lookup used an array-formula construct that fails silently in older Excel / LibreOffice / Numbers → replaced with portable SUMIFS pattern
3. NEAR CRITICAL lift threshold was hardcoded at 65% → moved to an adjustable named range (default 60%)
4. Labor Estimate tab now has a red banner warning users to calibrate productivity against their own job history before relying on the defaults

---

**Bottom line ask:** would you stake your shop's reputation on this pack as drafted? If no — where does it fall short?

Thanks for taking the time. Beer's on me next time you're up to the hotel.

— Johnathon
