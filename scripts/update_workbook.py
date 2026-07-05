import json
from pathlib import Path
from openpyxl import Workbook, load_workbook

WORKBOOK = Path("workbooks/Exposure-Tracking-Matrix.xlsx")

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

severity_weight = {
    "LOW": 1,
    "MODERATE": 2,
    "HIGH": 3,
    "CRITICAL": 4
}

risk_score = (
    severity_weight.get(case["severity"], 1)
    * case["confidence"]
)

if not WORKBOOK.exists():

    wb = Workbook()

    ws = wb.active

    ws.title = "Investigations"

    ws.append([
        "Date",
        "Case ID",
        "Operation",
        "Classification",
        "Severity",
        "Priority",
        "Risk Score",
        "Confidence",
        "Evidence",
        "IOCs",
        "Assets",
        "Platform",
        "Vendor",
        "Network Zone",
        "Lead Analyst",
        "Status"
    ])

else:

    wb = load_workbook(WORKBOOK)

    ws = wb["Investigations"]

ws.append([

    case["date"],

    case["case_id"],

    case["operation"],

    case["classification"],

    case["severity"],

    case["priority"],

    risk_score,

    case["confidence"],

    case["evidence_count"],

    case["ioc_count"],

    case["affected_assets"],

    case["affected_platform"],

    case["vendor"],

    case["network_zone"],

    case["lead_analyst"],

    case["status"]

])

wb.save(WORKBOOK)

print("Workbook updated.")
