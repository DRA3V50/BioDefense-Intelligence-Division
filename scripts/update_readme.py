import json
import csv
import os

# -----------------------------
# LOAD CASE
# -----------------------------
with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

# -----------------------------
# LOAD PHASE
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
# INTEL BRIEF STYLE REPORT
# -----------------------------
report = f"""
<!-- FSE-REPORT-START -->

# BIODEFENSE INTELLIGENCE DIVISION
## OPERATIONAL INTELLIGENCE BRIEF

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

## RESEARCH SCOPE

This division conducts structured analysis of firmware integrity events, embedded system anomalies, and digital biosecurity exposures across critical infrastructure environments.

Focus areas include:
- Firmware integrity validation
- Embedded system forensic analysis
- Supply-chain compromise detection
- Device-level persistence investigation
- Digital exposure reconstruction

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
# WRITE BACK
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

print("README updated (intel brief format).")
