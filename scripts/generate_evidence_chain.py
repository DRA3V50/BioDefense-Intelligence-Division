#!/usr/bin/env python3

"""
Generate an evidence chain analysis for the active investigation.

The script reads the active case, evidence manifest, and evidence
correlations, then creates:

    evidence/evidence_chain.md
"""

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


CURRENT_CASE = Path("data/current_case.json")
EVIDENCE_MANIFEST = Path("evidence/evidence_manifest.json")
EVIDENCE_CORRELATIONS = Path("evidence/evidence_correlations.json")
OUTPUT_FILE = Path("evidence/evidence_chain.md")


def load_json(path):
    """Load a JSON file and return an empty structure if it is unavailable."""

    if not path.exists():
        print(f"Warning: {path} was not found.")
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError) as error:
        print(f"Warning: Could not read {path}: {error}")
        return {}


def normalize_list(data, possible_keys):
    """
    Return a list from either a top-level list or a dictionary containing
    one of the expected keys.
    """

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in possible_keys:
            value = data.get(key)

            if isinstance(value, list):
                return value

    return []


def first_value(record, keys, default="Unknown"):
    """Return the first available non-empty value from a dictionary."""

    if not isinstance(record, dict):
        return default

    for key in keys:
        value = record.get(key)

        if value not in (None, "", [], {}):
            return value

    return default


def normalize_evidence_ids(value):
    """Convert evidence references into a clean list of evidence IDs."""

    if value in (None, "", [], {}):
        return []

    if isinstance(value, str):
        return [
            item.strip()
            for item in value.replace(";", ",").split(",")
            if item.strip()
        ]

    if isinstance(value, list):
        evidence_ids = []

        for item in value:
            if isinstance(item, str):
                evidence_ids.append(item)
            elif isinstance(item, dict):
                evidence_id = first_value(
                    item,
                    [
                        "evidence_id",
                        "id",
                        "artifact_id",
                        "reference",
                    ],
                    default=None,
                )

                if evidence_id:
                    evidence_ids.append(str(evidence_id))

        return evidence_ids

    return [str(value)]


def build_evidence_lookup(manifest_records):
    """Create a lookup table keyed by evidence ID."""

    lookup = {}

    for record in manifest_records:
        evidence_id = first_value(
            record,
            [
                "evidence_id",
                "id",
                "artifact_id",
                "record_id",
            ],
            default=None,
        )

        if evidence_id:
            lookup[str(evidence_id)] = record

    return lookup


def build_finding_groups(correlation_records):
    """
    Group correlation records by investigative finding.

    Each group stores evidence IDs, confidence values, and reasoning text.
    """

    findings = defaultdict(
        lambda: {
            "evidence_ids": [],
            "confidence": [],
            "reasoning": [],
        }
    )

    for record in correlation_records:
        finding = first_value(
            record,
            [
                "finding",
                "finding_name",
                "finding_type",
                "correlation",
                "correlation_type",
                "title",
                "threat",
                "assessment",
            ],
            default="Unclassified Investigative Finding",
        )

        evidence_value = first_value(
            record,
            [
                "evidence_ids",
                "supporting_evidence",
                "related_evidence",
                "evidence",
                "artifacts",
                "artifact_ids",
            ],
            default=[],
        )

        evidence_ids = normalize_evidence_ids(evidence_value)

        confidence = first_value(
            record,
            [
                "confidence",
                "confidence_level",
                "assessment_confidence",
            ],
            default=None,
        )

        reasoning = first_value(
            record,
            [
                "reasoning",
                "analysis",
                "description",
                "summary",
                "assessment",
                "explanation",
            ],
            default=None,
        )

        findings[str(finding)]["evidence_ids"].extend(evidence_ids)

        if confidence is not None:
            findings[str(finding)]["confidence"].append(str(confidence))

        if reasoning:
            findings[str(finding)]["reasoning"].append(str(reasoning))

    return findings


def unique_values(values):
    """Remove duplicates while preserving original order."""

    return list(dict.fromkeys(values))


def determine_confidence(values, case_confidence):
    """Select the most useful confidence value for a finding."""

    values = unique_values(values)

    if values:
        return values[0]

    if case_confidence not in (None, "", "Unknown"):
        return f"{case_confidence}%"

    return "Not assessed"


def describe_evidence(evidence_id, evidence_lookup):
    """Create a readable Markdown line for an evidence item."""

    record = evidence_lookup.get(evidence_id, {})

    evidence_type = first_value(
        record,
        [
            "evidence_type",
            "type",
            "artifact_type",
            "category",
        ],
        default="Unclassified evidence",
    )

    description = first_value(
        record,
        [
            "description",
            "summary",
            "name",
            "title",
            "filename",
        ],
        default="No description available",
    )

    integrity = first_value(
        record,
        [
            "integrity_status",
            "integrity",
            "verification_status",
        ],
        default="Not recorded",
    )

    return (
        f"- **{evidence_id}** — {evidence_type}: "
        f"{description}  \n"
        f"  Integrity: **{integrity}**"
    )


def build_fallback_finding(case, manifest_records):
    """
    Create one basic finding when no correlation records are available.
    """

    threat_family = case.get(
        "threat_family",
        "Active Investigation Assessment",
    )

    evidence_ids = []

    for record in manifest_records[:10]:
        evidence_id = first_value(
            record,
            [
                "evidence_id",
                "id",
                "artifact_id",
                "record_id",
            ],
            default=None,
        )

        if evidence_id:
            evidence_ids.append(str(evidence_id))

    return {
        str(threat_family): {
            "evidence_ids": evidence_ids,
            "confidence": [str(case.get("confidence", "Unknown"))],
            "reasoning": [
                case.get(
                    "assessment",
                    (
                        "Available evidence remains under review for its "
                        "relationship to the active investigation."
                    ),
                )
            ],
        }
    }


def build_report(case, manifest_records, correlation_records):
    """Build the complete Markdown evidence-chain report."""

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    evidence_lookup = build_evidence_lookup(manifest_records)
    finding_groups = build_finding_groups(correlation_records)

    if not finding_groups:
        finding_groups = build_fallback_finding(case, manifest_records)

    case_id = case.get("case_id", "Unknown")
    classification = case.get("classification", "Unknown")
    threat_family = case.get("threat_family", "Unknown")
    severity = case.get("severity", "Unknown")
    priority = case.get("priority", "Unknown")
    case_confidence = case.get("confidence", "Unknown")

    sections = []

    for number, (finding, details) in enumerate(
        finding_groups.items(),
        start=1,
    ):
        evidence_ids = unique_values(details["evidence_ids"])
        reasoning_values = unique_values(details["reasoning"])

        confidence = determine_confidence(
            details["confidence"],
            case_confidence,
        )

        if evidence_ids:
            evidence_lines = [
                describe_evidence(evidence_id, evidence_lookup)
                for evidence_id in evidence_ids
            ]
        else:
            evidence_lines = [
                "- No specific evidence references were recorded for this finding."
            ]

        if reasoning_values:
            reasoning = " ".join(reasoning_values)
        else:
            reasoning = (
                "The finding was generated from available evidence "
                "correlation records. Additional analyst review is required."
            )

        section = f"""## Finding {number}: {finding}

**Confidence:** {confidence}

### Supporting Evidence

{chr(10).join(evidence_lines)}

### Investigative Reasoning

{reasoning}

### Analyst Assessment

The listed evidence supports further review of **{finding}** within
investigation **{case_id}**. Evidence integrity, source reliability, and
chain-of-custody records should be verified before final attribution.

---
"""

        sections.append(section)

    report = f"""# Evidence Chain Analysis

**Generated:** {now}

**Case ID:** {case_id}

**Classification:** {classification}

**Threat Family:** {threat_family}

**Severity:** {severity}

**Priority:** {priority}

**Case Confidence:** {case_confidence}%

---

## Purpose

This report connects investigative findings to their supporting digital
evidence. It provides a traceable reasoning path between collected artifacts,
evidence correlations, and the active case assessment.

---

## Evidence Chain Summary

- **Evidence records reviewed:** {len(manifest_records)}
- **Correlation records reviewed:** {len(correlation_records)}
- **Investigative findings:** {len(finding_groups)}

---

{chr(10).join(sections)}

## Investigation Resources

- [Evidence Manifest](evidence_manifest.json)
- [Evidence Correlations](evidence_correlations.json)
- [Chain of Custody](chain_of_custody.md)
- [Command Brief](../operations/command_brief.md)
- [Investigation Timeline](../operations/investigation_timeline.md)

---

End of Evidence Chain Analysis
"""

    return report


def main():
    case_data = load_json(CURRENT_CASE)
    manifest_data = load_json(EVIDENCE_MANIFEST)
    correlation_data = load_json(EVIDENCE_CORRELATIONS)

    manifest_records = normalize_list(
        manifest_data,
        [
            "evidence",
            "evidence_items",
            "records",
            "manifest",
            "artifacts",
        ],
    )

    correlation_records = normalize_list(
        correlation_data,
        [
            "correlations",
            "evidence_correlations",
            "findings",
            "records",
            "relationships",
        ],
    )

    report = build_report(
        case_data,
        manifest_records,
        correlation_records,
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(report, encoding="utf-8")

    print(f"Evidence chain generated: {OUTPUT_FILE}")
    print(f"Evidence records processed: {len(manifest_records)}")
    print(f"Correlation records processed: {len(correlation_records)}")


if __name__ == "__main__":
    main()
