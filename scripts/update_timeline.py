import json

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

timeline = f"""
# Exposure Timeline Reconstruction

## {case['date']}

### Case Opened
Case ID: {case['case_id']}

### Classification
{case['classification']}

### Initial Assessment
{case['assessment']}

### Current Status
{case['status']}

### Severity
{case['severity']}

---
"""

with open(
    "reconstruction/exposure_timeline.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(timeline)

print("Timeline updated.")
