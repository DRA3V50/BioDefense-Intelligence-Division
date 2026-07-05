import json
import random

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

ioc_pool = [
    ("SHA256", "5e4c9b8f73a4b4d11873f4d8d36c1b9c72d62bfc991a6d3c7ad2a6c74f82e214"),
    ("SHA256", "71cfd17cda12cb2d6679b1f6c7496c7d91e7f3488d4d5ac5eaf9d617af28e441"),
    ("IPv4", "185.193.126.44"),
    ("IPv4", "91.214.124.18"),
    ("Domain", "telemetry-sync.net"),
    ("Domain", "device-update.org"),
    ("Hostname", "LAB-GW-014"),
    ("Hostname", "MED-NODE-22"),
    ("Service", "TelemetryMonitor"),
    ("Service", "DeviceIntegrityService"),
    ("Registry", "HKLM\\Software\\DeviceSecurity"),
    ("Process", "diagservice.exe"),
    ("Certificate", "Unsigned Embedded Certificate"),
    ("Firmware", "Unexpected boot image hash")
]

selected = random.sample(ioc_pool, 6)

report = f"""# Intelligence Bulletin

## Investigation

Case ID: {case["case_id"]}

Operation: {case["operation"]}

Classification: {case["classification"]}

Threat Family: {case["threat_family"]}

Priority: {case["priority"]}

---

## Indicators of Interest

| Type | Indicator |
|------|-----------|
"""

for t, v in selected:
    report += f"| {t} | {v} |\n"

report += f"""

---

## Analytical Notes

Current indicators require additional validation before attribution.

No indicator should be considered independently conclusive.

Correlation with collected evidence remains ongoing.

---

## Investigation Metrics

Evidence Items: {case["evidence_count"]}

Indicator Count: {case["ioc_count"]}

Confidence: {case["confidence"]}%

Status: {case["status"]}

Lead Analyst: {case["lead_analyst"]}

Recommended Action:

{case["recommended_action"]}
"""

with open(
    "intelligence/ioc_database.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(report)

print("IOC intelligence bulletin updated.")
