import json
from pathlib import Path

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

evidence_summary = ""

evidence_file = Path("reconstruction/evidence_summary.md")

if evidence_file.exists():
    evidence_summary = evidence_file.read_text(encoding="utf-8")
else:
    evidence_summary = "_Evidence summary unavailable._"

report = f"""# Digital Forensic Investigation Report

## Investigation Overview

| Item | Value |
|------|-------|
| Case ID | {case["case_id"]} |
| Operation | {case["operation"]} |
| Classification | {case["classification"]} |
| Threat Family | {case["threat_family"]} |
| Severity | {case["severity"]} |
| Status | {case["status"]} |

---

# Protected Environment

| Property | Value |
|----------|-------|
| Platform | {case["affected_platform"]} |
| Device | {case["device_family"]} |
| Vendor | {case["vendor"]} |
| Security Zone | {case["network_zone"]} |

---

# Investigation Metrics

| Metric | Value |
|--------|------:|
| Risk Score | {case["risk_score"]} |
| Confidence | {case["confidence"]}% |
| Evidence Collected | {case["evidence_count"]} |
| Indicators Identified | {case["ioc_count"]} |
| Affected Assets | {case["affected_assets"]} |

---

# Lead Investigator

**{case["lead_analyst"]}**

---

# Executive Assessment

{case["assessment"]}

---

# Observations

Current investigative activity indicates unauthorized interaction with protected biomedical infrastructure.

Digital evidence has been preserved for forensic reconstruction.

Analysts continue validating investigative artifacts to determine operational scope and potential attribution.

No destructive activity has been confirmed during the current phase of the investigation.

---

# Evidence Summary

{evidence_summary}

---

# Recommended Actions

- Preserve all collected digital evidence.
- Continue forensic acquisition.
- Expand artifact correlation.
- Validate affected research resources.
- Monitor protected laboratory infrastructure.
- Maintain chain-of-custody documentation.

---

# Investigation Status

Current Phase:

**{case["containment_phase"]}**

Current Status:

**{case["status"]}**

Priority:

**{case["priority"]}**

Recommended Action:

**{case["recommended_action"]}**
"""

with open(
    "reconstruction/forensic_summary.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(report)

print("Forensic summary updated.")
