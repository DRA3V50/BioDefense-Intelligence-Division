import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from case_state import atomic_write_json, atomic_write_text

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
    "Research Workstation Event Log",
    "Laboratory System Configuration",
    "Research Data Integrity Record",
    "Laboratory Information System Audit Log",
    "Network Connection Record",
    "Threat Intelligence Record",
    "Biosecurity Audit Record",
    "Analyst Observation",
    "Containment Validation Record",
]

ARTIFACT_PATHS = {
    "Firewall Log": "artifacts/firewall_log.json",
    "Access Control Log": "artifacts/access_control_log.json",
    "Laboratory System Configuration": "artifacts/device_configuration.json",
    # Compatibility alias for historical evidence manifests.
    "Biomedical Device Configuration": "artifacts/device_configuration.json",
}

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
    environment = environment_values(case)
    collected_at = current_utc_timestamp()
    evidence_items = []

    for number in range(1, evidence_count + 1):
        evidence_id = f"{case_id}-EV-{number:04d}"
        artifact_type = deterministic_artifact_type(case_id, evidence_id)
        evidence_items.append(
            {
                "evidence_id": evidence_id,
                "case_id": case_id,
                "artifact_type": artifact_type,
                "artifact_path": artifact_path_for_type(artifact_type),
                "source_system": environment["device"],
                "platform": environment["platform"],
                "vendor": environment["vendor"],
                "zone": environment["zone"],
                "collected_by": environment["lead_analyst"],
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
        )

    return evidence_items


def deterministic_artifact_type(case_id, evidence_id):
    """Choose a stable simulated type once from durable case/evidence identity."""

    digest = hashlib.sha256(
        f"{case_id}|{evidence_id}|artifact-type-v2".encode("utf-8")
    ).hexdigest()
    return EVIDENCE_TYPES[int(digest[:8], 16) % len(EVIDENCE_TYPES)]


def artifact_path_for_type(artifact_type):
    return ARTIFACT_PATHS.get(artifact_type, "artifacts/analyst_notes.md")


def environment_values(case):
    """Map the production case schema without adding duplicate case fields."""

    return {
        "device": get_case_value(
            case,
            "device_family",
            "device",
            "affected_device",
            default="Unknown Device",
        ),
        "platform": get_case_value(
            case,
            "affected_platform",
            "platform",
            default="Unknown Platform",
        ),
        "vendor": get_case_value(case, "vendor", default="Unknown Vendor"),
        "zone": get_case_value(
            case,
            "network_zone",
            "zone",
            "security_zone",
            default="Unknown Zone",
        ),
        "lead_analyst": get_case_value(
            case,
            "lead_analyst",
            "analyst",
            default="BioDefense Analyst Team",
        ),
        "baseline_version": get_case_value(
            case,
            "firmware_version",
            "baseline_version",
            "configuration_baseline",
            default="Baseline Pending Review",
        ),
    }


def write_evidence_manifest(case, evidence_items, case_directory):
    """
    Write all evidence records into evidence_manifest.json.
    """

    case_id = get_case_value(case, "case_id", default="UNKNOWN-CASE")

    manifest = {
        "schema_version": 2,
        "case_id": case_id,
        "generated_at": current_utc_timestamp(),
        "evidence_count": len(evidence_items),
        "evidence_items": evidence_items,
    }

    manifest_path = case_directory / "evidence_manifest.json"

    atomic_write_json(manifest_path, manifest)


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

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
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
    atomic_write_text(custody_path, stream.getvalue())


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

    environment = environment_values(case)
    platform = environment["platform"]
    vendor = environment["vendor"]
    device = environment["device"]
    zone = environment["zone"]

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

    atomic_write_text(summary_path, summary)


# ---------------------------------------------------------
# Representative artifact files
# ---------------------------------------------------------

def write_firewall_log(case, artifacts_directory):
    case_id = get_case_value(case, "case_id", default="UNKNOWN-CASE")
    environment = environment_values(case)
    device = environment["device"]
    zone = environment["zone"]

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

    atomic_write_json(path, firewall_data)


def write_access_control_log(case, artifacts_directory):
    case_id = get_case_value(case, "case_id", default="UNKNOWN-CASE")
    zone = environment_values(case)["zone"]

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

    atomic_write_json(path, access_data)


def write_device_configuration(case, artifacts_directory):
    case_id = get_case_value(case, "case_id", default="UNKNOWN-CASE")
    environment = environment_values(case)

    configuration_data = {
        "case_id": case_id,
        "artifact_type": "Laboratory System Configuration",
        "generated_at": current_utc_timestamp(),
        "platform": get_case_value(
            case,
            "affected_platform",
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
            "device_family",
            "device",
            default="Unknown Device",
        ),
        "baseline_version": get_case_value(
            case,
            "firmware_version",
            "baseline_version",
            "configuration_baseline",
            default="Baseline Pending Review",
        ),
        "zone": get_case_value(
            case,
            "network_zone",
            "zone",
            default="Unknown Zone",
        ),
        "security_state": "Under Investigation",
        "configuration_integrity": "Pending Analyst Validation",
    }

    path = artifacts_directory / "device_configuration.json"

    atomic_write_json(path, configuration_data)


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
        "device_family",
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

    atomic_write_text(path, notes)


def _validate_existing_evidence_bundle(
    case_id: str, manifest: dict, case_directory: Path
) -> None:
    """A manifest is reusable only when its committed support bundle exists."""

    custody_path = case_directory / "chain_of_custody.csv"
    summary_path = case_directory / "acquisition_summary.md"
    if not custody_path.exists() or not summary_path.exists():
        raise ValueError(
            "Existing evidence manifest has an incomplete support bundle; "
            "it was not overwritten."
        )
    with custody_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if (
        reader.fieldnames is None
        or "case_id" not in reader.fieldnames
        or len(rows) != manifest["evidence_count"]
        or any(row.get("case_id") != case_id for row in rows)
    ):
        raise ValueError(
            "Existing chain-of-custody data does not match its evidence manifest; "
            "it was not overwritten."
        )

    for item in manifest["evidence_items"]:
        artifact_relative = item.get("artifact_path")
        if not artifact_relative:
            continue
        artifact_path = case_directory / artifact_relative
        if not artifact_path.exists():
            raise ValueError(
                "Existing evidence manifest references a missing artifact; "
                "it was not overwritten."
            )
        if artifact_path.suffix.lower() == ".json":
            try:
                with artifact_path.open("r", encoding="utf-8") as handle:
                    artifact = json.load(handle)
            except (OSError, json.JSONDecodeError) as error:
                raise ValueError(
                    "Existing evidence artifact is unreadable; it was not overwritten."
                ) from error
            if artifact.get("case_id") != case_id:
                raise ValueError(
                    "Existing evidence artifact belongs to another case; "
                    "it was not overwritten."
                )


# ---------------------------------------------------------
# Main program
# ---------------------------------------------------------

def load_valid_existing_manifest(case, manifest_path):
    """Return a matching manifest that must be preserved on repeat runs."""

    if not manifest_path.exists():
        return None
    try:
        with manifest_path.open("r", encoding="utf-8") as file:
            manifest = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Existing evidence manifest is malformed and was not overwritten: {manifest_path}"
        ) from error

    case_id = get_case_value(case, "case_id", default="UNKNOWN-CASE")
    items = manifest.get("evidence_items")
    schema_version = manifest.get("schema_version")
    if schema_version is not None and (
        not isinstance(schema_version, int) or schema_version < 1
    ):
        raise ValueError(
            "Existing evidence manifest has an invalid schema version; it was not overwritten."
        )
    if manifest.get("case_id") != case_id or not isinstance(items, list):
        raise ValueError(
            f"Existing evidence manifest does not match active case {case_id}; "
            "it was not overwritten."
        )
    if manifest.get("evidence_count") != len(items):
        raise ValueError(
            "Existing evidence manifest count is inconsistent; it was not overwritten."
        )
    if manifest["evidence_count"] != int(case.get("evidence_count", 0)):
        raise ValueError(
            "Existing evidence manifest count differs from active case evidence_count; "
            "a deliberate evidence update is required instead of regeneration."
        )
    evidence_ids = set()
    for item in items:
        if (
            not isinstance(item, dict)
            or item.get("case_id") != case_id
            or not isinstance(item.get("evidence_id"), str)
            or not item["evidence_id"]
        ):
            raise ValueError(
                "Existing evidence manifest contains invalid case linkage; "
                "it was not overwritten."
            )
        if item["evidence_id"] in evidence_ids:
            raise ValueError(
                "Existing evidence manifest has duplicate evidence IDs; "
                "it was not overwritten."
            )
        evidence_ids.add(item["evidence_id"])
        artifact_path = item.get("artifact_path")
        if artifact_path is not None and (
            not isinstance(artifact_path, str)
            or not artifact_path.startswith("artifacts/")
            or ".." in Path(artifact_path).parts
        ):
            raise ValueError(
                "Existing evidence manifest has an unsafe artifact path; "
                "it was not overwritten."
            )
    _validate_existing_evidence_bundle(case_id, manifest, manifest_path.parent)
    return manifest


def main():
    case = load_current_case()

    case_id = get_case_value(
        case,
        "case_id",
        default="UNKNOWN-CASE",
    )

    case_directory = EVIDENCE_ROOT / case_id
    artifacts_directory = case_directory / "artifacts"

    existing_manifest = load_valid_existing_manifest(
        case,
        case_directory / "evidence_manifest.json",
    )
    if existing_manifest is not None:
        print(
            f"Evidence repository preserved for {case_id}: "
            f"{existing_manifest['evidence_count']} existing evidence records."
        )
        return

    case_directory.mkdir(parents=True, exist_ok=True)
    artifacts_directory.mkdir(parents=True, exist_ok=True)

    evidence_items = generate_evidence_items(case)

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

    # The manifest is the atomic commit marker: only publish it after every
    # linked evidence file has been written successfully.
    write_evidence_manifest(
        case,
        evidence_items,
        case_directory,
    )

    print(
        f"Evidence repository generated for {case_id}: "
        f"{len(evidence_items)} evidence records."
    )


if __name__ == "__main__":
    main()
