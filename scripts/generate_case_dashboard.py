import json
import csv
import os

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

# -----------------------------
# Investigation phase
# -----------------------------

phase = "Detection"

state_file = "data/investigation_state.json"

if os.path.exists(state_file):
    with open(state_file, "r", encoding="utf-8") as f:
        state = json.load(f)
        phase = state.get("current_phase", "Detection")

# -----------------------------
# History metrics
# -----------------------------

history_file = "data/investigation_history.csv"

history = []

if os.path.exists(history_file):

    with open(history_file, newline="", encoding="utf-8") as f:

        reader = csv.DictReader(f)

        history = list(reader)

total_cases = len(history)

critical = sum(
    1 for row in history
    if row.get("severity") == "CRITICAL"
)

high = sum(
    1 for row in history
    if row.get("severity") == "HIGH"
)

moderate = sum(
    1 for row in history
    if row.get("severity") == "MODERATE"
)

low = sum(
    1 for row in history
    if row.get("severity") == "LOW"
)

dashboard = f"""# Investigation Dashboard

## Current Investigation

| Item | Value |
|------|-------|
| Case ID | {case["case_id"]} |
| Operation | {case["operation"]} |
| Classification | {case["classification"]} |
| Threat Family | {case["threat_family"]} |
| Investigation Phase | {phase} |
| Status | {case["status"]} |

---

## Operational Profile

| Attribute | Value |
|-----------|-------|
| Platform | {case["affected_platform"]} |
| Device Family | {case["device_family"]} |
| Vendor | {case["vendor"]} |
| Network Zone | {case["network_zone"]} |
| Assets | {case["affected_assets"]} |

---

## Investigation Metrics

| Metric | Value |
|---------|------:|
| Confidence | {case["confidence"]}% |
| Risk Score | {case["risk_score"]} |
| Evidence Items | {case["evidence_count"]} |
| Indicators | {case["ioc_count"]} |

---

## Investigation History

| Metric | Value |
|---------|------:|
| Total Cases | {total_cases} |
| Critical | {critical} |
| High | {high} |
| Moderate | {moderate} |
| Low | {low} |

---

## Current Assessment

{case["assessment"]}

---

## Recommended Action

{case["recommended_action"]}

---

Generated automatically by the BioDefense Intelligence Division investigation pipeline.
"""

with open(
    "intelligence/investigation_dashboard.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(dashboard)

print("Investigation dashboard generated.")
