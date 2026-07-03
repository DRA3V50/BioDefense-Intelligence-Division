import json
import csv
import os

# -----------------------------
# LOAD CASE
# -----------------------------
with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

# -----------------------------
# LOAD STATE
# -----------------------------
phase_path = "data/investigation_state.json"
phase = "Unknown"

if os.path.exists(phase_path):
    with open(phase_path, "r", encoding="utf-8") as f:
        phase = json.load(f).get("current_phase", "Unknown")

# -----------------------------
# LOAD HISTORY
# -----------------------------
history_file = "data/investigation_history.csv"
history_rows = []

if os.path.exists(history_file):
    with open(history_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        history_rows = list(reader)

total_cases = len(history_rows)
high = sum(1 for r in history_rows if r.get("severity") == "HIGH")
critical = sum(1 for r in history_rows if r.get("severity") == "CRITICAL")

recent = history_rows[-5:]

history_table = ""
if recent:
    history_table += "| Case ID | Classification | Severity |\n"
    history_table += "|--------|---------------|----------|\n"
    for r in reversed(recent):
        history_table += f"| {r.get('case_id','N/A')} | {r.get('classification','N/A')} | {r.get('severity','N/A')} |\n"

# -----------------------------
# LOCKED HEADER DESCRIPTION (DO NOT GENERATE)
# -----------------------------
header_description = """
Blue-team digital intelligence environment focused on firmware compromise detection, embedded system analysis, and structured forensic reconstruction of device-level anomalies across operational networks.
"""

# -----------------------------
# LOCKED RESEARCH SCOPE
# -----------------------------
research_scope = """
## RESEARCH SCOPE

- Firmware compromise investigations
- Embedded device forensics
- Exposure pathway reconstruction
- Threat intelligence correlation
- Digital biosecurity research
- Defensive malware analysis
- Critical infrastructure protection

BioDefense Intelligence Division is an analytical research environment focused on firmware compromise investigations, embedded device security, operational threat intelligence, digital evidence management, and cyber incident reconstruction. The project emphasizes repeatable investigative workflows, structured reporting, forensic documentation, and automated evidence generation using Python and C#.
"""

# -----------------------------
# REPORT
# -----------------------------
report = f"""
<!-- FSE-REPORT-START -->

# BIODEFENSE INTELLIGENCE DIVISION

{header_description}

>>

## ACTIVE INVESTIGATION

**Case ID:** {case['case_id']}
**Date:** {case['date']}
**Phase:** {phase}

>>

## CLASSIFICATION PROFILE

**Classification:** {case['classification']}
**Severity:** {case['severity']}
**Platform:** {case['affected_platform']}
**Affected Assets:** {case['affected_assets']}
**Confidence:** {case['confidence']}%

>>

## ANALYST ASSESSMENT

{case['assessment']}

>>

{research_scope}

>>

## OPERATIONAL METRICS

| Metric | Value |
|--------|------|
| Total Investigations | {total_cases} |
| High Severity | {high} |
| Critical Severity | {critical} |
| Active Phase | {phase} |

>>

## RECENT INVESTIGATIONS

{history_table}

<!-- FSE-REPORT-END -->
"""

# -----------------------------
# SAFE WRITEBACK
# -----------------------------
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

print("README updated (header + research scope locked).")
