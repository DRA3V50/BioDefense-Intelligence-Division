#!/usr/bin/env python3

import json
import random
from datetime import date

today = date.today().isoformat()

classifications = [
    "Firmware Integrity Alert",
    "Unauthorized Firmware Modification",
    "Embedded Device Exposure",
    "Bootloader Anomaly",
    "Persistence Indicator Review",
    "Supply Chain Validation Review",
    "Unsigned Firmware Detection",
    "Memory Artifact Investigation"
]

statuses = [
    "Open",
    "Active Investigation",
    "Evidence Collection",
    "Monitoring",
    "Contained"
]

assessments = [
    "Observed firmware hash deviations requiring validation.",
    "Analyst review identified anomalous embedded system behavior.",
    "Artifact correlation suggests potential unauthorized modification.",
    "Evidence remains inconclusive and requires additional collection.",
    "Indicators warrant continued monitoring and forensic review.",
    "Embedded device telemetry revealed irregular execution patterns.",
    "Firmware validation process identified unexpected code segments.",
    "Behavioral analysis suggests persistence-related anomalies."
]

severity_levels = [
    "LOW",
    "MODERATE",
    "HIGH",
    "CRITICAL"
]

affected_platforms = [
    "Industrial Controller",
    "Network Appliance",
    "Embedded Linux Device",
    "IoT Gateway",
    "Router Firmware",
    "Security Appliance"
]

case_data = {
    "case_id": f"FSE-{date.today().year}-{random.randint(1000,9999)}",
    "date": today,
    "classification": random.choice(classifications),
    "severity": random.choice(severity_levels),
    "status": random.choice(statuses),
    "affected_platform": random.choice(affected_platforms),
    "confidence": random.randint(60,95),
    "affected_assets": random.randint(1,15),
    "assessment": random.choice(assessments)
}

with open("data/current_case.json", "w") as f:
    json.dump(case_data, f, indent=2)

print("Case generated.")
