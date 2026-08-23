#!/usr/bin/env python3

"""
generate_case.py

Generate one fictional cyber-biothreat investigation record for the
active BioDefense Intelligence Division campaign.

The campaign title is intentionally restrained and descriptive rather
than cinematic. Downstream scripts continue to use the existing JSON
key named "operation" for compatibility.
"""

import csv
import json
import random
from datetime import date
from pathlib import Path

from case_lifecycle import ensure_active_case

CURRENT_CASE_FILE = Path("data/current_case.json")
HISTORY_FILE = Path("data/investigation_history.csv")
OPERATION_FILE = Path("operations/active_operation.json")
ARCHIVE_JSON_DIR = Path("cases/archive/json")

TODAY = date.today().isoformat()

CAMPAIGN_TITLE = "Coordinated Biomedical Systems Intrusion"

CLASSIFICATIONS = [
    "Biomedical Infrastructure Investigation",
    "Biological Research Intelligence Collection",
    "Biocontainment Network Investigation",
    "Cyber-Biothreat Intelligence Review",
    "Digital Evidence Reconstruction Investigation",
    "Laboratory Access Control Investigation",
    "Laboratory Security Breach Investigation",
    "Medical Device Security Assessment",
    "Protected Research Systems Investigation",
    "Research Data Integrity Investigation",
    "Research Facility Intrusion Investigation",
    "Specimen Management Security Review",
    "Supply Chain Security Investigation",
    "Unauthorized Research System Access",
]

THREAT_FAMILIES = [
    "Access Control Record Manipulation",
    "Biomedical Supply Chain Compromise",
    "Biocontainment System Tampering",
    "Clinical Research Data Manipulation",
    "Credential Misuse",
    "Evidence Repository Manipulation",
    "Laboratory Information System Compromise",
    "Medical Device Communications Interference",
    "Protected Research Data Exfiltration",
    "Research Data Integrity Manipulation",
    "Research Workstation Compromise",
    "Specimen Tracking Manipulation",
    "Unauthorized Laboratory Network Access",
]

PLATFORMS = [
    "Biosecurity Operations Center",
    "Biomedical Analysis Cluster",
    "Clinical Research Environment",
    "Evidence Processing Network",
    "Federal Investigation Network",
    "Genome Sequencing Environment",
    "Laboratory Control Network",
    "Medical Research Laboratory",
    "Protected Research Network",
    "Research Data Repository",
]

DEVICE_FAMILIES = [
    "Access Control Server",
    "Biomedical Workstation",
    "Clinical Data Server",
    "Evidence Repository",
    "Genome Analysis Workstation",
    "Laboratory Information Server",
    "Medical Device Gateway",
    "Network Security Appliance",
    "Research Database Server",
    "Specimen Tracking Terminal",
]

VENDORS = [
    "Cisco",
    "Dell",
    "Fortinet",
    "HPE",
    "Lenovo",
    "Microsoft",
    "Palo Alto Networks",
    "Red Hat",
    "VMware",
]

ZONES = [
    "Biosecurity Segment",
    "Containment Network",
    "Evidence Network",
    "Federal Operations",
    "Protected Research Segment",
    "Research Operations",
    "Secure Laboratory",
]

ACCESS_VECTORS = [
    "Compromised Credentials",
    "Exposed Remote Service",
    "Insider Misuse",
    "Phishing",
    "Supply Chain Compromise",
    "Third-Party Access",
    "Unauthorized Physical Access",
    "Web Application Exploitation",
]

ANALYSTS = [
    "Analyst Team Alpha",
    "Analyst Team Bravo",
    "Analyst Team Delta",
    "BioDefense Task Force",
    "Joint Cyber Investigation Unit",
    "National Response Cell",
]

ASSESSMENTS = [
    (
        "Collected artifacts support continued investigation into "
        "cyber-enabled activity affecting protected biomedical systems."
    ),
    (
        "Evidence indicates unauthorized access requiring additional "
        "forensic review and coordinated containment validation."
    ),
    (
        "Correlated records suggest a multi-stage intrusion affecting "
        "research, evidence, or laboratory support infrastructure."
    ),
    (
        "Observed activity presents a credible risk to data integrity, "
        "case evidence, or protected research operations."
    ),
    (
        "Available evidence supports expanded review of access records, "
        "system changes, and related investigative indicators."
    ),
]

SEVERITY_PROFILES = {
    "LOW": {
        "priority": "ROUTINE",
        "confidence": (80, 90),
        "risk_score": (20, 39),
        "affected_assets": (2, 10),
        "evidence_count": (12, 55),
        "ioc_count": (3, 18),
    },
    "MODERATE": {
        "priority": "ELEVATED",
        "confidence": (82, 96),
        "risk_score": (40, 64),
        "affected_assets": (5, 20),
        "evidence_count": (35, 120),
        "ioc_count": (10, 45),
    },
    "HIGH": {
        "priority": "HIGH",
        "confidence": (86, 98),
        "risk_score": (65, 84),
        "affected_assets": (10, 40),
        "evidence_count": (80, 250),
        "ioc_count": (25, 100),
    },
    "CRITICAL": {
        "priority": "CRITICAL",
        "confidence": (90, 99),
        "risk_score": (85, 99),
        "affected_assets": (20, 60),
        "evidence_count": (180, 450),
        "ioc_count": (60, 180),
    },
}


def load_json(path: Path) -> dict:
    """Load a JSON object and fail clearly when it is unavailable."""

    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")

    return data


def random_from_range(bounds: tuple[int, int]) -> int:
    """Return a random integer from an inclusive two-value range."""

    minimum, maximum = bounds
    return random.randint(minimum, maximum)


def existing_case_ids() -> set[str]:
    """Collect known case identifiers to avoid accidental collisions."""

    identifiers: set[str] = set()

    if CURRENT_CASE_FILE.exists():
        try:
            with CURRENT_CASE_FILE.open(
                "r",
                encoding="utf-8",
            ) as file:
                current = json.load(file)

            if isinstance(current, dict) and current.get("case_id"):
                identifiers.add(str(current["case_id"]))

        except (json.JSONDecodeError, OSError):
            pass

    if HISTORY_FILE.exists():
        try:
            with HISTORY_FILE.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as file:
                for row in csv.DictReader(file):
                    if row.get("case_id"):
                        identifiers.add(str(row["case_id"]))

        except OSError:
            pass

    if ARCHIVE_JSON_DIR.exists():
        for archive in ARCHIVE_JSON_DIR.glob("*.json"):
            try:
                with archive.open("r", encoding="utf-8") as file:
                    archived_case = json.load(file)
                if isinstance(archived_case, dict) and archived_case.get("case_id"):
                    identifiers.add(str(archived_case["case_id"]))
            except (json.JSONDecodeError, OSError):
                continue

    return identifiers


def create_case_id() -> str:
    """Create a unique investigation identifier for the current year."""

    known_ids = existing_case_ids()

    for _ in range(100):
        candidate = (
            f"BID-{date.today().year}-"
            f"{random.randint(1000, 9999)}"
        )

        if candidate not in known_ids:
            return candidate

    raise RuntimeError(
        "Unable to create a unique case identifier after 100 attempts."
    )


def build_new_case(operation: dict) -> dict:
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

    return {
        "case_id": create_case_id(),
        "campaign_id": operation.get(
            "campaign_id",
            "BDC-UNKNOWN",
        ),
        "date": TODAY,
        "operation": CAMPAIGN_TITLE,
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
        "confidence": random_from_range(
            profile["confidence"]
        ),
        "risk_score": random_from_range(
            profile["risk_score"]
        ),
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
            (
                "Continue evidence acquisition and "
                "investigative review."
            ),
        ),
        "assessment": random.choice(ASSESSMENTS),
    }


def main() -> None:
    operation = load_json(OPERATION_FILE)
    result = ensure_active_case(lambda: build_new_case(operation))
    case = result.case

    if result.created:
        print(
            f"Created persistent investigation {case['case_id']}: "
            f"{case['severity']}, "
            f"{case['evidence_count']} evidence items, "
            f"{case['ioc_count']} indicators."
        )
    else:
        print(
            f"Reused persistent investigation {case['case_id']}: "
            f"stage={case['current_stage']}, "
            f"lifecycle={case['lifecycle_status']}."
        )
    print(f"Lifecycle decision: {result.reason}")
    print(f"Campaign: {CAMPAIGN_TITLE}")


if __name__ == "__main__":
    main()
