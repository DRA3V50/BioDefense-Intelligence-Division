#!/usr/bin/env python3

"""
Regenerate the controlled README section from live repository state.

Reads:
    data/current_case.json
    operations/active_operation.json
    data/investigation_history.csv
    workbooks/Exposure-Tracking-Matrix.csv
    evidence/<active-case>/evidence_manifest.json
    evidence/<active-case>/evidence_correlations.json
    reports/bioterror_threat_score_csharp.json
    active-case evidence/report products
    assets/biodefense-case-scan.gif

Writes:
    README.md

Only content between the FSE report markers is replaced.

Presentation contract:
    - GitHub-safe HTML tables are used for stable multi-column layout.
    - Native <details>/<summary> blocks provide expandable sections.
    - ◆ = generated/available product
    - ◇ = expected product currently unavailable
    - ■ = current status/state marker
    - ▸ = secondary reference/download
    - → = lifecycle progression
"""

import csv
import hashlib
import html
import json
from collections import Counter
from pathlib import Path
from statistics import mean

CURRENT_CASE_PATH = Path("data/current_case.json")
ACTIVE_OPERATION_PATH = Path("operations/active_operation.json")
HISTORY_PATH = Path("data/investigation_history.csv")
WORKBOOK_CSV_PATH = Path("workbooks/Exposure-Tracking-Matrix.csv")
README_PATH = Path("README.md")
SCANNER_BANNER_PATH = Path("assets/biodefense-case-scan.gif")
CSHARP_SCORE_PATH = Path("reports/bioterror_threat_score_csharp.json")

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

def field(data: dict, key: str, default="Unknown"):
    """Return a dictionary value with a readable fallback."""
    value = data.get(key, default)
    return default if value in (None, "") else value


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
    return f"{safe_int(value):,}"


def html_cell(value: object, default: str = "Unknown") -> str:
    """Escape dynamic text before placing it inside GitHub HTML."""
    if value in (None, ""):
        value = default
    return html.escape(str(value).strip(), quote=True)


def state_label(value: object, default: str = "UNKNOWN") -> str:
    """Format a machine-state value for human display."""
    if value in (None, ""):
        value = default
    return html_cell(str(value).replace("_", " ").strip().upper())


def file_status(path: Path) -> str:
    return "◆" if path.exists() else "◇"


def html_product_link(name: str, link: str, path: Path) -> str:
    return (
        f"{file_status(path)} "
        f'<a href="{html.escape(link, quote=True)}">'
        f"{html.escape(name)}</a>"
    )


def html_secondary_link(name: str, link: str) -> str:
    return (
        f'▸ <a href="{html.escape(link, quote=True)}">'
        f"{html.escape(name)}</a>"
    )


def html_bullets(items: object, empty_message: str) -> str:
    if not isinstance(items, list) or not items:
        return f"<p>{html.escape(empty_message)}</p>"

    rows = "\n".join(
        f"  <li>{html_cell(item)}</li>"
        for item in items
    )
    return f"<ul>\n{rows}\n</ul>"


def html_table(headers: list[str], rows: list[list[str]],
               aligns: list[str] | None = None) -> str:
    """Create a GitHub-compatible HTML table with already-safe cell HTML."""
    aligns = aligns or ["left"] * len(headers)

    head = "\n".join(
        f'      <th align="{aligns[i]}">{html.escape(header)}</th>'
        for i, header in enumerate(headers)
    )

    body_rows = []
    for row in rows:
        cells = "\n".join(
            f'      <td valign="top" align="{aligns[i]}">{cell}</td>'
            for i, cell in enumerate(row)
        )
        body_rows.append(f"    <tr>\n{cells}\n    </tr>")

    body = "\n".join(body_rows)

    return (
        "<table>\n"
        "  <thead>\n"
        "    <tr>\n"
        f"{head}\n"
        "    </tr>\n"
        "  </thead>\n"
        "  <tbody>\n"
        f"{body}\n"
        "  </tbody>\n"
        "</table>"
    )


def details(summary: str, body: str) -> str:
    return (
        "<details>\n"
        f"<summary><strong>{html.escape(summary)}</strong></summary>\n\n"
        "<br>\n\n"
        f"{body.strip()}\n\n"
        "</details>"
    )


# -------------------------------------------------
# Derived live data
# -------------------------------------------------

def calculate_history_metrics(history: list[dict]) -> dict:
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


def find_nested_value(data: object, candidate_keys: tuple[str, ...]):
    """Find the first matching key recursively in a JSON object."""
    if isinstance(data, dict):
        for key in candidate_keys:
            if key in data and data[key] not in (None, ""):
                return data[key]
        for value in data.values():
            found = find_nested_value(value, candidate_keys)
            if found not in (None, ""):
                return found
    elif isinstance(data, list):
        for value in data:
            found = find_nested_value(value, candidate_keys)
            if found not in (None, ""):
                return found
    return None


def canonical_threat_assessment(case: dict) -> tuple[str, str]:
    """
    Resolve the current canonical C# assessment.

    The C# JSON is preferred. Case-state values are used as a fallback because
    synchronized support state may already contain the canonical result.
    """
    score_data = load_json(CSHARP_SCORE_PATH)

    score = find_nested_value(
        score_data,
        (
            "overall_threat_score",
            "threat_score",
            "overall_score",
            "score",
        ),
    )
    level = find_nested_value(
        score_data,
        (
            "overall_threat_level",
            "threat_level",
            "canonical_classification",
            "classification",
            "level",
        ),
    )

    if score in (None, ""):
        score = field(case, "threat_score", "Unavailable")

    if level in (None, ""):
        level = field(
            case,
            "canonical_classification",
            field(case, "threat_level", "Unavailable"),
        )

    if score not in (None, "", "Unavailable"):
        score_text = f"{safe_int(score)} / 100"
    else:
        score_text = "Unavailable"

    return score_text, str(level).strip().upper()


def recent_investigation_rows(history: list[dict], count: int = 5) -> list[list[str]]:
    rows_with_cases = [
        row for row in history
        if row.get("case_id")
    ]
    recent = list(reversed(rows_with_cases[-count:]))

    if not recent:
        return [["No archived investigations", "—", "—"]]

    return [
        [
            html_cell(row.get("case_id"), "—"),
            html_cell(row.get("classification"), "—"),
            html_cell(row.get("severity"), "—"),
        ]
        for row in recent
    ]


def workbook_preview_rows(rows: list[dict], count: int = 5) -> list[list[str]]:
    recent = [
        row for row in rows
        if row.get("Case ID")
    ][-count:]
    recent.reverse()

    if not recent:
        return [["No workbook records available", "—", "—", "0", "0", "—"]]

    return [
        [
            html_cell(row.get("Date"), "—"),
            html_cell(row.get("Case ID"), "—"),
            html_cell(row.get("Severity"), "—"),
            html_cell(row.get("Risk Score"), "0"),
            html_cell(row.get("Confidence"), "0"),
            html_cell(row.get("Status"), "—"),
        ]
        for row in recent
    ]


# -------------------------------------------------
# README sections
# -------------------------------------------------

def build_banner() -> str:
    banner_version = "missing-banner"
    if SCANNER_BANNER_PATH.exists():
        banner_version = hashlib.sha256(
            SCANNER_BANNER_PATH.read_bytes()
        ).hexdigest()[:12]

    if not SCANNER_BANNER_PATH.exists():
        return ""

    return (
        '<p align="center">\n'
        '  <img '
        'src="assets/biodefense-case-scan.gif'
        f'?v={banner_version}" '
        'alt="Current BioDefense intelligence case interface" '
        'width="100%">\n'
        "</p>"
    )


def case_product_paths(case_id: str) -> dict[str, Path]:
    case_dir = Path("evidence") / case_id
    return {
        "investigation_report": Path("reports/investigation_report.md"),
        "bioterror_assessment": Path("reports/bioterror_threat_assessment.md"),
        "csharp_json": Path("reports/bioterror_threat_score_csharp.json"),
        "csharp_xml": Path("reports/bioterror_threat_score_csharp.xml"),
        "investigative_leads": Path("reports/investigative_leads.md"),
        "evidence_chain": Path("evidence/evidence_chain.md"),
        "manifest": case_dir / "evidence_manifest.json",
        "correlations": case_dir / "evidence_correlations.json",
        "chain_of_custody": case_dir / "chain_of_custody.md",
        "forensic_summary": case_dir / "forensic_summary.md",
        "acquisition_summary": case_dir / "acquisition_summary.md",
        "command_brief": Path("operations/command_brief.md"),
        "timeline": Path("operations/investigation_timeline.md"),
        "workbook_csv": WORKBOOK_CSV_PATH,
        "workbook_xlsx": Path("workbooks/Exposure-Tracking-Matrix.xlsx"),
    }


def build_case_file_access(case_id: str) -> str:
    paths = case_product_paths(case_id)

    reports = "<br>\n".join([
        html_product_link(
            "Investigation Report",
            "reports/investigation_report.md",
            paths["investigation_report"],
        ),
        html_product_link(
            "Bioterror Assessment",
            "reports/bioterror_threat_assessment.md",
            paths["bioterror_assessment"],
        ),
        html_product_link(
            "C# Canonical Threat Score (JSON)",
            "reports/bioterror_threat_score_csharp.json",
            paths["csharp_json"],
        ),
        html_product_link(
            "C# Canonical Threat Score (XML)",
            "reports/bioterror_threat_score_csharp.xml",
            paths["csharp_xml"],
        ),
        html_product_link(
            "Investigative Leads",
            "reports/investigative_leads.md",
            paths["investigative_leads"],
        ),
    ])

    evidence = "<br>\n".join([
        html_product_link(
            "Evidence Chain",
            "evidence/evidence_chain.md",
            paths["evidence_chain"],
        ),
        html_product_link(
            "Evidence Manifest",
            f"evidence/{case_id}/evidence_manifest.json",
            paths["manifest"],
        ),
        html_product_link(
            "Evidence Correlations",
            f"evidence/{case_id}/evidence_correlations.json",
            paths["correlations"],
        ),
        html_product_link(
            "Chain of Custody",
            f"evidence/{case_id}/chain_of_custody.md",
            paths["chain_of_custody"],
        ),
        html_product_link(
            "Forensic Summary",
            f"evidence/{case_id}/forensic_summary.md",
            paths["forensic_summary"],
        ),
        html_product_link(
            "Acquisition Summary",
            f"evidence/{case_id}/acquisition_summary.md",
            paths["acquisition_summary"],
        ),
    ])

    operations = "<br>\n".join([
        html_product_link(
            "Command Brief",
            "operations/command_brief.md",
            paths["command_brief"],
        ),
        html_product_link(
            "Investigation Timeline",
            "operations/investigation_timeline.md",
            paths["timeline"],
        ),
        html_product_link(
            "Exposure Matrix (CSV Preview)",
            "workbooks/Exposure-Tracking-Matrix.csv",
            paths["workbook_csv"],
        ),
        html_product_link(
            "Exposure Matrix (Excel)",
            "workbooks/Exposure-Tracking-Matrix.xlsx",
            paths["workbook_xlsx"],
        ),
    ])

    return (
        "## Case File Access\n\n"
        + html_table(
            ["Reports & Assessments", "Evidence & Forensics", "Operations & Data"],
            [[reports, evidence, operations]],
        )
    )


def build_overview_section(case: dict, operation: dict) -> str:
    case_id = str(field(case, "case_id", "UNKNOWN-CASE"))
    campaign_id = field(
        operation,
        "campaign_id",
        field(case, "campaign_id", "UNKNOWN-CAMPAIGN"),
    )

    record_status = state_label(field(case, "status", "ACTIVE"))
    current_stage = state_label(
        field(case, "current_stage", record_status)
    )
    lifecycle_status = state_label(
        field(case, "lifecycle_status", "ACTIVE")
    )

    record_table = html_table(
        ["Record Control", "Investigative State", "Exchange Package"],
        [[
            (
                f"<strong>Case:</strong> <code>{html_cell(case_id)}</code><br>\n"
                f"<strong>Campaign:</strong> <code>{html_cell(campaign_id)}</code>"
            ),
            (
                f"<strong>Record:</strong> <code>{record_status}</code><br>\n"
                f"<strong>Stage:</strong> ■ <code>{current_stage}</code><br>\n"
                f"<strong>Lifecycle:</strong> ■ <code>{lifecycle_status}</code>"
            ),
            (
                "<code>JSON</code> · <code>XML</code> · <code>Markdown</code><br>\n"
                "<code>CSV</code> · <code>XLSX</code>"
            ),
        ]],
    )

    return (
        f"{build_banner()}\n\n"
        "# BioDefense-Intelligence-Division\n\n"
        "> **CONTROLLED TRAINING RECORD** // "
        "Cyber-biothreat investigation data\n\n"
        f"{build_case_file_access(case_id)}\n\n"
        f"{record_table}\n\n"
        "BioDefense Intelligence Division is a cyber-biosecurity intelligence "
        "and investigative forensics platform built around federal-style case "
        "management and the examination of cyber-enabled threats affecting "
        "biomedical research, pharmaceutical laboratories, protected research "
        "environments, operational technology, connected medical systems, and "
        "critical infrastructure. The repository combines digital evidence "
        "acquisition and reconstruction, evidentiary correlation, chain-of-"
        "custody control, investigative leads, forensic reporting, threat "
        "assessment, and persistent case operations.\n\n"
        "Investigations retain case identity and evidentiary state across "
        "scheduled GitHub Actions executions. Case records, evidence "
        "repositories, correlations, forensic products, threat assessments, "
        "timelines, and operational intelligence remain synchronized throughout "
        "the investigative lifecycle, while the dashboard functions as a "
        "read-only visualization of authoritative case state."
    )


def build_campaign_dashboard(operation: dict) -> str:
    table = html_table(
        ["Campaign Record", "Operational Status", "Investigative Scope"],
        [[
            (
                f"<strong>ID:</strong> {html_cell(field(operation, 'campaign_id'))}<br>\n"
                f"<strong>Campaign:</strong> {html_cell(field(operation, 'operation'))}<br>\n"
                f"<strong>Designation:</strong> {html_cell(field(operation, 'threat_designation'))}"
            ),
            (
                f"<strong>Phase:</strong> ■ {html_cell(field(operation, 'campaign_phase'))}<br>\n"
                f"<strong>Containment:</strong> ■ {html_cell(field(operation, 'containment_level'))}<br>\n"
                f"<strong>Intrusions:</strong> {format_number(operation.get('confirmed_intrusions'))}"
            ),
            (
                f"<strong>Active Cases:</strong> {format_number(operation.get('active_cases'))}<br>\n"
                f"<strong>Evidence:</strong> {format_number(operation.get('evidence_collected'))}<br>\n"
                f"<strong>Indicators:</strong> {format_number(operation.get('ioc_count'))}<br>\n"
                f"<strong>Facilities / States:</strong> "
                f"{html_cell(field(operation, 'affected_facilities', 0))} / "
                f"{html_cell(field(operation, 'affected_states', 0))}"
            ),
        ]],
    )

    objective = (
        f"**Objective:** {html_cell(field(operation, 'campaign_objective'))}\n\n"
        f"**Next action:** {html_cell(field(operation, 'next_objective'))}"
    )

    return (
        "# Executive Case File\n\n"
        f"{table}\n\n"
        f"{details('Campaign objective and next action', objective)}"
    )


def build_active_investigation(case: dict) -> str:
    table = html_table(
        ["Case Profile", "Target Environment", "Response"],
        [[
            (
                f"<strong>Case:</strong> {html_cell(field(case, 'case_id'))}<br>\n"
                f"<strong>Classification:</strong> {html_cell(field(case, 'classification'))}<br>\n"
                f"<strong>Threat Family:</strong> {html_cell(field(case, 'threat_family'))}<br>\n"
                f"<strong>Severity / Priority:</strong> ■ "
                f"{html_cell(field(case, 'severity'))} / "
                f"{html_cell(field(case, 'priority'))}"
            ),
            (
                f"<strong>Platform:</strong> {html_cell(field(case, 'affected_platform'))}<br>\n"
                f"<strong>Vendor / Device:</strong> {html_cell(field(case, 'vendor'))} / "
                f"{html_cell(field(case, 'device_family'))}<br>\n"
                f"<strong>Zone:</strong> {html_cell(field(case, 'network_zone'))}<br>\n"
                f"<strong>Assets:</strong> {format_number(case.get('affected_assets'))}"
            ),
            (
                f"<strong>Confidence:</strong> {html_cell(field(case, 'confidence'))}%<br>\n"
                f"<strong>Evidence / IOCs:</strong> "
                f"{format_number(case.get('evidence_count'))} / "
                f"{format_number(case.get('ioc_count'))}<br>\n"
                f"<strong>Lead:</strong> {html_cell(field(case, 'lead_analyst'))}<br>\n"
                f"<strong>Initial Access:</strong> {html_cell(field(case, 'initial_access'))}"
            ),
        ]],
    )

    assessment = (
        f"**Assessment:** "
        f"{html_cell(field(case, 'assessment', 'No assessment available.'))}\n\n"
        f"**Recommended action:** "
        f"{html_cell(field(case, 'recommended_action'))}"
    )

    lifecycle_table = html_table(
        ["Investigative Control", "Implementation"],
        [
            [
                "<strong>Case Continuity</strong>",
                "Active case identity and authoritative state persist across workflow executions.",
            ],
            [
                "<strong>Evidence Integrity</strong>",
                "Evidence manifests, correlations, chain-of-custody records, and forensic products remain linked to the active Case ID.",
            ],
            [
                "<strong>Threat Assessment</strong>",
                "The C#/.NET scoring engine evaluates current evidence and correlation records and produces canonical machine-readable assessment output.",
            ],
            [
                "<strong>Automation</strong>",
                "GitHub Actions coordinates evidence processing, scoring, lifecycle evaluation, reporting, validation, rendering, and verified repository updates.",
            ],
            [
                "<strong>Visualization Control</strong>",
                "The dashboard consumes synchronized investigation state and remains read-only with respect to authoritative case data.",
            ],
        ],
    )

    lifecycle = (
        "The active investigation persists across scheduled workflow executions "
        "and advances only when defined lifecycle conditions are satisfied.\n\n"
        "**Lifecycle**\n\n"
        "`CASE SCAN → EVIDENCE REVIEW → VALIDATION → ASSESSMENT → "
        "PROBLEM REVIEW → DISPOSITION / ARCHIVE`\n\n"
        f"{lifecycle_table}"
    )

    return (
        "# Active Investigation\n\n"
        f"{table}\n\n"
        f"{details('Analyst assessment and recommended response', assessment)}\n\n"
        f"{details('Investigation lifecycle and automation', lifecycle)}"
    )


def build_evidence_dashboard_section(case: dict) -> str:
    case_id = str(field(case, "case_id", "UNKNOWN-CASE"))
    paths = case_product_paths(case_id)

    manifest = load_json(paths["manifest"])
    correlation_data = load_json(paths["correlations"])

    evidence_items = manifest.get("evidence_items", [])
    if not isinstance(evidence_items, list):
        evidence_items = []

    correlations = correlation_data.get("correlations", [])
    if not isinstance(correlations, list):
        correlations = []

    evidence_count = len(evidence_items)
    if evidence_count == 0:
        evidence_count = safe_int(
            manifest.get("evidence_count", case.get("evidence_count"))
        )

    correlation_count = len(correlations)

    verified_statuses = {"verified", "validated", "confirmed", "intact"}
    verified_count = sum(
        1
        for item in evidence_items
        if str(item.get("integrity_status", "")).strip().lower()
        in verified_statuses
    )

    pending_review_count = sum(
        1
        for item in evidence_items
        if any(
            term in str(item.get("review_status", "")).strip().lower()
            for term in ("pending", "awaiting", "unreviewed")
        )
    )

    artifact_counts = Counter(
        str(item.get("artifact_type", "Unspecified Evidence")).strip()
        or "Unspecified Evidence"
        for item in evidence_items
    )

    finding_counts = Counter(
        str(correlation.get("finding", "Unspecified Finding")).strip()
        or "Unspecified Finding"
        for correlation in correlations
    )

    count_table = html_table(
        ["Evidence Records", "Correlations", "Integrity Verified", "Pending Review"],
        [[
            str(evidence_count),
            str(correlation_count),
            str(verified_count),
            str(pending_review_count),
        ]],
        aligns=["right", "right", "right", "right"],
    )

    evidence_rows = [
        [html_cell(name), str(count)]
        for name, count in artifact_counts.most_common()
    ]
    if not evidence_rows:
        evidence_rows = [["No evidence breakdown available", "0"]]

    finding_rows = [
        [html_cell(name), str(count)]
        for name, count in finding_counts.most_common()
    ]
    if not finding_rows:
        finding_rows = [["No correlated findings available", "0"]]

    workbook_rows = load_csv_rows(WORKBOOK_CSV_PATH)
    workbook_table = html_table(
        ["Date", "Case ID", "Severity", "Risk", "Confidence", "Status"],
        workbook_preview_rows(workbook_rows),
        aligns=["left", "left", "left", "right", "right", "left"],
    )

    workbook_refs = (
        f"{html_secondary_link('Open the complete GitHub CSV preview', 'workbooks/Exposure-Tracking-Matrix.csv')}<br>\n"
        f"{html_secondary_link('Download the formatted Excel workbook', 'workbooks/Exposure-Tracking-Matrix.xlsx')}"
        f"\n\n<br>\n\n{workbook_table}"
    )

    repository_updated = field(
        manifest,
        "generated_at",
        field(case, "date", "Not specified"),
    )

    return (
        "<!-- EVIDENCE_DASHBOARD_START -->\n\n"
        "# Digital Evidence Record\n\n"
        f"**Active Case:** {html_cell(case_id)}\n\n"
        f"{count_table}\n\n"
        f"{details('Evidence breakdown', html_table(['Evidence Type', 'Records'], evidence_rows, aligns=['left', 'right']))}\n\n"
        f"{details('Priority investigative findings', html_table(['Investigative Finding', 'Correlations'], finding_rows, aligns=['left', 'right']))}\n\n"
        f"{details('Exposure Tracking Matrix preview', workbook_refs)}\n\n"
        f"**Threat Family:** {html_cell(field(case, 'threat_family'))} · "
        f"**Repository Updated:** {html_cell(repository_updated)}\n\n"
        "<!-- EVIDENCE_DASHBOARD_END -->"
    )


def build_supporting_details(
    history: list[dict],
    operation: dict,
    case: dict,
) -> str:
    metrics = calculate_history_metrics(history)

    metrics_table = html_table(
        ["Metric", "Value"],
        [
            ["Total Investigations", str(metrics["total"])],
            ["Low / Moderate", f'{metrics["low"]} / {metrics["moderate"]}'],
            ["High / Critical", f'{metrics["high"]} / {metrics["critical"]}'],
            ["Closed Cases", str(metrics["closed_cases"])],
            ["Average Confidence", f'{metrics["average_confidence"]}%'],
            ["Total Evidence", format_number(operation.get("evidence_collected"))],
            ["Total Indicators", format_number(operation.get("ioc_count"))],
        ],
        aligns=["left", "right"],
    )

    recent_table = html_table(
        ["Case", "Classification", "Severity"],
        recent_investigation_rows(history),
    )

    metrics_body = (
        f"{metrics_table}\n\n"
        "### Recent Investigations\n\n"
        f"{recent_table}"
    )

    laboratories = operation.get("laboratories_under_review", [])
    laboratory_body = html_bullets(
        laboratories,
        "No laboratories currently under review",
    )

    score_text, level_text = canonical_threat_assessment(case)

    scoring_table = html_table(
        ["Capability", "Purpose"],
        [
            ["Evidence Evaluation", "Processes evidence records associated with the active Case ID."],
            ["Correlation Review", "Incorporates linked investigative findings into the threat assessment."],
            ["Threat Scoring", "Produces the canonical machine-readable threat score and classification."],
            ["JSON Intelligence Output", "Generates structured threat-assessment data for downstream automation and reporting."],
            ["XML Intelligence Output", "Produces a formal exchange record for validation and archival use."],
            ["Pipeline Integration", "Executes within the automated investigation workflow before downstream synchronization and rendering."],
        ],
    )

    scoring_body = (
        "The repository includes a functioning C#/.NET threat-assessment "
        "component that evaluates the active investigation against current "
        "evidence and correlation records.\n\n"
        f"{scoring_table}\n\n"
        f"**Current canonical assessment:** `{html_cell(score_text)}` · "
        f"`{html_cell(level_text)}`\n\n"
        "**Generated records**\n\n"
        f"{html_secondary_link('C# Canonical Threat Score — JSON', 'reports/bioterror_threat_score_csharp.json')}<br>\n"
        f"{html_secondary_link('C# Canonical Threat Score — XML', 'reports/bioterror_threat_score_csharp.xml')}"
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
        f"{details('Operational metrics and recent investigations', metrics_body)}\n\n"
        f"{details('Laboratories under review', laboratory_body)}\n\n"
        f"{details('C# / .NET threat-scoring engine', scoring_body)}\n\n"
        f"{details('Automated intelligence product catalog', html_bullets(products, 'No products available'))}"
    )


def build_mission_section() -> str:
    scope = (
        "BioDefense Intelligence Division is an independent cybersecurity "
        "research and training project developed to study the intersection of "
        "digital forensics, cyber-biosecurity, laboratory and pharmaceutical "
        "infrastructure, operational technology, evidence management, "
        "investigative automation, and persistent case analysis.\n\n"
        "The repository uses synthetic investigative records and does not "
        "represent an operational government, laboratory, healthcare, "
        "pharmaceutical, or commercial system. No institutional affiliation "
        "or endorsement is implied."
    )

    return (
        "# Investigative Mission\n\n"
        "Defensive cybersecurity research centered on cyber-enabled biosecurity "
        "investigations, laboratory and pharmaceutical security, protected "
        "research infrastructure, digital evidence management, forensic "
        "reconstruction, bioterror threat assessment, investigative intelligence "
        "production, operational technology, connected medical systems, and "
        "critical infrastructure.\n\n"
        f"{details('Project scope and research context', scope)}"
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
        build_overview_section(case, operation),
        build_campaign_dashboard(operation),
        build_active_investigation(case),
        build_evidence_dashboard_section(case),
        build_supporting_details(history, operation, case),
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
        new_content = existing + separator + report + "\n"

    README_PATH.write_text(new_content, encoding="utf-8")


def main() -> None:
    case = load_json(CURRENT_CASE_PATH)
    operation = load_json(ACTIVE_OPERATION_PATH)
    history = load_csv_rows(HISTORY_PATH)

    report = build_report(case, operation, history)
    update_readme(report)

    print(
        "Controlled README updated: "
        f"{len(history)} investigations, "
        f"{safe_int(operation.get('confirmed_intrusions'))} "
        "confirmed intrusions."
    )


if __name__ == "__main__":
    main()
