import json
from pathlib import Path

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

# Create individual case file
case_file = Path(f"cases/{case['case_id']}.md")

case_content = f"""# {case['case_id']}

## Investigation Summary

Date: {case['date']}

Classification: {case['classification']}

Severity: {case['severity']}

Status: {case['status']}

Confidence: {case['confidence']}%

Affected Assets: {case['affected_assets']}

Affected Platform: {case['affected_platform']}

## Analyst Assessment

{case['assessment']}
"""

case_file.write_text(case_content, encoding="utf-8")

# Update archive
archive_file = Path("cases/archive.md")

if not archive_file.exists():
    archive_file.write_text(
        "# Archived Investigations\n\n---\n",
        encoding="utf-8"
    )

archive_entry = f"""
## {case['case_id']}

- Date: {case['date']}
- Classification: {case['classification']}
- Severity: {case['severity']}
- Status: {case['status']}
- Confidence: {case['confidence']}%

{case['assessment']}

---
"""

with open(archive_file, "a", encoding="utf-8") as f:
    f.write(archive_entry)

print(f"Archived {case['case_id']}")
