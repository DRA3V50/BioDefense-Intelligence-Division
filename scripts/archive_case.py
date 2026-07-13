#!/usr/bin/env python3

import json
from pathlib import Path

# -------------------------------------------------
# LOAD DATA
# -------------------------------------------------

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

with open("operations/active_operation.json", "r", encoding="utf-8") as f:
    operation = json.load(f)

# -------------------------------------------------
# CREATE INDIVIDUAL CASE FILE
# -------------------------------------------------

case_file = Path(f"cases/{case['case_id']}.md")

content = f"""# {case['case_id']}

## Investigation Overview

Campaign ID: {case['campaign_id']}

Operation: {case['operation']}

Campaign Phase: {operation['campaign_phase']}

Date Opened: {case['date']}

---

## Investigation

Classification: {case['classification']}

Threat Family: {case['threat_family']}

Severity: {case['severity']}

Status: {case['status']}

Priority: {case['priority']}

Containment Phase: {case['containment_phase']}

---

## Environment

Platform: {case['affected_platform']}

Device: {case['device_family']}

Vendor: {case['vendor']}

Network Zone: {case['network_zone']}

Affected Assets: {case['affected_assets']}

---

## Investigation Metrics

Confidence: {case['confidence']}%

Risk Score: {case['risk_score']}

Evidence Items: {case['evidence_count']}

Indicators: {case['ioc_count']}

---

## Analyst Assessment

{case['assessment']}

---

Lead Analyst:
{case['lead_analyst']}

Recommended Action:
{case['recommended_action']}
"""

case_file.write_text(content, encoding="utf-8")

# -------------------------------------------------
# UPDATE MASTER ARCHIVE
# -------------------------------------------------

archive = Path("cases/archive.md")

if not archive.exists():
    archive.write_text(
        "# BioDefense Intelligence Division Case Archive\n\n",
        encoding="utf-8"
    )

entry = f"""
## {case['case_id']}

Campaign:
{case['campaign_id']}

Operation:
{case['operation']}

Classification:
{case['classification']}

Threat:
{case['threat_family']}

Severity:
{case['severity']}

Status:
{case['status']}

Confidence:
{case['confidence']}%

Assessment:

{case['assessment']}

---

"""

with open(archive, "a", encoding="utf-8") as f:
    f.write(entry)

print(f"Archived investigation {case['case_id']}")
