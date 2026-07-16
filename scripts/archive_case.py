#!/usr/bin/env python3

import json
import csv
from pathlib import Path

# -------------------------------------------------
# Load current investigation
# -------------------------------------------------

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

with open("operations/active_operation.json", "r", encoding="utf-8") as f:
    operation = json.load(f)

# -------------------------------------------------
# Create archive folders
# -------------------------------------------------

archive_json = Path("cases/archive/json")
archive_md = Path("cases/archive/reports")

archive_json.mkdir(parents=True, exist_ok=True)
archive_md.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------
# Save JSON archive
# -------------------------------------------------

json_file = archive_json / f"{case['case_id']}.json"

with open(json_file, "w", encoding="utf-8") as f:
    json.dump(case, f, indent=4)

# -------------------------------------------------
# Save Markdown report
# -------------------------------------------------

md_file = archive_md / f"{case['case_id']}.md"

report = f"""# {case['case_id']}

# Investigation Overview

Operation:
{case["operation"]}

Campaign Phase:
{operation["campaign_phase"]}

Opened:
{case["date"]}

---

## Classification

{case["classification"]}

Threat Family

{case["threat_family"]}

Severity

{case["severity"]}

Priority

{case["priority"]}

Status

{case["status"]}

Containment

{case["containment_phase"]}

---

## Environment

Platform

{case["affected_platform"]}

Device

{case["device_family"]}

Vendor

{case["vendor"]}

Zone

{case["network_zone"]}

Affected Assets

{case["affected_assets"]}

---

## Metrics

Confidence

{case["confidence"]}%

Risk Score

{case["risk_score"]}

Evidence

{case["evidence_count"]}

Indicators

{case["ioc_count"]}

---

## Assessment

{case["assessment"]}

---

Lead Analyst

{case["lead_analyst"]}

Recommended Action

{case["recommended_action"]}
"""

md_file.write_text(report, encoding="utf-8")

# -------------------------------------------------
# Investigation History
# -------------------------------------------------

history_file = Path("data/investigation_history.csv")

new_file = not history_file.exists()

with open(history_file, "a", newline="", encoding="utf-8") as f:

    writer = csv.writer(f)

    if new_file:

        writer.writerow([
            "case_id",
            "date",
            "operation",
            "classification",
            "severity",
            "status",
            "priority"
        ])

    writer.writerow([
        case["case_id"],
        case["date"],
        case["operation"],
        case["classification"],
        case["severity"],
        case["status"],
        case["priority"]
    ])

print(f"Archived {case['case_id']}")
