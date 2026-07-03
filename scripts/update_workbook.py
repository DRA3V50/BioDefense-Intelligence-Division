import json
from pathlib import Path
from openpyxl import Workbook, load_workbook

workbook_path = Path("workbooks/Exposure-Tracking-Matrix.xlsx")

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

# -------------------------------------------------------
# Open workbook or create new workbook
# -------------------------------------------------------

if workbook_path.exists():
    wb = load_workbook(workbook_path)
else:
    wb = Workbook()

# -------------------------------------------------------
# Helper
# -------------------------------------------------------

def get_sheet(name):

    if name in wb.sheetnames:
        return wb[name]

    return wb.create_sheet(title=name)

# -------------------------------------------------------
# Remove default sheet if empty
# -------------------------------------------------------

if "Sheet" in wb.sheetnames:

    sheet = wb["Sheet"]

    if sheet.max_row == 1 and sheet.max_column == 1:
        wb.remove(sheet)

# =======================================================
# CASES
# =======================================================

cases = get_sheet("Cases")

if cases.max_row == 1 and cases["A1"].value is None:

    cases.append([
        "Date",
        "Case ID",
        "Classification",
        "Severity",
        "Platform",
        "Confidence",
        "Status",
        "Affected Assets"
    ])

cases.append([
    case["date"],
    case["case_id"],
    case["classification"],
    case["severity"],
    case["affected_platform"],
    case["confidence"],
    case["status"],
    case["affected_assets"]
])

# =======================================================
# EVIDENCE
# =======================================================

evidence = get_sheet("Evidence")

if evidence.max_row == 1 and evidence["A1"].value is None:

    evidence.append([
        "Case ID",
        "Evidence Type",
        "Collection Status"
    ])

evidence.append([
    case["case_id"],
    "Firmware Image",
    "Collected"
])

# =======================================================
# DEVICES
# =======================================================

devices = get_sheet("Devices")

if devices.max_row == 1 and devices["A1"].value is None:

    devices.append([
        "Case ID",
        "Platform",
        "Risk Level"
    ])

devices.append([
    case["case_id"],
    case["affected_platform"],
    case["severity"]
])

# =======================================================
# MITRE
# =======================================================

mitre = get_sheet("MITRE")

if mitre.max_row == 1 and mitre["A1"].value is None:

    mitre.append([
        "Case ID",
        "Framework",
        "Status"
    ])

mitre.append([
    case["case_id"],
    "MITRE ATT&CK",
    "Mapped"
])

# =======================================================
# METRICS
# =======================================================

metrics = get_sheet("Metrics")

if metrics.max_row == 1 and metrics["A1"].value is None:

    metrics.append([
        "Metric",
        "Value"
    ])

metrics.delete_rows(2, metrics.max_row)

metrics.append(["Investigations", cases.max_row - 1])
metrics.append(["Open Cases", cases.max_row - 1])
metrics.append(["Current Severity", case["severity"]])
metrics.append(["Current Confidence", case["confidence"]])

wb.save(workbook_path)

print("Workbook updated.")
