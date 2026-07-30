#!/usr/bin/env python3

"""
Generate the active bioterror threat assessment.

Reads:
    data/current_case.json
    evidence/<case_id>/evidence_manifest.json
    evidence/<case_id>/evidence_correlations.json

Writes:
    reports/bioterror_threat_assessment.md
"""

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json


CURRENT_CASE_PATH = Path("data/current_case.json")
EVIDENCE_ROOT = Path("evidence")
OUTPUT_PATH = Path("reports/bioterror_threat_assessment.md")


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


def get_first_value(
    data: dict,
    keys: list[str],
    default="Not specified",
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


def clamp_score(value: int) -> int:
    """Restrict a score to the 0-100 range."""

    return max(0, min(100, int(value)))


def score_label(score: int) -> str:
    """Translate a numeric score into a readable analytical level."""

    if score >= 85:
        return "CRITICAL"

    if score >= 70:
        return "HIGH"

    if score >= 45:
        return "ELEVATED"

    if score >= 20:
        return "GUARDED"

    return "LOW"


def confidence_label(score: int) -> str:
    """Translate an assessment-confidence score into a label."""

    if score >= 85:
        return "HIGH"

    if score >= 60:
        return "MODERATE"

    if score >= 35:
        return "LOW"

    return "LIMITED"


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
    """Return valid correlation records."""

    correlations = data.get("correlations", [])

    if not isinstance(correlations, list):
        return []

    return [
        item
        for item in correlations
        if isinstance(item, dict)
    ]


def build_finding_counter(
    correlations: list[dict],
) -> Counter:
    """Count investigative findings."""

    return Counter(
        normalize_text(
            correlation.get("finding")
        )
        or "Unspecified Investigative Finding"
        for correlation in correlations
    )


def count_matching_findings(
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


def count_matching_evidence(
    evidence_items: list[dict],
    keywords: list[str],
) -> int:
    """Count evidence records matching artifact or source keywords."""

    total = 0

    for item in evidence_items:
        searchable_text = " ".join(
            [
                normalize_text(item.get("artifact_type")),
                normalize_text(item.get("source_system")),
                normalize_text(item.get("category")),
                normalize_text(item.get("description")),
                normalize_text(item.get("vendor")),
            ]
        ).lower()

        if any(
            keyword.lower() in searchable_text
            for keyword in keywords
        ):
            total += 1

    return total


def count_verified_evidence(
    evidence_items: list[dict],
) -> int:
    """Count integrity-verified evidence records."""

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
        ).lower()
        in verified_statuses
    )


def count_pending_review(
    evidence_items: list[dict],
) -> int:
    """Count evidence records awaiting analyst review."""

    pending_terms = (
        "pending",
        "awaiting",
        "unreviewed",
    )

    return sum(
        1
        for item in evidence_items
        if any(
            term in normalize_text(
                item.get("review_status")
            ).lower()
            for term in pending_terms
        )
    )


def severity_base_score(severity: str) -> int:
    """Return a base score for the active case severity."""

    return {
        "CRITICAL": 85,
        "HIGH": 70,
        "MODERATE": 50,
        "LOW": 25,
    }.get(severity.upper(), 35)


def build_dimension_scores(
    case: dict,
    evidence_items: list[dict],
    finding_counter: Counter,
) -> dict[str, int]:
    """Calculate the major bioterror threat-assessment dimensions."""

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
            severity_base_score(severity),
        )
    )

    case_confidence = safe_int(
        get_first_value(
            case,
            ["confidence", "assessment_confidence"],
            50,
        )
    )

    affected_assets = safe_int(
        get_first_value(
            case,
            ["affected_assets"],
            0,
        )
    )

    credential = count_matching_findings(
        finding_counter,
        [
            "credential",
            "authentication",
            "account",
            "identity",
        ],
    )

    network = count_matching_findings(
        finding_counter,
        [
            "network",
            "command-and-control",
            "command and control",
            "c2",
            "exfiltration",
        ],
    )

    laboratory = count_matching_findings(
        finding_counter,
        [
            "laboratory system",
            "laboratory information system",
            "laboratory modification",
            "lims",
        ],
    )

    research = count_matching_findings(
        finding_counter,
        [
            "research data",
            "genomic",
            "genome",
            "data integrity",
            "biomedical",
        ],
    )

    biosecurity = count_matching_findings(
        finding_counter,
        [
            "biosecurity",
            "containment",
            "policy violation",
        ],
    )

    facility = count_matching_findings(
        finding_counter,
        [
            "facility access",
            "unauthorized facility",
            "physical access",
            "insider",
        ],
    )

    actor = count_matching_findings(
        finding_counter,
        [
            "known threat actor",
            "threat actor indicator",
            "attribution",
        ],
    )

    workstation = count_matching_findings(
        finding_counter,
        [
            "workstation compromise",
            "research workstation",
            "endpoint compromise",
        ],
    )

    laboratory_artifacts = count_matching_evidence(
        evidence_items,
        [
            "laboratory",
            "lims",
            "specimen",
            "biosecurity",
        ],
    )

    research_artifacts = count_matching_evidence(
        evidence_items,
        [
            "research",
            "genomic",
            "genome",
            "sequence",
            "biomedical",
        ],
    )

    access_artifacts = count_matching_evidence(
        evidence_items,
        [
            "authentication",
            "access control",
            "credential",
            "vpn",
        ],
    )

    network_artifacts = count_matching_evidence(
        evidence_items,
        [
            "network",
            "firewall",
            "connection",
            "proxy",
            "dns",
        ],
    )

    intent_score = clamp_score(
        15
        + actor * 3
        + network * 2
        + research * 2
        + laboratory * 2
        + biosecurity * 2
        + min(risk_score // 4, 20)
    )

    capability_score = clamp_score(
        10
        + credential * 2
        + network * 2
        + workstation * 2
        + laboratory * 2
        + actor * 2
        + min(affected_assets, 20)
    )

    biological_target_value_score = clamp_score(
        20
        + laboratory * 2
        + research * 3
        + biosecurity * 2
        + min(laboratory_artifacts, 15)
        + min(research_artifacts, 20)
    )

    laboratory_specimen_impact_score = clamp_score(
        8
        + laboratory * 3
        + research * 2
        + biosecurity * 2
        + facility * 2
        + min(laboratory_artifacts, 18)
    )

    public_health_risk_score = clamp_score(
        5
        + biosecurity * 3
        + laboratory * 2
        + research * 2
        + facility * 2
        + (
            15
            if severity == "CRITICAL"
            else 8
            if severity == "HIGH"
            else 0
        )
    )

    cyber_physical_escalation_score = clamp_score(
        5
        + facility * 3
        + laboratory * 2
        + biosecurity * 3
        + network
        + min(access_artifacts, 10)
    )

    attribution_confidence_score = clamp_score(
        round(
            case_confidence * 0.55
            + min(actor * 5, 25)
            + min(network_artifacts, 10)
            + min(len(finding_counter), 10)
        )
    )

    containment_phase = normalize_text(
        get_first_value(
            case,
            [
                "containment_phase",
                "containment_status",
                "status",
            ],
            "Unknown",
        )
    ).lower()

    containment_bonus = 0

    if any(
        term in containment_phase
        for term in (
            "recovery",
            "contained",
            "remediation",
            "monitoring",
        )
    ):
        containment_bonus = 20

    if any(
        term in containment_phase
        for term in (
            "active compromise",
            "escalation",
            "uncontained",
        )
    ):
        containment_bonus = -15

    verified_count = count_verified_evidence(evidence_items)
    evidence_count = len(evidence_items)

    integrity_ratio = (
        verified_count / evidence_count
        if evidence_count
        else 0.0
    )

    containment_confidence_score = clamp_score(
        round(
            case_confidence * 0.45
            + integrity_ratio * 35
            + containment_bonus
        )
    )

    return {
        "Threat Actor Intent": intent_score,
        "Threat Actor Capability": capability_score,
        "Biological Target Value": biological_target_value_score,
        "Laboratory and Specimen Impact": (
            laboratory_specimen_impact_score
        ),
        "Public-Health Risk": public_health_risk_score,
        "Cyber-to-Physical Escalation": (
            cyber_physical_escalation_score
        ),
        "Attribution Confidence": attribution_confidence_score,
        "Containment Confidence": containment_confidence_score,
    }


def calculate_overall_score(
    dimension_scores: dict[str, int],
    case: dict,
) -> int:
    """Calculate the weighted overall bioterror threat score."""

    weights = {
        "Threat Actor Intent": 0.16,
        "Threat Actor Capability": 0.14,
        "Biological Target Value": 0.16,
        "Laboratory and Specimen Impact": 0.15,
        "Public-Health Risk": 0.16,
        "Cyber-to-Physical Escalation": 0.13,
        "Attribution Confidence": 0.05,
        "Containment Confidence": -0.05,
    }

    weighted_score = sum(
        dimension_scores[name] * weight
        for name, weight in weights.items()
    )

    case_risk_score = safe_int(
        get_first_value(
            case,
            ["risk_score"],
            0,
        )
    )

    final_score = round(
        weighted_score
        + case_risk_score * 0.10
    )

    return clamp_score(final_score)


def build_overall_assessment(
    case: dict,
    overall_score: int,
    dimension_scores: dict[str, int],
) -> str:
    """Build the executive threat-assessment narrative."""

    threat_family = get_first_value(
        case,
        ["threat_family"],
        "cyber-enabled biothreat activity",
    )

    classification = get_first_value(
        case,
        ["classification"],
        "Cyber-Biothreat Investigation",
    )

    highest_dimensions = sorted(
        dimension_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:3]

    highest_text = ", ".join(
        name.lower()
        for name, _ in highest_dimensions
    )

    return (
        f"The active {classification} concerns suspected "
        f"{threat_family}. The calculated overall bioterror threat "
        f"score is **{overall_score}/100 ({score_label(overall_score)})**. "
        f"The strongest risk drivers are {highest_text}. This assessment "
        "supports defensive prioritization and investigative planning; it "
        "does not establish that a biological agent was released or that "
        "a physical bioterror event occurred."
    )


def build_defensive_posture(
    overall_score: int,
    dimension_scores: dict[str, int],
) -> list[str]:
    """Build recommended defensive actions from the analytical scores."""

    actions = []

    if overall_score >= 85:
        actions.extend(
            [
                "Maintain immediate multi-disciplinary incident command with cyber, laboratory, biosecurity, and public-health representation.",
                "Restrict access to affected research systems and validate all privileged identities before restoring normal operations.",
                "Preserve volatile, network, identity, laboratory, specimen-tracking, and research-integrity evidence.",
            ]
        )

    elif overall_score >= 70:
        actions.extend(
            [
                "Maintain elevated cyber-biosecurity monitoring and formal command oversight.",
                "Prioritize validation of laboratory-system changes, research-data integrity, and remote-access activity.",
            ]
        )

    elif overall_score >= 45:
        actions.extend(
            [
                "Continue targeted monitoring and complete priority forensic review.",
                "Validate whether observed activity affected protected biological research or operational laboratory systems.",
            ]
        )

    else:
        actions.append(
            "Maintain routine defensive monitoring while resolving remaining intelligence gaps."
        )

    if dimension_scores["Public-Health Risk"] >= 70:
        actions.append(
            "Coordinate a precautionary public-health impact review without implying confirmed biological release."
        )

    if dimension_scores["Cyber-to-Physical Escalation"] >= 70:
        actions.append(
            "Review physical-access, facility-control, specimen-handling, and laboratory workflow records for cyber-to-physical linkage."
        )

    if dimension_scores["Attribution Confidence"] < 60:
        actions.append(
            "Avoid definitive attribution until threat-intelligence indicators are independently corroborated by forensic evidence."
        )

    if dimension_scores["Containment Confidence"] < 70:
        actions.append(
            "Revalidate containment and recovery controls before declaring operational closure."
        )

    actions.extend(
        [
            "Preserve all new artifacts under the documented chain-of-custody process.",
            "Reassess the threat score whenever new evidence, correlations, or containment results become available.",
        ]
    )

    return list(dict.fromkeys(actions))


def build_key_judgments(
    case: dict,
    dimension_scores: dict[str, int],
    finding_counter: Counter,
) -> list[str]:
    """Create concise intelligence judgments from the active evidence."""

    judgments = []

    threat_family = get_first_value(
        case,
        ["threat_family"],
        "cyber-biothreat activity",
    )

    judgments.append(
        f"The investigation currently centers on **{threat_family}**."
    )

    if dimension_scores["Biological Target Value"] >= 70:
        judgments.append(
            "The targeted environment has high intelligence or operational value because it supports protected laboratory, biomedical, genomic, or specimen-related activity."
        )

    if dimension_scores["Threat Actor Capability"] >= 70:
        judgments.append(
            "The available evidence indicates a capable actor with access sufficient to affect multiple cyber-biosecurity systems or data sources."
        )

    if dimension_scores["Public-Health Risk"] < 70:
        judgments.append(
            "The current record does not independently establish a direct public-health emergency or confirmed biological-material release."
        )
    else:
        judgments.append(
            "The evidence supports elevated public-health review, but direct biological impact still requires validated non-cyber evidence."
        )

    if count_matching_findings(
        finding_counter,
        [
            "known threat actor",
            "threat actor indicator",
        ],
    ):
        judgments.append(
            "Threat-actor indicators are present, but attribution should remain provisional until corroborated."
        )

    if count_matching_findings(
        finding_counter,
        [
            "research data integrity",
            "genomic",
            "laboratory system modification",
        ],
    ):
        judgments.append(
            "Research-data or laboratory-system integrity requires continued validation to determine whether observed changes were malicious."
        )

    return judgments


def generate_bioterror_threat_assessment() -> None:
    """Generate the active bioterror threat assessment."""

    case = load_json(CURRENT_CASE_PATH)

    if not case:
        raise FileNotFoundError(
            "Unable to load data/current_case.json"
        )

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

    finding_counter = build_finding_counter(
        correlations
    )

    dimension_scores = build_dimension_scores(
        case,
        evidence_items,
        finding_counter,
    )

    overall_score = calculate_overall_score(
        dimension_scores,
        case,
    )

    verified_count = count_verified_evidence(
        evidence_items
    )

    pending_review_count = count_pending_review(
        evidence_items
    )

    key_judgments = build_key_judgments(
        case,
        dimension_scores,
        finding_counter,
    )

    defensive_posture = build_defensive_posture(
        overall_score,
        dimension_scores,
    )

    generated_at = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")

    report_lines = [
        "# BioDefense Intelligence Division",
        "",
        "## Bioterror Threat Assessment",
        "",
        f"**Generated:** {generated_at}",
        "",
        "---",
        "",
        "## Active Investigation",
        "",
        f"**Case ID:** {case_id}",
        "",
        f"**Campaign ID:** "
        f"{get_first_value(case, ['campaign_id'])}",
        "",
        f"**Operation:** "
        f"{get_first_value(case, ['operation'])}",
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
        f"**Priority:** "
        f"{get_first_value(case, ['priority'])}",
        "",
        f"**Risk Score:** "
        f"{get_first_value(case, ['risk_score'])}",
        "",
        f"**Assessment Confidence:** "
        f"{get_first_value(case, ['confidence'])}%",
        "",
        f"**Containment Phase:** "
        f"{get_first_value(case, ['containment_phase'])}",
        "",
        f"**Affected Platform:** "
        f"{get_first_value(case, ['affected_platform'])}",
        "",
        f"**Affected Assets:** "
        f"{get_first_value(case, ['affected_assets'])}",
        "",
        "---",
        "",
        "## Executive Assessment",
        "",
        build_overall_assessment(
            case,
            overall_score,
            dimension_scores,
        ),
        "",
        f"**Overall Bioterror Threat Level:** "
        f"{score_label(overall_score)}",
        "",
        f"**Overall Bioterror Threat Score:** "
        f"{overall_score}/100",
        "",
        "---",
        "",
        "## Analytical Dimensions",
        "",
        "| Assessment Dimension | Score | Level |",
        "|----------------------|------:|-------|",
    ]

    for dimension, score in dimension_scores.items():
        label = (
            confidence_label(score)
            if "Confidence" in dimension
            else score_label(score)
        )

        report_lines.append(
            f"| {dimension} | {score}/100 | {label} |"
        )

    report_lines.extend(
        [
            "",
            "---",
            "",
            "## Key Intelligence Judgments",
            "",
        ]
    )

    for judgment in key_judgments:
        report_lines.append(
            f"- {judgment}"
        )

    report_lines.extend(
        [
            "",
            "---",
            "",
            "## Evidence Basis",
            "",
            f"**Evidence Records Reviewed:** "
            f"{len(evidence_items)}",
            "",
            f"**Correlation Records Reviewed:** "
            f"{len(correlations)}",
            "",
            f"**Integrity-Verified Records:** "
            f"{verified_count}",
            "",
            f"**Pending Analyst Review:** "
            f"{pending_review_count}",
            "",
            "### Priority Findings",
            "",
        ]
    )

    if finding_counter:
        for finding, count in finding_counter.most_common():
            report_lines.append(
                f"- **{finding}:** {count}"
            )
    else:
        report_lines.append(
            "- No correlated findings were available."
        )

    report_lines.extend(
        [
            "",
            "---",
            "",
            "## Threat Intent and Capability",
            "",
            f"**Intent Assessment:** "
            f"{dimension_scores['Threat Actor Intent']}/100 "
            f"({score_label(dimension_scores['Threat Actor Intent'])})",
            "",
            f"**Capability Assessment:** "
            f"{dimension_scores['Threat Actor Capability']}/100 "
            f"({score_label(dimension_scores['Threat Actor Capability'])})",
            "",
            "The intent and capability scores are analytical estimates "
            "derived from the active case, evidence manifest, and correlated "
            "findings. They do not constitute final attribution.",
            "",
            "---",
            "",
            "## Biological Target and Laboratory Impact",
            "",
            f"**Biological Target Value:** "
            f"{dimension_scores['Biological Target Value']}/100 "
            f"({score_label(dimension_scores['Biological Target Value'])})",
            "",
            f"**Laboratory and Specimen Impact:** "
            f"{dimension_scores['Laboratory and Specimen Impact']}/100 "
            f"({score_label(dimension_scores['Laboratory and Specimen Impact'])})",
            "",
            "Analysts should determine whether cyber activity affected "
            "protected research records, genomic information, laboratory "
            "configurations, specimen-tracking systems, or operational "
            "biosecurity controls.",
            "",
            "---",
            "",
            "## Public-Health and Cyber-to-Physical Risk",
            "",
            f"**Public-Health Risk:** "
            f"{dimension_scores['Public-Health Risk']}/100 "
            f"({score_label(dimension_scores['Public-Health Risk'])})",
            "",
            f"**Cyber-to-Physical Escalation:** "
            f"{dimension_scores['Cyber-to-Physical Escalation']}/100 "
            f"({score_label(dimension_scores['Cyber-to-Physical Escalation'])})",
            "",
            "No conclusion regarding biological-agent release, specimen "
            "compromise, or public-health impact should be made unless it "
            "is directly supported by validated evidence.",
            "",
            "---",
            "",
            "## Attribution and Containment Confidence",
            "",
            f"**Attribution Confidence:** "
            f"{dimension_scores['Attribution Confidence']}/100 "
            f"({confidence_label(dimension_scores['Attribution Confidence'])})",
            "",
            f"**Containment Confidence:** "
            f"{dimension_scores['Containment Confidence']}/100 "
            f"({confidence_label(dimension_scores['Containment Confidence'])})",
            "",
            "Attribution and containment confidence should be reassessed "
            "as additional evidence is reviewed and recovery controls are "
            "validated.",
            "",
            "---",
            "",
            "## Recommended Defensive Posture",
            "",
        ]
    )

    for action in defensive_posture:
        report_lines.append(
            f"- {action}"
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
            "- [Investigative Leads and Intelligence Gaps]"
            "(investigative_leads.md)",
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
            "## Analytical Notice",
            "",
            "This report is part of a fictional defensive cyber-biothreat "
            "intelligence simulation. Scores are generated from simulated "
            "case and evidence data for cybersecurity, digital forensics, "
            "biosecurity, and portfolio demonstration purposes. They are "
            "not real-world biological-threat determinations.",
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
        "Bioterror threat assessment generated: "
        f"{OUTPUT_PATH}"
    )
    print(f"Case ID: {case_id}")
    print(f"Overall threat score: {overall_score}/100")
    print(f"Overall threat level: {score_label(overall_score)}")
    print(f"Evidence records reviewed: {len(evidence_items)}")
    print(f"Correlation records reviewed: {len(correlations)}")


if __name__ == "__main__":
    generate_bioterror_threat_assessment()
