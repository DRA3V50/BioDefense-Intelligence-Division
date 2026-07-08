#!/usr/bin/env python3

import json
import random
from datetime import date

today = date.today().isoformat()

operations = [
    "Operation Ashcroft",
    "Operation Black Archive",
    "Operation Cerberus",
    "Operation Eclipse",
    "Operation Lazarus",
    "Operation Genesis",
    "Operation Nightfall",
    "Operation Cold Harbor",
    "Operation Outbreak",
    "Operation Sentinel",
    "Operation Chimera",
    "Operation Dead Signal"
]

classifications = [
    "Biosecurity Infrastructure Investigation",
    "Biomedical Network Exposure",
    "Laboratory Security Breach",
    "Digital Pathogen Intelligence Review",
    "Research Facility Intrusion",
    "Biocontainment Network Investigation",
    "Medical Device Security Assessment",
    "Unauthorized Research System Access",
    "Evidence Reconstruction Investigation",
    "Counter-Bioterror Intelligence Case"
]

threat_families = [
    "Synthetic Genome Theft",
    "Laboratory Credential Abuse",
    "Research Network Persistence",
    "Medical Infrastructure Sabotage",
    "Unauthorized Experiment Access",
    "Biological Data Exfiltration",
    "Specimen Tracking Manipulation",
    "Secure Facility Reconnaissance",
    "Insider Research Compromise",
    "Digital Outbreak Simulation"
]

severity = [
    "LOW",
    "MODERATE",
    "HIGH",
    "CRITICAL"
]

statuses = [
    "Open",
    "Evidence Collection",
    "Intelligence Analysis",
    "Field Coordination",
    "Containment",
    "Monitoring"
]

containment = [
    "Detection",
    "Acquisition",
    "Forensic Analysis",
    "Containment",
    "Recovery",
    "Closed"
]

platforms = [
    "Research Network",
    "Biocontainment Facility",
    "Medical Research Laboratory",
    "Genomics Server",
    "Hospital Infrastructure",
    "Clinical Trial Environment",
    "Federal Investigation Network",
    "Digital Evidence Repository"
]

device_families = [
    "Laboratory Controller",
    "Evidence Storage Server",
    "Biomedical Workstation",
    "Research Cluster",
    "Clinical Database",
    "Forensic Imaging Station",
    "Specimen Tracking Server",
    "Access Control System"
]

vendors = [
    "Cisco",
    "Dell",
    "Microsoft",
    "Palo Alto Networks",
    "Fortinet",
    "VMware",
    "Lenovo",
    "Red Hat"
]

zones = [
    "Internal Research",
    "Evidence Network",
    "Secure Operations",
    "Federal Operations",
    "Quarantine Zone",
    "Biosecurity Segment"
]

access = [
    "Credential Abuse",
    "Remote Access",
    "Supply Chain",
    "Phishing",
    "Compromised VPN",
    "Unknown"
]

analysts = [
    "Analyst Team Alpha",
    "Analyst Team Bravo",
    "Analyst Team Delta",
    "Analyst Team Echo",
    "Special Response Unit",
    "BioDefense Task Force"
]

priorities = [
    "Priority III",
    "Priority II",
    "Priority I"
]

actions = [
    "Acquire volatile evidence from affected systems.",
    "Coordinate with federal response partners.",
    "Expand forensic acquisition across impacted hosts.",
    "Correlate collected intelligence with previous investigations.",
    "Validate chain of custody documentation.",
    "Review laboratory access records.",
    "Continue digital evidence reconstruction.",
    "Maintain operational monitoring."
]

assessments = [
    "Evidence suggests coordinated reconnaissance against protected biomedical infrastructure.",
    "Collected intelligence indicates unauthorized access requiring continued forensic reconstruction.",
    "Analysts identified suspicious activity affecting protected research resources.",
    "Current evidence supports expansion of the investigation into additional connected assets.",
    "Indicators remain consistent with a sophisticated cyber-enabled biosecurity investigation.",
    "Digital evidence continues to be evaluated to determine operational scope and attribution."
]

case = {

    "case_id": f"BID-{date.today().year}-{random.randint(1000,9999)}",

    "date": today,

    "operation": random.choice(operations),

    "classification": random.choice(classifications),

    "threat_family": random.choice(threat_families),

    "severity": random.choice(severity),

    "status": random.choice(statuses),

    "containment_phase": random.choice(containment),

    "affected_platform": random.choice(platforms),

    "device_family": random.choice(device_families),

    "vendor": random.choice(vendors),

    "network_zone": random.choice(zones),

    "firmware_version": f"{random.randint(1,5)}.{random.randint(0,9)}.{random.randint(0,9)}",

    "confidence": random.randint(78,99),

    "risk_score": random.randint(45,100),

    "affected_assets": random.randint(4,45),

    "evidence_count": random.randint(10,60),

    "ioc_count": random.randint(5,35),

    "initial_access": random.choice(access),

    "lead_analyst": random.choice(analysts),

    "priority": random.choice(priorities),

    "recommended_action": random.choice(actions),

    "assessment": random.choice(assessments)
}

with open(
    "data/current_case.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(case, f, indent=4)

print(f"Generated investigation {case['case_id']}")
