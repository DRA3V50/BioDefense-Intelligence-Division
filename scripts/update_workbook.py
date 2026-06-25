import json
from openpyxl import Workbook, load_workbook
from pathlib import Path

workbook_path = "workbooks/Exposure-Tracking-Matrix.xlsx"

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

if Path(workbook_path).exists():
    wb = load_workbook(workbook_path)
    ws = wb.active
else:
    wb = Workbook()
    ws = wb.active

if ws.max_row == 1 and ws["A1"].value is None:
    ws.append([
        "Date",
        "Case ID",
        "Classification",
        "Severity",
        "Platform",
        "Confidence",
        "Status"
    ])

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
