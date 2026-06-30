import json
import csv
import os

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

history = []

if os.path.exists("data/investigation_history.csv"):
    with open(
        "data/investigation_history.csv",
        newline="",
        encoding="utf-8"
    ) as csvfile:
        history = list(csv.DictReader(csvfile))

total_cases = len(history)

critical_cases = 0
high_cases = 0

for row in history:
    severity = row.get("severity", "").upper()

    if severity == "CRITICAL":
        critical_cases += 1

    if severity == "HIGH":
        high_cases += 1

recent = history[-5:]

history_table = ""

if recent:

    history_table += (
        "\n## Recent Intelligence Activity\n\n"
    )

    history_table += (
        "| Case | Classification | Severity |\n"
    )

    history_table += (
        "|------|-----------------------------|----------|\n"
    )

    for row in reversed(recent):

        history_table += (
            f"| {row.get('case_id','N/A')} | "
            f"{row.get('classification','N/A')} | "
            f"{row.get('severity','N/A')} |\n"
        )

report = f"""
<!-- FSE-REPORT-START -->

# BioDefense Intelligence Division

Blue-team research environment focused on digital biosecurity,
firmware threat analysis, embedded device investigations,
and intelligence-driven exposure reconstruction.

---

## Active Investigation

**Case ID:** {case['case_id']}

**Date:** {case['date']}

**Classification:** {case['classification']}

**Severity:** {case['severity']}

**Status:** {case['status']}

**Affected Platform:** {case['affected_platform']}

**Confidence:** {case['confidence']}%

**Affected Assets:** {case['affected_assets']}

---

## Analyst Assessment

{case['assessment']}

---

## Division Intelligence Overview

| Metric | Value |
|--------|------:|
| Investigations Logged | {total_cases} |
| High Severity Cases | {high_cases} |
| Critical Severity Cases | {critical_cases} |
| Division Status | ACTIVE |
| Mission Focus | Embedded Biosecurity |
| Investigation Type | Firmware Intelligence |

{history_table}

---

## Research Scope

- Firmware compromise investigations
- Embedded device forensics
- Exposure pathway reconstruction
- Threat intelligence correlation
- Digital biosecurity research
- Defensive malware analysis
- Critical infrastructure protection

> BioDefense Intelligence Division is an analytical research environment focused on firmware compromise investigations, embedded device security, operational threat intelligence, digital evidence management, and cyber incident reconstruction. 
> The project emphasizes repeatable investigative workflows, structured reporting, forensic documentation, and automated evidence generation using Python and C#.

<!-- FSE-REPORT-END -->
"""

with open("README.md", "r", encoding="utf-8") as f:
    content = f.read()

start = "<!-- FSE-REPORT-START -->"
end = "<!-- FSE-REPORT-END -->"

if start in content and end in content:

    before = content.split(start)[0]
    after = content.split(end)[1]

    new_content = before + report + after

else:

    new_content = content + "\n\n" + report

with open("README.md", "w", encoding="utf-8") as f:
    f.write(new_content)

print("README updated.")
