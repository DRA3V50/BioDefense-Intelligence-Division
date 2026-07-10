import json
from pathlib import Path

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

dashboard = f"""# Investigation Dashboard

## Current Case

| Field | Value |
|------|------|
| Case ID | {case["case_id"]} |
| Operation | {case["operation"]} |
| Classification | {case["classification"]} |
| Threat Family | {case["threat_family"]} |
| Severity | {case["severity"]} |
| Status | {case["status"]} |
| Phase | {case["containment_phase"]} |

---

## Protected Environment

| Field | Value |
|------|------|
| Platform | {case["affected_platform"]} |
| Device | {case["device_family"]} |
| Vendor | {case["vendor"]} |
| Network Zone | {case["network_zone"]} |

---

## Investigation Metrics

| Metric | Value |
|------|------:|
| Risk Score | {case["risk_score"]} |
| Confidence | {case["confidence"]}% |
| Evidence | {case["evidence_count"]} |
| Indicators | {case["ioc_count"]} |
| Affected Assets | {case["affected_assets"]} |

---

## Analyst

Lead Analyst: **{case["lead_analyst"]}**

Recommended Action:

{case["recommended_action"]}

Assessment:

{case["assessment"]}
"""

output = Path("intelligence/dashboard.md")
output.write_text(dashboard, encoding="utf-8")

print("Dashboard generated.")
