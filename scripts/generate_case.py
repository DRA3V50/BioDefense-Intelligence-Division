#!/usr/bin/env python3
import json
import random
from datetime import date

today = date.today().isoformat()
case_types = [
    "Firmware Integrity Alert",
    "Unauthorized Firmware Modification",
    "Embedded Device Exposure",
    "System Artifact Anomaly",
    "Persistence Indicator Review"
]

statuses = [
    "Open",
    "Active Investigation",
    "Monitoring",
    "Contained"
]

assessments = [
    "Observed firmware hash deviations requiring validation.",
    "Analyst review identified anomalous embedded system behavior.",
    "Artifact correlation suggests potential unauthorized modification.",
    "Evidence remains inconclusive and requires additional collection.",
    "Indicators warrant continued monitoring and forensic review."
]

case_data = {
    "case_id": f"FSE-{date.today().year}-{random.randint(1000,9999)}",
    "date": today,
    "classification": random.choice(case_types),
    "status": random.choice(statuses),
    "confidence": random.randint(60,95),
    "affected_assets": random.randint(1,12),
    "assessment": random.choice(assessments)
}

with open("data/current_case.json", "w") as f:
    json.dump(case_data, f, indent=2)

print("Case generated:")
print(json.dumps(case_data, indent=2))
