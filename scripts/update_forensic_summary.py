import json

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

report = f"""# Digital Forensic Summary

## Investigation Information

Case ID: {case['case_id']}

Date Opened: {case['date']}

Status: {case['status']}

Classification: {case['classification']}

Severity: {case['severity']}

Affected Platform: {case['affected_platform']}

---

## Executive Assessment

Initial triage identified indicators consistent with a firmware-related security event requiring detailed forensic examination. Current evidence supports continued analysis to determine scope, persistence mechanisms, and potential operational impact.

---

## Evidence Reviewed

• Firmware image integrity

• Embedded configuration artifacts

• Device telemetry

• System event records

• Boot sequence analysis

---

## Technical Findings

Current investigation identified anomalies requiring additional validation.

No conclusion has been reached regarding the complete extent of compromise.

Evidence collected to date remains internally consistent with the current investigative assessment.

---

## Risk Assessment

Confidence: {case['confidence']}%

Affected Assets: {case['affected_assets']}

Current Risk Level: {case['severity']}

---

## Recommended Next Actions

- Continue firmware validation

- Verify firmware hashes

- Correlate collected evidence

- Expand device acquisition

- Complete chain of custody review

- Finalize forensic reconstruction
"""

with open(
    "reconstruction/forensic_summary.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(report)

print("Forensic summary updated.")
