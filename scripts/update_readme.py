#!/usr/bin/env python3

"""
Regenerate the automated section of README.md.

Reads:
    data/current_case.json
    operations/active_operation.json
    data/investigation_history.csv

Writes:
    README.md

Only content between the FSE report markers is replaced.
"""

import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean

CURRENT_CASE_PATH = Path("data/current_case.json")
ACTIVE_OPERATION_PATH = Path("operations/active_operation.json")
HISTORY_PATH = Path("data/investigation_history.csv")
README_PATH = Path("README.md")

REPORT_START = "<!-- FSE-REPORT-START -->"
REPORT_END = "<!-- FSE-REPORT-END -->"

CLOSED_STATUSES = {
    "closed",
    "resolved",
    "archived",
    "complete",
    "completed",
}


# -------------------------------------------------
# Data loading
# -------------------------------------------------

def load_json(path: Path) -> dict:
    """Load JSON data, returning an empty dictionary on failure."""

    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return data if isinstance(data, dict) else {}

    except (json.JSONDecodeError, OSError):
        return {}


def load_history(path: Path) -> list[dict]:
    """Load investigation history rows."""

    if not path.exists():
        return []

    try:
        with path.open("r", newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))

    except OSError:
        return []


# -------------------------------------------------
# Formatting helpers
# -------------------------------------------------

def field(
    data: dict,
    key: str,
    default: str = "Unknown",
):
    """Return a dictionary value with a readable fallback."""

    value = data.get(key, default)

    if value in (None, ""):
        return default

    return value


def safe_int(value: object, default: int = 0) -> int:
    """Convert a value to an integer safely."""

    try:
        return int(float(str(value).strip()))

    except (TypeError, ValueError):
        return default


def safe_float(value: object, default: float = 0.0) -> float:
    """Convert a value to a float safely."""

    try:
        return float(str(value).strip())

    except (TypeError, ValueError):
        return default


def format_number(value: object) -> str:
    """Format numeric dashboard values with separators."""

    return f"{safe_int(value):,}"


def format_list(
    items: object,
    empty_message: str = "No data available",
) -> str:
    """Render a list as Markdown bullets."""

    if not isinstance(items, list) or not items:
        return f"- {empty_message}"

    return "\n".join(f"- {item}" for item in items)


# -------------------------------------------------
# Historical metrics
# -------------------------------------------------

def calculate_history_metrics(history: list[dict]) -> dict:
    """Calculate metrics that are naturally derived from case history."""

    severity_counts = Counter(
        str(row.get("severity", "")).strip().upper()
        for row in history
    )

    confidences = [
        safe_float(row.get("confidence"))
        for row in history
        if str(row.get("confidence", "")).strip()
    ]

    average_confidence = (
        round(mean(confidences), 1)
        if confidences
        else 0.0
    )

    closed_cases = sum(
        1
        for row in history
        if str(row.get("status", "")).strip().lower()
        in CLOSED_STATUSES
    )

    return {
        "total": len(history),
        "low": severity_counts["LOW"],
        "moderate": severity_counts["MODERATE"],
        "high": severity_counts["HIGH"],
        "critical": severity_counts["CRITICAL"],
        "closed_cases": closed_cases,
        "average_confidence": average_confidence,
    }


def recent_investigations_table(
    history: list[dict],
    count: int = 5,
) -> str:
    """Create the recent investigations Markdown table."""

    rows_with_cases = [
        row for row in history if row.get("case_id")
    ]

    recent = rows_with_cases[-count:]

    header = (
        "| Case | Classification | Severity |\n"
        "|------|----------------|----------|\n"
    )

    if not recent:
        return (
            header
            + "| No archived investigations | — | — |\n"
        )

    rows = "".join(
        f"| {row.get('case_id', 'Unknown')} "
        f"| {row.get('classification', 'Unknown')} "
        f"| {row.get('severity', 'Unknown')} |\n"
        for row in reversed(recent)
    )

    return header + rows


# -------------------------------------------------
# README sections
# -------------------------------------------------

def build_overview_section() -> str:
    return (
        "# BioDefense-Intelligence-Division\n\n"
        "BioDefense Intelligence Division is a cyber-biothreat "
        "investigation and digital forensics initiative inspired by "
        "federal investigative workflows. The project simulates how "
        "analysts identify, document, reconstruct, and manage "
        "cyber-enabled threats targeting biomedical research "
        "environments, protected laboratory infrastructure, and "
        "critical biosecurity systems through automated investigative "
        "workflows using Python and C#."
    )


def build_campaign_dashboard(operation: dict) -> str:
    affected_facilities = field(
        operation,
        "affected_facilities",
        0,
    )

    affected_states = field(
        operation,
        "affected_states",
        0,
    )

    return (
        "# Active Campaign Dashboard\n\n"
        "| Campaign Overview | Campaign Status |\n"
        "|--------------------|-----------------|\n"
        f"| **Campaign ID**<br>"
        f"{field(operation, 'campaign_id')}<br><br>"
        f"**Operation**<br>"
        f"{field(operation, 'operation')}<br><br>"
        f"**Campaign Phase**<br>"
        f"{field(operation, 'campaign_phase')}<br><br>"
        f"**Threat Designation**<br>"
        f"{field(operation, 'threat_designation')}<br><br>"
        f"**Containment Level**<br>"
        f"{field(operation, 'containment_level')} "
        f"| **Confirmed Intrusions**<br>"
        f"{format_number(operation.get('confirmed_intrusions'))}"
        f"<br><br>"
        f"**Active Cases**<br>"
        f"{format_number(operation.get('active_cases'))}<br><br>"
        f"**Evidence Collected**<br>"
        f"{format_number(operation.get('evidence_collected'))}"
        f"<br><br>"
        f"**Digital Artifacts**<br>"
        f"{format_number(operation.get('digital_artifacts'))}"
        f"<br><br>"
        f"**Indicators**<br>"
        f"{format_number(operation.get('ioc_count'))} |\n\n"
        "---\n\n"
        f"**Campaign Objective:** "
        f"{field(operation, 'campaign_objective')}\n\n"
        f"**Next Objective:** "
        f"{field(operation, 'next_objective')}\n\n"
        f"**Affected Facilities:** "
        f"{affected_facilities}\n\n"
        f"**Affected States:** "
        f"{affected_states}"
    )


def build_active_investigation(case: dict) -> str:
    return (
        "# Active Investigation\n\n"
        "| Investigation | Classification |\n"
        "|---------------|----------------|\n"
        f"| **Case ID**<br>"
        f"{field(case, 'case_id')}<br><br>"
        f"**Classification**<br>"
        f"{field(case, 'classification')}<br><br>"
        f"**Threat Family**<br>"
        f"{field(case, 'threat_family')}<br><br>"
        f"**Severity**<br>"
        f"{field(case, 'severity')} "
        f"| **Platform**<br>"
        f"{field(case, 'affected_platform')}<br><br>"
        f"**Vendor**<br>"
        f"{field(case, 'vendor')}<br><br>"
        f"**Device**<br>"
        f"{field(case, 'device_family')}<br><br>"
        f"**Zone**<br>"
        f"{field(case, 'network_zone')} |\n\n"
        "---\n\n"
        "| Investigation Status |\n"
        "|-----------------------|\n"
        f"| **Priority**<br>"
        f"{field(case, 'priority')}<br><br>"
        f"**Confidence**<br>"
        f"{field(case, 'confidence')}%<br><br>"
        f"**Evidence**<br>"
        f"{format_number(case.get('evidence_count'))}<br><br>"
        f"**Indicators**<br>"
        f"{format_number(case.get('ioc_count'))} |\n\n"
        "---\n\n"
        "# Analyst Assessment\n\n"
        f"{field(case, 'assessment', 'No assessment available.')}"
        "\n\n---\n\n"
        "# Current Response\n\n"
        f"- Lead Analyst: "
        f"**{field(case, 'lead_analyst')}**\n"
        f"- Initial Access: "
        f"**{field(case, 'initial_access')}**\n"
        f"- Recommended Action: "
        f"**{field(case, 'recommended_action')}**"
    )


def build_operational_metrics(
    history_metrics: dict,
    operation: dict,
) -> str:
    """
    Build operational metrics.

    Campaign totals and confirmed intrusions come directly from the
    recalculated active operation so the README cannot display a
    different number from active_operation.json.
    """

    return (
        "# Operational Metrics\n\n"
        "| Metric | Value |\n"
        "|---------|------:|\n"
        f"| Total Investigations "
        f"| {history_metrics['total']} |\n"
        f"| Low Severity Cases "
        f"| {history_metrics['low']} |\n"
        f"| Moderate Severity Cases "
        f"| {history_metrics['moderate']} |\n"
        f"| High Severity Cases "
        f"| {history_metrics['high']} |\n"
        f"| Critical Severity Cases "
        f"| {history_metrics['critical']} |\n"
        f"| Average Confidence "
        f"| {history_metrics['average_confidence']}% |\n"
        f"| Total Evidence Collected "
        f"| {format_number(operation.get('evidence_collected'))} |\n"
        f"| Total Indicators "
        f"| {format_number(operation.get('ioc_count'))} |\n"
        f"| Active Cases "
        f"| {format_number(operation.get('active_cases'))} |\n"
        f"| Confirmed Intrusions "
        f"| {format_number(operation.get('confirmed_intrusions'))} |"
    )


def build_recent_investigations(history: list[dict]) -> str:
    return (
        "# Recent Investigations\n\n"
        + recent_investigations_table(history)
    )


def build_laboratories_section(operation: dict) -> str:
    laboratories = operation.get(
        "laboratories_under_review",
        [],
    )

    return (
        "# Laboratories Under Review\n\n"
        + format_list(
            laboratories,
            "No laboratories currently under review",
        )
    )


def build_mission_section() -> str:
    return (
        "# Division Mission\n\n"
        "BioDefense Intelligence Division is a defensive cybersecurity "
        "research project centered on cyber-enabled biosecurity "
        "investigations, protected research infrastructure, digital "
        "evidence management, forensic reconstruction, and coordinated "
        "incident response. The repository simulates how analysts "
        "document, track, and reconstruct complex investigations "
        "involving sensitive biomedical environments and critical "
        "operational systems."
    )


def build_toolkit_section() -> str:
    return (
        "# BioDefense Intelligence Toolkit (C#)\n\n"
        "The repository includes lightweight C# utilities representing "
        "internal applications used by a federal cyber-biosecurity "
        "investigative division.\n\n"
        "| Utility | Purpose |\n"
        "|---------|---------|\n"
        "| BioThreatIntelligence | Correlates laboratory intrusion "
        "activity with active biosecurity investigations. |\n"
        "| GenomeEvidenceAnalyzer | Reviews genomic research evidence "
        "and validates chain-of-custody metadata. |\n"
        "| OutbreakCorrelationEngine | Links related cyber incidents "
        "into a coordinated investigative campaign. |\n"
        "| IncidentBriefGenerator | Produces executive intelligence "
        "briefings for command staff and partner agencies. |"
    )


def build_intelligence_products_section() -> str:
    products = [
        "Cyber-biothreat investigation case files",
        "Laboratory intrusion assessments",
        "Protected research facility exposure reports",
        "Evidence reconstruction logs",
        "Chain-of-custody documentation",
        "Threat actor campaign summaries",
        "Biological research impact assessments",
        "Cyber-biosecurity intelligence reports",
        "Compromised laboratory asset inventories",
        "Intelligence workbooks for investigative review",
        "Executive operational briefings",
        "Federal cyber-biosecurity situation reports",
    ]

    return (
        "# Automated Intelligence Products\n\n"
        "Every investigation automatically generates operational "
        "intelligence including:\n\n"
        + format_list(products)
    )


# -------------------------------------------------
# Report generation
# -------------------------------------------------

def build_report(
    case: dict,
    operation: dict,
    history: list[dict],
) -> str:
    history_metrics = calculate_history_metrics(history)

    sections = [
        build_overview_section(),
        build_campaign_dashboard(operation),
        build_active_investigation(case),
        build_operational_metrics(
            history_metrics,
            operation,
        ),
        build_recent_investigations(history),
        build_laboratories_section(operation),
        build_mission_section(),
        build_toolkit_section(),
        build_intelligence_products_section(),
    ]

    body = "\n\n---\n\n".join(sections)

    return (
        f"{REPORT_START}\n\n"
        f"{body}\n\n"
        f"{REPORT_END}"
    )


def update_readme(report: str) -> None:
    """Replace only the generated README block."""

    if README_PATH.exists():
        existing = README_PATH.read_text(encoding="utf-8")
    else:
        existing = ""

    if REPORT_START in existing and REPORT_END in existing:
        before = existing.split(REPORT_START, 1)[0]
        after = existing.split(REPORT_END, 1)[1]

        new_content = before + report + after

    else:
        separator = (
            "\n\n"
            if existing and not existing.endswith("\n\n")
            else ""
        )

        new_content = (
            existing
            + separator
            + report
            + "\n"
        )

    README_PATH.write_text(
        new_content,
        encoding="utf-8",
    )


def main() -> None:
    case = load_json(CURRENT_CASE_PATH)
    operation = load_json(ACTIVE_OPERATION_PATH)
    history = load_history(HISTORY_PATH)

    report = build_report(
        case,
        operation,
        history,
    )

    update_readme(report)

    print(
        "README updated: "
        f"{len(history)} investigations, "
        f"{safe_int(operation.get('confirmed_intrusions'))} "
        "confirmed intrusions."
    )


if __name__ == "__main__":
    main()
