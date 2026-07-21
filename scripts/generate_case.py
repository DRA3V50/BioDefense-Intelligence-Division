#!/usr/bin/env python3

"""
Generate a new cyber-biothreat investigation.

Case-level evidence, IOC, and asset counts are generated from controlled
severity-based ranges. Campaign totals are never used as random limits.
"""

import json
import random
from datetime import date
from pathlib import Path

OPERATION_FILE = Path("operations/active_operation.json")
CURRENT_CASE_FILE = Path("data/current_case.json")

TODAY = date.today().isoformat()


# -------------------------------------------------
# Data loading
# -------------------------------------------------

def load_json(path: Path) -> dict:
    """Load and validate a JSON object."""

    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")

    return data


# -------------------------------------------------
# Investigation vocabulary
# -------------------------------------------------

CLASSIFICATIONS = [
    "Biosecurity Infrastructure Investigation",
    "Biomedical Network Exposure",
    "Research Facility Intrusion",
    "Cyber-Biothreat Intelligence Review",
    "Counter-Bioterror Intelligence Case",
    "Laboratory Security Breach",
    "Medical Device Security Assessment",
    "Evidence Reconstruction Investigation",
    "Unauthorized Research System Access",
    "Biological Research Intelligence Collection",
]

THREAT_FAMILIES = [
    "Synthetic Genome Data Theft",
    "Research Data Integrity Manipulation",
    "Biological Data Exfiltration",
    "Laboratory Credential Abuse",
    "Research Network Persistence",
    "Biocontainment System Tampering",
    "Specimen Tracking Manipulation",
    "Insider Laboratory Compromise",
    "Unauthorized Genomic Data Modification",
    "Biomedical Infrastructure Reconnaissance",
]

PLATFORMS = [
    "Federal Investigation Network",
    "Research Network",
    "Biomedical Analysis Cluster",
    "Genome Sequencing Environment",
    "Laboratory Control Network",
    "Biosecurity Operations Center",
    "Clinical Research Environment",
    "Evidence Processing Network",
]

DEVICE_FAMILIES = [
    "Laboratory Controller",
    "Genome Sequencing Server",
    "Biomedical Workstation",
    "Evidence Repository",
    "Specimen Tracking Server",
    "Research Database",
    "Access Control System",
    "Digital Evidence Appliance",
]

VENDORS = [
    "Cisco",
    "Dell",
    "Microsoft",
    "VMware",
    "Fortinet",
    "Palo Alto Networks",
    "Red Hat",
    "Lenovo",
]

ZONES = [
    "Biosecurity Segment",
    "Evidence Network",
    "Research Operations",
    "Federal Operations",
    "Secure Laboratory",
    "Containment Network",
]

ACCESS_VECTORS = [
    "Credential Abuse",
    "Unauthorized Remote Access",
    "Supply Chain Compromise",
    "Compromised VPN Account",
    "Phishing",
    "Misconfigured External Service",
    "Unknown",
]

ANALYSTS = [
    "Analyst Team Alpha",
    "Analyst Team Bravo",
    "Analyst Team Delta",
    "BioDefense Task Force",
    "National Response Cell",
    "Joint Cyber Investigation Unit",
]

ASSESSMENTS = [
    (
        "Investigators identified coordinated cyber activity targeting "
        "protected biomedical infrastructure."
    ),
    (
        "Evidence indicates an organized campaign attempting unauthorized "
        "access to sensitive laboratory systems."
    ),
    (
        "Collected artifacts support continued investigation into cyber-enabled "
        "threat activity affecting protected research environments."
    ),
    (
        "Current intelligence suggests multiple related intrusions requiring "
        "expanded forensic acquisition."
    ),
    (
        "Analysts continue correlating evidence to determine campaign scope "
        "and operational objectives."
    ),
    (
        "Protected biomedical infrastructure remains under elevated monitoring "
        "while investigators collect additional evidence."
    ),
]


# -------------------------------------------------
# Severity-based case profiles
# -------------------------------------------------

SEVERITY_PROFILES = {
    "LOW": {
        "risk_score": (30, 49),
        "affected_assets": (2, 8),
        "evidence_count": (12, 45),
        "ioc_count": (3, 15),
        "confidence": (78, 91),
        "priority": "ROUTINE",
    },
    "MODERATE": {
        "risk_score": (50, 69),
        "affected_assets": (6, 18),
        "evidence_count": (35, 100),
        "ioc_count": (10, 35),
        "confidence": (82, 94),
        "priority": "ELEVATED",
    },
    "HIGH": {
        "risk_score": (70, 89),
        "affected_assets": (12, 32),
        "evidence_count": (80, 220),
        "ioc_count": (25, 80),
        "confidence": (86, 97),
        "priority": "HIGH",
    },
    "CRITICAL": {
        "risk_score": (90, 100),
        "affected_assets": (20, 55),
        "evidence_count": (160, 420),
        "ioc_count": (60, 160),
        "confidence": (90, 99),
        "priority": "CRITICAL",
    },
}


def random_from_range(value_range: tuple[int, int]) -> int:
    """Return a random integer from an inclusive two-value range."""

    return random.randint(value_range[0], value_range[1])


def create_case_id() -> str:
    """Create an investigation identifier for the current year."""

    return f"BID-{date.today().year}-{random.randint(1000, 9999)}"


def main() -> None:
    operation = load_json(OPERATION_FILE)

    severity = random.choices(
        ["LOW", "MODERATE", "HIGH", "CRITICAL"],
        weights=[20, 35, 30, 15],
        k=1,
    )[0]

    profile = SEVERITY_PROFILES[severity]

    status = random.choice(
        [
            "Open",
            "Evidence Collection",
            "Intelligence Analysis",
            "Field Coordination",
            "Containment",
            "Monitoring",
        ]
    )

    case = {
        "case_id": create_case_id(),
        "campaign_id": operation.get("campaign_id", "BDC-UNKNOWN"),
        "date": TODAY,
        "operation": operation.get("operation", "Unknown Operation"),
        "classification": random.choice(CLASSIFICATIONS),
        "threat_family": random.choice(THREAT_FAMILIES),
        "severity": severity,
        "status": status,
        "containment_phase": operation.get(
            "campaign_phase",
            "Detection",
        ),
        "affected_platform": random.choice(PLATFORMS),
        "device_family": random.choice(DEVICE_FAMILIES),
        "vendor": random.choice(VENDORS),
        "network_zone": random.choice(ZONES),
        "firmware_version": (
            f"{random.randint(1, 5)}."
            f"{random.randint(0, 9)}."
            f"{random.randint(0, 9)}"
        ),
        "confidence": random_from_range(profile["confidence"]),
        "risk_score": random_from_range(profile["risk_score"]),
        "affected_assets": random_from_range(
            profile["affected_assets"]
        ),
        "evidence_count": random_from_range(
            profile["evidence_count"]
        ),
        "ioc_count": random_from_range(
            profile["ioc_count"]
        ),
        "initial_access": random.choice(ACCESS_VECTORS),
        "lead_analyst": random.choice(ANALYSTS),
        "priority": profile["priority"],
        "recommended_action": operation.get(
            "next_objective",
            "Continue evidence acquisition and investigative review.",
        ),
        "assessment": random.choice(ASSESSMENTS),
    }

    CURRENT_CASE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with CURRENT_CASE_FILE.open("w", encoding="utf-8") as file:
        json.dump(case, file, indent=4)

    print(
        f"Generated investigation {case['case_id']}: "
        f"{severity}, "
        f"{case['evidence_count']} evidence items, "
        f"{case['ioc_count']} indicators."
    )


if __name__ == "__main__":
    main()
