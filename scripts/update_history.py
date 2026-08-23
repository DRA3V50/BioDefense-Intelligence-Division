#!/usr/bin/env python3
"""Idempotent compatibility index for persistent investigations.

The CSV is not authoritative state. It retains historical rows and keeps one
managed row per case instead of appending duplicates every workflow run.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from case_state import (
    CaseStateError,
    atomic_write_text,
    load_active_case,
    load_json_document,
    repository_root,
)


HISTORY_FILE = Path("data/investigation_history.csv")
ACTIVE_OPERATION_FILE = Path("operations/active_operation.json")
HEADER = [
    "date",
    "campaign_id",
    "case_id",
    "operation",
    "classification",
    "threat_family",
    "severity",
    "status",
    "campaign_phase",
    "platform",
    "device",
    "vendor",
    "zone",
    "confidence",
    "risk_score",
    "affected_assets",
    "evidence_count",
    "ioc_count",
    "initial_access",
    "lead_analyst",
    "priority",
]


def _history_path(root: Path | str | None) -> Path:
    return repository_root(root) / HISTORY_FILE


def _operation(root: Path | str | None) -> dict[str, Any]:
    return (
        load_json_document(
            repository_root(root) / ACTIVE_OPERATION_FILE,
            missing_ok=True,
        )
        or {}
    )


def _row_for_case(case: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": case["date"],
        "campaign_id": case["campaign_id"],
        "case_id": case["case_id"],
        "operation": case["operation"],
        "classification": case["classification"],
        "threat_family": case["threat_family"],
        "severity": case["severity"],
        "status": case["status"],
        "campaign_phase": operation.get("campaign_phase", ""),
        "platform": case["affected_platform"],
        "device": case["device_family"],
        "vendor": case["vendor"],
        "zone": case["network_zone"],
        "confidence": case["confidence"],
        "risk_score": case["risk_score"],
        "affected_assets": case["affected_assets"],
        "evidence_count": case["evidence_count"],
        "ioc_count": case["ioc_count"],
        "initial_access": case["initial_access"],
        "lead_analyst": case["lead_analyst"],
        "priority": case["priority"],
    }


def _read_history(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != HEADER:
            raise CaseStateError(
                "Investigation history header is unrecognized; it was not rewritten."
            )
        return list(reader)


def _serialize_history(rows: list[dict[str, Any]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=HEADER, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in HEADER})
    return stream.getvalue()


def sync_history(
    case: dict[str, Any], root: Path | str | None = None
) -> tuple[bool, bool]:
    """Return creation and update flags without rewriting unrelated rows."""

    path = _history_path(root)
    rows = _read_history(path)
    desired = {
        key: str(value)
        for key, value in _row_for_case(case, _operation(root)).items()
    }
    matches = [
        index for index, row in enumerate(rows) if row.get("case_id") == case["case_id"]
    ]
    if not matches:
        rows.append(desired)
        atomic_write_text(path, _serialize_history(rows))
        return True, False

    changed = False
    # Preserve pre-existing duplicate legacy rows; do not create any more.
    for index in matches:
        if rows[index] != desired:
            rows[index] = desired
            changed = True
    if changed:
        atomic_write_text(path, _serialize_history(rows))
    return False, changed


def main() -> None:
    case = load_active_case()
    if case is None:
        raise CaseStateError("No active case exists to index in investigation history.")
    created, updated = sync_history(case)
    if created:
        print("Investigation history row created.")
    elif updated:
        print("Investigation history row updated.")
    else:
        print("Investigation history already current.")


if __name__ == "__main__":
    main()
