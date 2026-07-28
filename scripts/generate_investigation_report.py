from datetime import datetime, timezone
from pathlib import Path
import json


CURRENT_CASE_FILE = Path("data/current_case.json")
REPORT_OUTPUT = Path("reports/investigation_report.md")

COMMAND_BRIEF_FILE = Path("operations/command_brief.md")
TIMELINE_FILE = Path("operations/investigation_timeline.md")
EVIDENCE_CHAIN_FILE = Path("evidence/evidence_chain.md")


def load_json(path: Path, default=None):
    if default is None:
        default = {}

    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return default


def file_status(path: Path) -> str:
    if path.exists():
        return "Available"

    return "Not Available"


def get_first_value(data: dict, keys: list[str], default: str = "Not specified"):
    for key in keys:
        value = data.get(key)

        if value not in (None, "", [], {}):
            return value

    return default


def get_case_evidence_paths(case_id: str):
    case_directory = Path("evidence") / case_id

    return {
        "directory": case_directory,
        "manifest": case_directory / "evidence_manifest.json",
        "correlations": case_directory / "evidence_correlations.json",
        "chain_of_custody": case_directory / "chain_of_custody.md",
        "forensic_summary": case_directory / "forensic_summary.md",
    }


def count_evidence(manifest: dict) -> int:
    evidence_items = manifest.get("evidence_items", [])

    if isinstance(evidence_items, list):
        return len(evidence_items)

    return int(manifest.get("evidence_count", 0) or 0)


def count_correlations(correlations_data: dict) -> int:
    correlations = correlations_data.get("correlations", [])

    if isinstance(correlations, list):
        return len(correlations)

    return 0


def count_verified_evidence(manifest: dict) -> int:
    evidence_items = manifest.get("evidence_items", [])

    if not isinstance(evidence_items, list):
        return 0

    verified_count = 0

    for item in evidence_items:
        integrity_status = str(
            item.get("integrity_status", "")
        ).strip().lower()

        if integrity_status in {
            "verified",
            "validated",
            "intact",
            "confirmed",
        }:
            verified_count += 1

    return verified_count


def determine_integrity_status(manifest: dict) -> str:
    total = count_evidence(manifest)

    if total == 0:
        return "No evidence records available"

    verified = count_verified_evidence(manifest)

    if verified == total:
        return "Verified"

    if verified > 0:
        return f"Partially verified ({verified} of {total})"

    return "Pending verification"


def build_threat_assessment(case: dict):
    severity = str(
        get_first_value(
            case,
            ["severity", "threat_level", "risk_level"],
            "UNKNOWN",
        )
    ).upper()

    classification = get_first_value(
        case,
        ["classification", "case_classification"],
        "Cyber-Biothreat Investigation",
    )

    threat_family = get_first_value(
        case,
        ["threat_family", "threat_type", "campaign_type"],
        "Unknown cyber-biothreat activity",
    )

    containment = get_first_value(
        case,
        ["containment_status", "containment_level", "status"],
        "Under investigation",
    )

    confidence = get_first_value(
        case,
        ["confidence", "confidence_score", "assessment_confidence"],
        "Not specified",
    )

    if isinstance(confidence, (int, float)):
        confidence = f"{confidence}%"

    return {
        "severity": severity,
        "classification": classification,
        "threat_family": threat_family,
        "containment": containment,
        "confidence": confidence,
    }


def build_analyst_assessment(case: dict, evidence_count: int, correlation_count: int):
    existing_summary = get_first_value(
        case,
        [
            "investigation_summary",
            "summary",
            "analyst_assessment",
            "description",
        ],
        "",
    )

    if existing_summary:
        return str(existing_summary)

    threat_family = get_first_value(
        case,
        ["threat_family", "threat_type"],
        "cyber-biothreat activity",
    )

    if evidence_count == 0:
        return (
            f"The investigation concerns suspected {threat_family}. "
            "Evidence collection remains in its initial stage, and no "
            "final determination has been reached."
        )

    return (
        f"The investigation concerns suspected {threat_family}. "
        f"Analysts reviewed {evidence_count} evidence records and "
        f"{correlation_count} correlation records. Current findings should "
        "be treated as an intelligence assessment rather than a final "
        "attribution. Continued validation is required to determine threat "
        "actor intent, biological research impact, and potential public "
        "health consequences."
    )


def build_recommendations(case: dict):
    recommendations = case.get("recommended_actions")

    if isinstance(recommendations, list) and recommendations:
        return [str(item) for item in recommendations]

    return [
        "Continue collection and preservation of cyber-biothreat evidence.",
        "Validate laboratory, biomedical, and specimen-tracking system integrity.",
        "Review access activity involving protected biological research assets.",
        "Correlate indicators with known threat actors and prior campaigns.",
        "Assess whether the activity indicates espionage, sabotage, or preparation for a biological attack.",
        "Maintain documented chain of custody for all investigative artifacts.",
        "Reassess containment and public-health risk as new evidence becomes available.",
    ]


def generate_report():
    current_case = load_json(CURRENT_CASE_FILE)

    if not current_case:
        raise FileNotFoundError(
            "Unable to load the active case from data/current_case.json"
        )

    case_id = str(
        get_first_value(
            current_case,
            ["case_id", "id"],
            "UNKNOWN-CASE",
        )
    )

    evidence_paths = get_case_evidence_paths(case_id)

    manifest = load_json(evidence_paths["manifest"])
    correlations_data = load_json(evidence_paths["correlations"])

    evidence_count = count_evidence(manifest)
    correlation_count = count_correlations(correlations_data)
    integrity_status = determine_integrity_status(manifest)

    threat_assessment = build_threat_assessment(current_case)

    operation_name = get_first_value(
        current_case,
        ["operation", "operation_name"],
        "Unassigned Operation",
    )

    campaign_id = get_first_value(
        current_case,
        ["campaign_id", "campaign"],
        "Not specified",
    )

    case_status = get_first_value(
        current_case,
        ["case_status", "status", "investigation_status"],
        "Active",
    )

    generated_at = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    analyst_assessment = build_analyst_assessment(
        current_case,
        evidence_count,
        correlation_count,
    )

    recommendations = build_recommendations(current_case)

    report_lines = [
        "# BioDefense Intelligence Division",
        "",
        "## Cyber-Biothreat Investigation Report",
        "",
        f"**Generated:** {generated_at}",
        "",
        "---",
        "",
        "## Investigation Identification",
        "",
        f"**Operation:** {operation_name}",
        "",
        f"**Campaign ID:** {campaign_id}",
        "",
        f"**Case ID:** {case_id}",
        "",
        f"**Case Status:** {case_status}",
        "",
        f"**Classification:** {threat_assessment['classification']}",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        analyst_assessment,
        "",
        "---",
        "",
        "## Cyber-Biothreat Assessment",
        "",
        f"**Threat Severity:** {threat_assessment['severity']}",
        "",
        f"**Threat Family:** {threat_assessment['threat_family']}",
        "",
        f"**Assessment Confidence:** {threat_assessment['confidence']}",
        "",
        f"**Containment Status:** {threat_assessment['containment']}",
        "",
        "The investigation evaluates whether cyber activity affected "
        "biological research, laboratory operations, biomedical information, "
        "specimen integrity, or protected biosecurity systems.",
        "",
        "---",
        "",
        "## Evidence Summary",
        "",
        f"**Evidence Records:** {evidence_count}",
        "",
        f"**Correlation Records:** {correlation_count}",
        "",
        f"**Evidence Integrity:** {integrity_status}",
        "",
        f"**Evidence Manifest:** {file_status(evidence_paths['manifest'])}",
        "",
        f"**Evidence Correlations:** {file_status(evidence_paths['correlations'])}",
        "",
        f"**Chain of Custody:** {file_status(evidence_paths['chain_of_custody'])}",
        "",
        f"**Forensic Summary:** {file_status(evidence_paths['forensic_summary'])}",
        "",
        "---",
        "",
        "## Biological and Public-Health Impact",
        "",
        "The available evidence should be reviewed for indications involving:",
        "",
        "- Unauthorized access to biological research systems",
        "- Manipulation or theft of genomic or biomedical information",
        "- Interference with specimen tracking or laboratory records",
        "- Compromise of laboratory information management systems",
        "- Biosecurity-control bypass",
        "- Insider assistance or credential misuse",
        "- Cyber activity supporting biological espionage or sabotage",
        "- Potential cyber-to-physical escalation",
        "",
        "No conclusion regarding biological material release should be made "
        "unless it is directly supported by validated evidence.",
        "",
        "---",
        "",
        "## Analyst Assessment",
        "",
        analyst_assessment,
        "",
        "The current assessment remains subject to revision as evidence is "
        "validated, correlated, and reviewed for attribution.",
        "",
        "---",
        "",
        "## Investigative Priorities",
        "",
        "- Determine the suspected threat actor's objective and capability.",
        "- Identify the biological, laboratory, or research assets targeted.",
        "- Establish whether evidence indicates espionage, sabotage, disruption, or attack preparation.",
        "- Verify whether physical specimens or laboratory processes were affected.",
        "- Identify unresolved intelligence gaps and conflicting evidence.",
        "- Assess possible public-health consequences.",
        "",
        "---",
        "",
        "## Recommended Actions",
        "",
    ]

    for recommendation in recommendations:
        report_lines.append(f"- {recommendation}")

    report_lines.extend(
        [
            "",
            "---",
            "",
            "## Investigation Resources",
            "",
            f"- [Command Brief](../operations/command_brief.md) — {file_status(COMMAND_BRIEF_FILE)}",
            f"- [Investigation Timeline](../operations/investigation_timeline.md) — {file_status(TIMELINE_FILE)}",
            f"- [Evidence Chain Analysis](../evidence/evidence_chain.md) — {file_status(EVIDENCE_CHAIN_FILE)}",
            f"- [Evidence Manifest](../evidence/{case_id}/evidence_manifest.json) — {file_status(evidence_paths['manifest'])}",
            f"- [Evidence Correlations](../evidence/{case_id}/evidence_correlations.json) — {file_status(evidence_paths['correlations'])}",
            f"- [Chain of Custody](../evidence/{case_id}/chain_of_custody.md) — {file_status(evidence_paths['chain_of_custody'])}",
            f"- [Forensic Summary](../evidence/{case_id}/forensic_summary.md) — {file_status(evidence_paths['forensic_summary'])}",
            "",
            "---",
            "",
            "## Investigative Notice",
            "",
            "This repository contains a fictional defensive intelligence "
            "simulation designed for cybersecurity, cyber-bio intelligence, "
            "biosecurity, incident response, and portfolio demonstration purposes.",
            "",
        ]
    )

    REPORT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    REPORT_OUTPUT.write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print(
        f"Investigation report generated: {REPORT_OUTPUT}"
    )
    print(f"Case: {case_id}")
    print(f"Evidence records: {evidence_count}")
    print(f"Correlation records: {correlation_count}")


if __name__ == "__main__":
    generate_report()
