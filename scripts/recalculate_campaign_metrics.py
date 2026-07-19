#!/usr/bin/env python3

"""
Recalculate campaign metrics from investigation_history.csv.

This script treats the investigation history as the source of truth and
updates both active_operation.json and operation_status.json.
"""

import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path
from statistics import mean

HISTORY_FILE = Path("data/investigation_history.csv")
OPERATION_FILE = Path("operations/active_operation.json")
STATUS_FILE = Path("operations/operation_status.json")

CLOSED_STATUSES = {
    "CLOSED",
    "RESOLVED",
    "ARCHIVED",
    "COMPLETE",
    "COMPLETED",
}


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")

    return data


def safe_int(value: object) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []

    with HISTORY_FILE.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def main() -> None:
    operation = load_json(OPERATION_FILE)
    rows = load_history()

    severity_counts = Counter(
        str(row.get("severity", "")).strip().upper()
        for row in rows
    )

    total_cases = len(rows)

    closed_cases = sum(
        1
        for row in rows
        if str(row.get("status", "")).strip().upper() in CLOSED_STATUSES
    )

    active_cases = total_cases - closed_cases

    evidence_total = sum(
        safe_int(row.get("evidence_count"))
        for row in rows
    )

    ioc_total = sum(
        safe_int(row.get("ioc_count"))
        for row in rows
    )

    confidences = [
        safe_int(row.get("confidence"))
        for row in rows
        if str(row.get("confidence", "")).strip()
    ]

    average_confidence = (
        round(mean(confidences), 1)
        if confidences
        else 0
    )

    threat_families = {
        str(row.get("threat_family", "")).strip()
        for row in rows
        if str(row.get("threat_family", "")).strip()
    }

    affected_platforms = {
        str(row.get("platform", "")).strip()
        for row in rows
        if str(row.get("platform", "")).strip()
    }

    confirmed_intrusions = severity_counts["CRITICAL"]

    # Update campaign dashboard data.
    operation["active_cases"] = active_cases
    operation["confirmed_intrusions"] = confirmed_intrusions
    operation["evidence_collected"] = evidence_total
    operation["ioc_count"] = ioc_total
    operation["known_threat_families"] = len(threat_families)

    # This represents distinct affected platform environments, not the
    # laboratories_under_review list.
    operation["affected_facilities"] = len(affected_platforms)
    operation["last_updated"] = date.today().isoformat()

    status = {
        "campaign_id": operation.get("campaign_id", "UNKNOWN"),
        "operation": operation.get("operation", "Unknown Operation"),
        "campaign_phase": operation.get("campaign_phase", "Unknown"),
        "total_cases": total_cases,
        "active_cases": active_cases,
        "closed_cases": closed_cases,
        "low_cases": severity_counts["LOW"],
        "moderate_cases": severity_counts["MODERATE"],
        "high_cases": severity_counts["HIGH"],
        "critical_cases": severity_counts["CRITICAL"],
        "affected_facilities": len(affected_platforms),
        "affected_states": safe_int(operation.get("affected_states")),
        "evidence_items": evidence_total,
        "digital_artifacts": safe_int(operation.get("digital_artifacts")),
        "ioc_count": ioc_total,
        "containment_level": operation.get(
            "containment_level",
            "ELEVATED",
        ),
        "average_confidence": average_confidence,
        "last_updated": date.today().isoformat(),
    }

    OPERATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OPERATION_FILE.open("w", encoding="utf-8") as file:
        json.dump(operation, file, indent=4)

    with STATUS_FILE.open("w", encoding="utf-8") as file:
        json.dump(status, file, indent=4)

    print(
        "Campaign metrics recalculated: "
        f"{total_cases} total cases, "
        f"{active_cases} active cases, "
        f"{evidence_total} evidence items, "
        f"{ioc_total} indicators."
    )


if __name__ == "__main__":
    main()
