#!/usr/bin/env python3

"""
Regenerate the compact automated section of README.md.

Reads:
    data/current_case.json
    operations/active_operation.json
    data/investigation_history.csv
    workbooks/Exposure-Tracking-Matrix.csv
    active-case evidence and report products

Writes:
    README.md

Only content between the FSE report markers is replaced.
"""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean

CURRENT_CASE_PATH = Path("data/current_case.json")
ACTIVE_OPERATION_PATH = Path(
    "operations/active_operation.json"
)
HISTORY_PATH = Path(
    "data/investigation_history.csv"
)
WORKBOOK_CSV_PATH = Path(
    "workbooks/Exposure-Tracking-Matrix.csv"
)
README_PATH = Path("README.md")
SCANNER_BANNER_PATH = Path(
    "assets/biodefense-case-scan.gif"
)

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
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        return data if isinstance(data, dict) else {}

    except (json.JSONDecodeError, OSError):
        return {}


def load_csv_rows(path: Path) -> list[dict]:
    """Load CSV rows, returning an empty list on failure."""

    if not path.exists():
        return []

    try:
        with path.open(
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as file:
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


def safe_int(
    value: object,
    default: int = 0,
) -> int:
    """Convert a value to an integer safely."""

    try:
        return int(float(str(value).strip()))

    except (TypeError, ValueError):
        return default


def safe_float(
    value: object,
    default: float = 0.0,
) -> float:
    """Convert a value to a float safely."""

    try:
        return float(str(value).strip())

    except (TypeError, ValueError):
        return default


def format_number(value: object) -> str:
    """Format numeric values with separators."""

    return f"{safe_int(value):,}"


def markdown_cell(value: object) -> str:
    """Prepare text for a Markdown table cell."""

    return (
        str(value if value not in (None, "") else "Unknown")
        .replace("|", r"\|")
        .replace("\n", " ")
        .strip()
    )


def file_status(path: Path) -> str:
    """Return a compact generated-file status."""

    return "◆" if path.exists() else "◇"


def product_link(
    name: str,
    link: str,
    path: Path,
) -> str:
    """Build a compact product link with availability status."""

    return (
        f"{file_status(path)} "
        f"[{name}]({link})"
    )


def format_list(
    items: object,
    empty_message: str = "No data available",
) -> str:
    """Render a list as Markdown bullets."""

    if not isinstance(items, list) or not items:
        return f"- {empty_message}"

    return "\n".join(
        f"- {markdown_cell(item)}"
        for item in items
    )


# -------------------------------------------------
# Metrics and previews
# -------------------------------------------------

def calculate_history_metrics(
    history: list[dict],
) -> dict:
    """Calculate case-history metrics."""

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
        if str(
            row.get("status", "")
        ).strip().lower()
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
    """Create the recent-investigations table."""

    rows_with_cases = [
        row
        for row in history
        if row.get("case_id")
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
        f"| {markdown_cell(row.get('case_id'))} "
        f"| {markdown_cell(row.get('classification'))} "
        f"| {markdown_cell(row.get('severity'))} |\n"
        for row in reversed(recent)
    )

    return header + rows


def workbook_preview_table(
    rows: list[dict],
    count: int = 5,
) -> str:
    """Show the latest workbook records directly in the README."""

    recent = [
        row
        for row in rows
        if row.get("Case ID")
    ][-count:]

    header = (
        "| Date | Case ID | Severity | Risk | Confidence | Status |\n"
        "|------|---------|----------|-----:|-----------:|--------|\n"
    )

    if not recent:
        return (
            header
            + "| No workbook records available | — | — | 0 | 0 | — |\n"
        )

    table_rows = "".join(
        f"| {markdown_cell(row.get('Date'))} "
        f"| {markdown_cell(row.get('Case ID'))} "
        f"| {markdown_cell(row.get('Severity'))} "
        f"| {markdown_cell(row.get('Risk Score'))} "
        f"| {markdown_cell(row.get('Confidence'))} "
        f"| {markdown_cell(row.get('Status'))} |\n"
        for row in reversed(recent)
    )

    return header + table_rows


# -------------------------------------------------
# README sections
# -------------------------------------------------

def build_overview_section(
    case: dict,
    operation: dict,
) -> str:
    """Build the archival case-record header."""

    case_id = markdown_cell(
        field(
            case,
            "case_id",
            "UNKNOWN-CASE",
        )
    )

    campaign_id = markdown_cell(
        field(
            operation,
            "campaign_id",
            field(
                case,
                "campaign_id",
                "UNKNOWN-CAMPAIGN",
            ),
        )
    )

    record_status = markdown_cell(
        str(
            field(
                case,
                "status",
                "ACTIVE",
            )
        ).upper()
    )

    # GitHub can cache repository images. This short deterministic
    # version token changes whenever the current case or campaign data
    # changes, forcing the README to request the newest generated GIF.
    banner_state = json.dumps(
        {
            "case": case,
            "operation": operation,
        },
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )

    banner_version = hashlib.sha256(
        banner_state.encode("utf-8")
    ).hexdigest()[:12]

    banner = ""

    if SCANNER_BANNER_PATH.exists():
        banner = (
            '<p align="center">\n'
            '  <img '
            'src="assets/biodefense-case-scan.gif'
            f'?v={banner_version}" '
            'alt="Current BioDefense intelligence case interface" '
            'width="100%">\n'
            '</p>\n\n'
        )

    return (
        f"{banner}"
        "# BioDefense-Intelligence-Division\n\n"
        "> **CONTROLLED TRAINING RECORD** // "
        "Fictional cyber-biothreat investigation data\n\n"
        "| Record Control | Investigative State | Exchange Package |\n"
        "|----------------|---------------------|------------------|\n"
        f"| **Case:** `{case_id}`"
        f"<br>**Campaign:** `{campaign_id}` "
        f"| **Record:** `{record_status}`"
        f"<br>**Evidence:** `MANIFEST-TRACKED` "
        "| `XML` · `JSON` · `CSV` · `XLSX` |\n\n"
        "Automated cyber-biothreat investigation and digital forensics "
        "simulation using Python and C#. The project models federal-style "
        "case management, evidence reconstruction, threat assessment, "
        "chain of custody, intelligence reporting, and controlled "
        "operational recovery for fictional threats affecting biomedical "
        "research and protected laboratory environments."
    )

def build_campaign_dashboard(
    operation: dict,
) -> str:
    """Build a compact three-column campaign dashboard."""

    return (
        "# Executive Case File\n\n"
        "| Campaign Record | Operational Status | Investigative Scope |\n"
        "|----------|--------------------|-------|\n"
        f"| **ID:** {markdown_cell(field(operation, 'campaign_id'))}"
        f"<br>**Campaign:** "
        f"{markdown_cell(field(operation, 'operation'))}"
        f"<br>**Designation:** "
        f"{markdown_cell(field(operation, 'threat_designation'))} "
        f"| **Phase:** "
        f"{markdown_cell(field(operation, 'campaign_phase'))}"
        f"<br>**Containment:** "
        f"{markdown_cell(field(operation, 'containment_level'))}"
        f"<br>**Intrusions:** "
        f"{format_number(operation.get('confirmed_intrusions'))} "
        f"| **Active Cases:** "
        f"{format_number(operation.get('active_cases'))}"
        f"<br>**Evidence:** "
        f"{format_number(operation.get('evidence_collected'))}"
        f"<br>**Indicators:** "
        f"{format_number(operation.get('ioc_count'))}"
        f"<br>**Facilities / States:** "
        f"{markdown_cell(field(operation, 'affected_facilities', 0))}"
        f" / "
        f"{markdown_cell(field(operation, 'affected_states', 0))} |\n\n"
        "<details>\n"
        "<summary><strong>Campaign objective and next action</strong>"
        "</summary>\n\n"
        f"**Objective:** "
        f"{markdown_cell(field(operation, 'campaign_objective'))}\n\n"
        f"**Next action:** "
        f"{markdown_cell(field(operation, 'next_objective'))}\n\n"
        "</details>"
    )


def build_active_investigation(
    case: dict,
) -> str:
    """Build a compact three-column active-case dashboard."""

    return (
        "# Active Investigation\n\n"
        "| Case Profile | Target Environment | Response |\n"
        "|--------------|--------------------|----------|\n"
        f"| **Case:** {markdown_cell(field(case, 'case_id'))}"
        f"<br>**Classification:** "
        f"{markdown_cell(field(case, 'classification'))}"
        f"<br>**Threat Family:** "
        f"{markdown_cell(field(case, 'threat_family'))}"
        f"<br>**Severity / Priority:** "
        f"{markdown_cell(field(case, 'severity'))} / "
        f"{markdown_cell(field(case, 'priority'))} "
        f"| **Platform:** "
        f"{markdown_cell(field(case, 'affected_platform'))}"
        f"<br>**Vendor / Device:** "
        f"{markdown_cell(field(case, 'vendor'))} / "
        f"{markdown_cell(field(case, 'device_family'))}"
        f"<br>**Zone:** "
        f"{markdown_cell(field(case, 'network_zone'))}"
        f"<br>**Assets:** "
        f"{format_number(case.get('affected_assets'))} "
        f"| **Confidence:** "
        f"{markdown_cell(field(case, 'confidence'))}%"
        f"<br>**Evidence / IOCs:** "
        f"{format_number(case.get('evidence_count'))} / "
        f"{format_number(case.get('ioc_count'))}"
        f"<br>**Lead:** "
        f"{markdown_cell(field(case, 'lead_analyst'))}"
        f"<br>**Initial Access:** "
        f"{markdown_cell(field(case, 'initial_access'))} |\n\n"
        "<details>\n"
        "<summary><strong>Analyst assessment and recommended "
        "response</strong></summary>\n\n"
        f"**Assessment:** "
        f"{markdown_cell(field(case, 'assessment', 'No assessment available.'))}"
        "\n\n"
        f"**Recommended action:** "
        f"{markdown_cell(field(case, 'recommended_action'))}\n\n"
        "</details>"
    )


def build_evidence_dashboard_section(
    case: dict,
) -> str:
    """Build the compact evidence dashboard and product grid."""

    case_id = str(
        field(
            case,
            "case_id",
            "UNKNOWN-CASE",
        )
    )

    case_directory = Path("evidence") / case_id

    manifest_path = (
        case_directory
        / "evidence_manifest.json"
    )

    correlations_path = (
        case_directory
        / "evidence_correlations.json"
    )

    chain_of_custody_path = (
        case_directory
        / "chain_of_custody.md"
    )

    forensic_summary_path = (
        case_directory
        / "forensic_summary.md"
    )

    acquisition_summary_path = (
        case_directory
        / "acquisition_summary.md"
    )

    investigation_report_path = Path(
        "reports/investigation_report.md"
    )

    bioterror_assessment_path = Path(
        "reports/bioterror_threat_assessment.md"
    )

    csharp_json_path = Path(
        "reports/bioterror_threat_score_csharp.json"
    )

    csharp_xml_path = Path(
        "reports/bioterror_threat_score_csharp.xml"
    )

    investigative_leads_path = Path(
        "reports/investigative_leads.md"
    )

    command_brief_path = Path(
        "operations/command_brief.md"
    )

    timeline_path = Path(
        "operations/investigation_timeline.md"
    )

    evidence_chain_path = Path(
        "evidence/evidence_chain.md"
    )

    workbook_xlsx_path = Path(
        "workbooks/Exposure-Tracking-Matrix.xlsx"
    )

    workbook_csv_path = WORKBOOK_CSV_PATH

    manifest = load_json(manifest_path)
    correlation_data = load_json(
        correlations_path
    )

    evidence_items = manifest.get(
        "evidence_items",
        [],
    )

    if not isinstance(evidence_items, list):
        evidence_items = []

    correlations = correlation_data.get(
        "correlations",
        [],
    )

    if not isinstance(correlations, list):
        correlations = []

    evidence_count = len(evidence_items)

    if evidence_count == 0:
        evidence_count = safe_int(
            manifest.get(
                "evidence_count",
                case.get("evidence_count"),
            )
        )

    correlation_count = len(correlations)

    verified_statuses = {
        "verified",
        "validated",
        "confirmed",
        "intact",
    }

    verified_count = sum(
        1
        for item in evidence_items
        if str(
            item.get(
                "integrity_status",
                "",
            )
        ).strip().lower()
        in verified_statuses
    )

    pending_review_count = sum(
        1
        for item in evidence_items
        if any(
            term in str(
                item.get(
                    "review_status",
                    "",
                )
            ).strip().lower()
            for term in (
                "pending",
                "awaiting",
                "unreviewed",
            )
        )
    )

    artifact_counts = Counter(
        str(
            item.get(
                "artifact_type",
                "Unspecified Evidence",
            )
        ).strip()
        or "Unspecified Evidence"
        for item in evidence_items
    )

    finding_counts = Counter(
        str(
            correlation.get(
                "finding",
                "Unspecified Finding",
            )
        ).strip()
        or "Unspecified Finding"
        for correlation in correlations
    )

    evidence_rows = "".join(
        f"| {markdown_cell(name)} | {count} |\n"
        for name, count in artifact_counts.most_common()
    )

    if not evidence_rows:
        evidence_rows = (
            "| No evidence breakdown available | 0 |\n"
        )

    finding_rows = "".join(
        f"| {markdown_cell(name)} | {count} |\n"
        for name, count in finding_counts.most_common()
    )

    if not finding_rows:
        finding_rows = (
            "| No correlated findings available | 0 |\n"
        )

    reports = [
        product_link(
            "Investigation Report",
            "reports/investigation_report.md",
            investigation_report_path,
        ),
        product_link(
            "Bioterror Assessment",
            "reports/bioterror_threat_assessment.md",
            bioterror_assessment_path,
        ),
        product_link(
            "C# Threat Score (JSON)",
            "reports/bioterror_threat_score_csharp.json",
            csharp_json_path,
        ),
        product_link(
            "C# Threat Score (XML)",
            "reports/bioterror_threat_score_csharp.xml",
            csharp_xml_path,
        ),
        product_link(
            "Investigative Leads",
            "reports/investigative_leads.md",
            investigative_leads_path,
        ),
    ]

    evidence_products = [
        product_link(
            "Evidence Chain",
            "evidence/evidence_chain.md",
            evidence_chain_path,
        ),
        product_link(
            "Evidence Manifest",
            f"evidence/{case_id}/evidence_manifest.json",
            manifest_path,
        ),
        product_link(
            "Evidence Correlations",
            f"evidence/{case_id}/evidence_correlations.json",
            correlations_path,
        ),
        product_link(
            "Chain of Custody",
            f"evidence/{case_id}/chain_of_custody.md",
            chain_of_custody_path,
        ),
        product_link(
            "Forensic Summary",
            f"evidence/{case_id}/forensic_summary.md",
            forensic_summary_path,
        ),
        product_link(
            "Acquisition Summary",
            f"evidence/{case_id}/acquisition_summary.md",
            acquisition_summary_path,
        ),
    ]

    operations_products = [
        product_link(
            "Command Brief",
            "operations/command_brief.md",
            command_brief_path,
        ),
        product_link(
            "Investigation Timeline",
            "operations/investigation_timeline.md",
            timeline_path,
        ),
        product_link(
            "Exposure Matrix (GitHub CSV Preview)",
            "workbooks/Exposure-Tracking-Matrix.csv",
            workbook_csv_path,
        ),
        product_link(
            "Exposure Matrix (Excel Download)",
            "workbooks/Exposure-Tracking-Matrix.xlsx",
            workbook_xlsx_path,
        ),
    ]

    workbook_rows = load_csv_rows(
        workbook_csv_path
    )

    repository_updated = field(
        manifest,
        "generated_at",
        field(
            case,
            "date",
            "Not specified",
        ),
    )

    return (
        "<!-- EVIDENCE_DASHBOARD_START -->\n\n"
        "# Digital Evidence Record\n\n"
        f"**Active Case:** {markdown_cell(case_id)}\n\n"
        "| Evidence Records | Correlations | Integrity Verified "
        "| Pending Review |\n"
        "|-----------------:|-------------:|-------------------:"
        "|---------------:|\n"
        f"| {format_number(evidence_count)} "
        f"| {format_number(correlation_count)} "
        f"| {format_number(verified_count)} "
        f"| {format_number(pending_review_count)} |\n\n"
        "## Active Case Intelligence Products\n\n"
        "| Reports & Assessments | Evidence & Forensics "
        "| Operations & Data |\n"
        "|-----------------------|----------------------"
        "|-------------------|\n"
        f"| {'<br>'.join(reports)} "
        f"| {'<br>'.join(evidence_products)} "
        f"| {'<br>'.join(operations_products)} |\n\n"
        "<details>\n"
        "<summary><strong>Evidence breakdown</strong></summary>\n\n"
        "| Evidence Type | Records |\n"
        "|---------------|--------:|\n"
        f"{evidence_rows}\n"
        "</details>\n\n"
        "<details>\n"
        "<summary><strong>Priority investigative findings</strong>"
        "</summary>\n\n"
        "| Investigative Finding | Correlations |\n"
        "|-----------------------|-------------:|\n"
        f"{finding_rows}\n"
        "</details>\n\n"
        "<details>\n"
        "<summary><strong>Exposure Tracking Matrix preview</strong>"
        "</summary>\n\n"
        "[Open the complete GitHub CSV preview]"
        "(workbooks/Exposure-Tracking-Matrix.csv)"
        " · "
        "[Download the formatted Excel workbook]"
        "(workbooks/Exposure-Tracking-Matrix.xlsx)\n\n"
        f"{workbook_preview_table(workbook_rows)}\n"
        "</details>\n\n"
        f"**Threat Family:** "
        f"{markdown_cell(field(case, 'threat_family'))}"
        f" · **Repository Updated:** "
        f"{markdown_cell(repository_updated)}\n\n"
        "<!-- EVIDENCE_DASHBOARD_END -->"
    )


def build_supporting_details(
    history: list[dict],
    operation: dict,
) -> str:
    """Build collapsed supporting sections."""

    metrics = calculate_history_metrics(history)

    operational_table = (
        "| Metric | Value |\n"
        "|--------|------:|\n"
        f"| Total Investigations | {metrics['total']} |\n"
        f"| Low / Moderate | "
        f"{metrics['low']} / {metrics['moderate']} |\n"
        f"| High / Critical | "
        f"{metrics['high']} / {metrics['critical']} |\n"
        f"| Closed Cases | {metrics['closed_cases']} |\n"
        f"| Average Confidence | "
        f"{metrics['average_confidence']}% |\n"
        f"| Total Evidence | "
        f"{format_number(operation.get('evidence_collected'))} |\n"
        f"| Total Indicators | "
        f"{format_number(operation.get('ioc_count'))} |\n"
    )

    laboratories = operation.get(
        "laboratories_under_review",
        [],
    )

    toolkit_table = (
        "| Utility | Purpose |\n"
        "|---------|---------|\n"
        "| BioThreatIntelligence | Correlates laboratory intrusion "
        "activity with active investigations. |\n"
        "| GenomeEvidenceAnalyzer | Reviews genomic evidence and "
        "chain-of-custody metadata. |\n"
        "| OutbreakCorrelationEngine | Links related incidents into "
        "a coordinated campaign. |\n"
        "| IncidentBriefGenerator | Produces command-level "
        "intelligence briefings. |\n"
    )

    products = [
        "Cyber-biothreat case files",
        "Laboratory intrusion assessments",
        "Protected facility exposure reports",
        "Evidence reconstruction logs",
        "Chain-of-custody documentation",
        "Threat actor campaign summaries",
        "Biological research impact assessments",
        "Cyber-biosecurity intelligence reports",
        "Bioterror threat assessments",
        "Investigative leads and intelligence gaps",
        "Exposure-tracking workbooks and CSV previews",
        "Executive operational briefings",
    ]

    return (
        "# Supporting Case Records\n\n"
        "<details>\n"
        "<summary><strong>Operational metrics and recent "
        "investigations</strong></summary>\n\n"
        f"{operational_table}\n"
        "### Recent Investigations\n\n"
        f"{recent_investigations_table(history)}\n"
        "</details>\n\n"
        "<details>\n"
        "<summary><strong>Laboratories under review</strong>"
        "</summary>\n\n"
        f"{format_list(laboratories, 'No laboratories currently under review')}"
        "\n\n</details>\n\n"
        "<details>\n"
        "<summary><strong>BioDefense Intelligence Toolkit "
        "(C#)</strong></summary>\n\n"
        "Lightweight utilities representing internal investigative "
        "applications.\n\n"
        f"{toolkit_table}\n"
        "</details>\n\n"
        "<details>\n"
        "<summary><strong>Automated intelligence product "
        "catalog</strong></summary>\n\n"
        f"{format_list(products)}\n\n"
        "</details>"
    )


def build_mission_section() -> str:
    return (
        "# Investigative Mission\n\n"
        "Defensive cybersecurity research focused on cyber-enabled "
        "biosecurity investigations, protected research infrastructure, "
        "digital evidence management, forensic reconstruction, and "
        "coordinated incident response."
    )


# -------------------------------------------------
# Report generation
# -------------------------------------------------

def build_report(
    case: dict,
    operation: dict,
    history: list[dict],
) -> str:
    sections = [
        build_overview_section(
            case,
            operation,
        ),
        build_campaign_dashboard(operation),
        build_active_investigation(case),
        build_evidence_dashboard_section(case),
        build_supporting_details(
            history,
            operation,
        ),
        build_mission_section(),
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
        existing = README_PATH.read_text(
            encoding="utf-8",
        )
    else:
        existing = ""

    if (
        REPORT_START in existing
        and REPORT_END in existing
    ):
        before = existing.split(
            REPORT_START,
            1,
        )[0]

        after = existing.split(
            REPORT_END,
            1,
        )[1]

        new_content = before + report + after

    else:
        separator = (
            "\n\n"
            if existing
            and not existing.endswith("\n\n")
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
    operation = load_json(
        ACTIVE_OPERATION_PATH
    )
    history = load_csv_rows(HISTORY_PATH)

    report = build_report(
        case,
        operation,
        history,
    )

    update_readme(report)

    print(
        "Compact README updated: "
        f"{len(history)} investigations, "
        f"{safe_int(operation.get('confirmed_intrusions'))} "
        "confirmed intrusions."
    )


if __name__ == "__main__":
    main()
