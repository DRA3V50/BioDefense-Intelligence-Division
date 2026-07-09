import json
import random

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

findings_pool = [

    "Unauthorized access to protected biomedical research resources was confirmed during evidence review.",

    "Analysts identified abnormal authentication activity originating from restricted laboratory infrastructure.",

    "Digital evidence suggests attempted collection of sensitive genomic research datasets.",

    "Multiple investigative artifacts require additional correlation before attribution can be established.",

    "Evidence preservation procedures successfully secured affected systems for forensic reconstruction.",

    "Suspicious outbound communication was detected prior to containment operations.",

    "Privilege escalation activity was observed within a protected research environment.",

    "Analysts recovered digital artifacts consistent with unauthorized research intelligence collection.",

    "No destructive malware activity has been identified at this stage of the investigation.",

    "Chain-of-custody documentation has been completed for all acquired digital evidence.",

    "Indicators remain consistent with a coordinated cyber-enabled bioterror intelligence operation.",

    "Additional forensic examination is required to determine the full operational scope.",

    "Evidence indicates possible insider-assisted access to protected laboratory resources.",

    "Collected indicators continue to support an active counter-bioterrorism investigation.",

    "Laboratory network telemetry remains under continuous monitoring pending case closure."

]

selected = random.sample(findings_pool, 5)

report = f"""# Active Investigation Findings

## Investigation

Case ID:
{case["case_id"]}

Operation:
{case["operation"]}

Classification:
{case["classification"]}

Threat Family:
{case["threat_family"]}

Severity:
{case["severity"]}

Priority:
{case["priority"]}

---

# Investigative Findings

### Finding 1

{selected[0]}

### Finding 2

{selected[1]}

### Finding 3

{selected[2]}

### Finding 4

{selected[3]}

### Finding 5

{selected[4]}

---

# Investigation Metrics

Affected Assets:
{case["affected_assets"]}

Evidence Collected:
{case["evidence_count"]}

Indicators Identified:
{case["ioc_count"]}

Analyst Confidence:
{case["confidence"]}%

Containment Phase:
{case["containment_phase"]}

---

# Analyst Assessment

{case["assessment"]}

---

# Operational Status

Current Status:
{case["status"]}

Recommended Action:

{case["recommended_action"]}

Lead Analyst:

{case["lead_analyst"]}
"""

with open(
    "intelligence/active_findings.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(report)

print("Active findings updated.")
