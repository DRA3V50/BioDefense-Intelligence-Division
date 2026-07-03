import json
from pathlib import Path
from openpyxl import Workbook, load_workbook

workbook_path = Path("workbooks/Exposure-Tracking-Matrix.xlsx")

# -----------------------------
# Load case + phase
# -----------------------------
with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

phase_path = "data/investigation_state.json"

phase = "Unknown"

try:
    with open(phase_path, "r", encoding="utf-8") as f:
        phase = json.load(f).get("current_phase", "Unknown")
except:
    pass

# -----------------------------
# Open or create workbook
# -----------------------------
if workbook_path.exists():
    wb = load_workbook(workbook_path)
else:
    wb = Workbook()

def get_sheet(name):
    if name in wb.sheetnames:
        return wb[name]
    return wb.create_sheet(title=name)

# Remove default sheet
if "Sheet" in wb.sheetnames:
    wb.remove(wb["Sheet"])

# =====================================================
# CASES (with phase tracking)
# =====================================================
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
        "Phase"
    ])

cases.append([
    case["date"],
    case["case_id"],
    case["classification"],
    case["severity"],
    case["affected_platform"],
    case["confidence"],
    case["status"],
    phase
])

# =====================================================
# EVIDENCE
# =====================================================
evidence = get_sheet("Evidence")

if evidence.max_row == 1 and evidence["A1"].value is None:
    evidence.append([
        "Case ID",
        "Evidence Type",
        "Status",
        "Phase"
    ])

evidence.append([
    case["case_id"],
    "Firmware Artifact",
    "Collected",
    phase
])

# =====================================================
# DEVICES
# =====================================================
devices = get_sheet("Devices")

if devices.max_row == 1 and devices["A1"].value is None:
    devices.append([
        "Case ID",
        "Platform",
        "Severity",
        "Phase"
    ])

devices.append([
    case["case_id"],
    case["affected_platform"],
    case["severity"],
    phase
])

# =====================================================
# MITRE
# =====================================================
mitre = get_sheet("MITRE")

if mitre.max_row == 1 and mitre["A1"].value is None:
    mitre.append([
        "Case ID",
        "Framework",
        "Status",
        "Phase"
    ])

mitre.append([
    case["case_id"],
    "MITRE ATT&CK",
    "Mapped",
    phase
])

# =====================================================
# METRICS DASHBOARD
# =====================================================
metrics = get_sheet("Metrics")

metrics.delete_rows(1, metrics.max_row)

metrics.append(["Metric", "Value"])
metrics.append(["Current Case", case["case_id"]])
metrics.append(["Current Phase", phase])
metrics.append(["Severity", case["severity"]])
metrics.append(["Confidence", case["confidence"]])
metrics.append(["Platform", case["affected_platform"]])

wb.save(workbook_path)

print("Workbook updated with investigation phase.")
