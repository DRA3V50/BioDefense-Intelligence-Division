import json

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

timeline = f"""# Exposure Timeline Reconstruction

This document tracks reconstructed compromise timelines based on investigative findings and collected evidence.

---

## {case['date']} - Case Opened

### Case ID
{case['case_id']}

### Classification
{case['classification']}

### Severity
{case['severity']}

### Status
{case['status']}

### Affected Platform
{case['affected_platform']}

### Confidence
{case['confidence']}%

### Analyst Assessment
{case['assessment']}
"""

with open(
    "reconstruction/exposure_timeline.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(timeline)

print("Timeline updated.")
