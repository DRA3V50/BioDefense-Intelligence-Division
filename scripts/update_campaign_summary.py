import json
import csv
from pathlib import Path

case_file = Path("data/current_case.json")
history_file = Path("data/investigation_history.csv")
output_file = Path("intelligence/campaign_summary.md")

with open(case_file, "r", encoding="utf-8") as f:
    case = json.load(f)

total_cases = 0

if history_file.exists():
    with open(history_file, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        total_cases = sum(1 for _ in reader)

report = f"""# Operational Investigation Summary

## Current Investigation

Case ID:
{case["case_id"]}

Operation:
{case["operation"]}

Classification:
{case["classification"]}

Threat Family:
{case["threat_family"]}

Current Phase:
{case["containment_phase"]}

Status:
{case["status"]}

---

## Protected Environment

Platform:
{case["affected_platform"]}

Device:
{case["device_family"]}

Vendor:
{case["vendor"]}

Security Zone:
{case["network_zone"]}

---

## Investigation Metrics

Investigations Recorded:
{total_cases}

Evidence Collected:
{case["evidence_count"]}

Indicators Identified:
{case["ioc_count"]}

Affected Assets:
{case["affected_assets"]}

Confidence:
{case["confidence"]}%

Risk Score:
{case["risk_score"]}

---

## Operational Assessment

Current investigative activity remains focused on identifying unauthorized access affecting protected biomedical infrastructure.

Digital evidence continues to be correlated to establish investigative scope, determine potential attribution, and preserve forensic integrity.

No destructive activity has been confirmed during the current phase of this investigation.

---

## Recommended Operational Priorities

• Continue forensic acquisition

• Preserve digital evidence

• Correlate investigative artifacts

• Monitor protected laboratory infrastructure

• Complete attribution analysis

• Prepare investigative findings for final review
"""

with open(output_file, "w", encoding="utf-8") as f:
    f.write(report)

print("Operational investigation summary updated.")
