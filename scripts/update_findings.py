import json
import random

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

findings = [
    "Firmware hash mismatch detected.",
    "Unsigned module identified during validation.",
    "Boot sequence integrity review required.",
    "Embedded device telemetry anomaly detected.",
    "Unexpected firmware artifact discovered.",
    "Configuration persistence indicator observed.",
    "Supply chain verification remains incomplete.",
    "Memory analysis revealed irregular execution patterns."
]

selected = random.sample(findings, 3)

content = f"""# Active Findings

## Finding 1
{selected[0]}

## Finding 2
{selected[1]}

## Finding 3
{selected[2]}

## Case ID
{case['case_id']}

## Analyst Confidence
{case['confidence']}%
"""

with open(
    "intelligence/active_findings.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(content)

print("Findings updated.")
