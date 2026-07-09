import json
from pathlib import Path

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

cases_dir = Path("cases")
cases_dir.mkdir(exist_ok=True)

report = f"""# {case["case_id"]}

## Investigation Summary

| Item | Value |
|------|-------|
| Operation | {case["operation"]} |
| Classification | {case["classification"]} |
| Threat Family | {case["threat_family"]} |
| Severity | {case["severity"]} |
| Status | {case["status"]} |
| Phase | {case["containment_phase"]} |

---

## Infrastructure

- Platform: {case["affected_platform"]}
- Device: {case["device_family"]}
- Vendor: {case["vendor"]}
- Network Zone: {case["network_zone"]}

---

## Investigation Metrics

- Confidence: {case["confidence"]}%
- Risk Score: {case["risk_score"]}
- Evidence Items: {case["evidence_count"]}
- Indicators: {case["ioc_count"]}
- Affected Assets: {case["affected_assets"]}

---

## Operational Response

Lead Analyst:
{case["lead_analyst"]}

Initial Access:
{case["initial_access"]}

Recommended Action:
{case["recommended_action"]}

---

## Analyst Assessment

{case["assessment"]}

---

Generated automatically by BioDefense Intelligence Division.
"""

output = cases_dir / f"{case['case_id']}.md"
output.write_text(report, encoding="utf-8")

print(f"Archived investigation: {output.name}")
