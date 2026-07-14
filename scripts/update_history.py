#!/usr/bin/env python3

import csv
import json
from pathlib import Path

history_file = Path("data/investigation_history.csv")

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

header = [
    "date",
    "campaign_id",
    "case_id",
    "operation",
    "classification",
    "threat_family",
    "severity",
    "status",
    "confidence",
    "risk_score"
]

write_header = not history_file.exists()

with open(history_file, "a", newline="", encoding="utf-8") as csvfile:

    writer = csv.writer(csvfile)

    if write_header:
        writer.writerow(header)

    writer.writerow([
        case["date"],
        case["campaign_id"],
        case["case_id"],
        case["operation"],
        case["classification"],
        case["threat_family"],
        case["severity"],
        case["status"],
        case["confidence"],
        case["risk_score"]
    ])

print(f"History updated for {case['case_id']}")

print(f"Investigation archived: {case['case_id']}")
