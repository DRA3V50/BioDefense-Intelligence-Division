import json

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

summary = f"""# Campaign Intelligence Summary

## Executive Summary

Investigation **{case['case_id']}** remains under active analysis following detection of a **{case['classification']}** event affecting a **{case['affected_platform']}**.

Current analysis indicates the activity is consistent with unauthorized firmware-level modification requiring continued evidence collection and validation.

---

## Operational Assessment

Severity: {case['severity']}

Status: {case['status']}

Analyst Confidence: {case['confidence']}%

Affected Assets: {case['affected_assets']}

---

## Technical Assessment

Current investigative priorities include:

- Firmware integrity validation
- Embedded device forensic analysis
- Evidence correlation
- Exposure reconstruction
- Persistence verification
- Configuration analysis

---

## Intelligence Assessment

Current evidence does not indicate widespread compromise.

Additional telemetry collection and firmware validation remain in progress.

---

## Recommended Analyst Actions

- Continue firmware validation
- Review evidence chain
- Validate cryptographic hashes
- Compare firmware baseline
- Complete forensic reconstruction
- Update investigation documentation
"""

with open(
    "intelligence/campaign_summary.md",
    "w",
    encoding="utf-8"
) as f:

    f.write(summary)

print("Campaign summary updated.")
