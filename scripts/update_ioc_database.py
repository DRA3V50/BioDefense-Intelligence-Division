import json
import random
import os

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

iocs = [

    ("SHA256",
     "5e4c9b8f73a4b4d11873f4d8d36c1b9c72d62bfc991a6d3c7ad2a6c74f82e214"),

    ("SHA256",
     "71cfd17cda12cb2d6679b1f6c7496c7d91e7f3488d4d5ac5eaf9d617af28e441"),

    ("IP Address",
     "185.193.126.44"),

    ("IP Address",
     "91.214.124.18"),

    ("Domain",
     "fw-update-check.net"),

    ("Domain",
     "embedded-sync.org"),

    ("Registry Key",
     "HKLM\\Software\\Firmware\\Persistence"),

    ("Registry Key",
     "HKCU\\Software\\BootMonitor"),

    ("Service",
     "FirmwareHealthService"),

    ("Process",
     "fwupdate.exe")
]

random.shuffle(iocs)

selected = iocs[:5]

output = f"""# Indicators of Compromise

Investigation: {case['case_id']}

Classification: {case['classification']}

---

| IOC Type | Indicator |
|-----------|-----------|
"""

for ioc_type, value in selected:

    output += f"| {ioc_type} | {value} |\n"

output += f"""

---

Confidence: {case['confidence']}%

Status: Active Investigation
"""

with open(
    "intelligence/ioc_database.md",
    "w",
    encoding="utf-8"
) as f:

    f.write(output)

print("IOC database updated.")
