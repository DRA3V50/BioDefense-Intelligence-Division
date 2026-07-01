import json
import csv
import os

# -----------------------------
# Current Investigation
# -----------------------------
with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

history_rows = []

history_file = "data/investigation_history.csv"

if os.path.exists(history_file):

    with open(history_file, newline="", encoding="utf-8") as csvfile:

        reader = csv.DictReader(csvfile)

        history_rows = list(reader)

total_cases = len(history_rows)

high_cases = sum(
    1 for row in history_rows
    if row.get("severity") == "HIGH"
)

critical_cases = sum(
    1 for row in history_rows
    if row.get("severity") == "CRITICAL"
)

recent_rows = history_rows[-5:]

recent_table = ""

if recent_rows:

    recent_table += "| Case | Classification | Severity |\n"
    recent_table += "|------|---------------|----------|\n"

    for row in reversed(recent_rows):

        recent_table += (
            f"| {row.get('case_id','N/A')} | "
            f"{row.get('classification','N/A')} | "
            f"{row.get('severity','N/A')} |\n"
        )

else:

    recent_table = (
        "| Case | Classification | Severity |\n"
        "|------|---------------|----------|\n"
        "| N/A | N/A | N/A |\n"
    )

report = f"""
<!-- FSE-REPORT-START -->

# Active Investigation

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

---

## Recent Intelligence Activity

{recent_table}

---

## Research Scope

- Firmware compromise investigations
- Embedded device forensics
- Threat intelligence correlation
- Digital evidence management
- Firmware validation
- Exposure reconstruction
- Malware persistence analysis
- Critical infrastructure security

>BioDefense Intelligence Division is an analytical research environment focused on firmware compromise investigations, embedded device security, operational threat intelligence, digital evidence management, and cyber incident reconstruction. The project emphasizes repeatable investigative workflows, structured reporting, forensic documentation, and automated evidence generation using Python and C#.

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
