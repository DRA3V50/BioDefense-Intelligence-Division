import json
import random

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

artifacts = [

    ("Network Artifact", "Suspicious outbound TLS session to untrusted infrastructure"),
    ("Authentication", "Privileged account authenticated outside approved maintenance window"),
    ("Research Storage", "Unauthorized access to protected genomic repository"),
    ("Endpoint Activity", "Unsigned executable observed within laboratory environment"),
    ("System Log", "Unexpected privilege escalation recorded"),
    ("PowerShell", "Encoded administrative command execution detected"),
    ("Database", "Protected biomedical dataset queried outside normal operating hours"),
    ("Identity", "Credential reuse detected across isolated research segments"),
    ("Network", "Unexpected east-west traffic between laboratory VLANs"),
    ("Evidence", "Acquired forensic image verified using SHA-256"),
    ("Infrastructure", "Firewall policy deviation identified"),
    ("Cloud", "Restricted research archive synchronized to unauthorized destination"),
    ("Device", "Protected workstation entered evidence preservation mode"),
    ("Security", "Multi-factor authentication bypass attempt recorded"),
    ("Email", "Targeted spear-phishing message delivered to laboratory personnel")

]

selected = random.sample(artifacts, 6)

report = f"""# Investigation Artifacts

## Investigation

Case ID:
{case["case_id"]}

Operation:
{case["operation"]}

Classification:
{case["classification"]}

---

| Category | Observation |
|----------|-------------|
"""

for category, observation in selected:
    report += f"| {category} | {observation} |\n"

report += f"""

---

## Investigation Statistics

Evidence Collected:
{case["evidence_count"]}

Indicators Reviewed:
{case["ioc_count"]}

Risk Score:
{case["risk_score"]}

Confidence:
{case["confidence"]}%

---

Lead Analyst:

{case["lead_analyst"]}

Current Status:

{case["status"]}
"""

with open(
    "intelligence/ioc_database.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(report)

print("Investigation artifact database updated.")
