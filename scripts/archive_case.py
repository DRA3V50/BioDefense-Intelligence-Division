#!/usr/bin/env python3
"""Terminal-only case archival for the persistent active-case lifecycle."""

from __future__ import annotations

import csv
import copy
from datetime import datetime
from pathlib import Path
from typing import Any

from case_lifecycle import load_validated_artifact_snapshot, mark_case_archived
from case_state import (
    TERMINAL_STATES,
    CaseStateError,
    StateValidationError,
    atomic_write_json,
    atomic_write_text,
    iso_timestamp,
    load_active_case,
    load_json_document,
    normalize_case_metadata,
    repository_root,
    utc_now,
    validate_active_case,
)
from update_history import sync_history


def _archive_paths(case_id: str, root: Path | str | None) -> tuple[Path, Path]:
    base = repository_root(root) / "cases" / "archive"
    return base / "json" / f"{case_id}.json", base / "reports" / f"{case_id}.md"


def _load_operation(root: Path | str | None) -> dict[str, Any]:
    operation = load_json_document(
        repository_root(root) / "operations" / "active_operation.json",
        missing_ok=True,
    )
    return operation or {}


def _validate_custody(case: dict[str, Any], root: Path | str | None) -> None:
    """Require the generated custody index to remain tied to the same case."""

    case_id = case["case_id"]
    path = repository_root(root) / "evidence" / case_id / "chain_of_custody.csv"
    if not path.exists():
        raise CaseStateError(
            f"Terminal archive requires chain-of-custody evidence at {path}."
        )
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "case_id" not in reader.fieldnames:
            raise StateValidationError("Chain-of-custody CSV has no case_id column.")
        rows = list(reader)
    if len(rows) != case["evidence_count"]:
        raise StateValidationError(
            "Chain-of-custody row count does not match active case evidence_count."
        )
    if any(row.get("case_id") != case_id for row in rows):
        raise StateValidationError(
            "Chain-of-custody CSV contains evidence for a different case."
        )


def _archive_report(case: dict[str, Any], operation: dict[str, Any]) -> str:
    return f"""# {case["case_id"]}

## Investigation Overview

- Operation: {case["operation"]}
- Campaign ID: {case["campaign_id"]}
- Campaign Phase Context: {operation.get("campaign_phase", "Unavailable")}
- Opened: {case["date"]}
- Lifecycle Status: {case["lifecycle_status"]}
- Workflow Stage: {case["current_stage"]}
- Terminal State: {case["lifecycle_status"]}

## Classification

- Classification: {case["classification"]}
- Threat Family: {case["threat_family"]}
- Severity: {case["severity"]}
- Priority: {case["priority"]}
- Legacy Case Status: {case["status"]}
- Containment: {case["containment_phase"]}

## Environment

- Platform: {case["affected_platform"]}
- Device: {case["device_family"]}
- Vendor: {case["vendor"]}
- Zone: {case["network_zone"]}
- Affected Assets: {case["affected_assets"]}

## Metrics

- Confidence: {case["confidence"]}%
- Risk Score: {case["risk_score"]}
- Evidence: {case["evidence_count"]}
- Indicators: {case["ioc_count"]}

## Assessment

{case["assessment"]}

## Closure

- Lead Analyst: {case["lead_analyst"]}
- Recommended Action: {case["recommended_action"]}
"""


def _validate_existing_archive(
    json_path: Path, report_path: Path, case: dict[str, Any]
) -> None:
    if report_path.exists() and not json_path.exists():
        raise StateValidationError(
            "Archive report exists without its JSON case snapshot; it was not replaced."
        )
    if not json_path.exists():
        return
    archived = load_json_document(json_path)
    if (
        archived.get("case_id") != case["case_id"]
        or archived.get("lifecycle_status") not in TERMINAL_STATES
    ):
        raise StateValidationError(
            "Existing archive JSON conflicts with the active terminal case."
        )
    if report_path.exists():
        report_text = report_path.read_text(encoding="utf-8")
        if case["case_id"] not in report_text:
            raise StateValidationError(
                "Existing archive report conflicts with the active terminal case."
            )


def archive_terminal_case(
    root: Path | str | None = None,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], bool]:
    """Archive one terminal case, then and only then release the active slot."""

    now = now or utc_now()
    case = load_active_case(root)
    if case is None:
        raise CaseStateError("No active case exists to archive.")
    case, _ = normalize_case_metadata(case, now)
    validate_active_case(case)
    if case["lifecycle_status"] not in TERMINAL_STATES:
        return case, False

    json_path, report_path = _archive_paths(case["case_id"], root)
    _validate_existing_archive(json_path, report_path, case)
    if case.get("archive_status") == "ARCHIVED":
        if not json_path.exists() or not report_path.exists():
            raise StateValidationError(
                "Active case claims ARCHIVED but its required archive files are missing."
            )
        return case, False

    load_validated_artifact_snapshot(case, root)
    _validate_custody(case, root)
    operation = _load_operation(root)
    archive_snapshot = copy.deepcopy(case)
    archive_snapshot["archive_status"] = "ARCHIVED"
    archive_snapshot["archived_at"] = iso_timestamp(now)
    archive_snapshot["updated_at"] = iso_timestamp(now)
    archive_snapshot["state_revision"] = int(case["state_revision"]) + 1
    validate_active_case(archive_snapshot, previous=case)
    if not json_path.exists():
        atomic_write_json(json_path, archive_snapshot)
    if not report_path.exists():
        atomic_write_text(report_path, _archive_report(archive_snapshot, operation))

    # History sync must succeed before the active slot can become eligible.
    sync_history(case, root)
    archived = mark_case_archived(root, now=now)
    return archived, True


def main() -> None:
    case, archived = archive_terminal_case()
    if archived:
        print(f"Archived terminal investigation {case['case_id']}.")
    elif case["lifecycle_status"] in TERMINAL_STATES:
        print(f"Terminal investigation {case['case_id']} archive already verified.")
    else:
        print(
            f"Archive skipped for active investigation {case['case_id']}; "
            "terminal lifecycle state is required."
        )


if __name__ == "__main__":
    main()
