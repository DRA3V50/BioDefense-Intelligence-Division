import json
from pathlib import Path

with open("data/current_case.json") as f:
    case = json.load(f)

case_file = Path(f"cases/{case['case_id']}.md")

content = f"""# {case['case_id']}

## Investigation Summary

**Date:** {case['date']}

**Classification:** {case['classification']}

**Status:** {case['status']}

**Confidence:** {case['confidence']}%

**Affected Assets:** {case['affected_assets']}

## Analyst Assessment

{case['assessment']}
"""

case_file.write_text(content, encoding="utf-8")

print(f"Archived {case['case_id']}")
