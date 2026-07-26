#!/usr/bin/env python3

"""
Generate an executive command brief for the active investigation.
"""

import json
from datetime import datetime
from pathlib import Path

CURRENT_CASE = Path("data/current_case.json")
ACTIVE_OPERATION = Path("operations/active_operation.json")
OUTPUT_FILE = Path("operations/command_brief.md")


def load_json(path):
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main():

    case = load_json(CURRENT_CASE)
    operation = load_json(ACTIVE_OPERATION)

    report = f"""# BioDefense Command Brief

**Generated:** {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}

---

## Operation

**Operation:** {operation.get("operation", "Unknown")}

**Campaign ID:** {operation.get("campaign_id", "Unknown")}

**Campaign Phase:** {operation.get("campaign_phase", "Unknown")}

**Containment Level:** {operation.get("containment_level", "Unknown")}

---

## Active Investigation

**Case ID:** {case.get("case_id", "Unknown")}

**Classification:** {case.get("classification", "Unknown")}

**Severity:** {case.get("severity", "Unknown")}

**Threat Family:** {case.get("threat_family", "Unknown")}

**Confidence:** {case.get("confidence", "Unknown")}%

---

## Investigation Summary

{case.get("assessment", "No assessment available.")}

---

## Evidence Summary

Evidence Collected: **{case.get("evidence_count", 0)}**

Indicators: **{case.get("ioc_count", 0)}**

Priority: **{case.get("priority", "Unknown")}**

---

## Current Response

Lead Analyst:
**{case.get("lead_analyst", "Unknown")}**

Initial Access:
**{case.get("initial_access", "Unknown")}**

Recommended Action:
**{case.get("recommended_action", "Unknown")}**

---

## Campaign Status

Active Cases:
**{operation.get("active_cases", 0)}**

Confirmed Intrusions:
**{operation.get("confirmed_intrusions", 0)}**

Total Evidence:
**{operation.get("evidence_collected", 0)}**

Total Indicators:
**{operation.get("ioc_count", 0)}**

---

## Operational Highlights

- {case.get("evidence_count", 0)} evidence items are associated with the active investigation.
- {case.get("ioc_count", 0)} indicators are currently linked to the case.
- Containment remains at **{operation.get("containment_level", "Unknown")}**.
- Analyst confidence is **{case.get("confidence", "Unknown")}%**.
- Current investigation priority is **{case.get("priority", "Unknown")}**.

---

## Immediate Priorities

1. {case.get("recommended_action", "Continue investigation and review available evidence.")}
2. Continue IOC correlation across affected systems.
3. Verify evidence integrity and chain-of-custody records.
4. Prepare the final operational assessment.

---

## Investigation Resources

- [Investigation Timeline](investigation_timeline.md)
- [Evidence Chain Analysis](../evidence/evidence_chain.md)
- [Active Operation](active_operation.json)
- [Operation Status](operation_status.json)

---

End of Command Brief
"""

    OUTPUT_FILE.write_text(report, encoding="utf-8")

    print("Command brief generated.")


if __name__ == "__main__":
    main()
