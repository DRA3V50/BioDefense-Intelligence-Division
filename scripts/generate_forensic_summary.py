from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json


CURRENT_CASE_FILE = Path("data/current_case.json")
EVIDENCE_ROOT = Path("evidence")


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


def get_first_value(data: dict, keys: list[str], default="Not specified"):
    for key in keys:
        value = data.get(key)

        if value not in (None, "", [], {}):
            return value

    return default


def normalize_text(value) -> str:
    return str(value or "").strip()


def get_case_paths(case_id: str) -> dict[str, Path]:
    case_directory = EVIDENCE_ROOT / case_id

    return {
        "directory": case_directory,
        "manifest": case_directory / "evidence_manifest.json",
        "correlations": case_directory / "evidence_correlations.json",
        "chain_of_custody": case_directory / "chain_of_custody.md",
        "output": case_directory / "forensic_summary.md",
    }


def get_evidence_items(manifest: dict) -> list[dict]:
    evidence_items = manifest.get("evidence_items", [])

    if isinstance(evidence_items, list):
        return [
            item for item in evidence_items
            if isinstance(item, dict)
        ]

    return []


def get_correlations(correlation_data: dict) -> list[dict]:
    correlations = correlation_data.get("correlations", [])

    if isinstance(correlations, list):
        return [
            item for item in correlations
            if isinstance(item, dict)
        ]

    return []


def count_verified_evidence(evidence_items: list[dict]) -> int:
    verified_statuses = {
        "verified",
        "validated",
        "confirmed",
        "intact",
    }

    return sum(
        1
        for item in evidence_items
        if normalize_text(
            item.get("integrity_status")
        ).lower() in verified_statuses
    )


def count_pending_review(evidence_items: list[dict]) -> int:
    pending_terms = {
        "pending",
        "pending review",
        "unreviewed",
        "awaiting review",
        "analyst review pending",
    }

    return sum(
        1
        for item in evidence_items
        if normalize_text(
            item.get("review_status")
        ).lower() in pending_terms
    )


def build_counter(
    records: list[dict],
    key: str,
    default="Unspecified",
) -> Counter:
    values = []

    for record in records:
        value = normalize_text(record.get(key))

        if not value:
            value = default

        values.append(value)

    return Counter(values)


def format_counter_lines(
    counter: Counter,
    empty_message: str,
) -> list[str]:
    if not counter:
        return [empty_message]

    return [
        f"- **{name}:** {count}"
        for name, count in counter.most_common()
    ]


def find_matching_evidence(
    evidence_items: list[dict],
    keywords: list[str],
) -> list[dict]:
    matches = []

    for item in evidence_items:
        searchable_fields = [
            item.get("artifact_type"),
            item.get("source_system"),
            item.get("description"),
            item.get("finding"),
            item.get("category"),
            item.get("vendor"),
        ]

        searchable_text = " ".join(
            normalize_text(value).lower()
            for value in searchable_fields
        )

        if any(
            keyword.lower() in searchable_text
            for keyword in keywords
        ):
            matches.append(item)

    return matches


def find_matching_correlations(
    correlations: list[dict],
    keywords: list[str],
) -> list[dict]:
    matches = []

    for item in correlations:
        searchable_fields = [
            item.get("finding"),
            item.get("artifact_type"),
            item.get("related_indicator"),
            item.get("analysis_status"),
            item.get("reasoning"),
            item.get("description"),
        ]

        searchable_text = " ".join(
            normalize_text(value).lower()
            for value in searchable_fields
        )

        if any(
            keyword.lower() in searchable_text
            for keyword in keywords
        ):
            matches.append(item)

    return matches


def build_category_section(
    evidence_items: list[dict],
    correlations: list[dict],
    evidence_keywords: list[str],
    correlation_keywords: list[str],
    no_finding_text: str,
) -> list[str]:
    matching_evidence = find_matching_evidence(
        evidence_items,
        evidence_keywords,
    )

    matching_correlations = find_matching_correlations(
        correlations,
        correlation_keywords,
    )

    lines = [
        f"**Relevant Evidence Records:** {len(matching_evidence)}",
        "",
        f"**Relevant Correlations:** {len(matching_correlations)}",
        "",
    ]

    finding_counter = build_counter(
        matching_correlations,
        "finding",
    )

    if finding_counter:
        lines.append("### Correlated Findings")
        lines.append("")

        for finding, count in finding_counter.most_common():
            lines.append(f"- **{finding}:** {count}")

        lines.append("")
    else:
        lines.append(no_finding_text)
        lines.append("")

    return lines


def build_executive_finding(
    case: dict,
    evidence_count: int,
    correlation_count: int,
) -> str:
    assessment = get_first_value(
        case,
        [
            "assessment",
            "investigation_summary",
            "summary",
            "analyst_assessment",
        ],
        "",
    )

    if assessment:
        return str(assessment)

    threat_family = get_first_value(
        case,
        ["threat_family", "threat_type"],
        "cyber-enabled biothreat activity",
    )

    return (
        f"Forensic review identified {evidence_count} evidence records "
        f"and {correlation_count} correlation records associated with "
        f"suspected {threat_family}. Findings remain subject to analyst "
        "validation and should not be treated as final attribution."
    )


def build_forensic_conclusion(
    case: dict,
    evidence_count: int,
    verified_count: int,
    correlation_count: int,
) -> str:
    threat_family = get_first_value(
        case,
        ["threat_family", "threat_type"],
        "cyber-biothreat activity",
    )

    containment_phase = get_first_value(
        case,
        [
            "containment_phase",
            "containment_status",
            "status",
        ],
        "Not specified",
    )

    if evidence_count == 0:
        return (
            "No evidence records were available for substantive forensic "
            "analysis. Additional collection is required before conclusions "
            "can be reached."
        )

    return (
        f"The forensic record contains {evidence_count} evidence artifacts, "
        f"of which {verified_count} passed integrity validation, together "
        f"with {correlation_count} investigative correlations. The current "
        f"record supports continued investigation into {threat_family}. "
        f"The case remains in the {containment_phase} phase. Additional "
        "analysis is required to determine threat actor intent, biological "
        "research impact, specimen integrity, and any potential public-health "
        "consequences."
    )


def generate_forensic_summary():
    case = load_json(CURRENT_CASE_FILE)

    if not case:
        raise FileNotFoundError(
            "Unable to load active case from data/current_case.json"
        )

    case_id = str(
        get_first_value(
            case,
            ["case_id", "id"],
            "UNKNOWN-CASE",
        )
    )

    paths = get_case_paths(case_id)

    manifest = load_json(paths["manifest"])
    correlation_data = load_json(paths["correlations"])

    evidence_items = get_evidence_items(manifest)
    correlations = get_correlations(correlation_data)

    evidence_count = len(evidence_items)
    correlation_count = len(correlations)
    verified_count = count_verified_evidence(evidence_items)
    pending_review_count = count_pending_review(evidence_items)

    artifact_types = build_counter(
        evidence_items,
        "artifact_type",
    )

    source_systems = build_counter(
        evidence_items,
        "source_system",
    )

    vendors = build_counter(
        evidence_items,
        "vendor",
    )

    findings = build_counter(
        correlations,
        "finding",
    )

    generated_at = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    report_lines = [
        "# BioDefense Intelligence Division",
        "",
        "## Forensic Summary",
        "",
        f"**Generated:** {generated_at}",
        "",
        "---",
        "",
        "## Investigation Information",
        "",
        f"**Case ID:** {case_id}",
        "",
        f"**Operation:** {get_first_value(case, ['operation'])}",
        "",
        f"**Campaign ID:** {get_first_value(case, ['campaign_id'])}",
        "",
        f"**Classification:** {get_first_value(case, ['classification'])}",
        "",
        f"**Threat Family:** {get_first_value(case, ['threat_family'])}",
        "",
        f"**Severity:** {get_first_value(case, ['severity'])}",
        "",
        f"**Risk Score:** {get_first_value(case, ['risk_score'])}",
        "",
        f"**Lead Analyst:** {get_first_value(case, ['lead_analyst'])}",
        "",
        f"**Investigation Status:** {get_first_value(case, ['status'])}",
        "",
        f"**Containment Phase:** {get_first_value(case, ['containment_phase'])}",
        "",
        "---",
        "",
        "## Executive Forensic Finding",
        "",
        build_executive_finding(
            case,
            evidence_count,
            correlation_count,
        ),
        "",
        "---",
        "",
        "## Evidence Overview",
        "",
        f"**Evidence Records Reviewed:** {evidence_count}",
        "",
        f"**Correlation Records Reviewed:** {correlation_count}",
        "",
        f"**Integrity-Verified Records:** {verified_count}",
        "",
        f"**Pending Analyst Review:** {pending_review_count}",
        "",
        f"**Chain of Custody:** "
        f"{'Available' if paths['chain_of_custody'].exists() else 'Not Available'}",
        "",
        "### Evidence Types",
        "",
    ]

    report_lines.extend(
        format_counter_lines(
            artifact_types,
            "No evidence types were available.",
        )
    )

    report_lines.extend(
        [
            "",
            "### Source Systems",
            "",
        ]
    )

    report_lines.extend(
        format_counter_lines(
            source_systems,
            "No source systems were identified.",
        )
    )

    report_lines.extend(
        [
            "",
            "### Vendors",
            "",
        ]
    )

    report_lines.extend(
        format_counter_lines(
            vendors,
            "No vendor information was available.",
        )
    )

    report_lines.extend(
        [
            "",
            "---",
            "",
            "## Authentication and Access Findings",
            "",
        ]
    )

    report_lines.extend(
        build_category_section(
            evidence_items,
            correlations,
            [
                "authentication",
                "credential",
                "access control",
                "login",
                "identity",
                "vpn",
            ],
            [
                "credential",
                "unauthorized access",
                "facility access",
                "authentication",
                "account",
            ],
            (
                "No authentication-specific forensic finding was identified "
                "in the current correlation record."
            ),
        )
    )

    report_lines.extend(
        [
            "---",
            "",
            "## Network and Command-and-Control Findings",
            "",
        ]
    )

    report_lines.extend(
        build_category_section(
            evidence_items,
            correlations,
            [
                "network",
                "firewall",
                "connection",
                "traffic",
                "dns",
                "proxy",
            ],
            [
                "network",
                "command-and-control",
                "c2",
                "communication",
                "exfiltration",
            ],
            (
                "No network or command-and-control finding was identified "
                "in the current correlation record."
            ),
        )
    )

    report_lines.extend(
        [
            "---",
            "",
            "## Laboratory-System Findings",
            "",
        ]
    )

    report_lines.extend(
        build_category_section(
            evidence_items,
            correlations,
            [
                "laboratory",
                "lims",
                "specimen",
                "biosecurity",
                "containment",
                "facility",
            ],
            [
                "laboratory",
                "specimen",
                "biosecurity",
                "containment",
                "facility",
            ],
            (
                "No laboratory-system-specific finding was identified "
                "in the current correlation record."
            ),
        )
    )

    report_lines.extend(
        [
            "---",
            "",
            "## Research and Genomic Findings",
            "",
        ]
    )

    report_lines.extend(
        build_category_section(
            evidence_items,
            correlations,
            [
                "research",
                "genomic",
                "genome",
                "biomedical",
                "sequence",
                "pathogen",
            ],
            [
                "research",
                "genomic",
                "biomedical",
                "data integrity",
                "modification",
            ],
            (
                "No research or genomic-specific finding was identified "
                "in the current correlation record."
            ),
        )
    )

    report_lines.extend(
        [
            "---",
            "",
            "## Containment and Recovery Findings",
            "",
        ]
    )

    report_lines.extend(
        build_category_section(
            evidence_items,
            correlations,
            [
                "containment",
                "recovery",
                "validation",
                "isolation",
                "remediation",
            ],
            [
                "containment",
                "recovery",
                "validation",
                "remediation",
            ],
            (
                "No containment or recovery-specific finding was identified "
                "in the current correlation record."
            ),
        )
    )

    report_lines.extend(
        [
            "---",
            "",
            "## Priority Correlated Findings",
            "",
        ]
    )

    report_lines.extend(
        format_counter_lines(
            findings,
            "No correlated findings were available.",
        )
    )

    report_lines.extend(
        [
            "",
            "---",
            "",
            "## Evidence Integrity Assessment",
            "",
            f"Integrity validation confirmed **{verified_count} of "
            f"{evidence_count}** evidence records.",
            "",
        ]
    )

    if evidence_count == 0:
        report_lines.append(
            "No evidence records were available for integrity review."
        )
    elif verified_count == evidence_count:
        report_lines.append(
            "All evidence records passed the recorded integrity validation."
        )
    elif verified_count > 0:
        report_lines.append(
            "Some evidence records passed integrity validation, while "
            "remaining records require additional review."
        )
    else:
        report_lines.append(
            "The current manifest does not identify any evidence records "
            "as integrity verified."
        )

    report_lines.extend(
        [
            "",
            "Integrity status reflects the values recorded in the evidence "
            "manifest and does not independently verify the underlying files.",
            "",
            "---",
            "",
            "## Forensic Conclusion",
            "",
            build_forensic_conclusion(
                case,
                evidence_count,
                verified_count,
                correlation_count,
            ),
            "",
            "---",
            "",
            "## Recommended Forensic Actions",
            "",
            "- Complete analyst review of pending evidence artifacts.",
            "- Validate access activity involving protected laboratory systems.",
            "- Review network evidence for command-and-control or exfiltration indicators.",
            "- Examine research and genomic records for unauthorized modification.",
            "- Confirm specimen-tracking and laboratory information-system integrity.",
            "- Correlate forensic findings with known threat actors and prior campaigns.",
            "- Preserve all artifacts under the documented chain-of-custody process.",
            "- Reassess biological and public-health impact as new evidence becomes available.",
            "",
            "---",
            "",
            "## Related Evidence Files",
            "",
            f"- [Evidence Manifest](evidence_manifest.json)",
            f"- [Evidence Correlations](evidence_correlations.json)",
            f"- [Chain of Custody](chain_of_custody.md)",
            f"- [Acquisition Summary](acquisition_summary.md)",
            "",
            "---",
            "",
            "## Investigative Notice",
            "",
            "This forensic summary is part of a fictional defensive "
            "cyber-biothreat intelligence simulation. Findings are generated "
            "for cybersecurity, digital forensics, biosecurity, and portfolio "
            "demonstration purposes.",
            "",
        ]
    )

    paths["directory"].mkdir(parents=True, exist_ok=True)

    paths["output"].write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print(f"Forensic summary generated: {paths['output']}")
    print(f"Case ID: {case_id}")
    print(f"Evidence records reviewed: {evidence_count}")
    print(f"Correlation records reviewed: {correlation_count}")
    print(f"Integrity-verified records: {verified_count}")


if __name__ == "__main__":
    generate_forensic_summary()
