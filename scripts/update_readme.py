import json
import csv
import os

with open("data/current_case.json") as f:
    case = json.load(f)
with open(
    "data/investigation_history.csv",
    "r",
    encoding="utf-8"
) as f:
    history = f.readlines()

total_cases = len(history)

history_rows = []

if os.path.exists("data/investigation_history.csv"):
    with open("data/investigation_history.csv", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        history_rows = list(reader)[-5:]

history_table = ""

if history_rows:
    history_table += "\n## Recent Investigations\n\n"
    history_table += "| Case ID | Classification | Severity |\n"
    history_table += "|---------|---------------|----------|\n"

    for row in reversed(history_rows):
        history_table += (
            f"| {row['case_id']} | "
            f"{row['classification']} | "
            f"{row['severity']} |\n"
        )

report = f"""
<!-- FSE-REPORT-START -->

# 🔍 Active Investigation

**Case ID:** {case['case_id']}

**Date:** {case['date']}

**Classification:** {case['classification']}

**Severity:** {case['severity']}

**Status:** {case['status']}

**Affected Platform:** {case['affected_platform']}

**Confidence:** {case['confidence']}%

**Affected Assets:** {case['affected_assets']}

## Analyst Assessment

{case['assessment']}

{history_table}

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
