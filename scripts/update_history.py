#!/usr/bin/env python3

import csv
import json
from pathlib import Path

# -------------------------------------------------
# Load current investigation
# -------------------------------------------------

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

with open("operations/active_operation.json", "r", encoding="utf-8") as f:
    operation = json.load(f)

history_file = Path("data/investigation_history.csv")

header = [
    "date",
    "campaign_id",
    "case_id",
    "operation",
    "classification",
    "threat_family",
    "severity",
    "status",
    "campaign_phase",
    "platform",
    "device",
    "vendor",
    "zone",
    "confidence",
    "risk_score",
    "affected_assets",
    "evidence_count",
    "ioc_count",
    "initial_access",
    "lead_analyst",
    "priority"
]

write_header = not history_file.exists()

with open(history_file, "a", newline="", encoding="utf-8") as f:

    writer = csv.writer(f)

    if write_header:
        writer.writerow(header)

    writer.writerow([
        case["date"],
        operation["campaign_id"],
        case["case_id"],
        case["operation"],
        case["classification"],
        case["threat_family"],
        case["severity"],
        case["status"],
        operation["campaign_phase"],
        case["affected_platform"],
        case["device_family"],
        case["vendor"],
        case["network_zone"],
        case["confidence"],
        case["risk_score"],
        case["affected_assets"],
        case["evidence_count"],
        case["ioc_count"],
        case["initial_access"],
        case["lead_analyst"],
        case["priority"]
    ])

print("Investigation history updated.")
