import json
from openpyxl import Workbook, load_workbook
from pathlib import Path

workbook_path = "workbooks/Exposure-Tracking-Matrix.xlsx"

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

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
    case["status"]
])

wb.save(workbook_path)

print("Workbook updated.")
