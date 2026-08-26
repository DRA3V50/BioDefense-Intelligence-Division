#!/usr/bin/env python3
"""Perform deterministic, bounded work for the persisted active-case stage.

This worker intentionally does not choose workflow stages.  The following
``update_case_progress.py`` step remains the only lifecycle evaluator and may
perform at most one transition.  All work is driven by the current persisted
case and the matching evidence/correlation artifacts.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from case_lifecycle import (
    COMPLETED_REVIEW_STATUSES,
    load_validated_artifact_snapshot,
    mark_assessment_complete,
    record_problem_review_outcome,
)
from case_state import (
    ACTIVE_LIFECYCLE_STATUS,
    CaseStateError,
    StateValidationError,
    append_case_event,
    atomic_write_json,
    iso_timestamp,
    load_active_case,
    load_json_document,
    load_normalized_csharp_threat,
    repository_root,
    save_active_case,
    utc_now,
    validate_active_case,
)


EVIDENCE_ROOT = Path("evidence")
REVIEW_PENDING = "PENDING ANALYST REVIEW"
REVIEW_COMPLETED = {"REVIEWED", "VALIDATED"}
CORRELATION_PENDING = "CORRELATED"
CORRELATION_COMPLETED = {"VALIDATED"}
TERMINAL_POLICY_SEVERITIES = {"LOW", "MODERATE", "HIGH", "CRITICAL"}
TERMINAL_POLICY_NAME = "terminal-disposition-v1"


@dataclass(frozen=True)
class StageWorkResult:
    """A read-friendly summary of one deterministic stage-work attempt."""

    case: dict[str, Any]
    stage: str
    changed: bool
    action: str
    reason: str
    processed_ids: tuple[str, ...] = ()
    completed_count: int = 0
    total_count: int = 0
    outcome: str | None = None


def _status(value: object) -> str:
    return str(value or "").strip().upper()


def _artifact_paths(case_id: str, root: Path | str | None) -> tuple[Path, Path]:
    directory = repository_root(root) / EVIDENCE_ROOT / case_id
    return directory / "evidence_manifest.json", directory / "evidence_correlations.json"


def _result(
    case: dict[str, Any],
    *,
    changed: bool,
    action: str,
    reason: str,
    processed_ids: tuple[str, ...] = (),
    completed_count: int = 0,
    total_count: int = 0,
    outcome: str | None = None,
) -> StageWorkResult:
    return StageWorkResult(
        case=case,
        stage=str(case["current_stage"]),
        changed=changed,
        action=action,
        reason=reason,
        processed_ids=processed_ids,
        completed_count=completed_count,
        total_count=total_count,
        outcome=outcome,
    )


def _prepared_case_activity(
    case: dict[str, Any],
    root: Path | str | None,
    now: datetime,
    *,
    activity: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Prepare one valid, same-stage authoritative case revision.

    The artifact document is written only after this prospective case is
    validated.  ``stage_updated_at`` is deliberately untouched: this script
    performs work, while the lifecycle step owns stage changes.
    """

    previous = copy.deepcopy(case)
    updated = copy.deepcopy(case)
    updated["updated_at"] = iso_timestamp(now)
    updated["state_revision"] = int(previous["state_revision"]) + 1
    # Timestamp/revision-only saves are intentionally rejected by case_state.
    # This persisted summary makes the bounded work itself auditable without
    # changing the current workflow stage or any source evidence provenance.
    updated["stage_work"] = {
        "stage": case["current_stage"],
        "recorded_at": updated["updated_at"],
        **activity,
    }
    validate_active_case(updated, previous=previous)
    return previous, updated


def _commit_case_activity(
    previous: dict[str, Any],
    updated: dict[str, Any],
    root: Path | str | None,
) -> dict[str, Any]:
    save_active_case(updated, root, previous=previous)
    return updated


def _artifact_blocker(case: dict[str, Any], error: Exception) -> StageWorkResult:
    return _result(
        case,
        changed=False,
        action="BLOCKED",
        reason=f"artifact prerequisite blocked stage work: {error}",
    )


def _process_evidence_review(
    case: dict[str, Any], root: Path | str | None, now: datetime
) -> StageWorkResult:
    try:
        artifacts = load_validated_artifact_snapshot(case, root)
    except CaseStateError as error:
        return _artifact_blocker(case, error)
    if not artifacts.evidence_items:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason="evidence review requires a matching evidence manifest.",
        )

    statuses = {_status(item.get("review_status")) for item in artifacts.evidence_items}
    unexpected = statuses - {REVIEW_PENDING, *REVIEW_COMPLETED}
    if unexpected:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason=(
                "evidence review found unsupported review status values: "
                f"{sorted(unexpected)}"
            ),
        )

    total = len(artifacts.evidence_items)
    completed_before = sum(
        _status(item.get("review_status")) in REVIEW_COMPLETED
        for item in artifacts.evidence_items
    )
    pending_ids = sorted(
        str(item["evidence_id"])
        for item in artifacts.evidence_items
        if _status(item.get("review_status")) == REVIEW_PENDING
    )
    if not pending_ids:
        return _result(
            case,
            changed=False,
            action="NOOP",
            reason="all evidence records are already reviewed.",
            completed_count=completed_before,
            total_count=total,
        )

    batch_size = max(1, math.ceil(total / 6))
    selected_ids = tuple(pending_ids[:batch_size])
    selected = set(selected_ids)
    manifest_path, _ = _artifact_paths(str(case["case_id"]), root)
    manifest = load_json_document(manifest_path)
    if manifest is None:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason="evidence manifest disappeared before review work could begin.",
        )
    stamp = iso_timestamp(now)
    for item in manifest["evidence_items"]:
        if item.get("evidence_id") in selected:
            item["review_status"] = "Reviewed"
            item["reviewed_at"] = stamp
    completed_after = completed_before + len(selected_ids)
    processing = manifest.get("lifecycle_processing")
    if not isinstance(processing, dict):
        processing = {}
    manifest["lifecycle_processing"] = {
        **processing,
        "reviewed_count": completed_after,
        "total_evidence_count": total,
        "last_review_batch_size": len(selected_ids),
        "last_reviewed_at": stamp,
        "last_updated_by": "process_active_case_stage",
    }
    manifest["updated_at"] = stamp

    previous, updated = _prepared_case_activity(
        case,
        root,
        now,
        activity={
            "action": "EVIDENCE_REVIEW_BATCH",
            "completed_count": completed_after,
            "total_count": total,
            "processed_count": len(selected_ids),
            "processed_through_id": selected_ids[-1],
        },
    )
    atomic_write_json(manifest_path, manifest)
    updated = _commit_case_activity(previous, updated, root)
    append_case_event(
        updated,
        event_type="EVIDENCE_REVIEW_PROGRESS",
        message=f"Evidence review progress: {completed_after}/{total} reviewed",
        source="process_active_case_stage",
        intensity=45,
        idempotency_key=f"evidence-review-{completed_after}-of-{total}",
        timestamp=now,
        root=root,
    )
    return _result(
        updated,
        changed=True,
        action="EVIDENCE_REVIEW_BATCH",
        reason=(
            f"reviewed deterministic evidence batch of {len(selected_ids)} "
            f"from {total} records."
        ),
        processed_ids=selected_ids,
        completed_count=completed_after,
        total_count=total,
    )


def _process_validation(
    case: dict[str, Any], root: Path | str | None, now: datetime
) -> StageWorkResult:
    try:
        artifacts = load_validated_artifact_snapshot(case, root)
    except CaseStateError as error:
        return _artifact_blocker(case, error)
    if not artifacts.evidence_items or not artifacts.correlations:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason="validation requires matching evidence and correlations.",
        )
    if not all(
        _status(item.get("review_status")) in REVIEW_COMPLETED
        for item in artifacts.evidence_items
    ):
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason="validation cannot begin until all evidence review is complete.",
        )

    statuses = {_status(item.get("analysis_status")) for item in artifacts.correlations}
    unexpected = statuses - {CORRELATION_PENDING, *CORRELATION_COMPLETED}
    if unexpected:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason=(
                "correlation validation found unsupported analysis status values: "
                f"{sorted(unexpected)}"
            ),
        )

    total = len(artifacts.correlations)
    completed_before = sum(
        _status(item.get("analysis_status")) in CORRELATION_COMPLETED
        for item in artifacts.correlations
    )
    # Correlation records have a one-to-one, stable existing evidence_id linkage.
    pending_ids = sorted(
        str(item["evidence_id"])
        for item in artifacts.correlations
        if _status(item.get("analysis_status")) == CORRELATION_PENDING
    )
    if not pending_ids:
        return _result(
            case,
            changed=False,
            action="NOOP",
            reason="all correlation records are already validated.",
            completed_count=completed_before,
            total_count=total,
        )

    batch_size = max(1, math.ceil(total / 3))
    selected_ids = tuple(pending_ids[:batch_size])
    selected = set(selected_ids)
    _, correlations_path = _artifact_paths(str(case["case_id"]), root)
    correlations_document = load_json_document(correlations_path)
    if correlations_document is None:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason="correlation document disappeared before validation could begin.",
        )
    stamp = iso_timestamp(now)
    for item in correlations_document["correlations"]:
        if item.get("evidence_id") in selected:
            item["analysis_status"] = "Validated"
            item["validated_at"] = stamp
    completed_after = completed_before + len(selected_ids)
    processing = correlations_document.get("lifecycle_processing")
    if not isinstance(processing, dict):
        processing = {}
    correlations_document["lifecycle_processing"] = {
        **processing,
        "validated_count": completed_after,
        "total_correlation_count": total,
        "last_validation_batch_size": len(selected_ids),
        "last_validated_at": stamp,
        "last_updated_by": "process_active_case_stage",
    }
    correlations_document["updated_at"] = stamp

    previous, updated = _prepared_case_activity(
        case,
        root,
        now,
        activity={
            "action": "CORRELATION_VALIDATION_BATCH",
            "completed_count": completed_after,
            "total_count": total,
            "processed_count": len(selected_ids),
            "processed_through_id": selected_ids[-1],
        },
    )
    atomic_write_json(correlations_path, correlations_document)
    updated = _commit_case_activity(previous, updated, root)
    append_case_event(
        updated,
        event_type="CORRELATION_VALIDATION_PROGRESS",
        message=f"Correlation validation progress: {completed_after}/{total} validated",
        source="process_active_case_stage",
        intensity=58,
        idempotency_key=f"correlation-validation-{completed_after}-of-{total}",
        timestamp=now,
        root=root,
    )
    return _result(
        updated,
        changed=True,
        action="CORRELATION_VALIDATION_BATCH",
        reason=(
            f"validated deterministic correlation batch of {len(selected_ids)} "
            f"from {total} records."
        ),
        processed_ids=selected_ids,
        completed_count=completed_after,
        total_count=total,
    )


def _assessment_prerequisites(
    case: dict[str, Any], root: Path | str | None
) -> tuple[bool, str]:
    try:
        artifacts = load_validated_artifact_snapshot(case, root)
    except CaseStateError as error:
        return False, f"artifact prerequisite blocked assessment: {error}"
    if not artifacts.evidence_items or not all(
        _status(item.get("review_status")) in REVIEW_COMPLETED
        for item in artifacts.evidence_items
    ):
        return False, "assessment requires completed evidence review."
    if not artifacts.correlations or not all(
        _status(item.get("analysis_status")) in CORRELATION_COMPLETED
        for item in artifacts.correlations
    ):
        return False, "assessment requires validated correlations."
    if not str(case.get("assessment", "")).strip():
        return False, "assessment requires persisted assessment material."
    return True, "assessment prerequisites are complete."


def _process_assessment(
    case: dict[str, Any], root: Path | str | None, now: datetime
) -> StageWorkResult:
    ready, reason = _assessment_prerequisites(case, root)
    if not ready:
        return _result(case, changed=False, action="BLOCKED", reason=reason)
    try:
        threat = load_normalized_csharp_threat(case, root)
    except CaseStateError as error:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason=f"assessment requires a current canonical C# report: {error}",
        )
    if threat is None:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason="assessment requires a current canonical C# report.",
        )
    if case.get("assessment_completed_at"):
        return _result(
            case,
            changed=False,
            action="NOOP",
            reason="assessment completion is already recorded.",
        )
    try:
        updated = mark_assessment_complete(root, now=now)
    except CaseStateError as error:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason=f"assessment completion was blocked: {error}",
        )
    return _result(
        updated,
        changed=True,
        action="ASSESSMENT_COMPLETED",
        reason="assessment completion was recorded through case_lifecycle.",
    )


def _problem_review_prerequisites(
    case: dict[str, Any], root: Path | str | None
) -> tuple[bool, str]:
    ready, reason = _assessment_prerequisites(case, root)
    if not ready:
        return ready, reason
    if not case.get("assessment_completed_at"):
        return False, "problem review requires assessment_completed_at."
    return True, "problem-review prerequisites are complete."


def _process_problem_review(
    case: dict[str, Any], root: Path | str | None, now: datetime
) -> StageWorkResult:
    ready, reason = _problem_review_prerequisites(case, root)
    if not ready:
        return _result(case, changed=False, action="BLOCKED", reason=reason)
    if case.get("problem_review_outcome"):
        return _result(
            case,
            changed=False,
            action="NOOP",
            reason="an explicit problem-review outcome is already recorded.",
            outcome=str(case["problem_review_outcome"]),
        )
    try:
        threat = load_normalized_csharp_threat(case, root)
    except CaseStateError as error:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason=f"canonical C# report blocked terminal disposition: {error}",
        )
    if threat is None:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason="canonical C# report is required for terminal disposition.",
        )

    score = threat.get("score")
    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason="canonical C# score is missing, malformed, or outside 0..100.",
        )
    severity = _status(case.get("severity"))
    if severity not in TERMINAL_POLICY_SEVERITIES:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason=(
                "terminal policy requires severity LOW, MODERATE, HIGH, or "
                "CRITICAL."
            ),
        )

    if score >= 60 or severity in {"HIGH", "CRITICAL"}:
        outcome = "ESCALATED"
    elif score < 20 and severity == "LOW":
        outcome = "CLOSED"
    elif 0 <= score <= 59 and severity in {"LOW", "MODERATE"}:
        outcome = "RESOLVED"
    else:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason=(
                "terminal policy has no deterministic disposition for "
                f"canonical_score={score}; severity={severity}."
            ),
        )

    message = (
        f"Problem review disposition: {outcome}; canonical_score={score}; "
        f"severity={severity}; policy={TERMINAL_POLICY_NAME}"
    )
    try:
        updated = record_problem_review_outcome(
            outcome,
            root,
            now=now,
            event_message=message,
            event_idempotency_key=(
                f"{TERMINAL_POLICY_NAME}-{outcome}-{score}-{severity}"
            ),
        )
    except CaseStateError as error:
        return _result(
            case,
            changed=False,
            action="BLOCKED",
            reason=f"terminal disposition was blocked: {error}",
        )
    return _result(
        updated,
        changed=True,
        action="PROBLEM_REVIEW_DISPOSITION",
        reason=message,
        outcome=outcome,
    )


def process_active_case_stage(
    root: Path | str | None = None,
    *,
    now: datetime | None = None,
) -> StageWorkResult:
    """Perform one bounded deterministic batch for the persisted current stage."""

    now = now or utc_now()
    case = load_active_case(root)
    if case is None:
        raise CaseStateError("Cannot process stage work without an active case.")
    validate_active_case(case)
    if case["lifecycle_status"] != ACTIVE_LIFECYCLE_STATUS:
        return _result(
            case,
            changed=False,
            action="NOOP",
            reason="terminal cases do not receive active-stage work.",
        )

    stage = case["current_stage"]
    if stage == "CASE_SCAN":
        return _result(
            case,
            changed=False,
            action="NOOP",
            reason="CASE_SCAN has no bounded artifact-processing batch.",
        )
    if stage == "EVIDENCE_REVIEW":
        return _process_evidence_review(case, root, now)
    if stage == "VALIDATION":
        return _process_validation(case, root, now)
    if stage == "ASSESSMENT":
        return _process_assessment(case, root, now)
    if stage == "PROBLEM_REVIEW":
        return _process_problem_review(case, root, now)
    raise StateValidationError(f"Unsupported current_stage: {stage!r}")


def main() -> None:
    result = process_active_case_stage()
    message = (
        f"Active case {result.case['case_id']} stage={result.stage} "
        f"action={result.action}. {result.reason}"
    )
    if result.processed_ids:
        message += f" Processed={','.join(result.processed_ids)}."
    print(message)


if __name__ == "__main__":
    main()
