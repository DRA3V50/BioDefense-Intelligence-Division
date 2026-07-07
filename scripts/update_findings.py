import json
import random

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

findings_pool = [

    "Evidence review identified anomalous activity requiring continued investigation.",

    "Device telemetry contained indicators inconsistent with expected operational behavior.",

    "Analysts observed integrity deviations requiring additional validation.",

    "Multiple artifacts require correlation before final assessment can be established.",

    "Evidence supports continued monitoring of affected infrastructure.",

    "Collected records indicate potential unauthorized system interaction.",

    "Investigation data suggests elevated operational risk within the affected environment.",

    "Additional forensic acquisition is recommended to determine full scope of activity.",

    "Observed indicators remain under active analytical review.",

    "Current evidence remains insufficient for attribution."
]

selected = random.sample(findings_pool, 5)

report = f"""# Active Investigation Findings

## Investigation Information

Case ID: {case["case_id"]}

Operation: {case["operation"]}

Classification: {case["classification"]}

Severity: {case["severity"]}

Priority: {case["priority"]}

---

## Analytical Findings

### Finding 1

{selected[0]}

### Finding 2

{selected[1]}

### Finding 3

{selected[2]}

### Finding 4

{selected[3]}

### Finding 5

{selected[4]}

---

## Investigation Metrics

Evidence Items:
{case["evidence_count"]}

Indicators Recorded:
{case["ioc_count"]}

Affected Assets:
{case["affected_assets"]}

Confidence:
{case["confidence"]}%

---

## Analyst Assessment

{case["assessment"]}

---

## Current Status

{case["status"]}
"""

with open(
    "intelligence/active_findings.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(report)

print("Investigation findings updated.")
