import json

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

mapping = {

    "Firmware Integrity Alert": [
        ("T1542", "Pre-OS Boot"),
        ("T1601", "Modify System Image")
    ],

    "Unauthorized Firmware Modification": [
        ("T1601", "Modify System Image"),
        ("T1542", "Pre-OS Boot")
    ],

    "Bootloader Anomaly": [
        ("T1542.003", "Bootkit"),
        ("T1601", "Modify System Image")
    ],

    "Embedded Device Exposure": [
        ("T1195", "Supply Chain Compromise"),
        ("T1078", "Valid Accounts")
    ],

    "Persistence Indicator Review": [
        ("T1547", "Boot or Logon Autostart"),
        ("T1053", "Scheduled Task")
    ],

    "Supply Chain Validation Review": [
        ("T1195", "Supply Chain Compromise"),
        ("T1588", "Obtain Capabilities")
    ],

    "Unsigned Firmware Detection": [
        ("T1553", "Subvert Trust Controls"),
        ("T1601", "Modify System Image")
    ],

    "Memory Artifact Investigation": [
        ("T1003", "Credential Dumping"),
        ("T1055", "Process Injection")
    ]
}

techniques = mapping.get(case["classification"], [])

report = f"""# MITRE ATT&CK Mapping

Investigation: {case['case_id']}

Classification: {case['classification']}

---

| Technique | Description |
|-----------|-------------|
"""

for t_id, desc in techniques:
    report += f"| {t_id} | {desc} |\n"

report += f"""

---

Analyst Confidence: {case['confidence']}%

Status: Correlated
"""

with open(
    "intelligence/mitre_attack_mapping.md",
    "w",
    encoding="utf-8"
) as f:

    f.write(report)

print("MITRE mapping updated.")
