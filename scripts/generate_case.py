#!/usr/bin/env python3

import json
import random
from datetime import date

today = date.today().isoformat()

# -------------------------------------------------
# LOAD ACTIVE OPERATION
# -------------------------------------------------

with open(
    "operations/active_operation.json",
    "r",
    encoding="utf-8"
) as f:
    operation = json.load(f)

# -------------------------------------------------
# CASE DATA
# -------------------------------------------------

classifications = [
    "Biosecurity Infrastructure Investigation",
    "Biomedical Network Exposure",
    "Research Facility Intrusion",
    "Digital Pathogen Intelligence Review",
    "Counter-Bioterror Intelligence Case",
    "Laboratory Security Breach",
    "Medical Device Security Assessment",
    "Evidence Reconstruction Investigation",
    "Unauthorized Research System Access",
    "Biological Intelligence Collection"
]

threat_families = [
    "Synthetic Genome Theft",
    "Digital Pathogen Deployment",
    "Biological Data Exfiltration",
    "Laboratory Credential Abuse",
    "Research Network Persistence",
    "Biocontainment Sabotage",
    "Specimen Tracking Manipulation",
    "Insider Laboratory Compromise",
    "Unauthorized Genome Modification",
    "Biomedical Infrastructure Reconnaissance"
]

platforms = [
    "Federal Investigation Network",
    "Research Network",
    "Biomedical Analysis Cluster",
    "Genome Sequencing Environment",
    "Laboratory Control Network",
    "Biosecurity Operations Center",
    "Clinical Research Environment",
    "Evidence Processing Network"
]

device_families = [
    "Laboratory Controller",
    "Genome Sequencing Server",
    "Biomedical Workstation",
    "Evidence Repository",
    "Specimen Tracking Server",
    "Research Database",
    "Access Control System",
    "Digital Evidence Appliance"
]

vendors = [
    "Cisco",
    "Dell",
    "Microsoft",
    "VMware",
    "Fortinet",
    "Palo Alto Networks",
    "Red Hat",
    "Lenovo"
]

zones = [
    "Biosecurity Segment",
    "Evidence Network",
    "Research Operations",
    "Federal Operations",
    "Secure Laboratory",
    "Containment Network"
]

access_vectors = [
    "Credential Abuse",
    "Remote Access",
    "Supply Chain",
    "Compromised VPN",
    "Phishing",
    "Unknown"
]

analysts = [
    "Analyst Team Alpha",
    "Analyst Team Bravo",
    "Analyst Team Delta",
    "BioDefense Task Force",
    "National Response Cell",
    "Joint Cyber Investigation Unit"
]

assessments = [
    "Investigators identified coordinated cyber activity targeting protected biomedical infrastructure.",
    "Evidence indicates an organized campaign attempting unauthorized access to sensitive laboratory systems.",
    "Collected artifacts support continued investigation into cyber-enabled bioterror activities.",
    "Current intelligence suggests multiple related intrusions requiring expanded forensic acquisition.",
    "Analysts continue correlating evidence to determine campaign scope and operational objectives.",
    "Protected biomedical infrastructure remains under elevated monitoring while investigators collect additional evidence."
]

# -------------------------------------------------
# DERIVED VALUES
# -------------------------------------------------

severity = random.choices(
    ["LOW", "MODERATE", "HIGH", "CRITICAL"],
    weights=[20, 35, 30, 15],
    k=1
)[0]

status = random.choice([
    "Open",
    "Evidence Collection",
    "Intelligence Analysis",
    "Field Coordination",
    "Containment",
    "Monitoring"
])

if severity == "LOW":
    risk_score = random.randint(30, 49)
elif severity == "MODERATE":
    risk_score = random.randint(50, 69)
elif severity == "HIGH":
    risk_score = random.randint(70, 89)
else:
    risk_score = random.randint(90, 100)

# -------------------------------------------------
# BUILD CASE
# -------------------------------------------------

case = {

    "case_id": f"BID-{date.today().year}-{random.randint(1000,9999)}",

    "campaign_id": operation["campaign_id"],

    "date": today,

    "operation": operation["operation"],

    "classification": random.choice(classifications),

    "threat_family": random.choice(threat_families),

    "severity": severity,

    "status": status,

    "containment_phase": operation["campaign_phase"],

    "affected_platform": random.choice(platforms),

    "device_family": random.choice(device_families),

    "vendor": random.choice(vendors),

    "network_zone": random.choice(zones),

    "firmware_version": f"{random.randint(1,5)}.{random.randint(0,9)}.{random.randint(0,9)}",

    "confidence": random.randint(84, 99),

    "risk_score": risk_score,

    "affected_assets": random.randint(6, 40),

    "evidence_count": random.randint(20, operation["evidence_collected"]),

    "ioc_count": random.randint(8, operation["ioc_count"]),

    "initial_access": random.choice(access_vectors),

    "lead_analyst": random.choice(analysts),

    "priority": operation["containment_level"],

    "recommended_action": operation["next_objective"],

    "assessment": random.choice(assessments)
}

# -------------------------------------------------
# SAVE
# -------------------------------------------------

with open(
    "data/current_case.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(case, f, indent=4)

print(f"Generated investigation {case['case_id']}")
