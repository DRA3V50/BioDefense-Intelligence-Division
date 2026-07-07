import json
from pathlib import Path

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

sections = [
    ("Campaign Summary", "intelligence/campaign_summary.md"),
    ("Active Findings", "intelligence/active_findings.md"),
    ("Operational Assessment", "intelligence/weekly_assessment.md"),
    ("IOC Intelligence", "intelligence/ioc_database.md"),
    ("Forensic Summary", "reconstruction/forensic_summary.md"),
    ("Device Profile", "reconstruction/device_profile.md"),
    ("Exposure Timeline", "reconstruction/exposure_timeline.md")
]

report = f"""# BioDefense Intelligence Division

## Investigation Report

Case ID: {case["case_id"]}

Operation: {case["operation"]}

Date: {case["date"]}

Classification: {case["classification"]}

Severity: {case["severity"]}

Lead Analyst: {case["lead_analyst"]}

---

"""

for title, filename in sections:

    report += f"\n# {title}\n\n"

    path = Path(filename)

    if path.exists():

        report += path.read_text(encoding="utf-8")

    else:

        report += "_Section unavailable._"

    report += "\n\n---\n"

output = Path(f"cases/{case['case_id']}_REPORT.md")

output.write_text(report, encoding="utf-8")

print(f"Investigation report generated: {output.name}")
