from pathlib import Path
from collections import Counter
import json

README_FILE = Path("README.md")
CURRENT_CASE_FILE = Path("data/current_case.json")
EVIDENCE_ROOT = Path("evidence")


def load_json_file(file_path):
    """
    Load and return JSON data from a file.
    """

    if not file_path.exists():
        raise FileNotFoundError(
            f"Required file not found: {file_path}"
        )

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_current_case():
    """
    Load the active investigation.
    """

    return load_json_file(CURRENT_CASE_FILE)


def load_evidence_manifest(case_id):
    """
    Load the evidence manifest for the active investigation.
    """

    manifest_path = (
        EVIDENCE_ROOT
        / case_id
        / "evidence_manifest.json"
    )

    return load_json_file(manifest_path)


def load_evidence_correlations(case_id):
    """
    Load the evidence correlations for the active investigation.
    """

    correlations_path = (
        EVIDENCE_ROOT
        / case_id
        / "evidence_correlations.json"
    )

    return load_json_file(correlations_path)


def build_dashboard(case, manifest, correlations):
    """
    Build the Markdown evidence dashboard.
    """

    case_id = case.get(
        "case_id",
        "Unknown Case",
    )

    evidence_items = manifest.get(
        "evidence_items",
        []
    )

    correlation_items = correlations.get(
        "correlations",
        []
    )

    evidence_type_counts = Counter(
        item.get(
            "artifact_type",
            "Unknown Evidence Type",
        )
        for item in evidence_items
    )

    finding_counts = Counter(
        item.get(
            "finding",
            "Unknown Finding",
        )
        for item in correlation_items
    )

    integrity_counts = Counter(
        item.get(
            "integrity_status",
            "Unknown",
        )
        for item in evidence_items
    )

    review_counts = Counter(
        item.get(
            "review_status",
            "Unknown",
        )
        for item in evidence_items
    )

    evidence_total = len(evidence_items)
    correlation_total = len(correlation_items)

    verified_total = integrity_counts.get(
        "Verified",
        0,
    )

    pending_review_total = review_counts.get(
        "Pending Analyst Review",
        0,
    )

    generated_at = manifest.get(
        "generated_at",
        "Unknown",
    )

    evidence_directory = (
        EVIDENCE_ROOT
        / case_id
    )

    manifest_link = (
        evidence_directory
        / "evidence_manifest.json"
    ).as_posix()

    correlations_link = (
        evidence_directory
        / "evidence_correlations.json"
    ).as_posix()

    custody_link = (
        evidence_directory
        / "chain_of_custody.csv"
    ).as_posix()

    dashboard_lines = [
        "## Latest Digital Evidence Summary",
        "",
        f"**Active Case:** `{case_id}`",
        "",
        "| Evidence Metric | Value |",
        "|---|---:|",
        f"| Evidence Records | {evidence_total:,} |",
        f"| Correlated Records | {correlation_total:,} |",
        f"| Integrity Verified | {verified_total:,} |",
        f"| Pending Analyst Review | {pending_review_total:,} |",
        "",
        "### Evidence Breakdown",
        "",
        "| Evidence Type | Records |",
        "|---|---:|",
    ]

    for evidence_type, count in evidence_type_counts.most_common():
        dashboard_lines.append(
            f"| {evidence_type} | {count:,} |"
        )

    dashboard_lines.extend(
        [
            "",
            "### Priority Findings",
            "",
            "| Investigative Finding | Correlations |",
            "|---|---:|",
        ]
    )

    for finding, count in finding_counts.most_common():
        dashboard_lines.append(
            f"| {finding} | {count:,} |"
        )

    dashboard_lines.extend(
        [
            "",
            "### Evidence Files",
            "",
            f"- [Evidence Manifest]({manifest_link})",
            f"- [Evidence Correlations]({correlations_link})",
            f"- [Chain of Custody]({custody_link})",
            "",
            f"**Evidence Repository Updated:** `{generated_at}`",
        ]
    )

    return "\n".join(dashboard_lines)


def update_readme(dashboard):
    """
    Replace the evidence dashboard section in README.md.
    """

    start_marker = "<!-- EVIDENCE_DASHBOARD_START -->"
    end_marker = "<!-- EVIDENCE_DASHBOARD_END -->"

    if not README_FILE.exists():
        raise FileNotFoundError(
            f"README file not found: {README_FILE}"
        )

    readme_content = README_FILE.read_text(
        encoding="utf-8"
    )

    if start_marker not in readme_content:
        raise ValueError(
            f"Missing README marker: {start_marker}"
        )

    if end_marker not in readme_content:
        raise ValueError(
            f"Missing README marker: {end_marker}"
        )

    start_index = readme_content.index(start_marker)
    end_index = readme_content.index(end_marker)

    if end_index < start_index:
        raise ValueError(
            "Evidence dashboard markers are in the wrong order."
        )

    replacement = (
        f"{start_marker}\n\n"
        f"{dashboard}\n\n"
        f"{end_marker}"
    )

    updated_content = (
        readme_content[:start_index]
        + replacement
        + readme_content[
            end_index + len(end_marker):
        ]
    )

    README_FILE.write_text(
        updated_content,
        encoding="utf-8",
    )


def main():
    case = load_current_case()

    manifest = load_evidence_manifest(
        case["case_id"]
    )

    correlations = load_evidence_correlations(
        case["case_id"]
    )

    dashboard = build_dashboard(
        case,
        manifest,
        correlations,
    )

    update_readme(dashboard)

    print("Evidence dashboard updated.")


if __name__ == "__main__":
    main()
