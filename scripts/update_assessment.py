import json
import random

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

observations = [

    "Current evidence supports continued investigative activity.",

    "Observed indicators remain consistent with the current operational assessment.",

    "Additional forensic validation is required before investigative conclusions can be established.",

    "Evidence correlation remains in progress across collected artifacts.",

    "Operational monitoring continues while analysts validate recovered evidence.",

    "No confirmed attribution has been established during the current investigation.",

    "Analysts continue evaluating recovered indicators for operational significance.",

    "Current findings support maintaining the existing investigation priority."

]

report = f"""# Operational Assessment

## Investigation Overview

Case ID: {case["case_id"]}

Operation: {case["operation"]}

Classification: {case["classification"]}

Threat Family: {case["threat_family"]}

Current Status: {case["status"]}

Containment Phase: {case["containment_phase"]}

---

## Executive Assessment

{random.choice(observations)}

{case["assessment"]}

---

## Operational Metrics

Priority:
{case["priority"]}

Risk Score:
{case["risk_score"]}

Confidence:
{case["confidence"]}%

Affected Assets:
{case["affected_assets"]}

Evidence Collected:
{case["evidence_count"]}

Indicators Recorded:
{case["ioc_count"]}

---

## Recommended Action

{case["recommended_action"]}

---

## Analyst

Lead Investigator:

{case["lead_analyst"]}

Date:

{case["date"]}
"""

with open(
    "intelligence/weekly_assessment.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(report)

print("Operational assessment updated.")
