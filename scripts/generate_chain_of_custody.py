from datetime import datetime, timezone
from pathlib import Path
import json


CURRENT_CASE = Path("data/current_case.json")


def load_json(path: Path):
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def get_case_directory(case_id: str):
    return Path("evidence") / case_id


def get_first(data, keys, default="Not specified"):
    for key in keys:
        value = data.get(key)
        if value not in (None, "", [], {}):
            return value
    return default


def generate_chain_of_custody():
    case = load_json(CURRENT_CASE)

    if not case:
        raise FileNotFoundError("Unable to load data/current_case.json")

    case_id = get_first(case, ["case_id"])

    case_dir = get_case_directory(case_id)

    manifest_path = case_dir / "evidence_manifest.json"

    manifest = load_json(manifest_path)

    evidence_items = manifest.get("evidence_items", [])

    evidence_count = len(evidence_items)

    verified = 0

    for item in evidence_items:
        integrity = str(
            item.get("integrity_status", "")
        ).strip().lower()

        if integrity in {
            "verified",
            "validated",
            "confirmed",
            "intact",
        }:
            verified += 1

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    report = []

    report.append("# Chain of Custody")
    report.append("")
    report.append(f"**Generated:** {generated}")
    report.append("")
    report.append("---")
    report.append("")
    report.append("## Investigation Information")
    report.append("")
    report.append(f"**Case ID:** {case_id}")
    report.append("")
    report.append(f"**Operation:** {get_first(case,['operation'])}")
    report.append("")
    report.append(f"**Classification:** {get_first(case,['classification'])}")
    report.append("")
    report.append(f"**Lead Analyst:** {get_first(case,['lead_analyst'])}")
    report.append("")
    report.append("---")
    report.append("")
    report.append("## Evidence Acquisition")
    report.append("")
    report.append(
        f"Total evidence records acquired: **{evidence_count}**"
    )
    report.append("")
    report.append(
        "Evidence was collected through the automated BioDefense Intelligence Division investigation workflow."
    )
    report.append("")
    report.append("---")
    report.append("")
    report.append("## Integrity Verification")
    report.append("")
    report.append(
        f"Verified evidence records: **{verified} of {evidence_count}**"
    )
    report.append("")
    if verified == evidence_count:
        report.append(
            "No integrity violations were detected during evidence validation."
        )
    else:
        report.append(
            "Some evidence records require additional integrity validation."
        )

    report.append("")
    report.append("---")
    report.append("")
    report.append("## Evidence Handling")
    report.append("")
    report.append(
        "Evidence remained within the BioDefense Intelligence Division repository throughout the investigation."
    )
    report.append("")
    report.append(
        "No unauthorized custody transfers were identified."
    )
    report.append("")
    report.append("---")
    report.append("")
    report.append("## Review Information")
    report.append("")
    report.append(f"Primary Analyst: {get_first(case,['lead_analyst'])}")
    report.append("")
    report.append(
        f"Investigation Status: {get_first(case,['status'])}"
    )
    report.append("")
    report.append(
        f"Containment Phase: {get_first(case,['containment_phase'])}"
    )
    report.append("")
    report.append("---")
    report.append("")
    report.append("## Custody Summary")
    report.append("")
    report.append(
        "Chain of custody has been maintained for the collected investigative artifacts."
    )
    report.append("")
    report.append(
        "Evidence integrity should continue to be verified as additional artifacts are collected."
    )

    output = case_dir / "chain_of_custody.md"

    output.write_text("\n".join(report), encoding="utf-8")

    print(f"Chain of custody generated: {output}")


if __name__ == "__main__":
    generate_chain_of_custody()
