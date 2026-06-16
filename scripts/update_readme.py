import json

with open("data/current_case.json") as f:
    case = json.load(f)

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
