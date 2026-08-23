#!/usr/bin/env python3
"""Deterministic persistent lifecycle for the production active case.

This module owns lifecycle decisions. Renderers only consume the resulting
state through dashboard_state.py.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from case_state import (
    ACTIVE_LIFECYCLE_STATUS,
    TERMINAL_STATES,
    CaseStateError,
    StaleDataError,
    StateValidationError,
    append_case_event,
    atomic_write_json,
    current_case_path,
    iso_timestamp,
    load_active_case,
    load_json_document,
    load_normalized_csharp_threat,
    normalize_case_metadata,
    parse_timestamp,
    repository_root,
    save_active_case,
    synchronize_anomaly_history,
    synchronize_relationships,
    synchronize_system_status,
    synchronize_threat_history,
    utc_now,
    validate_active_case,
    validate_support_state,
)


EVIDENCE_ROOT = Path("evidence")
ARCHIVE_JSON_ROOT = Path("cases/archive/json")
ARCHIVE_REPORT_ROOT = Path("cases/archive/reports")
TERMINAL_REVIEW_OUTCOMES = {"CLOSED", "RESOLVED", "ESCALATED"}
COMPLETED_REVIEW_STATUSES = {"REVIEWED", "VALIDATED"}
COMPLETED_CORRELATION_STATUSES = {"CORRELATED", "VALIDATED"}


@dataclass(frozen=True)
class ArtifactSnapshot:
    evidence_count: int | None
    correlation_count: int | None
    evidence_items: list[dict[str, Any]]
    correlations: list[dict[str, Any]]


@dataclass(frozen=True)
class LifecycleResult:
    case: dict[str, Any]
    created: bool
    migrated: bool
    transition: str | None
    reason: str
    stale_threat_report_rejected: bool


def _paths(case_id: str, root: Path | str | None) -> tuple[Path, Path]:
    base = repository_root(root) / EVIDENCE_ROOT / case_id
    return base / "evidence_manifest.json", base / "evidence_correlations.json"


def _terminal_archive_is_verified(
    case: dict[str, Any], root: Path | str | None
) -> bool:
    """Require the actual terminal archive before releasing the active slot."""

    base = repository_root(root)
    json_path = base / ARCHIVE_JSON_ROOT / f"{case['case_id']}.json"
    report_path = base / ARCHIVE_REPORT_ROOT / f"{case['case_id']}.md"
    if not json_path.exists() or not report_path.exists():
        return False
    archived = load_json_document(json_path)
    if (
        archived.get("case_id") != case["case_id"]
        or archived.get("campaign_id") != case["campaign_id"]
        or archived.get("lifecycle_status") != case["lifecycle_status"]
        or archived.get("terminal_state") != case["terminal_state"]
        or archived.get("archive_status") != "ARCHIVED"
        or archived.get("state_revision") != case["state_revision"]
    ):
        return False
    return case["case_id"] in report_path.read_text(encoding="utf-8")


def load_validated_artifact_snapshot(
    case: dict[str, Any], root: Path | str | None = None
) -> ArtifactSnapshot:
    manifest_path, correlations_path = _paths(case["case_id"], root)
    manifest = load_json_document(manifest_path, missing_ok=True)
    correlations_document = load_json_document(correlations_path, missing_ok=True)

    evidence_items: list[dict[str, Any]] = []
    correlation_items: list[dict[str, Any]] = []
    evidence_count: int | None = None
    correlation_count: int | None = None

    if manifest is not None:
        schema_version = manifest.get("schema_version")
        if schema_version is not None and (
            not isinstance(schema_version, int) or schema_version < 1
        ):
            raise StateValidationError("Evidence manifest has an invalid schema_version.")
        if manifest.get("case_id") != case["case_id"]:
            raise StaleDataError("Evidence manifest belongs to another case.")
        raw_items = manifest.get("evidence_items")
        if not isinstance(raw_items, list):
            raise StateValidationError("Evidence manifest evidence_items must be a list.")
        evidence_items = [item for item in raw_items if isinstance(item, dict)]
        if len(evidence_items) != len(raw_items):
            raise StateValidationError("Evidence manifest contains a non-object item.")
        evidence_count = manifest.get("evidence_count")
        if not isinstance(evidence_count, int) or evidence_count != len(evidence_items):
            raise StateValidationError("Evidence manifest count does not match its items.")
        if evidence_count != case["evidence_count"]:
            raise StateValidationError(
                "Evidence manifest count does not match active case evidence_count."
            )
        evidence_ids: set[str] = set()
        for item in evidence_items:
            if item.get("case_id") != case["case_id"]:
                raise StaleDataError("An evidence item belongs to another case.")
            evidence_id = item.get("evidence_id")
            if not isinstance(evidence_id, str) or evidence_id in evidence_ids:
                raise StateValidationError("Evidence identifiers must be unique.")
            evidence_ids.add(evidence_id)

    if correlations_document is not None:
        if manifest is None:
            raise StaleDataError(
                "Evidence correlations exist without a matching active-case manifest."
            )
        schema_version = correlations_document.get("schema_version")
        if schema_version is not None and (
            not isinstance(schema_version, int) or schema_version < 1
        ):
            raise StateValidationError(
                "Evidence correlation document has an invalid schema_version."
            )
        if correlations_document.get("case_id") != case["case_id"]:
            raise StaleDataError("Evidence correlations belong to another case.")
        raw_correlations = correlations_document.get("correlations")
        if not isinstance(raw_correlations, list):
            raise StateValidationError("Evidence correlations must be a list.")
        correlation_items = [
            item for item in raw_correlations if isinstance(item, dict)
        ]
        if len(correlation_items) != len(raw_correlations):
            raise StateValidationError("Evidence correlations contains a non-object item.")
        correlation_count = correlations_document.get("correlation_count")
        if not isinstance(correlation_count, int) or correlation_count != len(
            correlation_items
        ):
            raise StateValidationError(
                "Evidence correlation_count does not match correlation records."
            )
        evidence_ids = {item["evidence_id"] for item in evidence_items}
        correlation_ids = [item.get("evidence_id") for item in correlation_items]
        if any(
            item.get("case_id") != case["case_id"]
            for item in correlation_items
        ):
            raise StaleDataError(
                "A correlation record belongs to a different active case."
            )
        if (
            any(not isinstance(evidence_id, str) for evidence_id in correlation_ids)
            or len(set(correlation_ids)) != len(correlation_ids)
            or set(correlation_ids) != evidence_ids
        ):
            raise StaleDataError(
                "Correlations must cover each active-manifest evidence ID exactly once."
            )

    return ArtifactSnapshot(
        evidence_count=evidence_count,
        correlation_count=correlation_count,
        evidence_items=evidence_items,
        correlations=correlation_items,
    )


def _next_transition(
    case: dict[str, Any],
    artifacts: ArtifactSnapshot,
    root: Path | str | None,
) -> tuple[str | None, str]:
    if case["lifecycle_status"] in TERMINAL_STATES:
        return None, "terminal case remains immutable pending archival."

    stage = case["current_stage"]
    if stage == "CASE_SCAN":
        if artifacts.evidence_count and artifacts.evidence_count > 0:
            return "EVIDENCE_REVIEW", "matching evidence manifest is available."
        return None, "no matching evidence manifest is available."

    if stage == "EVIDENCE_REVIEW":
        if not artifacts.evidence_items:
            return None, "no evidence exists for review."
        if all(
            str(item.get("review_status", "")).upper()
            in COMPLETED_REVIEW_STATUSES
            for item in artifacts.evidence_items
        ):
            return "VALIDATION", "all evidence records have completed review states."
        return None, "evidence review remains incomplete."

    if stage == "VALIDATION":
        if not artifacts.evidence_items or not artifacts.correlations:
            return None, "validation requires matching evidence and correlations."
        if len(artifacts.correlations) != len(artifacts.evidence_items):
            return None, "correlation count does not cover all evidence records."
        if all(
            str(item.get("analysis_status", "")).upper()
            in COMPLETED_CORRELATION_STATUSES
            for item in artifacts.correlations
        ):
            return "ASSESSMENT", "all correlations are validated against evidence."
        return None, "correlation validation remains incomplete."

    if stage == "ASSESSMENT":
        try:
            threat = load_normalized_csharp_threat(case, root)
        except StaleDataError:
            return None, "matching C# threat report is not yet available."
        if (
            threat is not None
            and str(case.get("assessment", "")).strip()
            and case.get("assessment_completed_at")
        ):
            return "PROBLEM_REVIEW", "matching C# threat assessment was explicitly completed."
        return None, "assessment awaits an explicit completion record."

    if stage == "PROBLEM_REVIEW":
        outcome = str(case.get("problem_review_outcome") or "").upper()
        if outcome in TERMINAL_REVIEW_OUTCOMES:
            return outcome, "explicit problem-review outcome is terminal."
        return None, "problem review awaits an explicit terminal outcome."

    raise StateValidationError(f"Unsupported current_stage: {stage!r}")


def _refresh_derived_state(
    case: dict[str, Any],
    artifacts: ArtifactSnapshot,
    root: Path | str | None,
) -> bool:
    stale_threat_report_rejected = False
    try:
        threat = synchronize_threat_history(case, root)
    except StaleDataError:
        threat = None
        stale_threat_report_rejected = True
    synchronize_anomaly_history(case, root)
    synchronize_system_status(case, root, threat=threat)
    synchronize_relationships(
        case,
        root,
        evidence_count=artifacts.evidence_count,
        correlation_count=artifacts.correlation_count,
        threat=threat,
    )
    validate_support_state(
        case,
        root,
        evidence_count=artifacts.evidence_count,
        correlation_count=artifacts.correlation_count,
        threat=threat,
        validate_relationship_inputs=True,
    )
    return stale_threat_report_rejected


def _save_transition(
    previous: dict[str, Any],
    current: dict[str, Any],
    root: Path | str | None,
    now: datetime,
) -> None:
    current["updated_at"] = iso_timestamp(now)
    current["state_revision"] = int(previous["state_revision"]) + 1
    save_active_case(current, root, previous=previous)


def _stage_intensity(stage: str) -> int:
    return {
        "CASE_SCAN": 30,
        "EVIDENCE_REVIEW": 45,
        "VALIDATION": 58,
        "ASSESSMENT": 70,
        "PROBLEM_REVIEW": 82,
        "CLOSED": 20,
        "RESOLVED": 18,
        "ESCALATED": 90,
    }.get(stage, 40)


def _append_transition_event(
    case: dict[str, Any],
    transition: str,
    reason: str,
    root: Path | str | None,
    now: datetime,
) -> None:
    if transition in TERMINAL_STATES:
        event_type = "CASE_TERMINAL"
        message = f"Problem review recorded terminal outcome {transition}: {reason}"
    else:
        event_type = "WORKFLOW_STAGE_CHANGED"
        message = f"Workflow advanced to {transition}: {reason}"
    append_case_event(
        case,
        event_type=event_type,
        message=message,
        intensity=_stage_intensity(transition),
        idempotency_key=f"revision-{case['state_revision']}-{event_type}",
        timestamp=now,
        root=root,
    )


def ensure_active_case(
    create_case: Callable[[], dict[str, Any]],
    root: Path | str | None = None,
    *,
    now: datetime | None = None,
) -> LifecycleResult:
    """Create only when there is no active case or a terminal archive succeeded."""

    now = now or utc_now()
    existing = load_active_case(root)
    if existing is None:
        created, _ = normalize_case_metadata(create_case(), now)
        created["lifecycle_status"] = ACTIVE_LIFECYCLE_STATUS
        created["archive_status"] = "NOT_REQUIRED"
        created["terminal_at"] = None
        created["archived_at"] = None
        save_active_case(created, root)
        append_case_event(
            created,
            event_type="CASE_CREATED",
            message="Persistent active case created.",
            intensity=_stage_intensity("CASE_SCAN"),
            idempotency_key="case-created",
            timestamp=now,
            root=root,
        )
        artifacts = load_validated_artifact_snapshot(created, root)
        stale = _refresh_derived_state(created, artifacts, root)
        return LifecycleResult(
            created,
            created=True,
            migrated=False,
            transition=None,
            reason="no active case existed; created a persistent active case.",
            stale_threat_report_rejected=stale,
        )

    normalized, migrated = normalize_case_metadata(existing, now)
    validate_active_case(normalized)
    if migrated:
        save_active_case(normalized, root)
        append_case_event(
            normalized,
            event_type="CASE_MIGRATED",
            message="Legacy active case received persistent lifecycle metadata.",
            intensity=_stage_intensity(normalized["current_stage"]),
            idempotency_key="case-migrated",
            timestamp=now,
            root=root,
        )

    if normalized["lifecycle_status"] in TERMINAL_STATES:
        archive_verified = (
            normalized.get("archive_status") == "ARCHIVED"
            and _terminal_archive_is_verified(normalized, root)
        )
        if not archive_verified:
            artifacts = load_validated_artifact_snapshot(normalized, root)
            stale = _refresh_derived_state(normalized, artifacts, root)
            return LifecycleResult(
                normalized,
                created=False,
                migrated=migrated,
                transition=None,
                reason=(
                    "terminal case is awaiting a verified successful archive; "
                    "no replacement was created."
                ),
                stale_threat_report_rejected=stale,
            )
        created, _ = normalize_case_metadata(create_case(), now)
        created["lifecycle_status"] = ACTIVE_LIFECYCLE_STATUS
        created["archive_status"] = "NOT_REQUIRED"
        created["terminal_at"] = None
        created["archived_at"] = None
        save_active_case(created, root)
        append_case_event(
            created,
            event_type="CASE_CREATED",
            message="Persistent active case created after prior terminal archive.",
            intensity=_stage_intensity("CASE_SCAN"),
            idempotency_key="case-created",
            timestamp=now,
            root=root,
        )
        artifacts = load_validated_artifact_snapshot(created, root)
        stale = _refresh_derived_state(created, artifacts, root)
        return LifecycleResult(
            created,
            created=True,
            migrated=False,
            transition=None,
            reason="prior terminal case was archived; created the next active case.",
            stale_threat_report_rejected=stale,
        )

    artifacts = load_validated_artifact_snapshot(normalized, root)
    stale = _refresh_derived_state(normalized, artifacts, root)
    return LifecycleResult(
        normalized,
        created=False,
        migrated=migrated,
        transition=None,
        reason="reused existing non-terminal active case.",
        stale_threat_report_rejected=stale,
    )


def update_active_case(
    root: Path | str | None = None,
    *,
    now: datetime | None = None,
) -> LifecycleResult:
    """Evaluate at most one data-driven transition using persisted prior artifacts."""

    now = now or utc_now()
    existing = load_active_case(root)
    if existing is None:
        raise CaseStateError("Cannot update lifecycle without an active case.")
    case, migrated = normalize_case_metadata(existing, now)
    validate_active_case(case)
    if migrated:
        save_active_case(case, root)
        append_case_event(
            case,
            event_type="CASE_MIGRATED",
            message="Legacy active case received persistent lifecycle metadata.",
            intensity=_stage_intensity(case["current_stage"]),
            idempotency_key="case-migrated",
            timestamp=now,
            root=root,
        )

    artifacts = load_validated_artifact_snapshot(case, root)
    transition, reason = _next_transition(case, artifacts, root)
    if transition is not None:
        previous = copy.deepcopy(case)
        if transition in TERMINAL_STATES:
            case["lifecycle_status"] = transition
            case["status"] = transition
            case["terminal_state"] = transition
            case["terminal_at"] = iso_timestamp(now)
            case["archive_status"] = "PENDING"
        else:
            case["current_stage"] = transition
            case["stage_updated_at"] = iso_timestamp(now)
        _save_transition(previous, case, root, now)
        _append_transition_event(case, transition, reason, root, now)

    stale = _refresh_derived_state(case, artifacts, root)
    return LifecycleResult(
        case,
        created=False,
        migrated=migrated,
        transition=transition,
        reason=reason,
        stale_threat_report_rejected=stale,
    )


def mark_assessment_complete(
    root: Path | str | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utc_now()
    case = load_active_case(root)
    if case is None:
        raise CaseStateError("No active case exists.")
    case, _ = normalize_case_metadata(case, now)
    if case["lifecycle_status"] in TERMINAL_STATES:
        raise StateValidationError("Terminal cases cannot be marked for assessment.")
    if case["current_stage"] != "ASSESSMENT":
        raise StateValidationError(
            "Assessment completion may only be recorded at ASSESSMENT."
        )
    if load_normalized_csharp_threat(case, root) is None:
        raise StateValidationError(
            "Assessment completion requires a current C# threat report."
        )
    if case.get("assessment_completed_at"):
        return case
    previous = copy.deepcopy(case)
    case["assessment_completed_at"] = iso_timestamp(now)
    _save_transition(previous, case, root, now)
    append_case_event(
        case,
        event_type="ASSESSMENT_COMPLETED",
        message="Assessment completion was explicitly recorded.",
        intensity=_stage_intensity("ASSESSMENT"),
        idempotency_key="assessment-completed",
        timestamp=now,
        root=root,
    )
    _refresh_derived_state(
        case,
        load_validated_artifact_snapshot(case, root),
        root,
    )
    return case


def record_problem_review_outcome(
    outcome: str,
    root: Path | str | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utc_now()
    normalized_outcome = outcome.upper()
    if normalized_outcome not in TERMINAL_REVIEW_OUTCOMES:
        raise StateValidationError(
            f"Unsupported terminal problem-review outcome: {outcome!r}"
        )
    case = load_active_case(root)
    if case is None:
        raise CaseStateError("No active case exists.")
    case, _ = normalize_case_metadata(case, now)
    if case["current_stage"] != "PROBLEM_REVIEW":
        raise StateValidationError(
            "Problem-review outcome may only be recorded at PROBLEM_REVIEW."
        )
    existing_outcome = case.get("problem_review_outcome")
    if existing_outcome:
        if existing_outcome == normalized_outcome:
            return case
        raise StateValidationError("A problem-review outcome cannot be replaced.")
    previous = copy.deepcopy(case)
    case["problem_review_outcome"] = normalized_outcome
    case["problem_reviewed_at"] = iso_timestamp(now)
    _save_transition(previous, case, root, now)
    append_case_event(
        case,
        event_type="PROBLEM_REVIEW_OUTCOME_RECORDED",
        message=f"Problem-review outcome recorded: {normalized_outcome}.",
        intensity=_stage_intensity(normalized_outcome),
        idempotency_key=f"problem-review-{normalized_outcome}",
        timestamp=now,
        root=root,
    )
    _refresh_derived_state(
        case,
        load_validated_artifact_snapshot(case, root),
        root,
    )
    return case


def mark_case_archived(
    root: Path | str | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Mark the slot eligible only after archive_case.py has written final files."""

    now = now or utc_now()
    case = load_active_case(root)
    if case is None:
        raise CaseStateError("No active case exists.")
    case, _ = normalize_case_metadata(case, now)
    if case["lifecycle_status"] not in TERMINAL_STATES:
        raise StateValidationError("Only terminal cases may be marked archived.")
    if case.get("archive_status") == "ARCHIVED":
        return case
    previous = copy.deepcopy(case)
    case["archive_status"] = "ARCHIVED"
    case["archived_at"] = iso_timestamp(now)
    _save_transition(previous, case, root, now)
    append_case_event(
        case,
        event_type="CASE_ARCHIVED",
        message="Terminal case archive completed and active slot is eligible.",
        intensity=_stage_intensity(case["lifecycle_status"]),
        idempotency_key="case-archived",
        timestamp=now,
        root=root,
    )
    _refresh_derived_state(
        case,
        load_validated_artifact_snapshot(case, root),
        root,
    )
    return case
