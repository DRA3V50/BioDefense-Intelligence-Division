import json

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

report = f"""# Digital Investigation Summary

## Case Information

| Item | Value |
|------|-------|
| Case ID | {case["case_id"]} |
| Operation | {case["operation"]} |
| Investigation Date | {case["date"]} |
| Classification | {case["classification"]} |
| Threat Family | {case["threat_family"]} |
| Investigation Status | {case["status"]} |
| Containment Phase | {case["containment_phase"]} |

---

## Operational Overview

This investigation concerns a suspected digital biosecurity event affecting monitored operational technology and embedded systems.

Current investigative activity is focused on determining the origin of anomalous behavior, validating collected evidence, identifying exposure pathways, and reconstructing the sequence of events leading to detection.

At this stage no attribution has been established and investigative activities remain ongoing.

---

## Infrastructure Profile

| Attribute | Value |
|----------|-------|
| Platform | {case["affected_platform"]} |
| Device Family | {case["device_family"]} |
| Vendor | {case["vendor"]} |
| Firmware Version | {case["firmware_version"]} |
| Network Zone | {case["network_zone"]} |
| Affected Assets | {case["affected_assets"]} |

---

## Evidence Summary

Evidence collected during this investigation currently includes:

• Firmware images

• Embedded configuration artifacts

• Device telemetry

• Boot records

• System event logs

• Network observations

Evidence collection remains active while additional artifacts are validated.

---

## Exposure Assessment

Threat Family:

{case["threat_family"]}

Initial Access Vector:

{case["initial_access"]}

Observed Risk Score:

{case["risk_score"]}

Confidence Level:

{case["confidence"]}%

Priority:

{case["priority"]}

---

## Analyst Assessment

{case["assessment"]}

---

## Recommended Actions

Primary Recommendation

{case["recommended_action"]}

Additional investigative actions:

- Continue forensic acquisition
- Expand evidence correlation
- Validate device integrity
- Preserve collected artifacts
- Continue monitoring affected infrastructure

---

## Current Investigation Status

Lead Analyst:

{case["lead_analyst"]}

Current Status:

{case["status"]}

Evidence Items:

{case["evidence_count"]}

Indicators of Interest:

{case["ioc_count"]}

Containment Phase:

{case["containment_phase"]}

---

This report is automatically generated as part of the BioDefense Intelligence Division investigative workflow.
"""

with open(
    "reconstruction/forensic_summary.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(report)

print("Forensic summary updated.")
