#!/usr/bin/env python3
"""State-tailored zip builder for ContrPro deliverables.

Given (tier, state, [side, trade]) builds one ZIP at:
    contrpro/files/packages/built/{state}-{tier}[-{side}[-{trade}]].zip

Tier manifests below are the SINGLE SOURCE OF TRUTH for which files land
in each tier. Edits to file inventory should happen here, not by adding
files into the per-tier folders.

State tailoring (v1 — minimal):
  - states.json: filtered to buyer's state only (lower tiers).
                 Complete keeps the full 50-state file as a bonus.
  - Lien guide: per-state extract for lower tiers; full 50-state for Complete.
  - 4 legal docs: state-specific addendum appended to the HTML, DOCX
                  rebuilt from the augmented HTML. Existing static body
                  stays untouched in v1; deeper field-level interpolation
                  is a v1.1 followup.
  - README.txt: per-tier + per-state header noting buyer choice.

Usage:
    python -m contrpro.scripts.build_tailored_zip --tier complete-sub-steel --state TN
    python -m contrpro.scripts.build_tailored_zip --all  # all 50 states × all tier-variants
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # contrpro/
PACKAGES_ROOT = ROOT / "files" / "packages"
BUILT_DIR = PACKAGES_ROOT / "built"

sys.path.insert(0, str(ROOT.parent))
sys.path.insert(0, str(ROOT / "scripts"))
from contrpro.states import get_profile, ALL_STATES, available_profiles  # noqa: E402
from contrpro.states._schema import StateProfile  # noqa: E402
from build_docx_from_html import convert as _html_to_docx  # noqa: E402


# ---------------------------------------------------------------------------
# Tier manifests — single source of truth.
# Each entry: (source_path_relative_to_PACKAGES_ROOT, dest_path_in_zip).
# State-aware files use sentinel paths handled by the builder, marked
# with a leading "@" — the builder routes those to generators instead of
# straight copies.
# ---------------------------------------------------------------------------

# Files that are universal across all tiers. Legal docs get state-tailored
# (handled below); guides and states.json get state-tailored for lower
# tiers OR the full 50-state version for Complete.
ESSENTIAL_FILES: list[tuple[str, str]] = [
    ("complete/documents/construction-contract.html",  "documents/construction-contract.html"),
    ("complete/documents/mechanics-lien.html",         "documents/mechanics-lien.html"),
    ("complete/documents/preliminary-notice.html",     "documents/preliminary-notice.html"),
    ("complete/documents/release-of-lien.html",        "documents/release-of-lien.html"),
    # DOCX versions get rebuilt per state, see _render_legal_docs()
    ("@states.json",                                   "states.json"),
    ("@lien_guide",                                    "guides/Lien_Laws_{STATE}.md"),
    ("@readme",                                        "README.txt"),
]

# Pro adds 4 trackers (CSV only). The tracker source files live under business/
# because that's where the most recent versions sit; the per-tier folder dup
# inventory is being deprecated.
PROFESSIONAL_ADDS: list[tuple[str, str]] = [
    ("business/Job_Costing_Spreadsheet.csv",  "Job_Costing_Spreadsheet.csv"),
    ("business/Change_Order_Log.csv",         "Change_Order_Log.csv"),
    ("business/AR_Tracker.csv",               "AR_Tracker.csv"),
    ("business/Subcontractor_Tracker.csv",    "Subcontractor_Tracker.csv"),
]

# Business adds the other 4 trackers + XLSX upgrades + SBA + CSI templates.
BUSINESS_ADDS: list[tuple[str, str]] = [
    # Project / AP / COI / Sub_Pro — both CSV and XLSX
    ("business/Project_Tracker.csv",                  "Project_Tracker.csv"),
    ("business/Project_Tracker.xlsx",                 "Project_Tracker.xlsx"),
    ("business/AP_Tracker.csv",                       "AP_Tracker.csv"),
    ("business/AP_Tracker.xlsx",                      "AP_Tracker.xlsx"),
    ("business/COI_Tracker.csv",                      "COI_Tracker.csv"),
    ("business/COI_Tracker.xlsx",                     "COI_Tracker.xlsx"),
    ("business/Subcontractor_Tracker_Pro.csv",        "Subcontractor_Tracker_Pro.csv"),
    ("business/Subcontractor_Tracker_Pro.xlsx",       "Subcontractor_Tracker_Pro.xlsx"),
    # XLSX upgrades of the 4 trackers Pro got as CSV
    ("business/Job_Costing_Spreadsheet.xlsx",         "Job_Costing_Spreadsheet.xlsx"),
    ("business/Change_Order_Log.xlsx",                "Change_Order_Log.xlsx"),
    ("business/AR_Tracker.xlsx",                      "AR_Tracker.xlsx"),
    ("business/Subcontractor_Tracker.xlsx",           "Subcontractor_Tracker.xlsx"),
    # SBA bundled in Business+
    ("complete/sba/SBA_Funding_Mastery_Guide.md",     "sba/SBA_Funding_Mastery_Guide.md"),
    ("complete/sba/Lender_Comparison_Matrix.md",      "sba/Lender_Comparison_Matrix.md"),
]

# Complete-tier add-ons (shared between GC + all Sub variants):
# SBA bonus (4 documents — each in MD + DOCX, two also as XLSX workbooks)
# + Marketing Playbook + Lender Matrix workbook. Walked dynamically so any
# file added to complete/sba/ or complete/bonus/ lands in every Complete zip.
def _complete_addons():
    return _walk("complete/sba", "sba/") + _walk("complete/bonus", "bonus/")


def _resolve_tier(tier: str, side: str | None, trade: str | None) -> tuple[str, list[tuple[str, str]]]:
    """Return (tier_label, ordered_manifest) for the requested SKU."""
    base = list(ESSENTIAL_FILES)
    if tier == "essential":
        return ("essential", base)
    base = base + PROFESSIONAL_ADDS
    if tier == "professional":
        return ("professional", base)
    base = base + BUSINESS_ADDS
    if tier == "business":
        return ("business", base)
    if tier == "complete":
        if side == "gc":
            extras = _complete_addons() + _walk("complete/gc", "gc/")
            return ("complete-gc", base + extras)
        if side == "sub":
            if trade == "steel":
                extras = (_complete_addons()
                          + _walk("complete/sub", "sub/")
                          + _walk("complete/steel-erection", "steel-erection/"))
                return ("complete-sub-steel", base + extras)
            if trade == "plumbing":
                extras = (_complete_addons()
                          + _walk("complete/sub", "sub/")
                          + _walk("complete/plumbing", "plumbing/"))
                return ("complete-sub-plumbing", base + extras)
            if trade == "electrical":
                extras = (_complete_addons()
                          + _walk("complete/sub", "sub/")
                          + _walk("complete/electrical", "electrical/"))
                return ("complete-sub-electrical", base + extras)
            if trade == "mechanical":
                extras = (_complete_addons()
                          + _walk("complete/sub", "sub/")
                          + _walk("complete/mechanical", "mechanical/"))
                return ("complete-sub-mechanical", base + extras)
            raise ValueError(f"trade {trade!r} not yet available; supported: steel | plumbing | electrical | mechanical")
        raise ValueError(f"complete tier requires side='gc' or 'sub'; got {side!r}")
    raise ValueError(f"unknown tier {tier!r}")


def _walk(src_subdir: str, zip_prefix: str) -> list[tuple[str, str]]:
    """Walk a source subdirectory and produce (src, zip-dest) pairs.
    Used for the multi-file suites (GC, Sub, Steel Erection) where the
    manifest would otherwise enumerate dozens of files explicitly.
    Strips macOS hidden files. Skips per-tier README.txt clashes (the
    suite READMEs land under their own subdir)."""
    src_root = PACKAGES_ROOT / src_subdir
    entries: list[tuple[str, str]] = []
    if not src_root.exists():
        return entries
    for p in sorted(src_root.rglob("*")):
        if p.is_dir() or p.name.startswith(".") or p.name == ".DS_Store":
            continue
        rel = p.relative_to(src_root)
        entries.append((f"{src_subdir}/{rel.as_posix()}", f"{zip_prefix}{rel.as_posix()}"))
    return entries


# ---------------------------------------------------------------------------
# State-tailoring generators
# ---------------------------------------------------------------------------

def _filter_states_json(state_code: str, source: Path) -> bytes:
    """Return JSON bytes with only the buyer's state retained.
    Lower tiers ship this; Complete-tier swaps in the full file."""
    raw = json.loads(source.read_text())
    if state_code in raw:
        return json.dumps({state_code: raw[state_code]}, indent=2).encode("utf-8")
    # State key missing in source — ship a stub with a note rather than failing.
    return json.dumps({state_code: {"_note": f"State data for {state_code} not yet populated."}}, indent=2).encode("utf-8")


def _render_lien_guide(profile: StateProfile, fallback_50state: Path) -> bytes:
    """Render the per-state lien guide markdown from the state profile.
    Falls back to the 50-state guide if no profile or no lien facts."""
    if profile is None or profile.mechanics_lien is None:
        return fallback_50state.read_bytes()
    ml = profile.mechanics_lien
    pp = profile.prompt_pay_retainage
    lines = [
        f"# {profile.state_name} ({profile.state_code}) — Mechanics' Lien & Prompt-Pay Quick Reference",
        "",
        f"*Last verified: {profile.last_verified_iso}. Depth: {profile.depth_status}.*",
        "",
        f"**Governing statute:** {ml.governing_statute_section or '—'}",
        "",
        "## Prime contractors (direct contract with the owner)",
        "",
        f"- **Preliminary notice required:** {'No' if ml.prime_preliminary_notice_required is False else ('Yes' if ml.prime_preliminary_notice_required else '—')}",
        f"- **Recording deadline:** {_fmt_days(ml.prime_recording_deadline_days)} {ml.prime_recording_deadline_basis or ''}".rstrip(),
        f"- **Authority:** {ml.prime_recording_statute or '—'}",
        "",
        "## Remote contractors (subs, sub-subs, suppliers)",
        "",
        f"- **Preliminary notice required:** {'Yes' if ml.remote_preliminary_notice_required else 'No' if ml.remote_preliminary_notice_required is False else '—'}",
        f"- **Preliminary notice window:** {_fmt_days(ml.remote_preliminary_notice_window_days)} ({ml.remote_preliminary_notice_basis or '—'})",
        f"- **Preliminary notice authority:** {ml.remote_preliminary_notice_statute or '—'}",
        f"- **Recording deadline:** {_fmt_days(ml.remote_recording_deadline_days)} {ml.remote_recording_deadline_basis or ''}".rstrip(),
        f"- **Recording authority:** {ml.remote_recording_statute or '—'}",
        "",
        "## Residential",
        "",
        f"- **Notice to Owner required (prime, residential):** {'Yes' if ml.residential_notice_to_owner_required else 'No' if ml.residential_notice_to_owner_required is False else '—'}",
        f"- **Authority:** {ml.residential_notice_to_owner_statute or '—'}",
        "",
        "## Notice of Completion accelerator",
        "",
        f"- **Commercial window:** {_fmt_days(ml.notice_of_completion_commercial_window_days)}",
        f"- **Residential window:** {_fmt_days(ml.notice_of_completion_residential_window_days)}",
        f"- **Authority:** {ml.notice_of_completion_statute or '—'}",
        "",
        "## Lien lifecycle",
        "",
        f"- **Duration:** {ml.lien_duration_months or '—'} months",
        f"- **Owner demand-to-enforce window:** {_fmt_days(ml.lien_owner_demand_to_enforce_window_days)}",
        f"- **Authority:** {ml.lien_lifecycle_statute or '—'}",
    ]
    if ml.state_specific_notes:
        lines += ["", "## State-specific notes", "", ml.state_specific_notes]
    if pp:
        lines += [
            "",
            "## Prompt Pay & Retainage",
            "",
            f"- **Act:** {pp.prompt_pay_act_section or '—'}",
            f"- **Owner-to-prime payment max days:** {pp.owner_to_prime_payment_max_days or '—'}",
            f"- **Statutory interest on late payment:** {pp.statutory_interest_rate_pct_per_month or '—'}% / month",
            f"- **Retainage cap:** {pp.retainage_max_pct or '—'}% — {pp.retainage_statute or '—'}",
            f"- **Third-party escrow required above:** ${pp.retainage_escrow_required_above_usd:,}".replace("$None", "—") if pp.retainage_escrow_required_above_usd else "- **Third-party escrow required:** —",
            f"- **Retainage release window:** {_fmt_days(pp.retainage_release_days_after_completion)} after completion",
            f"- **Prime-to-sub retainage flow-down:** {_fmt_days(pp.retainage_prime_to_sub_release_days)} after prime receives release",
        ]
    if profile.sources:
        lines += ["", "## Sources", "", *(f"- {s}" for s in profile.sources)]
    lines += [
        "",
        "---",
        "*This quick reference is informational. Confirm citations against the current state code before relying on any specific deadline or threshold. ContrPro is not a law firm; consult your attorney for application to your facts.*",
    ]
    return "\n".join(lines).encode("utf-8")


def _fmt_days(n: int | None) -> str:
    return f"{n} days" if n is not None else "—"


def _render_state_addendum_html(profile: StateProfile | None, doc_kind: str) -> str:
    """Return an HTML <section> describing the buyer's state context for
    one of the 4 legal docs. v1 is conservative: appends a state-aware
    notice rather than splicing inline. Empty string if no profile."""
    if profile is None:
        return ""
    ml = profile.mechanics_lien
    pp = profile.prompt_pay_retainage
    note_blocks: list[str] = []
    if doc_kind == "construction-contract":
        if ml and ml.governing_statute_section:
            note_blocks.append(f"<li><strong>State mechanics' lien statute:</strong> {ml.governing_statute_section}</li>")
        if pp and pp.prompt_pay_act_section:
            note_blocks.append(f"<li><strong>State prompt-pay act:</strong> {pp.prompt_pay_act_section}</li>")
        if pp and pp.retainage_max_pct:
            note_blocks.append(f"<li><strong>Retainage cap:</strong> {pp.retainage_max_pct}% (state law)</li>")
        if pp and pp.owner_to_prime_payment_max_days:
            note_blocks.append(f"<li><strong>Owner-to-prime payment deadline:</strong> {pp.owner_to_prime_payment_max_days} days after timely application for payment</li>")
    elif doc_kind == "mechanics-lien":
        if ml:
            if ml.prime_recording_deadline_days:
                note_blocks.append(f"<li><strong>Prime contractor recording deadline:</strong> {ml.prime_recording_deadline_days} days {ml.prime_recording_deadline_basis or ''} ({ml.prime_recording_statute or '—'})</li>")
            if ml.remote_recording_deadline_days:
                note_blocks.append(f"<li><strong>Remote contractor recording deadline:</strong> {ml.remote_recording_deadline_days} days {ml.remote_recording_deadline_basis or ''} ({ml.remote_recording_statute or '—'})</li>")
            if ml.lien_duration_months:
                note_blocks.append(f"<li><strong>Lien duration:</strong> {ml.lien_duration_months} months from recording</li>")
    elif doc_kind == "preliminary-notice":
        if ml:
            if ml.remote_preliminary_notice_required is not None:
                rq = "Required" if ml.remote_preliminary_notice_required else "Not required"
                note_blocks.append(f"<li><strong>Preliminary notice (remote claimants):</strong> {rq}</li>")
            if ml.remote_preliminary_notice_window_days:
                note_blocks.append(f"<li><strong>Notice window:</strong> {ml.remote_preliminary_notice_window_days} days ({ml.remote_preliminary_notice_basis or '—'})</li>")
            if ml.remote_preliminary_notice_statute:
                note_blocks.append(f"<li><strong>Authority:</strong> {ml.remote_preliminary_notice_statute}</li>")
    elif doc_kind == "release-of-lien":
        if ml:
            if ml.lien_duration_months:
                note_blocks.append(f"<li><strong>Lien duration before release becomes academic:</strong> {ml.lien_duration_months} months</li>")
            if ml.governing_statute_section:
                note_blocks.append(f"<li><strong>Release authority:</strong> {ml.governing_statute_section}</li>")
    if not note_blocks:
        return ""
    return (
        f'<section class="state-addendum" style="margin-top:2em;padding:1em;'
        f'border-top:3px solid #1e3a5f;background:#f7f9fc;">'
        f'<h2>State-specific notes — {profile.state_name} ({profile.state_code})</h2>'
        f'<p><em>The body of this document is a state-neutral template. The notes below '
        f'reflect rules specific to {profile.state_name} as of {profile.last_verified_iso}. '
        f'Confirm citations against the current state code; consult your attorney for '
        f'application to your facts.</em></p>'
        f"<ul>{''.join(note_blocks)}</ul>"
        f"</section>"
    )


def _render_legal_docs(staging: Path, profile: StateProfile | None, tier_label: str) -> None:
    """For each of the 4 legal docs, copy the source HTML, append the
    state addendum, then rebuild the DOCX from the augmented HTML. Both
    end up under staging/documents/.

    Caller has already staged the HTML files via the manifest copy pass;
    this function rewrites them in place with the state addendum and
    regenerates DOCX. Idempotent within a single build."""
    docs_dir = staging / "documents"
    if not docs_dir.exists():
        return
    for kind in ("construction-contract", "mechanics-lien", "preliminary-notice", "release-of-lien"):
        html_path = docs_dir / f"{kind}.html"
        if not html_path.exists():
            continue
        addendum = _render_state_addendum_html(profile, kind)
        if addendum:
            html = html_path.read_text(encoding="utf-8")
            # Splice before </body> so the addendum is part of the document body.
            if "</body>" in html:
                html = html.replace("</body>", f"{addendum}\n</body>", 1)
            else:
                html = html + addendum
            html_path.write_text(html, encoding="utf-8")
        # Regenerate DOCX from the augmented HTML (in-process call).
        docx_path = docs_dir / f"{kind}.docx"
        try:
            _html_to_docx(html_path, docx_path)
        except Exception as exc:  # noqa: BLE001
            # Don't fail the whole build if one DOCX regen errors; fall back
            # to copying the canonical (state-neutral) DOCX so the buyer at
            # least gets a working file.
            src_docx = PACKAGES_ROOT / "complete" / "documents" / f"{kind}.docx"
            if src_docx.exists():
                shutil.copy2(src_docx, docx_path)
            sys.stderr.write(
                f"[warn] DOCX regen failed for {kind} "
                f"(state={profile.state_code if profile else '?'}): {exc}; "
                f"fell back to canonical DOCX.\n"
            )


def _render_readme(profile: StateProfile | None, tier_label: str, state_code: str | None = None) -> bytes:
    """Per-tier + per-state README. Lists what's in the package, how to
    use it, legal disclaimer, support contact.

    If `profile` is None (state has no curated profile yet, e.g. DC),
    fall back to the supplied state_code so the README still references
    the buyer's state correctly. The state-tailored states.json + lien
    guide ARE in the zip even when no profile exists; the README should
    not mislead the buyer into thinking otherwise.
    """
    if profile:
        state_line = f"Tailored for: {profile.state_name} ({profile.state_code})"
    elif state_code:
        state_line = (
            f"Tailored for: {state_code} (state code) — full state profile pending; "
            "states.json + lien guide are still state-filtered."
        )
    else:
        state_line = "State: not tailored (universal templates)"
    contents = _TIER_CONTENTS_BLURB.get(tier_label, "(tier contents — see folder structure)")
    body = f"""ContrPro — {tier_label.upper().replace('-', ' ')} package
{'=' * 78}

{state_line}
Generated: {profile.last_verified_iso if profile else 'n/a'}

WHAT'S IN THIS PACKAGE
{'-' * 78}
{contents}

STATE TAILORING (v1)
{'-' * 78}
Lower-tier packages (Essential / Professional / Business) ship with:
  - states.json filtered to your state only
  - A {profile.state_name + ' ' if profile else ''}lien & prompt-pay quick reference under guides/
  - 4 legal docs (HTML + DOCX) with a state-specific addendum appended

The Complete package (GC or Sub) keeps the FULL 50-state reference data and
50-state lien guide as a bonus, alongside the state-tailored quick-reference
under guides/.

HOW TO USE
{'-' * 78}
1. Unzip into a project folder.
2. Open the legal docs (.docx files) in Word / LibreOffice / Google Docs.
3. Workbooks (.xlsx) open in Excel / Numbers / LibreOffice Calc / Sheets.
4. CSI MasterFormat dropdowns in the GC workbooks: select a Division first;
   the Subdivision cell then filters to children of that Division.
5. State quick reference under guides/ is the fastest path to deadlines.

LEGAL DISCLAIMER
{'-' * 78}
ContrPro provides templates and reference material. It is not a law firm
and does not provide legal advice. Statute citations were verified at the
date shown above; statutory changes after that date are not reflected.
Consult a licensed attorney in your state before relying on any specific
clause, deadline, or threshold for a live transaction.

SUPPORT
{'-' * 78}
Email: support@contrpro.com
Web:   https://contrpro.com

Thank you for buying ContrPro. Updates ship at https://contrpro.com — your
download link is valid for repeated downloads until it expires.
"""
    return body.encode("utf-8")


_TIER_CONTENTS_BLURB: dict[str, str] = {
    "essential": (
        "  - 4 legal documents (HTML + DOCX): construction contract, mechanics'\n"
        "    lien, preliminary notice, release of lien\n"
        "  - State-tailored lien & prompt-pay quick reference under guides/\n"
        "  - State-filtered states.json (your state only)"
    ),
    "professional": (
        "  - Everything in Essential\n"
        "  - 4 CSV trackers: Job Costing, Change Order Log, AR, Subcontractor"
    ),
    "business": (
        "  - Everything in Professional\n"
        "  - XLSX upgrades of the 4 Professional trackers\n"
        "  - 4 more trackers (CSV + XLSX): Project, AP, COI, Subcontractor Pro\n"
        "  - SBA Funding Mastery Guide + Lender Comparison Matrix"
    ),
    "complete-gc": (
        "  - Everything in Business\n"
        "  - GC Suite: 8 contract docs (HTML + DOCX) + 3 working workbooks\n"
        "    (GC Bid Estimator, GC Application for Payment, GC Project Operations)\n"
        "    All workbooks are CSI MasterFormat-coded with cascading dropdowns.\n"
        "  - SBA Bonus: Business Plan + Financial Projection templates\n"
        "  - Marketing Playbook\n"
        "  - FULL 50-state reference data (states.json) and 50-state lien guide"
    ),
    "complete-sub-steel": (
        "  - Everything in Business\n"
        "  - Universal Sub Suite: 8 docs (HTML + DOCX) + 4 working workbooks\n"
        "    (Sub Schedule of Values, T&M Tracker, Certified Payroll, Daily Field Report)\n"
        "  - Steel Erection Trade Pack: 6 deliverables\n"
        "    (Steel Erection Bid Estimator, Site-Specific Erection Plan,\n"
        "     Pre-Erection Meeting Checklist, Crane & Rigging Lift Plan,\n"
        "     Bolt Installation & Inspection Guide, Plumb & True Tolerance Guide)\n"
        "  - SBA Bonus: Business Plan + Financial Projection templates\n"
        "  - Marketing Playbook\n"
        "  - FULL 50-state reference data (states.json) and 50-state lien guide"
    ),
    "complete-sub-plumbing": (
        "  - Everything in Business\n"
        "  - Universal Sub Suite: 8 docs (HTML + DOCX) + 4 working workbooks\n"
        "  - Plumbing Trade Pack: 6 deliverables — Plumbing Bid Estimator, Site-Specific\n"
        "    Plumbing Plan, Pre-Construction Coordination Checklist, Cross-Connection\n"
        "    Control + Backflow Guide + Test Log, Pipe Installation + Test Guide +\n"
        "    Pressure Test Log, Closeout + Inspection Guide + Punch List + As-Built Log\n"
        "  - SBA Bonus + Marketing Playbook\n"
        "  - FULL 50-state reference + 50-state lien guide"
    ),
    "complete-sub-electrical": (
        "  - Everything in Business\n"
        "  - Universal Sub Suite: 8 docs (HTML + DOCX) + 4 working workbooks\n"
        "  - Electrical Trade Pack: 6 deliverables — Electrical Bid Estimator,\n"
        "    Site-Specific Electrical Plan, Pre-Construction Coordination Checklist,\n"
        "    LOTO + Arc-Flash + Energized Work Guide + Log, Conduit + Cable Install\n"
        "    Guide + Pull/Insulation Test Log, Grounding + Bonding Guide + Ground\n"
        "    Resistance Test Log\n"
        "  - SBA Bonus + Marketing Playbook\n"
        "  - FULL 50-state reference + 50-state lien guide"
    ),
    "complete-sub-mechanical": (
        "  - Everything in Business\n"
        "  - Universal Sub Suite: 8 docs (HTML + DOCX) + 4 working workbooks\n"
        "  - Mechanical Trade Pack: 6 deliverables — Mechanical Bid Estimator,\n"
        "    Site-Specific Mechanical Plan, Pre-Construction Coordination Checklist,\n"
        "    Refrigerant + Hot Work Guide + Log, Ductwork + Piping Install + Test Guide\n"
        "    + Pressure / Leakage Log, TAB + Commissioning Guide + FPT Log\n"
        "  - SBA Bonus + Marketing Playbook\n"
        "  - FULL 50-state reference + 50-state lien guide"
    ),
}


# ---------------------------------------------------------------------------
# Builder entry points
# ---------------------------------------------------------------------------

@dataclass
class BuildRequest:
    tier: str            # essential | professional | business | complete
    state: str           # USPS code
    side: str | None = None    # gc | sub (required for complete)
    trade: str | None = None   # steel | None (only for complete-sub)

    @property
    def tier_label(self) -> str:
        if self.tier != "complete":
            return self.tier
        if self.side == "gc":
            return "complete-gc"
        return f"complete-sub-{self.trade}"

    @property
    def zip_basename(self) -> str:
        return f"{self.state}-{self.tier_label}.zip"


def build(req: BuildRequest) -> Path:
    """Build one tailored zip. Returns the output path."""
    state = req.state.upper().strip()
    if state not in ALL_STATES:
        raise ValueError(f"unknown state code {state!r}")
    profile = get_profile(state)  # None if no curated profile yet — guide falls back
    tier_label, manifest = _resolve_tier(req.tier, req.side, req.trade)
    is_complete = tier_label.startswith("complete-")

    BUILT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BUILT_DIR / f"{state}-{tier_label}.zip"

    with tempfile.TemporaryDirectory(prefix=f"contrpro-build-{state}-{tier_label}-") as td:
        staging = Path(td)
        # Pass 1: straight copies from the manifest.
        for src_rel, zip_dest in manifest:
            dest = staging / zip_dest.replace("{STATE}", state)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src_rel.startswith("@"):
                continue  # handled in pass 2
            src = PACKAGES_ROOT / src_rel
            if not src.exists():
                sys.stderr.write(f"[warn] missing source: {src_rel}\n")
                continue
            shutil.copy2(src, dest)

        # Pass 2: state-aware generators.
        states_json_src = PACKAGES_ROOT / "complete" / "states.json"
        if is_complete:
            shutil.copy2(states_json_src, staging / "states.json")
            shutil.copy2(
                PACKAGES_ROOT / "complete" / "guides" / "Lien_Laws_50_State_Guide.md",
                staging / "guides" / "Lien_Laws_50_State_Guide.md",
            )
        else:
            (staging / "states.json").write_bytes(_filter_states_json(state, states_json_src))
        # Per-state lien guide (always shipped under guides/Lien_Laws_{STATE}.md)
        guide_target = staging / "guides" / f"Lien_Laws_{state}.md"
        guide_target.parent.mkdir(parents=True, exist_ok=True)
        guide_target.write_bytes(
            _render_lien_guide(
                profile,
                PACKAGES_ROOT / "complete" / "guides" / "Lien_Laws_50_State_Guide.md",
            )
        )
        # State addendum + DOCX regen for the 4 legal docs
        _render_legal_docs(staging, profile, tier_label)
        # README
        (staging / "README.txt").write_bytes(_render_readme(profile, tier_label, state_code=state))

        # Zip it
        if out_path.exists():
            out_path.unlink()
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(staging.rglob("*")):
                if p.is_dir():
                    continue
                zf.write(p, p.relative_to(staging))
    return out_path


def _iter_all_skus() -> list[BuildRequest]:
    """Every SKU × every state. Used by --all."""
    reqs: list[BuildRequest] = []
    for state in ALL_STATES:
        for tier in ("essential", "professional", "business"):
            reqs.append(BuildRequest(tier=tier, state=state))
        reqs.append(BuildRequest(tier="complete", state=state, side="gc"))
        reqs.append(BuildRequest(tier="complete", state=state, side="sub", trade="steel"))
        reqs.append(BuildRequest(tier="complete", state=state, side="sub", trade="plumbing"))
        reqs.append(BuildRequest(tier="complete", state=state, side="sub", trade="electrical"))
        reqs.append(BuildRequest(tier="complete", state=state, side="sub", trade="mechanical"))
    return reqs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build one or all state-tailored ContrPro zips.")
    ap.add_argument("--tier", choices=["essential", "professional", "business", "complete"])
    ap.add_argument("--state", help="USPS state code (e.g. TN)")
    ap.add_argument("--side", choices=["gc", "sub"], help="Required for tier=complete")
    ap.add_argument("--trade", choices=["steel", "plumbing", "electrical", "mechanical"],
                    help="Required for tier=complete + side=sub")
    ap.add_argument("--all", action="store_true", help="Build the full SKU x state matrix")
    args = ap.parse_args(argv)

    if args.all:
        reqs = _iter_all_skus()
    else:
        if not (args.tier and args.state):
            ap.error("--tier and --state required unless --all")
        reqs = [BuildRequest(tier=args.tier, state=args.state, side=args.side, trade=args.trade)]

    built = 0
    failed = 0
    for req in reqs:
        try:
            path = build(req)
            print(f"OK   {req.state} {req.tier_label:24s} {path.stat().st_size:>10,} bytes  {path}")
            built += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {req.state} {req.tier_label:24s} {exc}")
            failed += 1
    print(f"\n{built} built, {failed} failed; profiles available: {available_profiles()}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
