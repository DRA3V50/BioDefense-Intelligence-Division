import json
from openpyxl import Workbook, load_workbook
from pathlib import Path

workbook_path = "workbooks/Exposure-Tracking-Matrix.xlsx"

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

# NEW: derived analyst metrics (adds realism)
risk_score = int(case.get("confidence", 0)) * {
    "LOW": 1,
    "MODERATE": 2,
    "HIGH": 3,
    "CRITICAL": 4
}.get(case.get("severity", "LOW"), 1)

attack_surface = len(case.get("affected_assets", [])) if isinstance(case.get("affected_assets"), list) else case.get("affected_assets", 0)

if not Path(workbook_path).exists():
    wb = Workbook()
    ws = wb.active

    ws.append([
        "Date",
        "Case ID",
        "Classification",
        "Severity",
        "Platform",
        "Confidence",
        "Risk Score",
        "Attack Surface",
        "Status"
    ])

else:
    wb = load_workbook(workbook_path)
    ws = wb.active

ws.append([
    case["date"],
    case["case_id"],
    case["classification"],
    case["severity"],
    case["affected_platform"],
    case["confidence"],
    risk_score,
    attack_surface,
    case["status"]
])

wb.save(workbook_path)

print("Workbook updated with analyst metrics.")
