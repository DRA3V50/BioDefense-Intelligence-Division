import json
import csv
from pathlib import Path

current_case = Path("data/current_case.json")
history = Path("data/investigation_history.csv")
output = Path("intelligence/campaign_summary.md")

with open(current_case, "r", encoding="utf-8") as f:
    case = json.load(f)

total_cases = 0
critical_cases = 0
high_cases = 0

if history.exists():
    with open(history, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:

            total_cases += 1

            if row.get("severity") == "CRITICAL":
                critical_cases += 1

            elif row.get("severity") == "HIGH":
                high_cases += 1

report = f"""# Operational Campaign Summary

## Current Investigation

Case ID: {case["case_id"]}

Operation: {case["operation"]}

Threat Family: {case["threat_family"]}

Classification: {case["classification"]}

Current Phase: {case["status"]}

Priority: {case["priority"]}

Lead Analyst: {case["lead_analyst"]}

---

## Operational Activity

Total Investigations Recorded: {total_cases}

High Severity Cases: {high_cases}

Critical Severity Cases: {critical_cases}

Current Confidence: {case["confidence"]}%

Affected Assets: {case["affected_assets"]}

Evidence Collected: {case["evidence_count"]}

Indicators Recorded: {case["ioc_count"]}

---

## Intelligence Assessment

Current investigative activity indicates continued monitoring of a suspected digital biosecurity event.

Analysts are correlating recovered evidence, validating exposure indicators, reconstructing observed activity, and assessing potential operational impact.

No attribution has been established at this stage.

---

## Operational Priorities

• Evidence correlation

• Digital forensic reconstruction

• Embedded system validation

• Device integrity verification

• Indicator analysis

• Operational monitoring

---

## Recommended Action

{case["recommended_action"]}
"""

with open(output, "w", encoding="utf-8") as f:
    f.write(report)

print("Campaign summary updated.")
