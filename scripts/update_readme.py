import json
import csv
import os

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

phase = "Detection"

state_file = "data/investigation_state.json"

if os.path.exists(state_file):
    with open(state_file, "r", encoding="utf-8") as f:
        phase = json.load(f).get("current_phase", "Detection")

history = []

history_file = "data/investigation_history.csv"

if os.path.exists(history_file):
    with open(history_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        history = list(reader)

total = len(history)

high = sum(
    1 for row in history
    if row.get("severity") == "HIGH"
)

critical = sum(
    1 for row in history
    if row.get("severity") == "CRITICAL"
)

recent_rows = ""

for row in reversed(history[-5:]):

    recent_rows += (
        f"| {row.get('case_id')} | "
        f"{row.get('classification')} | "
        f"{row.get('severity')} |\n"
    )

if recent_rows == "":
    recent_rows = (
        "| N/A | N/A | N/A |\n"
    )

header = """
Blue-team digital investigation environment dedicated to firmware compromise analysis, embedded system forensics, evidence reconstruction, operational reporting, and digital biosecurity research.
"""

scope = """
## RESEARCH SCOPE

- Embedded device investigations
- Firmware integrity analysis
- Evidence reconstruction
- Digital forensic reporting
- Exposure pathway analysis
- Device attribution
- Operational biosecurity research
- Incident documentation
"""

report = f"""
<!-- FSE-REPORT-START -->

# BIODEFENSE INTELLIGENCE DIVISION

{header}

>

## ACTIVE INVESTIGATION

| Item | Value |
|------|-------|
| Case ID | {case['case_id']} |
| Date | {case['date']} |
| Operation | {case['operation']} |
| Investigation Phase | {phase} |

>

## CLASSIFICATION PROFILE

| Attribute | Value |
|-----------|-------|
| Classification | {case['classification']} |
| Threat Family | {case['threat_family']} |
| Severity | {case['severity']} |
| Priority | {case['priority']} |
| Risk Score | {case['risk_score']} |
| Confidence | {case['confidence']}% |

>

## DEVICE PROFILE

| Attribute | Value |
|-----------|-------|
| Platform | {case['affected_platform']} |
| Device Family | {case['device_family']} |
| Vendor | {case['vendor']} |
| Firmware | {case['firmware_version']} |
| Network Zone | {case['network_zone']} |
| Assets | {case['affected_assets']} |

>

## INVESTIGATION STATUS

| Metric | Value |
|---------|------|
| Evidence Items | {case['evidence_count']} |
| Indicators | {case['ioc_count']} |
| Initial Access | {case['initial_access']} |
| Lead Analyst | {case['lead_analyst']} |
| Recommended Action | {case['recommended_action']} |

>

## ANALYST ASSESSMENT

{case['assessment']}

>

{scope}

>

## OPERATIONAL METRICS

| Metric | Value |
|---------|------:|
| Total Investigations | {total} |
| High Severity Cases | {high} |
| Critical Severity Cases | {critical} |
| Current Phase | {phase} |

>

## RECENT INVESTIGATIONS

| Case ID | Classification | Severity |
|---------|---------------|----------|
{recent_rows}

<!-- FSE-REPORT-END -->
"""

with open("README.md", "r", encoding="utf-8") as f:
    readme = f.read()

start = "<!-- FSE-REPORT-START -->"
end = "<!-- FSE-REPORT-END -->"

if start in readme and end in readme:

    before = readme.split(start)[0]

    after = readme.split(end)[1]

    readme = before + report + after

else:

    readme += "\n\n" + report

with open("README.md", "w", encoding="utf-8") as f:
    f.write(readme)

print("README updated.")
