import json
import csv
import os

# -----------------------------
# Load case
# -----------------------------
with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

# -----------------------------
# Load phase state
# -----------------------------
phase_path = "data/investigation_state.json"

current_phase = "Unknown"

if os.path.exists(phase_path):
    with open(phase_path, "r", encoding="utf-8") as f:
        state = json.load(f)
        current_phase = state.get("current_phase", "Unknown")

# -----------------------------
# Load history
# -----------------------------
history_file = "data/investigation_history.csv"
history_rows = []

if os.path.exists(history_file):
    with open(history_file, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        history_rows = list(reader)

total_cases = len(history_rows)

high_cases = sum(1 for r in history_rows if r.get("severity") == "HIGH")
critical_cases = sum(1 for r in history_rows if r.get("severity") == "CRITICAL")

recent_rows = history_rows[-5:]

table = ""

if recent_rows:
    table += "| Case | Classification | Severity |\n"
    table += "|------|---------------|----------|\n"

    for r in reversed(recent_rows):
        table += f"| {r.get('case_id','N/A')} | {r.get('classification','N/A')} | {r.get('severity','N/A')} |\n"

# -----------------------------
# REPORT
# -----------------------------
report = f"""
<!-- FSE-REPORT-START -->

# Active Investigation

**Case ID:** {case['case_id']}

**Date:** {case['date']}

**Classification:** {case['classification']}

**Severity:** {case['severity']}

**Status:** {case['status']}

**Investigation Phase:** {current_phase}

**Platform:** {case['affected_platform']}

**Confidence:** {case['confidence']}%

**Affected Assets:** {case['affected_assets']}

---

## Analyst Assessment

{case['assessment']}

---

## Operational Intelligence Overview

| Metric | Value |
|--------|------:|
| Total Investigations | {total_cases} |
| High Severity Cases | {high_cases} |
| Critical Cases | {critical_cases} |
| Active Phase | {current_phase} |

---

## Recent Investigations

{table}

<!-- FSE-REPORT-END -->
"""

# -----------------------------
# Inject into README
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

print("README updated with investigation phase.")
