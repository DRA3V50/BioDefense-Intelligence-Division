"""
update_readme.py
 
Regenerates the auto-generated section of README.md for the
BioDefense-Intelligence-Division portfolio project.
 
Reads:
    data/current_case.json          -> active investigation snapshot
    operations/active_operation.json -> active campaign snapshot
    data/investigation_history.csv   -> historical investigation log
 
Writes:
    README.md (only the block between the FSE-REPORT markers is replaced)
"""
 
import csv
import json
from pathlib import Path
 
# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
 
ROOT = Path(__file__).resolve().parent.parent if False else Path(".")
 
CURRENT_CASE_PATH = Path("data/current_case.json")
ACTIVE_OPERATION_PATH = Path("operations/active_operation.json")
HISTORY_PATH = Path("data/investigation_history.csv")
README_PATH = Path("README.md")
 
REPORT_START = "<!-- FSE-REPORT-START -->"
REPORT_END = "<!-- FSE-REPORT-END -->"
 
 
# ---------------------------------------------------------------------------
# Data loading helpers (all fail gracefully)
# ---------------------------------------------------------------------------
 
def load_json(path: Path) -> dict:
    """Load a JSON file, returning an empty dict if it is missing or invalid."""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
 
 
def load_history(path: Path) -> list:
    """Load the investigation history CSV, returning an empty list if missing."""
    if not path.exists():
        return []
    try:
        with path.open("r", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []
 
 
# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
 
def field(data: dict, key: str, default: str = "Unknown") -> str:
    """Fetch a field from a dict, falling back to a default placeholder."""
    value = data.get(key, default)
    if value in (None, ""):
        return default
    return value
 
 
def to_number(value, default=0):
    """Best-effort numeric coercion; returns default on any failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
 
 
def format_list(items, empty_message="No data available") -> str:
    """Render a list of strings as a markdown bullet list."""
    if not items:
        return f"- {empty_message}"
    return "\n".join(f"- {item}" for item in items)
 
 
# ---------------------------------------------------------------------------
# Metric calculations (derived from investigation_history.csv)
# ---------------------------------------------------------------------------
 
def calculate_metrics(history: list) -> dict:
    """Compute aggregate operational metrics from the investigation history."""
 
    total = len(history)
 
    critical = sum(
        1 for h in history
        if h.get("severity", "").strip().upper() == "CRITICAL"
    )
 
    high = sum(
        1 for h in history
        if h.get("severity", "").strip().upper() == "HIGH"
    )
 
    confidences = [
        to_number(h.get("confidence")) for h in history if h.get("confidence")
    ]
    avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else 0
 
    total_evidence = sum(to_number(h.get("evidence_count")) for h in history)
    total_indicators = sum(to_number(h.get("ioc_count")) for h in history)
 
    active_cases = sum(
        1 for h in history
        if h.get("status", "").strip().lower() not in ("closed", "resolved", "")
    )
 
    confirmed_intrusions = sum(
        1 for h in history
        if "intrusion" in h.get("classification", "").strip().lower()
    )
 
    return {
        "total": total,
        "critical": critical,
        "high": high,
        "avg_confidence": avg_confidence,
        "total_evidence": int(total_evidence),
        "total_indicators": int(total_indicators),
        "active_cases": active_cases,
        "confirmed_intrusions": confirmed_intrusions,
    }
 
 
def recent_investigations_table(history: list, count: int = 5) -> str:
    """Build a markdown table of the most recent investigations."""
 
    dated = [h for h in history if h.get("case_id")]
 
    # Preserve file order (assumed chronological); take the last N and
    # reverse so the newest investigation appears first.
    recent = dated[-count:]
 
    header = "| Case | Classification | Severity |\n|------|---------------|----------|\n"
 
    if not recent:
        return header + "| No archived investigations | — | — |\n"
 
    rows = "".join(
        f"| {row.get('case_id', 'Unknown')} "
        f"| {row.get('classification', 'Unknown')} "
        f"| {row.get('severity', 'Unknown')} |\n"
        for row in reversed(recent)
    )
 
    return header + rows
 
 
# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------
 
def build_overview_section() -> str:
    return (
        "# BioDefense-Intelligence-Division\n\n"
        "BioDefense Intelligence Division is a cyber-biothreat investigation "
        "and digital forensics initiative inspired by federal investigative "
        "workflows. The project simulates how analysts identify, document, "
        "reconstruct, and manage cyber-enabled threats targeting biomedical "
        "research environments, protected laboratory infrastructure, and "
        "critical biosecurity systems through automated investigative "
        "workflows using Python and C#."
    )
 
 
def build_campaign_dashboard(op: dict) -> str:
    facilities = op.get("affected_facilities", [])
    states = op.get("affected_states", [])
 
    if isinstance(facilities, list):
        facilities_str = ", ".join(facilities) if facilities else "Unknown"
    else:
        facilities_str = field(op, "affected_facilities")
 
    if isinstance(states, list):
        states_str = ", ".join(states) if states else "Unknown"
    else:
        states_str = field(op, "affected_states")
 
    return (
        "# Active Campaign Dashboard\n\n"
        "| Campaign Overview | Campaign Status |\n"
        "|--------------------|-----------------|\n"
        f"| **Campaign ID**<br>{field(op, 'campaign_id')}<br><br>"
        f"**Operation**<br>{field(op, 'operation')}<br><br>"
        f"**Campaign Phase**<br>{field(op, 'campaign_phase')}<br><br>"
        f"**Threat Designation**<br>{field(op, 'threat_designation')}<br><br>"
        f"**Containment Level**<br>{field(op, 'containment_level')} "
        f"| **Confirmed Intrusions**<br>{field(op, 'confirmed_intrusions')}<br><br>"
        f"**Active Cases**<br>{field(op, 'active_cases')}<br><br>"
        f"**Evidence Collected**<br>{field(op, 'evidence_collected')}<br><br>"
        f"**Digital Artifacts**<br>{field(op, 'digital_artifacts')}<br><br>"
        f"**Indicators**<br>{field(op, "ioc_count")} |\n\n"
        "---\n\n"
        f"**Campaign Objective:** {field(op, 'campaign_objective')}\n\n"
        f"**Next Objective:** {field(op, 'next_objective')}\n\n"
        f"**Affected Facilities:** {facilities_str}\n\n"
        f"**Affected States:** {states_str}"
    )
 
 
def build_active_investigation(case: dict) -> str:
    return (
        "# Active Investigation\n\n"
        "| Investigation | Classification |\n"
        "|---------------|----------------|\n"
        f"| **Case ID**<br>{field(case, 'case_id')}<br><br>"
        f"**Classification**<br>{field(case, 'classification')}<br><br>"
        f"**Threat Family**<br>{field(case, 'threat_family')}<br><br>"
        f"**Severity**<br>{field(case, 'severity')} "
        f"| **Platform**<br>{field(case, 'affected_platform')}<br><br>"
        f"**Vendor**<br>{field(case, 'vendor')}<br><br>"
        f"**Device**<br>{field(case, 'device_family')}<br><br>"
        f"**Zone**<br>{field(case, 'network_zone')} |\n\n"
        "---\n\n"
        "| Investigation Status |\n"
        "|-----------------------|\n"
        f"| **Priority**<br>{field(case, 'priority')}<br><br>"
        f"**Confidence**<br>{field(case, 'confidence')}%<br><br>"
        f"**Evidence**<br>{field(case, 'evidence_count')}<br><br>"
        f"**Indicators**<br>{field(case, 'ioc_count')} |\n\n"
        "---\n\n"
        "# Analyst Assessment\n\n"
        f"{field(case, 'assessment', 'No assessment available.')}\n\n"
        "---\n\n"
        "# Current Response\n\n"
        f"- Lead Analyst: **{field(case, 'lead_analyst')}**\n"
        f"- Initial Access: **{field(case, 'initial_access')}**\n"
        f"- Recommended Action: **{field(case, 'recommended_action')}**"
    )
 
 
def build_operational_metrics(metrics: dict) -> str:
    return (
        "# Operational Metrics\n\n"
        "| Metric | Value |\n"
        "|---------|------:|\n"
        f"| Total Investigations | {metrics['total']} |\n"
        f"| High Severity Cases | {metrics['high']} |\n"
        f"| Critical Severity Cases | {metrics['critical']} |\n"
        f"| Average Confidence | {metrics['avg_confidence']}% |\n"
        f"| Total Evidence Collected | {metrics['total_evidence']} |\n"
        f"| Total Indicators | {metrics['total_indicators']} |\n"
        f"| Active Cases | {metrics['active_cases']} |\n"
        f"| Confirmed Intrusions | {metrics['confirmed_intrusions']} |"
    )
 
 
def build_recent_investigations(history: list) -> str:
    return "# Recent Investigations\n\n" + recent_investigations_table(history)
 
 
def build_laboratories_section(op: dict) -> str:
    labs = op.get("laboratories", [])
 
    if isinstance(labs, list) and labs and isinstance(labs[0], dict):
        header = "| Laboratory | Location | Status |\n|------------|----------|--------|\n"
        rows = "".join(
            f"| {lab.get('name', 'Unknown')} "
            f"| {lab.get('location', 'Unknown')} "
            f"| {lab.get('status', 'Unknown')} |\n"
            for lab in labs
        )
        body = header + rows
    else:
        body = format_list(labs if isinstance(labs, list) else [], "No laboratories currently under review")
 
    return "# Laboratories Under Review\n\n" + body
 
 
def build_mission_section() -> str:
    return (
        "# Division Mission\n\n"
        "BioDefense Intelligence Division is a defensive cybersecurity research "
        "project centered on cyber-enabled biosecurity investigations, protected "
        "research infrastructure, digital evidence management, forensic "
        "reconstruction, and coordinated incident response. The repository "
        "simulates how analysts document, track, and reconstruct complex "
        "investigations involving sensitive biomedical environments and "
        "critical operational systems."
    )
 
 
def build_toolkit_section() -> str:
    return (
        "# BioDefense Intelligence Toolkit (C#)\n\n"
        "The repository includes lightweight C# utilities representing internal "
        "applications used by a federal cyber-biosecurity investigative division "
        "during cyber-enabled bioterrorism investigations.\n\n"
        "| Utility | Purpose |\n"
        "|---------|---------|\n"
        "| BioThreatIntelligence | Correlates laboratory intrusion activity with active biosecurity investigations. |\n"
        "| GenomeEvidenceAnalyzer | Reviews genomic research evidence and validates chain-of-custody metadata. |\n"
        "| OutbreakCorrelationEngine | Links multiple cyber incidents into a single coordinated bioterror campaign. |\n"
        "| IncidentBriefGenerator | Produces executive intelligence briefings for command staff and partner agencies. |"
    )
 
 
def build_intelligence_products_section() -> str:
    products = [
        "Digital bioterrorism case files",
        "Laboratory intrusion assessments",
        "Protected research facility exposure reports",
        "Evidence reconstruction logs",
        "Chain-of-custody documentation",
        "Threat actor campaign summaries",
        "Biological research impact assessments",
        "Digital pathogen intelligence reports",
        "Compromised laboratory asset inventories",
        "Intelligence workbooks for investigative review",
        "Executive operational briefings",
        "Federal cyber-biosecurity situation reports",
    ]
    return (
        "# Automated Intelligence Products\n\n"
        "Every investigation automatically generates operational intelligence "
        "including:\n\n" + format_list(products)
    )
 
 
# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------
 
def build_report(case: dict, op: dict, history: list) -> str:
    metrics = calculate_metrics(history)
 
    sections = [
        build_overview_section(),
        build_campaign_dashboard(op),
        build_active_investigation(case),
        build_operational_metrics(metrics),
        build_recent_investigations(history),
        build_laboratories_section(op),
        build_mission_section(),
        build_toolkit_section(),
        build_intelligence_products_section(),
    ]
 
    body = "\n\n---\n\n".join(sections)
 
    return f"{REPORT_START}\n\n{body}\n\n{REPORT_END}"
 
 
def update_readme(report: str) -> None:
    """Replace the auto-generated block in README.md, preserving everything else."""
 
    if README_PATH.exists():
        existing = README_PATH.read_text(encoding="utf-8")
    else:
        existing = ""
 
    if REPORT_START in existing and REPORT_END in existing:
        before = existing.split(REPORT_START)[0]
        after = existing.split(REPORT_END)[1]
        new_content = before + report + after
    else:
        # No markers found yet -> append the report block to the end.
        separator = "\n\n" if existing and not existing.endswith("\n\n") else ""
        new_content = existing + separator + report + "\n"
 
    README_PATH.write_text(new_content, encoding="utf-8")
 
 
# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
 
def main() -> None:
    case = load_json(CURRENT_CASE_PATH)
    operation = load_json(ACTIVE_OPERATION_PATH)
    history = load_history(HISTORY_PATH)
 
    report = build_report(case, operation, history)
    update_readme(report)
 
    print("README updated.")
 
 
if __name__ == "__main__":
    main()
 
