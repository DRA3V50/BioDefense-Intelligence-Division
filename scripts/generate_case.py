#!/usr/bin/env python3

import json
import random
from datetime import date

today = date.today().isoformat()

operation_codenames = [
    "Operation ASHCROFT",
    "Operation HELIX",
    "Operation CERBERUS",
    "Operation CHIMERA",
    "Operation BLACKWELL",
    "Operation AEGIS",
    "Operation SENTINEL"
]

threat_families = [
    "Synthetic Persistence",
    "Firmware Rootkit",
    "Embedded Backdoor",
    "Supply Chain Implant",
    "Memory Injection",
    "Bootloader Compromise",
    "Digital Pathogen"
]

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

severity_levels = [
    "LOW",
    "MODERATE",
    "HIGH",
    "CRITICAL"
]

statuses = [
    "Open",
    "Evidence Collection",
    "Analysis",
    "Containment",
    "Monitoring"
]

containment_status = [
    "Contained",
    "Partially Contained",
    "Under Investigation",
    "Escalated"
]

biosecurity_levels = [
    "GREEN",
    "BLUE",
    "YELLOW",
    "ORANGE",
    "RED"
]

analysts = [
    "J. Carter",
    "M. Hayes",
    "R. Sullivan",
    "A. Brooks",
    "L. Chen",
    "S. Patel"
]

platforms = [
    "Industrial Controller",
    "Embedded Linux Device",
    "Router Firmware",
    "IoT Gateway",
    "Security Appliance",
    "Network Appliance"
]

vendors = [
    "Cisco",
    "Siemens",
    "Juniper",
    "Dell",
    "Advantech",
    "Schneider Electric"
]

mitre = [
    "T1542",
    "T1055",
    "T1078",
    "T1027",
    "T1105",
    "T1562",
    "T1003"
]

vectors = [
    "Supply Chain",
    "Firmware Update",
    "Remote Access",
    "USB Media",
    "Credential Abuse",
    "Unknown"
]

assessments = [
    "Observed firmware integrity deviations requiring immediate validation.",
    "Embedded telemetry indicates persistent unauthorized execution.",
    "Evidence supports possible firmware manipulation.",
    "Behavior consistent with advanced persistence techniques.",
    "Indicators warrant continued monitoring and forensic collection."
]

case = {
    "case_id": f"BID-{date.today().year}-{random.randint(1000,9999)}",
    "date": today,

    "operation_codename": random.choice(operation_codenames),

    "classification": random.choice(classifications),

    "threat_family": random.choice(threat_families),

    "severity": random.choice(severity_levels),

    "biosecurity_level": random.choice(biosecurity_levels),

    "status": random.choice(statuses),

    "containment_status": random.choice(containment_status),

    "affected_platform": random.choice(platforms),

    "vendor": random.choice(vendors),

    "firmware_version": f"{random.randint(1,9)}.{random.randint(0,9)}.{random.randint(0,9)}",

    "confidence": random.randint(70,99),

    "affected_assets": random.randint(2,30),

    "evidence_count": random.randint(5,40),

    "ioc_count": random.randint(3,25),

    "risk_score": random.randint(55,100),

    "mitre_attack": random.choice(mitre),

    "initial_access": random.choice(vectors),

    "lead_analyst": random.choice(analysts),

    "priority": random.choice([
        "Routine",
        "Elevated",
        "High",
        "Critical"
    ]),

    "recommended_action": random.choice([
        "Continue forensic analysis.",
        "Collect firmware image.",
        "Isolate affected systems.",
        "Deploy containment controls.",
        "Validate firmware signatures."
    ]),

    "assessment": random.choice(assessments)
}

with open("data/current_case.json", "w", encoding="utf-8") as f:
    json.dump(case, f, indent=4)

print("BioDefense Intelligence case generated.")
