import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from case_state import atomic_write_json

CURRENT_CASE_FILE = Path("data/current_case.json")
EVIDENCE_ROOT = Path("evidence")

ARTIFACT_PATHS = {
    "Firewall Log": "artifacts/firewall_log.json",
    "Access Control Log": "artifacts/access_control_log.json",
    "Laboratory System Configuration": "artifacts/device_configuration.json",
    # Read-only compatibility alias for historical records.
    "Biomedical Device Configuration": "artifacts/device_configuration.json",
}


def timestamp():
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_current_case():
    with CURRENT_CASE_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def deterministic_correlation(case_id, evidence_id):
    digest = hashlib.sha256(
        f"{case_id}|{evidence_id}|correlation-v2".encode("utf-8")
    ).hexdigest()
    numeric = int(digest[:12], 16)
    return {
        "related_indicator": f"IOC-{case_id.split('-')[1]}-{1000 + numeric % 9000}",
        "confidence": 80 + (numeric >> 8) % 20,
    }


def artifact_path_for_item(item):
    explicit_path = item.get("artifact_path")
    if isinstance(explicit_path, str) and explicit_path.startswith("artifacts/"):
        return explicit_path
    return ARTIFACT_PATHS.get(
        item.get("artifact_type"),
        "artifacts/analyst_notes.md",
    )


def load_valid_existing_correlations(case_id, path, evidence_ids):
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"Existing correlation file is malformed and was not overwritten: {path}"
        ) from error
    correlations = payload.get("correlations")
    if payload.get("case_id") != case_id or not isinstance(correlations, list):
        raise ValueError(
            "Existing correlations do not match the active case and were not overwritten."
        )
    if payload.get("correlation_count") != len(correlations):
        raise ValueError(
            "Existing correlation count is inconsistent and was not overwritten."
        )
    correlation_ids = [
        item.get("evidence_id") for item in correlations if isinstance(item, dict)
    ]
    if (
        len(correlation_ids) != len(correlations)
        or any(item.get("case_id") != case_id for item in correlations)
        or any(not isinstance(evidence_id, str) for evidence_id in correlation_ids)
        or len(set(correlation_ids)) != len(correlation_ids)
        or set(correlation_ids) != evidence_ids
    ):
        raise ValueError(
            "Existing correlations do not cover the active evidence manifest "
            "and were not overwritten."
        )
    return payload


def main():
    case = load_current_case()

    case_id = case["case_id"]

    case_directory = EVIDENCE_ROOT / case_id

    manifest_path = case_directory / "evidence_manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Evidence manifest not found: {manifest_path}"
        )

    with manifest_path.open("r", encoding="utf-8") as file:
        manifest = json.load(file)

    if manifest.get("case_id") != case_id:
        raise ValueError("Evidence manifest belongs to a different case.")
    if not isinstance(manifest.get("evidence_items"), list):
        raise ValueError("Evidence manifest evidence_items must be a list.")
    evidence_ids = {
        item.get("evidence_id")
        for item in manifest["evidence_items"]
        if isinstance(item, dict)
        and item.get("case_id") == case_id
        and item.get("evidence_id")
    }
    if len(evidence_ids) != len(manifest["evidence_items"]):
        raise ValueError("Evidence manifest has invalid or duplicate evidence IDs.")

    output_path = case_directory / "evidence_correlations.json"
    existing = load_valid_existing_correlations(case_id, output_path, evidence_ids)
    if existing is not None:
        print(
            f"Preserved {existing['correlation_count']} existing evidence correlations "
            f"for {case_id}"
        )
        return

    correlations = []

    finding_map = {
        "Access Control Log": "Unauthorized Facility Access",
        "Authentication Log": "Credential Misuse",
        "Firewall Log": "Suspicious Network Activity",
        "Research Workstation Event Log": "Research Workstation Compromise",
        "Laboratory System Configuration": "Laboratory System Modification",
        "Biomedical Device Configuration": "Laboratory System Modification",
        "Research Data Integrity Record": "Research Data Integrity Anomaly",
        "Laboratory Information System Audit Log": "Laboratory Information System Anomaly",
        "Network Connection Record": "Command-and-Control Communication",
        "Threat Intelligence Record": "Known Threat Actor Indicator",
        "Biosecurity Audit Record": "Biosecurity Policy Violation",
        "Analyst Observation": "Analyst Intelligence Assessment",
        "Containment Validation Record": "Containment Verification",
}

    for item in manifest["evidence_items"]:

        evidence_id = item["evidence_id"]

        artifact_type = item["artifact_type"]

        artifact_file = artifact_path_for_item(item)
        deterministic = deterministic_correlation(case_id, evidence_id)

        correlations.append(
            {
                "case_id": case_id,
                "evidence_id": evidence_id,
                "artifact_type": artifact_type,
                "artifact_path": artifact_file,
                "related_indicator": deterministic["related_indicator"],
                "finding": finding_map.get(artifact_type,"General Investigative Finding"),
                "confidence": deterministic["confidence"],
                "analysis_status": "Correlated",
            }
        )

    output = {
        "schema_version": 2,
        "case_id": case_id,
        "generated_at": timestamp(),
        "correlation_count": len(correlations),
        "correlations": correlations,
    }

    atomic_write_json(output_path, output)

    print(
        f"Generated {len(correlations)} evidence correlations for {case_id}"
    )


if __name__ == "__main__":
    main()
