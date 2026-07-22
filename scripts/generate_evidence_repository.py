import csv
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------
# File locations
# ---------------------------------------------------------

CURRENT_CASE_FILE = Path("data/current_case.json")
EVIDENCE_ROOT = Path("evidence")


# ---------------------------------------------------------
# Evidence categories
# ---------------------------------------------------------

EVIDENCE_TYPES = [
    "Access Control Log",
    "Authentication Log",
    "Firewall Log",
    "Endpoint Event Log",
    "Biomedical Device Configuration",
    "Firmware Metadata",
    "Embedded Controller Log",
    "Network Connection Record",
    "Threat Indicator Record",
    "Laboratory Audit Record",
    "Analyst Observation",
    "Containment Validation Record",
]


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def load_current_case():
    """
    Load the current investigation from data/current_case.json.
    """

    if not CURRENT_CASE_FILE.exists():
        raise FileNotFoundError(
            f"Could not find current case file: {CURRENT_CASE_FILE}"
        )

    with CURRENT_CASE_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_case_value(case, *possible_names, default="Unknown"):
    """
    Safely retrieve a value even if the JSON field uses a slightly
    different name.
    """

    for name in possible_names:
        if name in case and case[name] not in (None, ""):
            return case[name]

    return default


def create_simulated_hash(case_id, evidence_id, artifact_type):
    """
    Create a repeatable simulated SHA-256 integrity hash.
    """

    hash_input = f"{case_id}|{evidence_id}|{artifact_type}"

    return hashlib.sha256(
        hash_input.encode("utf-8")
    ).hexdigest()


def current_utc_timestamp():
    """
    Return the current UTC time in ISO 8601 format.
    """

    return datetime.now(timezone.utc).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------
# Evidence manifest
# ---------------------------------------------------------

def generate_evidence_items(case):
    """
    Generate structured evidence records matching the evidence_count
    stored in the current case.
    """

    case_id = get_case_value(case, "case_id", default="UNKNOWN-CASE")

    evidence_count = int(
        get_case_value(
            case,
            "evidence_count",
            "evidence",
            default=0,
        )
    )

    classification = get_case_value(
        case,
        "classification",
        default="Unclassified Investigation",
    )

    device = get_case_value(
        case,
        "device",
        "affected_device",
        default="Unknown Device",
    )

    platform = get_case_value(
        case,
        "platform",
        default="Unknown Platform",
    )

    vendor = get_case_value(
        case,
        "vendor",
        default="Unknown Vendor",
    )

    zone = get_case_value(
        case,
        "zone",
        "security_zone",
        default="Unknown Zone",
    )

    lead_analyst = get_case_value(
        case,
        "lead_analyst",
        "analyst",
        default="BioDefense Analyst Team",
    )

    collected_at = current_utc_timestamp()

    evidence_items = []

    for number in range(1, evidence_count + 1):
        evidence_id = f"{case_id}-EV-{number:04d}"
        artifact_type = random.choice(EVIDENCE_TYPES)

        evidence_item = {
            "evidence_id": evidence_id,
            "case_id": case_id,
            "artifact_type": artifact_type,
            "source_system": device,
            "platform": platform,
            "vendor": vendor,
            "zone": zone,
            "collected_by": lead_analyst,
            "collected_at": collected_at,
            "integrity_status": "Verified",
            "sha256": create_simulated_hash(
                case_id,
                evidence_id,
                artifact_type,
            ),
            "classification": classification,
            "review_status": "Pending Analyst Review",
        }

        evidence_items.append(evidence_item)

    return evidence_items


def write_evidence_manifest(case, evidence_items, case_directory):
    """
    Write all evidence records into evidence_manifest.json.
    """

    case_id = get_case_value(case, "case_id", default="UNKNOWN-CASE")

    manifest = {
        "case_id": case_id,
        "generated_at": current_utc_timestamp(),
        "evidence_count": len(evidence_items),
        "evidence_items": evidence_items,
    }

    manifest_path = case_directory / "evidence_manifest.json"

    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=4)


# ---------------------------------------------------------
# Chain of custody
# ---------------------------------------------------------

def write_chain_of_custody(case, evidence_items, case_directory):
    """
    Create the initial chain-of-custody record for every evidence item.
    """

    case_id = get_case_value(case, "case_id", default="UNKNOWN-CASE")

    lead_analyst = get_case_value(
        case,
        "lead_analyst",
        "analyst",
        default="BioDefense Analyst Team",
    )

    custody_path = case_directory / "chain_of_custody.csv"

    fieldnames = [
        "evidence_id",
        "case_id",
        "event_type",
        "performed_by",
        "timestamp",
        "storage_location",
        "integrity_status",
    ]

    with custody_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for evidence_item in evidence_items:
            writer.writerow(
                {
                    "evidence_id": evidence_item["evidence_id"],
                    "case_id": case_id,
                    "event_type": "Collected",
                    "performed_by": lead_analyst,
                    "timestamp": evidence_item["collected_at"],
                    "storage_location": str(case_directory),
                    "integrity_status": "Verified",
                }
            )


# ---------------------------------------------------------
# Acquisition summary
# ---------------------------------------------------------

def write_acquisition_summary(case, evidence_items, case_directory):
    """
    Create a readable Markdown summary of the evidence acquisition.
    """

    case_id = get_case_value(case, "case_id", default="UNKNOWN-CASE")

    classification = get_case_value(
        case,
        "classification",
        default="Unknown",
    )

    severity = get_case_value(
        case,
        "severity",
        default="Unknown",
    )

    lead_analyst = get_case_value(
        case,
        "lead_analyst",
        "analyst",
        default="BioDefense Analyst Team",
    )

    platform = get_case_value(
        case,
        "platform",
        default="Unknown Platform",
    )

    vendor = get_case_value(
        case,
        "vendor",
        default="Unknown Vendor",
    )

    device = get_case_value(
        case,
        "device",
        "affected_device",
        default="Unknown Device",
    )

    zone = get_case_value(
        case,
        "zone",
        "security_zone",
        default="Unknown Zone",
    )

    summary = f"""# Digital Evidence Acquisition Summary

## Case Information

- Case ID: {case_id}
- Classification: {classification}
- Severity: {severity}
- Lead Analyst: {lead_analyst}
- Evidence Records: {len(evidence_items)}

## Affected Environment

- Platform: {platform}
- Vendor: {vendor}
- Device: {device}
- Zone: {zone}

## Acquisition Status

Evidence records were generated for a simulated defensive cyber-biothreat
investigation, forensic documentation, integrity validation, and analyst review.

## Integrity

All generated evidence records include simulated SHA-256 integrity values.

## Notice

This repository contains simulated evidence created for defensive cybersecurity,
digital forensics, biosecurity research, and portfolio demonstration purposes.
"""

    summary_path = case_directory / "acquisition_summary.md"

    with summary_path.open("w", encoding="utf-8") as file:
        file.write(summary)


# ---------------------------------------------------------
# Representative artifact files
# ---------------------------------------------------------

def write_firewall_log(case, artifacts_directory):
    case_id = get_case_value(case, "case_id", default="UNKNOWN-CASE")
    device = get_case_value(case, "device", default="Unknown Device")
    zone = get_case_value(case, "zone", default="Unknown Zone")

    firewall_data = {
        "case_id": case_id,
        "artifact_type": "Firewall Log",
        "generated_at": current_utc_timestamp(),
        "source_device": device,
        "security_zone": zone,
        "events": [
            {
                "event_id": "FW-001",
                "action": "Blocked",
                "protocol": "HTTPS",
                "source": "Simulated External Host",
                "destination": device,
                "description": (
                    "Simulated unauthorized outbound connection attempt."
                ),
            },
            {
                "event_id": "FW-002",
                "action": "Allowed",
                "protocol": "DNS",
                "source": device,
                "destination": "Authorized DNS Service",
                "description": (
                    "Routine name-resolution activity retained for analysis."
                ),
            },
        ],
    }

    path = artifacts_directory / "firewall_log.json"

    with path.open("w", encoding="utf-8") as file:
        json.dump(firewall_data, file, indent=4)


def write_access_control_log(case, artifacts_directory):
    case_id = get_case_value(case, "case_id", default="UNKNOWN-CASE")
    zone = get_case_value(case, "zone", default="Unknown Zone")

    access_data = {
        "case_id": case_id,
        "artifact_type": "Access Control Log",
        "generated_at": current_utc_timestamp(),
        "security_zone": zone,
        "events": [
            {
                "event_id": "AC-001",
                "result": "Denied",
                "credential": "Simulated Credential 104",
                "location": zone,
                "description": (
                    "Access attempt occurred outside the approved schedule."
                ),
            },
            {
                "event_id": "AC-002",
                "result": "Granted",
                "credential": "Authorized Laboratory Personnel",
                "location": zone,
                "description": (
                    "Authorized access event retained for timeline comparison."
                ),
            },
        ],
    }

    path = artifacts_directory / "access_control_log.json"

    with path.open("w", encoding="utf-8") as file:
        json.dump(access_data, file, indent=4)


def write_device_configuration(case, artifacts_directory):
    case_id = get_case_value(case, "case_id", default="UNKNOWN-CASE")

    configuration_data = {
        "case_id": case_id,
        "artifact_type": "Device Configuration Snapshot",
        "generated_at": current_utc_timestamp(),
        "platform": get_case_value(
            case,
            "platform",
            default="Unknown Platform",
        ),
        "vendor": get_case_value(
            case,
            "vendor",
            default="Unknown Vendor",
        ),
        "device": get_case_value(
            case,
            "device",
            default="Unknown Device",
        ),
        "firmware_version": get_case_value(
            case,
            "firmware_version",
            "firmware",
            default="Not Applicable",
        ),
        "zone": get_case_value(
            case,
            "zone",
            default="Unknown Zone",
        ),
        "security_state": "Under Investigation",
        "configuration_integrity": "Pending Analyst Validation",
    }

    path = artifacts_directory / "device_configuration.json"

    with path.open("w", encoding="utf-8") as file:
        json.dump(configuration_data, file, indent=4)


def write_analyst_notes(case, artifacts_directory):
    case_id = get_case_value(case, "case_id", default="UNKNOWN-CASE")

    classification = get_case_value(
        case,
        "classification",
        default="Unclassified Investigation",
    )

    severity = get_case_value(
        case,
        "severity",
        default="Unknown",
    )

    device = get_case_value(
        case,
        "device",
        default="Unknown Device",
    )

    notes = f"""# Analyst Notes

## Investigation

- Case ID: {case_id}
- Classification: {classification}
- Severity: {severity}
- Affected Device: {device}

## Initial Assessment

The available simulated evidence indicates activity requiring defensive
forensic review, integrity validation, and correlation with the active
cyber-biothreat campaign.

## Analyst Priorities

1. Validate evidence integrity.
2. Review access-control and firewall activity.
3. Compare device configuration data with the approved baseline.
4. Correlate indicators with related investigations.
5. Document containment and recovery recommendations.

## Scope Notice

These notes describe a fictional but professionally structured defensive
cybersecurity simulation. They are not operational instructions.
"""

    path = artifacts_directory / "analyst_notes.md"

    with path.open("w", encoding="utf-8") as file:
        file.write(notes)


# ---------------------------------------------------------
# Main program
# ---------------------------------------------------------

def main():
    case = load_current_case()

    case_id = get_case_value(
        case,
        "case_id",
        default="UNKNOWN-CASE",
    )

    case_directory = EVIDENCE_ROOT / case_id
    artifacts_directory = case_directory / "artifacts"

    case_directory.mkdir(parents=True, exist_ok=True)
    artifacts_directory.mkdir(parents=True, exist_ok=True)

    evidence_items = generate_evidence_items(case)

    write_evidence_manifest(
        case,
        evidence_items,
        case_directory,
    )

    write_chain_of_custody(
        case,
        evidence_items,
        case_directory,
    )

    write_acquisition_summary(
        case,
        evidence_items,
        case_directory,
    )

    write_firewall_log(
        case,
        artifacts_directory,
    )

    write_access_control_log(
        case,
        artifacts_directory,
    )

    write_device_configuration(
        case,
        artifacts_directory,
    )

    write_analyst_notes(
        case,
        artifacts_directory,
    )

    print(
        f"Evidence repository generated for {case_id}: "
        f"{len(evidence_items)} evidence records."
    )


if __name__ == "__main__":
    main()
