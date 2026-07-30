#!/usr/bin/env python3

"""
Generate the active cyber-biothreat investigation leads report.

Reads:
    data/current_case.json
    data/investigation_history.csv
    evidence/<case_id>/evidence_manifest.json
    evidence/<case_id>/evidence_correlations.json

Writes:
    reports/investigative_leads.md
"""

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


CURRENT_CASE_PATH = Path("data/current_case.json")
HISTORY_PATH = Path("data/investigation_history.csv")
EVIDENCE_ROOT = Path("evidence")
OUTPUT_PATH = Path("reports/investigative_leads.md")


# -------------------------------------------------
# Data loading
# -------------------------------------------------

def load_json(path: Path) -> dict:
    """Load a JSON dictionary, returning an empty dictionary on failure."""

    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return data if isinstance(data, dict) else {}

    except (json.JSONDecodeError, OSError):
        return {}


def load_history(path: Path) -> list[dict]:
    """Load investigation-history records."""

    if not path.exists():
        return []

    try:
        with path.open(
            "r",
            newline="",
            encoding="utf-8",
        ) as file:
            return list(csv.DictReader(file))

    except OSError:
        return []


# -------------------------------------------------
# General helpers
# -------------------------------------------------

def get_first_value(
    data: dict,
    keys: list[str],
    default: str = "Not specified",
):
    """Return the first populated value from a list of possible keys."""

    for key in keys:
        value = data.get(key)

        if value not in (None, "", [], {}):
            return value

    return default


def normalize_text(value: object) -> str:
    """Convert a value into normalized display text."""

    return str(value or "").strip()


def safe_int(value: object, default: int = 0) -> int:
    """Convert a value into an integer safely."""

    try:
        return int(float(str(value).strip()))

    except (TypeError, ValueError):
        return default


def get_case_paths(case_id: str) -> dict[str, Path]:
    """Return evidence paths associated with the active case."""

    case_directory = EVIDENCE_ROOT / case_id

    return {
        "directory": case_directory,
        "manifest": case_directory / "evidence_manifest.json",
        "correlations": (
            case_directory / "evidence_correlations.json"
        ),
        "chain_of_custody": (
            case_directory / "chain_of_custody.md"
        ),
        "forensic_summary": (
            case_directory / "forensic_summary.md"
        ),
    }


def get_evidence_items(manifest: dict) -> list[dict]:
    """Return valid evidence items from the manifest."""

    evidence_items = manifest.get("evidence_items", [])

    if not isinstance(evidence_items, list):
        return []

    return [
        item
        for item in evidence_items
        if isinstance(item, dict)
    ]


def get_correlations(data: dict) -> list[dict]:
    """Return valid evidence-correlation records."""

    correlations = data.get("correlations", [])

    if not isinstance(correlations, list):
        return []

    return [
        item
        for item in correlations
        if isinstance(item, dict)
    ]


def get_correlation_evidence_ids(
    correlation: dict,
) -> list[str]:
    """Support both evidence_id and evidence_ids correlation schemas."""

    evidence_ids = correlation.get("evidence_ids")

    if isinstance(evidence_ids, list):
        return [
            normalize_text(evidence_id)
            for evidence_id in evidence_ids
            if normalize_text(evidence_id)
        ]

    evidence_id = normalize_text(
        correlation.get("evidence_id")
    )

    return [evidence_id] if evidence_id else []


def confidence_label(score: int) -> str:
    """Convert a numeric hypothesis score into a confidence label."""

    if score >= 70:
        return "HIGH"

    if score >= 45:
        return "MODERATE"

    if score >= 20:
        return "LOW"

    return "INSUFFICIENT EVIDENCE"


# -------------------------------------------------
# Evidence analysis
# -------------------------------------------------

def build_evidence_index(
    evidence_items: list[dict],
) -> dict[str, dict]:
    """Index evidence records by evidence ID."""

    evidence_index = {}

    for item in evidence_items:
        evidence_id = normalize_text(
            item.get("evidence_id")
        )

        if evidence_id:
            evidence_index[evidence_id] = item

    return evidence_index


def group_correlations_by_finding(
    correlations: list[dict],
) -> dict[str, list[dict]]:
    """Group correlation records by investigative finding."""

    groups = defaultdict(list)

    for correlation in correlations:
        finding = normalize_text(
            correlation.get("finding")
        )

        if not finding:
            finding = "Unspecified Investigative Finding"

        groups[finding].append(correlation)

    return dict(groups)


def build_finding_counter(
    correlations: list[dict],
) -> Counter:
    """Count correlated investigative findings."""

    return Counter(
        normalize_text(
            correlation.get("finding")
        )
        or "Unspecified Investigative Finding"
        for correlation in correlations
    )


def find_matching_count(
    finding_counter: Counter,
    keywords: list[str],
) -> int:
    """Count findings containing any supplied keyword."""

    total = 0

    for finding, count in finding_counter.items():
        finding_lower = finding.lower()

        if any(
            keyword.lower() in finding_lower
            for keyword in keywords
        ):
            total += count

    return total


def find_artifact_count(
    evidence_items: list[dict],
    keywords: list[str],
) -> int:
    """Count evidence records matching artifact or source keywords."""

    count = 0

    for item in evidence_items:
        searchable_text = " ".join(
            [
                normalize_text(item.get("artifact_type")),
                normalize_text(item.get("source_system")),
                normalize_text(item.get("category")),
                normalize_text(item.get("description")),
            ]
        ).lower()

        if any(
            keyword.lower() in searchable_text
            for keyword in keywords
        ):
            count += 1

    return count


def collect_supporting_evidence(
    correlation_group: list[dict],
    evidence_index: dict[str, dict],
    limit: int = 8,
) -> list[str]:
    """Create readable supporting-evidence lines for a finding."""

    evidence_ids = []

    for correlation in correlation_group:
        evidence_ids.extend(
            get_correlation_evidence_ids(correlation)
        )

    unique_ids = list(dict.fromkeys(evidence_ids))

    lines = []

    for evidence_id in unique_ids[:limit]:
        evidence = evidence_index.get(
            evidence_id,
            {},
        )

        artifact_type = normalize_text(
            evidence.get("artifact_type")
        ) or "Unspecified artifact"

        source_system = normalize_text(
            evidence.get("source_system")
        ) or "Unknown source"

        integrity_status = normalize_text(
            evidence.get("integrity_status")
        ) or "Unknown integrity status"

        lines.append(
            f"- `{evidence_id}` — {artifact_type}; "
            f"source: {source_system}; "
            f"integrity: {integrity_status}"
        )

    return lines


# -------------------------------------------------
# Investigative leads
# -------------------------------------------------

LEAD_DEFINITIONS = [
    {
        "title": "Credential and Identity Compromise",
        "finding_keywords": [
            "credential",
            "authentication",
            "account",
            "identity",
        ],
        "summary": (
            "Investigators should determine whether compromised "
            "credentials were obtained externally, reused from an "
            "earlier breach, or provided by an insider."
        ),
        "question": (
            "Which account was first compromised, and how was access "
            "obtained?"
        ),
    },
    {
        "title": "Possible Insider or Facility-Assisted Access",
        "finding_keywords": [
            "unauthorized facility",
            "insider",
            "access control",
            "physical access",
        ],
        "summary": (
            "Access-control and facility evidence may indicate insider "
            "assistance, unauthorized physical entry, or misuse of "
            "legitimate laboratory privileges."
        ),
        "question": (
            "Did an employee, contractor, or trusted partner facilitate "
            "the intrusion?"
        ),
    },
    {
        "title": "Laboratory-System Modification",
        "finding_keywords": [
            "laboratory system modification",
            "laboratory information system",
            "laboratory system",
            "lims",
        ],
        "summary": (
            "Laboratory-system changes require validation to determine "
            "whether configuration, workflow, specimen, or research "
            "records were altered."
        ),
        "question": (
            "Were the laboratory changes operational, administrative, "
            "or intended to affect protected biological research?"
        ),
    },
    {
        "title": "Research or Genomic Data Integrity",
        "finding_keywords": [
            "research data integrity",
            "genomic",
            "genome",
            "research data",
            "data integrity anomaly",
        ],
        "summary": (
            "Research-data anomalies should be examined for unauthorized "
            "modification, deletion, manipulation, or intelligence "
            "collection."
        ),
        "question": (
            "Were protected research records changed, copied, or prepared "
            "for exfiltration?"
        ),
    },
    {
        "title": "Command-and-Control and External Infrastructure",
        "finding_keywords": [
            "command-and-control",
            "command and control",
            "c2",
            "suspicious network",
            "network activity",
        ],
        "summary": (
            "Network correlations may identify external infrastructure, "
            "persistent access, data staging, or communication with a "
            "coordinated threat actor."
        ),
        "question": (
            "Does the external infrastructure connect this case to prior "
            "Operation Black Eclipse investigations?"
        ),
    },
    {
        "title": "Known Threat Actor Association",
        "finding_keywords": [
            "known threat actor",
            "threat actor indicator",
            "attribution",
        ],
        "summary": (
            "Threat-intelligence indicators should be validated before "
            "being used for attribution or campaign linkage."
        ),
        "question": (
            "Are the actor indicators independently corroborated by "
            "forensic evidence?"
        ),
    },
    {
        "title": "Biosecurity-Control Bypass",
        "finding_keywords": [
            "biosecurity policy violation",
            "biosecurity",
            "containment",
        ],
        "summary": (
            "Biosecurity-control findings require review to determine "
            "whether cyber access could affect protected laboratory "
            "operations or support cyber-to-physical escalation."
        ),
        "question": (
            "Were biosecurity controls bypassed intentionally, and did "
            "the bypass affect physical laboratory processes?"
        ),
    },
]


def build_active_leads(
    finding_groups: dict[str, list[dict]],
    evidence_index: dict[str, dict],
) -> list[dict]:
    """Build active leads from correlated findings."""

    leads = []

    for definition in LEAD_DEFINITIONS:
        matching_groups = {}

        for finding, records in finding_groups.items():
            finding_lower = finding.lower()

            if any(
                keyword.lower() in finding_lower
                for keyword in definition["finding_keywords"]
            ):
                matching_groups[finding] = records

        if not matching_groups:
            continue

        matching_records = []

        for records in matching_groups.values():
            matching_records.extend(records)

        evidence_lines = collect_supporting_evidence(
            matching_records,
            evidence_index,
        )

        leads.append(
            {
                "title": definition["title"],
                "summary": definition["summary"],
                "question": definition["question"],
                "correlation_count": len(matching_records),
                "findings": list(matching_groups.keys()),
                "evidence_lines": evidence_lines,
            }
        )

    return leads


# -------------------------------------------------
# Competing hypotheses
# -------------------------------------------------

def build_hypotheses(
    case: dict,
    finding_counter: Counter,
    evidence_items: list[dict],
) -> list[dict]:
    """Score competing investigative hypotheses."""

    severity = normalize_text(
        get_first_value(
            case,
            ["severity"],
            "UNKNOWN",
        )
    ).upper()

    risk_score = safe_int(
        get_first_value(
            case,
            ["risk_score"],
            0,
        )
    )

    credential_findings = find_matching_count(
        finding_counter,
        ["credential", "authentication", "account"],
    )

    network_findings = find_matching_count(
        finding_counter,
        [
            "network",
            "command-and-control",
            "command and control",
            "c2",
        ],
    )

    actor_findings = find_matching_count(
        finding_counter,
        ["known threat actor", "threat actor"],
    )

    laboratory_findings = find_matching_count(
        finding_counter,
        [
            "laboratory system modification",
            "laboratory information system",
            "laboratory system",
        ],
    )

    research_findings = find_matching_count(
        finding_counter,
        [
            "research data integrity",
            "research data",
            "genomic",
        ],
    )

    facility_findings = find_matching_count(
        finding_counter,
        [
            "unauthorized facility",
            "facility access",
            "insider",
        ],
    )

    biosecurity_findings = find_matching_count(
        finding_counter,
        [
            "biosecurity",
            "containment",
        ],
    )

    access_artifacts = find_artifact_count(
        evidence_items,
        [
            "authentication",
            "access control",
            "credential",
        ],
    )

    research_artifacts = find_artifact_count(
        evidence_items,
        [
            "research",
            "genomic",
            "laboratory",
            "specimen",
        ],
    )

    espionage_score = min(
        95,
        10
        + credential_findings * 3
        + network_findings * 2
        + actor_findings * 4
        + research_findings * 2
        + min(research_artifacts, 15),
    )

    sabotage_score = min(
        95,
        8
        + laboratory_findings * 4
        + research_findings * 3
        + biosecurity_findings * 2
        + min(research_artifacts, 12),
    )

    insider_score = min(
        95,
        5
        + credential_findings * 2
        + facility_findings * 5
        + laboratory_findings * 2
        + min(access_artifacts, 12),
    )

    attack_preparation_score = (
        5
        + biosecurity_findings * 3
        + facility_findings * 2
        + laboratory_findings * 2
        + research_findings * 2
    )

    if severity == "CRITICAL":
        attack_preparation_score += 15

    elif severity == "HIGH":
        attack_preparation_score += 8

    if risk_score >= 80:
        attack_preparation_score += 10

    elif risk_score >= 60:
        attack_preparation_score += 5

    attack_preparation_score = min(
        95,
        attack_preparation_score,
    )

    hypotheses = [
        {
            "name": "Biomedical Research Espionage",
            "score": espionage_score,
            "assessment": (
                "The intrusion may be intended to collect protected "
                "biomedical, genomic, laboratory, or research intelligence."
            ),
        },
        {
            "name": "Laboratory-System Sabotage",
            "score": sabotage_score,
            "assessment": (
                "The activity may be intended to alter laboratory systems, "
                "research records, operational configurations, or protected "
                "biosecurity processes."
            ),
        },
        {
            "name": "Insider-Facilitated Compromise",
            "score": insider_score,
            "assessment": (
                "A trusted employee, contractor, partner, or compromised "
                "authorized account may have facilitated access."
            ),
        },
        {
            "name": "Preparation for a Cyber-Enabled Biological Attack",
            "score": attack_preparation_score,
            "assessment": (
                "The activity may represent reconnaissance, access "
                "development, control bypass, or preparation for later "
                "cyber-to-physical escalation. This hypothesis requires "
                "direct supporting evidence before escalation."
            ),
        },
    ]

    return sorted(
        hypotheses,
        key=lambda item: item["score"],
        reverse=True,
    )


# -------------------------------------------------
# Gaps and collection priorities
# -------------------------------------------------

def build_intelligence_gaps(
    case: dict,
    finding_counter: Counter,
    evidence_items: list[dict],
) -> list[str]:
    """Identify unresolved intelligence requirements."""

    gaps = []

    actor_findings = find_matching_count(
        finding_counter,
        ["known threat actor", "threat actor"],
    )

    facility_findings = find_matching_count(
        finding_counter,
        ["facility access", "unauthorized facility", "insider"],
    )

    research_findings = find_matching_count(
        finding_counter,
        ["research data", "genomic", "data integrity"],
    )

    biosecurity_findings = find_matching_count(
        finding_counter,
        ["biosecurity", "containment"],
    )

    network_findings = find_matching_count(
        finding_counter,
        ["network", "command-and-control", "c2"],
    )

    pending_review = sum(
        1
        for item in evidence_items
        if any(
            term in normalize_text(
                item.get("review_status")
            ).lower()
            for term in (
                "pending",
                "awaiting",
                "unreviewed",
            )
        )
    )

    if actor_findings == 0:
        gaps.append(
            "Threat actor identity and attribution remain unresolved."
        )

    else:
        gaps.append(
            "Threat actor attribution requires independent forensic "
            "corroboration."
        )

    if facility_findings == 0:
        gaps.append(
            "No current correlation establishes whether insider or "
            "physical-facility assistance occurred."
        )

    if research_findings == 0:
        gaps.append(
            "The effect on genomic, biomedical, or protected research "
            "data has not been established."
        )

    if biosecurity_findings == 0:
        gaps.append(
            "The investigation has not established whether operational "
            "biosecurity controls were affected."
        )

    if network_findings == 0:
        gaps.append(
            "External infrastructure and command-and-control activity "
            "remain insufficiently documented."
        )

    gaps.extend(
        [
            "The investigation has not confirmed whether physical "
            "specimens or laboratory processes were affected.",
            "The threat actor's final objective—espionage, sabotage, "
            "disruption, or attack preparation—remains under assessment.",
            "Public-health consequences cannot be determined without "
            "validated biological-impact evidence.",
        ]
    )

    if pending_review > 0:
        gaps.append(
            f"{pending_review} evidence records remain pending analyst "
            "review."
        )

    return list(dict.fromkeys(gaps))


def build_collection_priorities(
    finding_counter: Counter,
) -> list[str]:
    """Build next evidence-collection priorities."""

    priorities = []

    if find_matching_count(
        finding_counter,
        ["credential", "authentication", "account"],
    ):
        priorities.append(
            "Reconstruct the complete credential-abuse timeline and "
            "identify the earliest unauthorized authentication event."
        )

    if find_matching_count(
        finding_counter,
        ["network", "command-and-control", "c2"],
    ):
        priorities.append(
            "Preserve network, firewall, proxy, DNS, and remote-access "
            "records associated with suspected external infrastructure."
        )

    if find_matching_count(
        finding_counter,
        ["laboratory system", "laboratory information system"],
    ):
        priorities.append(
            "Validate laboratory-system configurations and compare them "
            "with approved operational baselines."
        )

    if find_matching_count(
        finding_counter,
        ["research data", "genomic", "data integrity"],
    ):
        priorities.append(
            "Compare protected research and genomic records against "
            "known-good integrity baselines."
        )

    if find_matching_count(
        finding_counter,
        ["facility access", "unauthorized facility", "insider"],
    ):
        priorities.append(
            "Correlate physical-access records with account activity, "
            "work schedules, and contractor authorization data."
        )

    priorities.extend(
        [
            "Correlate active indicators with earlier Operation Black "
            "Eclipse investigations.",
            "Identify evidence that supports or contradicts each competing "
            "hypothesis.",
            "Confirm whether specimen-tracking, laboratory workflows, or "
            "physical research processes were affected.",
            "Document all new acquisitions under the active chain-of-custody "
            "process.",
            "Reassess biological and public-health risk after completing "
            "priority forensic review.",
        ]
    )

    return list(dict.fromkeys(priorities))


def find_related_cases(
    case: dict,
    history: list[dict],
    limit: int = 5,
) -> list[dict]:
    """Find previous cases with matching threat family or classification."""

    current_case_id = normalize_text(
        case.get("case_id")
    )

    threat_family = normalize_text(
        case.get("threat_family")
    ).lower()

    classification = normalize_text(
        case.get("classification")
    ).lower()

    related_cases = []

    for row in reversed(history):
        row_case_id = normalize_text(
            row.get("case_id")
        )

        if not row_case_id or row_case_id == current_case_id:
            continue

        row_threat_family = normalize_text(
            row.get("threat_family")
        ).lower()

        row_classification = normalize_text(
            row.get("classification")
        ).lower()

        reasons = []

        if (
            threat_family
            and row_threat_family
            and row_threat_family == threat_family
        ):
            reasons.append("matching threat family")

        if (
            classification
            and row_classification
            and row_classification == classification
        ):
            reasons.append("matching classification")

        if reasons:
            related_cases.append(
                {
                    "case_id": row_case_id,
                    "classification": normalize_text(
                        row.get("classification")
                    ) or "Unknown",
                    "severity": normalize_text(
                        row.get("severity")
                    ) or "Unknown",
                    "reason": ", ".join(reasons),
                }
            )

        if len(related_cases) >= limit:
            break

    return related_cases


# -------------------------------------------------
# Report generation
# -------------------------------------------------

def generate_investigative_leads() -> None:
    """Generate the active investigative leads report."""

    case = load_json(CURRENT_CASE_PATH)

    if not case:
        raise FileNotFoundError(
            "Unable to load data/current_case.json"
        )

    history = load_history(HISTORY_PATH)

    case_id = normalize_text(
        get_first_value(
            case,
            ["case_id", "id"],
            "UNKNOWN-CASE",
        )
    )

    paths = get_case_paths(case_id)

    manifest = load_json(paths["manifest"])
    correlation_data = load_json(
        paths["correlations"]
    )

    evidence_items = get_evidence_items(manifest)
    correlations = get_correlations(
        correlation_data
    )

    evidence_index = build_evidence_index(
        evidence_items
    )

    finding_groups = group_correlations_by_finding(
        correlations
    )

    finding_counter = build_finding_counter(
        correlations
    )

    active_leads = build_active_leads(
        finding_groups,
        evidence_index,
    )

    hypotheses = build_hypotheses(
        case,
        finding_counter,
        evidence_items,
    )

    intelligence_gaps = build_intelligence_gaps(
        case,
        finding_counter,
        evidence_items,
    )

    collection_priorities = build_collection_priorities(
        finding_counter
    )

    related_cases = find_related_cases(
        case,
        history,
    )

    generated_at = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")

    report_lines = [
        "# BioDefense Intelligence Division",
        "",
        "## Investigative Leads and Intelligence Gaps",
        "",
        f"**Generated:** {generated_at}",
        "",
        "---",
        "",
        "## Active Investigation",
        "",
        f"**Case ID:** {case_id}",
        "",
        f"**Operation:** "
        f"{get_first_value(case, ['operation'])}",
        "",
        f"**Campaign ID:** "
        f"{get_first_value(case, ['campaign_id'])}",
        "",
        f"**Classification:** "
        f"{get_first_value(case, ['classification'])}",
        "",
        f"**Threat Family:** "
        f"{get_first_value(case, ['threat_family'])}",
        "",
        f"**Severity:** "
        f"{get_first_value(case, ['severity'])}",
        "",
        f"**Risk Score:** "
        f"{get_first_value(case, ['risk_score'])}",
        "",
        f"**Lead Analyst:** "
        f"{get_first_value(case, ['lead_analyst'])}",
        "",
        f"**Evidence Records Reviewed:** "
        f"{len(evidence_items)}",
        "",
        f"**Correlation Records Reviewed:** "
        f"{len(correlations)}",
        "",
        "---",
        "",
        "## Current Analyst Assessment",
        "",
        normalize_text(
            get_first_value(
                case,
                ["assessment"],
                (
                    "The investigation remains active while analysts "
                    "evaluate the available cyber-biothreat evidence."
                ),
            )
        ),
        "",
        "This report distinguishes investigative leads and analytical "
        "hypotheses from confirmed findings. No hypothesis should be "
        "treated as final attribution without supporting evidence.",
        "",
        "---",
        "",
        "## Active Investigative Leads",
        "",
    ]

    if active_leads:
        for index, lead in enumerate(
            active_leads,
            start=1,
        ):
            report_lines.extend(
                [
                    f"### Lead {index}: {lead['title']}",
                    "",
                    f"**Supporting Correlations:** "
                    f"{lead['correlation_count']}",
                    "",
                    lead["summary"],
                    "",
                    "**Associated Findings:**",
                    "",
                ]
            )

            for finding in lead["findings"]:
                report_lines.append(
                    f"- {finding}"
                )

            report_lines.extend(
                [
                    "",
                    "**Supporting Evidence:**",
                    "",
                ]
            )

            if lead["evidence_lines"]:
                report_lines.extend(
                    lead["evidence_lines"]
                )

            else:
                report_lines.append(
                    "- No evidence identifiers were recorded for this lead."
                )

            report_lines.extend(
                [
                    "",
                    f"**Key Question:** {lead['question']}",
                    "",
                ]
            )

    else:
        report_lines.extend(
            [
                "No active investigative leads could be derived from "
                "the current correlation record.",
                "",
            ]
        )

    report_lines.extend(
        [
            "---",
            "",
            "## Competing Investigative Hypotheses",
            "",
            "| Hypothesis | Analytical Score | Confidence |",
            "|------------|-----------------:|------------|",
        ]
    )

    for hypothesis in hypotheses:
        report_lines.append(
            f"| {hypothesis['name']} "
            f"| {hypothesis['score']} "
            f"| {confidence_label(hypothesis['score'])} |"
        )

    report_lines.extend(
        [
            "",
            "### Hypothesis Assessments",
            "",
        ]
    )

    for hypothesis in hypotheses:
        report_lines.extend(
            [
                f"#### {hypothesis['name']}",
                "",
                f"**Confidence:** "
                f"{confidence_label(hypothesis['score'])}",
                "",
                hypothesis["assessment"],
                "",
            ]
        )

    report_lines.extend(
        [
            "---",
            "",
            "## Related Campaign Activity",
            "",
        ]
    )

    if related_cases:
        report_lines.extend(
            [
                "| Related Case | Classification | Severity | Link Basis |",
                "|--------------|----------------|----------|------------|",
            ]
        )

        for related_case in related_cases:
            report_lines.append(
                f"| {related_case['case_id']} "
                f"| {related_case['classification']} "
                f"| {related_case['severity']} "
                f"| {related_case['reason']} |"
            )

    else:
        report_lines.extend(
            [
                "No earlier investigation in the current history file "
                "matched the active threat family or classification.",
                "",
            ]
        )

    report_lines.extend(
        [
            "",
            "---",
            "",
            "## Intelligence Gaps",
            "",
        ]
    )

    for gap in intelligence_gaps:
        report_lines.append(
            f"- {gap}"
        )

    report_lines.extend(
        [
            "",
            "---",
            "",
            "## Unresolved Questions",
            "",
            "- Was the operation intended for biomedical espionage, "
            "laboratory sabotage, disruption, or attack preparation?",
            "- Was the initial access performed by an external threat "
            "actor or enabled by an insider?",
            "- Were protected biological research records copied, "
            "modified, deleted, or staged for exfiltration?",
            "- Were physical specimens, laboratory workflows, or "
            "biosecurity controls affected?",
            "- Does the external infrastructure overlap with earlier "
            "Operation Black Eclipse cases?",
            "- Which evidence supports the leading hypothesis, and which "
            "evidence contradicts it?",
            "- What additional evidence is required before attribution "
            "or public-health escalation?",
            "",
            "---",
            "",
            "## Next Collection Priorities",
            "",
        ]
    )

    for priority in collection_priorities:
        report_lines.append(
            f"- {priority}"
        )

    report_lines.extend(
        [
            "",
            "---",
            "",
            "## Investigation Resources",
            "",
            "- [Cyber-Biothreat Investigation Report]"
            "(investigation_report.md)",
            "- [Command Brief]"
            "(../operations/command_brief.md)",
            "- [Investigation Timeline]"
            "(../operations/investigation_timeline.md)",
            "- [Evidence Chain Analysis]"
            "(../evidence/evidence_chain.md)",
            f"- [Evidence Manifest]"
            f"(../evidence/{case_id}/evidence_manifest.json)",
            f"- [Evidence Correlations]"
            f"(../evidence/{case_id}/evidence_correlations.json)",
            f"- [Chain of Custody]"
            f"(../evidence/{case_id}/chain_of_custody.md)",
            f"- [Forensic Summary]"
            f"(../evidence/{case_id}/forensic_summary.md)",
            "",
            "---",
            "",
            "## Investigative Notice",
            "",
            "This report is part of a fictional defensive cyber-biothreat "
            "intelligence simulation. Investigative leads, hypotheses, "
            "and confidence assessments are generated for cybersecurity, "
            "digital forensics, biosecurity, and portfolio demonstration "
            "purposes.",
            "",
        ]
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    print(
        f"Investigative leads report generated: {OUTPUT_PATH}"
    )
    print(f"Case ID: {case_id}")
    print(f"Active leads: {len(active_leads)}")
    print(f"Evidence records reviewed: {len(evidence_items)}")
    print(f"Correlation records reviewed: {len(correlations)}")


if __name__ == "__main__":
    generate_investigative_leads()
