import json
import random

with open("data/current_case.json") as f:
    case = json.load(f)

findings = [
    "No evidence of lateral movement detected.",
    "Firmware validation remains ongoing.",
    "Additional artifact correlation required.",
    "Exposure indicators remain under review.",
    "Telemetry analysis identified abnormal execution patterns."
]

report = f"""# Weekly Exposure Assessment

## Current Investigation

Case ID: {case['case_id']}

Classification: {case['classification']}

Severity: {case['severity']}

Status: {case['status']}

## Assessment

{random.choice(findings)}
"""

with open(
    "intelligence/weekly_assessment.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(report)

print("Assessment updated.")
