import csv
import json
import os

case_file = "data/current_case.json"
history_file = "data/investigation_history.csv"

with open(case_file, "r", encoding="utf-8") as f:
    case = json.load(f)

headers = [
    "date",
    "case_id",
    "operation",
    "classification",
    "threat_family",
    "severity",
    "status",
    "containment_phase",
    "affected_platform",
    "device_family",
    "vendor",
    "network_zone",
    "confidence",
    "risk_score",
    "affected_assets",
    "evidence_count",
    "ioc_count",
    "initial_access",
    "lead_analyst",
    "priority"
]

write_header = (
    not os.path.exists(history_file)
    or os.path.getsize(history_file) == 0
)

with open(history_file, "a", newline="", encoding="utf-8") as f:

    writer = csv.DictWriter(f, fieldnames=headers)

    if write_header:
        writer.writeheader()

    writer.writerow({
        "date": case["date"],
        "case_id": case["case_id"],
        "operation": case["operation"],
        "classification": case["classification"],
        "threat_family": case["threat_family"],
        "severity": case["severity"],
        "status": case["status"],
        "containment_phase": case["containment_phase"],
        "affected_platform": case["affected_platform"],
        "device_family": case["device_family"],
        "vendor": case["vendor"],
        "network_zone": case["network_zone"],
        "confidence": case["confidence"],
        "risk_score": case["risk_score"],
        "affected_assets": case["affected_assets"],
        "evidence_count": case["evidence_count"],
        "ioc_count": case["ioc_count"],
        "initial_access": case["initial_access"],
        "lead_analyst": case["lead_analyst"],
        "priority": case["priority"]
    })

print(f"Investigation archived: {case['case_id']}")
