#!/usr/bin/env python3

import json
import random
from datetime import datetime

today = datetime.utcnow().strftime("%Y-%m-%d")

operation_names = [
    "Operation Sentinel",
    "Operation Black Horizon",
    "Operation Helix",
    "Operation Iron Shield",
    "Operation Eclipse",
    "Operation Aegis",
    "Operation Catalyst",
    "Operation Ashcroft",
    "Operation Silent Vector",
    "Operation Night Watch"
]

classifications = [
    "Embedded Device Exposure",
    "Firmware Integrity Alert",
    "Unauthorized Firmware Modification",
    "Bootloader Anomaly",
    "Persistence Indicator Review",
    "Supply Chain Validation Review",
    "Memory Artifact Investigation",
    "Firmware Signature Failure"
]

threat_families = [
    "Firmware Rootkit",
    "Embedded Persistence",
    "Supply Chain Implant",
    "Memory Injection",
    "Unauthorized Boot Module",
    "Configuration Tampering",
    "Privilege Escalation Component"
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

containment_phases = [
    "Detection",
    "Collection",
    "Analysis",
    "Correlation",
    "Containment",
    "Recovery"
]

platforms = [
    "Industrial Controller",
    "Industrial Gateway",
    "Router Firmware",
    "Embedded Linux Device",
    "Medical Embedded Device",
    "Security Appliance",
    "Network Appliance"
]

device_families = [
    "Industrial Router",
    "Programmable Logic Controller",
    "Embedded Sensor",
    "Access Gateway",
    "Medical Controller",
    "SCADA Controller"
]

network_zones = [
    "Research VLAN",
    "Operations VLAN",
    "Manufacturing Network",
    "DMZ",
    "Internal Core",
    "Secure Segment"
]

vendors = [
    "Cisco",
    "Siemens",
    "Schneider Electric",
    "Juniper",
    "Dell",
    "Advantech"
]

vectors = [
    "Supply Chain",
    "Remote Access",
    "Firmware Update",
    "Credential Abuse",
    "USB Media",
    "Unknown"
]

analysts = [
    "Analyst Team Alpha",
    "Analyst Team Bravo",
    "Analyst Team Delta",
    "Analyst Team Sigma"
]

assessments = [
    "Firmware integrity deviations require continued validation before containment decisions are finalized.",
    "Collected evidence indicates unauthorized modification requiring additional forensic acquisition.",
    "Embedded telemetry demonstrates abnormal execution behavior consistent with persistent firmware compromise.",
    "Device artifacts require additional reconstruction to determine operational impact.",
    "Investigation remains active while analysts continue evidence correlation and firmware verification."
]

recommendations = [
    "Acquire complete firmware image.",
    "Expand forensic acquisition.",
    "Verify firmware signatures.",
    "Perform hash validation.",
    "Isolate affected devices.",
    "Continue evidence collection."
]

case = {
    "case_id": f"BID-{datetime.utcnow().year}-{random.randint(1000,9999)}",
    "date": today,

    "operation": random.choice(operation_names),

    "classification": random.choice(classifications),

    "threat_family": random.choice(threat_families),

    "severity": random.choice(severity_levels),

    "status": random.choice(statuses),

    "containment_phase": random.choice(containment_phases),

    "affected_platform": random.choice(platforms),

    "device_family": random.choice(device_families),

    "vendor": random.choice(vendors),

    "network_zone": random.choice(network_zones),

    "firmware_version":
        f"{random.randint(1,8)}."
        f"{random.randint(0,9)}."
        f"{random.randint(0,9)}",

    "confidence": random.randint(75,99),

    "risk_score": random.randint(40,100),

    "affected_assets": random.randint(3,40),

    "evidence_count": random.randint(8,60),

    "ioc_count": random.randint(2,25),

    "initial_access": random.choice(vectors),

    "lead_analyst": random.choice(analysts),

    "priority": random.choice([
        "Priority I",
        "Priority II",
        "Priority III"
    ]),

    "recommended_action": random.choice(recommendations),

    "assessment": random.choice(assessments)
}

with open(
    "data/current_case.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(case, f, indent=4)

print(f"Generated investigation {case['case_id']}")
