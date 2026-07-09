import json
import csv
import os

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

phase = "Detection"

if os.path.exists("data/investigation_state.json"):
    with open("data/investigation_state.json", "r", encoding="utf-8") as f:
        phase = json.load(f).get(
            "current_phase",
            "Detection"
        )

history = []

if os.path.exists("data/investigation_history.csv"):
    with open(
        "data/investigation_history.csv",
        newline="",
        encoding="utf-8"
    ) as f:
        history = list(csv.DictReader(f))

total = len(history)

critical = sum(
    1 for h in history
    if h.get("severity") == "CRITICAL"
)

high = sum(
    1 for h in history
    if h.get("severity") == "HIGH"
)

recent = history[-5:]

recent_table = ""

if recent:

    recent_table += "| Case | Classification | Severity |\n"
    recent_table += "|------|---------------|----------|\n"

    for row in reversed(recent):

        recent_table += (
            f"| {row.get('case_id')} "
            f"| {row.get('classification')} "
            f"| {row.get('severity')} |\n"
        )

else:

    recent_table = (
        "| Case | Classification | Severity |\n"
        "|------|---------------|----------|\n"
        "| None | None | None |\n"
    )

report = f"""
<!-- FSE-REPORT-START -->

# BioDefense-Intelligence-Division

Federal cyber-biosecurity investigative environment dedicated to digital evidence reconstruction, laboratory infrastructure protection, protected biomedical infrastructure, laboratory network security, and structured forensic case management. The project automates investigative workflows, evidence tracking, reporting, and analyst documentation using Python and C#.
---

# Active Investigation

| Investigation | Classification |
|---------------|----------------|
| **Case ID**<br>{case["case_id"]}<br><br>**Operation**<br>{case["operation"]}<br><br>**Phase**<br>{phase} | **Classification**<br>{case["classification"]}<br><br>**Threat Family**<br>{case["threat_family"]}<br><br>**Severity**<br>{case["severity"]} |

---

| Device Profile | Investigation Status |
|---------------|----------------------|
| **Platform**<br>{case["affected_platform"]}<br><br>**Device**<br>{case["device_family"]}<br><br>**Vendor**<br>{case["vendor"]}<br><br>**Zone**<br>{case["network_zone"]} | **Priority**<br>{case["priority"]}<br><br>**Confidence**<br>{case["confidence"]}%<br><br>**Evidence**<br>{case["evidence_count"]}<br><br>**Indicators**<br>{case["ioc_count"]} |

---

# Analyst Assessment

{case["assessment"]}

---

# Current Response

- Lead Analyst: **{case["lead_analyst"]}**
- Initial Access: **{case["initial_access"]}**
- Recommended Action: **{case["recommended_action"]}**

---

# Operational Metrics

| Metric | Value |
|---------|------:|
| Investigations | {total} |
| High Severity | {high} |
| Critical Severity | {critical} |
| Current Phase | {phase} |

---

# Recent Investigations

{recent_table}

---

# Division Mission

BioDefense Intelligence Division is a defensive cybersecurity research project centered on cyber-enabled biosecurity investigations, protected research infrastructure, digital evidence management, forensic reconstruction, and coordinated incident response. The repository simulates how analysts document, track, and reconstruct complex investigations involving sensitive biomedical environments and critical operational systems.

<!-- FSE-REPORT-END -->
"""

with open("README.md", "r", encoding="utf-8") as f:
    existing = f.read()

start = "<!-- FSE-REPORT-START -->"
end = "<!-- FSE-REPORT-END -->"

if start in existing and end in existing:

    before = existing.split(start)[0]

    after = existing.split(end)[1]

    new = before + report + after

else:

    new = existing + "\n\n" + report

with open("README.md", "w", encoding="utf-8") as f:
    f.write(new)

print("README updated.")
