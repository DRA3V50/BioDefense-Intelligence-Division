import json
import random
from datetime import datetime, timezone
from pathlib import Path


CURRENT_CASE_FILE = Path("data/current_case.json")
EVIDENCE_ROOT = Path("evidence")


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

    correlations = []

    finding_map = {
    "Firewall Log": "Suspicious Network Activity",
    "Access Control Log": "Unauthorized Facility Access",
    "Authentication Log": "Credential Misuse",
    "Biomedical Device Configuration": "Laboratory System Modification",
    "Embedded Controller Log": "Critical Infrastructure Anomaly",
    "Firmware Metadata": "Digital Evidence Requiring Examination",
    "Endpoint Event Log": "Endpoint Compromise",
    "Network Connection Record": "Command-and-Control Communication",
    "Threat Indicator Record": "Known Threat Actor Indicator",
    "Analyst Observation": "Analyst Intelligence Assessment",
    "Containment Validation Record": "Containment Verification",
    "Laboratory Audit Record": "Biosecurity Policy Violation",
}

    for item in manifest["evidence_items"]:

        evidence_id = item["evidence_id"]

        artifact_type = item["artifact_type"]

        if artifact_type == "Firewall Log":
            artifact_file = "artifacts/firewall_log.json"

        elif artifact_type == "Access Control Log":
            artifact_file = "artifacts/access_control_log.json"

        elif artifact_type == "Biomedical Device Configuration":
            artifact_file = "artifacts/device_configuration.json"

        else:
            artifact_file = "artifacts/analyst_notes.md"

        correlations.append(
            {
                "evidence_id": evidence_id,
                "artifact_type": artifact_type,
                "artifact_path": artifact_file,
                "related_indicator": (
                    f"IOC-2026-{random.randint(1000,9999)}"
                ),
                "finding": finding_map.get(artifact_type,"General Investigative Finding"),
                "confidence": random.randint(80, 99),
                "analysis_status": "Correlated",
            }
        )

    output = {
        "case_id": case_id,
        "generated_at": timestamp(),
        "correlation_count": len(correlations),
        "correlations": correlations,
    }

    output_path = case_directory / "evidence_correlations.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=4)

    print(
        f"Generated {len(correlations)} evidence correlations for {case_id}"
    )


if __name__ == "__main__":
    main()
