#!/usr/bin/env python3
"""
Generate flat CSVs (QB-friendly headers) for each Universal Sub Suite XLSX
tracker. CSV ships alongside the XLSX so users can import into QuickBooks,
Sage, FreshBooks, or any other system that prefers a flat CSV.

Output:
  /Users/home/charles/contrpro/files/packages/complete/sub/
    Sub_Schedule_of_Values.csv
    TM_Tracker.csv
    Certified_Payroll_Tracker.csv
    Daily_Field_Report.csv
"""

import csv
import os

OUT_DIR = "/Users/home/charles/contrpro/files/packages/complete/sub"

# ---------------------------------------------------------------------------
# Sub Schedule of Values — line items
# ---------------------------------------------------------------------------

SOV_HEADERS = [
    "Job", "Line #", "Description", "CSI Division", "CSI Section",
    "Item Type", "Scheduled Value", "Quantity", "Unit",
    "Pct of Subcontract", "Billed To Date", "Balance to Finish",
    "Variance", "Status", "Notes",
]
SOV_SAMPLE = [
    ["Sample Project", 1, "Mobilization", "01", "01 50 00", "Base Bid", 0, 1, "LS", "", 0, 0, 0, "Not Started", ""],
    ["", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
]

# ---------------------------------------------------------------------------
# T&M Tracker — labor tickets (primary data)
# ---------------------------------------------------------------------------

TM_HEADERS = [
    "Date", "Job", "Ticket #", "Worker Name", "Employee ID",
    "Classification", "Task / CO Ref", "ST Hours", "OT Hours",
    "ST Rate", "OT Rate", "Labor ST $", "Labor OT $", "Total Labor $",
    "Status", "GC Signature", "Notes",
]
TM_SAMPLE = [
    ["", "Sample Project", "", "", "", "Journeyman", "", 0, 0, 0, 0, 0, 0, 0, "Pending", "", ""],
    ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
]

# ---------------------------------------------------------------------------
# Certified Payroll Tracker — weekly payroll line items
# ---------------------------------------------------------------------------

CERT_HEADERS = [
    "Project", "Sub", "Prime Contract No.", "WD ID", "Payroll #", "Week Ending",
    "Worker Name", "Employee ID", "Classification", "Apprentice (Y/N)",
    "Sun ST", "Mon ST", "Tue ST", "Wed ST", "Thu ST", "Fri ST", "Sat ST",
    "Total ST Hrs", "Total OT Hrs",
    "ST Rate", "OT Rate", "Cash Fringe per Hr", "Plan Fringe per Hr",
    "ST Gross", "OT Gross", "Fringe Cash", "Total Gross",
    "Deductions", "Net Wages",
]
CERT_SAMPLE = [
    ["Sample Project", "Sub Name", "", "", 1, "", "", "", "Journeyman", "N",
     0, 0, 0, 0, 0, 0, 0, 0, 0,
     0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    [""] * len(CERT_HEADERS),
]

# ---------------------------------------------------------------------------
# Daily Field Report — flat crew log
# ---------------------------------------------------------------------------

DFR_HEADERS = [
    "Date", "DFR #", "Project", "Sub", "Foreman",
    "AM Temp", "PM Temp", "Weather Impact", "Idle Hrs Weather",
    "Worker Name", "Classification", "ST Hrs", "OT Hrs", "Task / Location",
    "Materials Delivered", "Materials Installed",
    "Conditions Affecting Work", "Directives/RFIs/T&M Issued",
    "Recordable Incidents", "Near Misses", "First Aid",
    "OSHA Visit (Y/N)", "Visitors", "Photo Count", "Open Items / Escalations",
    "Foreman Signed (Y/N)", "GC Field Rep Countersig (Y/N)",
]
DFR_SAMPLE = [
    ["", 1, "Sample Project", "Sub Name", "",
     "", "", "None", 0,
     "", "Journeyman", 0, 0, "",
     "", "", "", "",
     0, 0, 0, "N", "", 0, "", "N", "N"],
    [""] * len(DFR_HEADERS),
]


def write_csv(filename, headers, rows):
    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow(r)
    print(f"  ✓ Wrote {path}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"Generating CSVs in {OUT_DIR}")
    write_csv("Sub_Schedule_of_Values.csv", SOV_HEADERS, SOV_SAMPLE)
    write_csv("TM_Tracker.csv", TM_HEADERS, TM_SAMPLE)
    write_csv("Certified_Payroll_Tracker.csv", CERT_HEADERS, CERT_SAMPLE)
    write_csv("Daily_Field_Report.csv", DFR_HEADERS, DFR_SAMPLE)


if __name__ == "__main__":
    main()
