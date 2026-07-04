import json
import csv
from pathlib import Path

current_case = Path("data/current_case.json")
history = Path("data/investigation_history.csv")
output = Path("intelligence/campaign_summary.md")

with open(current_case, "r", encoding="utf-8") as f:
    case = json.load(f)

total = 0

if history.exists():
    with open(history, newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        next(reader, None)
        for row in reader:
            if row:
                total += 1

report = f"""# Campaign Summary

## Operational Overview

Current Campaign ID:
{case["case_id"]}

Current Classification:
{case["classification"]}

Operational Phase:
{case["status"]}

Investigations Recorded:
{total}

Affected Platform:
{case["affected_platform"]}

Current Confidence:
{case["confidence"]}%

---

## Division Assessment

Current investigative activity remains focused on identifying embedded device compromise, firmware integrity deviations, and recurring exposure behavior across monitored operational environments.

Analysts continue evidence correlation, forensic reconstruction, and device attribution while monitoring for additional indicators requiring containment.

---

## Current Operational Priority

Firmware Integrity Analysis

Exposure Path Reconstruction

Device Attribution

Evidence Correlation

Operational Monitoring
"""

with open(output, "w", encoding="utf-8") as f:
    f.write(report)

print("Campaign summary updated.")
