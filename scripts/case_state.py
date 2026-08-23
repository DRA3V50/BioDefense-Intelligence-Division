#!/usr/bin/env python3
"""Authoritative persistent active-case state helpers for Subsystem #8."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
ACTIVE_CASE_FILE = Path("data/current_case.json")
CASE_STATE_ROOT = Path("cases/state")
CSHARP_THREAT_REPORT = Path("reports/bioterror_threat_score_csharp.json")

WORKFLOW_STAGES = (
    "CASE_SCAN",
    "EVIDENCE_REVIEW",
    "VALIDATION",
    "ASSESSMENT",
    "PROBLEM_REVIEW",
)
TERMINAL_STATES = {"CLOSED", "RESOLVED", "ESCALATED"}
ACTIVE_LIFECYCLE_STATUS = "ACTIVE"
THREAT_SOURCE = "C# BioterrorThreatScoringEngine"
SYSTEM_STATUS_METRIC_UNITS = {
    "cpu_percent": "percent",
    "memory_percent": "percent",
    "network_percent": "percent",
    "disk_percent": "percent",
    "queue_depth": "count",
}
EVENT_SEVERITIES = {
    "INFO",
    "LOW",
    "MODERATE",
    "MEDIUM",
    "ELEVATED",
    "HIGH",
    "CRITICAL",
}

CASE_ID_PATTERN = re.compile(r"^BID-\d{4}-\d{4}$")
CAMPAIGN_ID_PATTERN = re.compile(r"^BDC-\d{4}-\d{3}$")

REQUIRED_CASE_FIELDS = (
    "case_id",
    "campaign_id",
    "date",
    "operation",
    "classification",
    "threat_family",
    "severity",
    "status",
    "containment_phase",
    "affected_platform",
    "device_family",
    "vendor",
    "network_zone",
    "firmware_version",
    "confidence",
    "risk_score",
    "affected_assets",
    "evidence_count",
    "ioc_count",
    "initial_access",
    "lead_analyst",
    "priority",
    "recommended_action",
    "assessment",
)
NUMERIC_CASE_FIELDS = (
    "confidence",
    "risk_score",
    "affected_assets",
    "evidence_count",
    "ioc_count",
)


class CaseStateError(RuntimeError):
    """Base error for authoritative active-case state failures."""


class MalformedStateError(CaseStateError):
    """Raised after preserving an unreadable JSON state file."""


class StateValidationError(CaseStateError):
    """Raised when an otherwise readable state document is inconsistent."""


class StaleDataError(CaseStateError):
    """Raised when generated data belongs to another active-case revision."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_timestamp(value: datetime | None = None) -> str:
    value = value or utc_now()
    if value.tzinfo is None or value.utcoffset() is None:
        raise StateValidationError("Authoritative timestamps must be timezone-aware.")
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_timestamp(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise StateValidationError(f"{field_name} must be a populated ISO-8601 timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise StateValidationError(
            f"{field_name} is not a valid ISO-8601 timestamp: {value!r}"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StateValidationError(f"{field_name} must include a timezone.")
    return parsed.astimezone(timezone.utc)


def parse_csharp_timestamp(value: object) -> datetime:
    """Normalize current ISO timestamps and the legacy C# UTC-labelled format."""

    if not isinstance(value, str) or not value.strip():
        raise StateValidationError("C# threat report generatedAt is missing.")
    try:
        return parse_timestamp(value, "C# threat report generatedAt")
    except StateValidationError:
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M UTC").replace(
                tzinfo=timezone.utc
            )
        except ValueError as error:
            raise StateValidationError(
                f"C# threat report generatedAt is invalid: {value!r}"
            ) from error


def repository_root(root: Path | str | None = None) -> Path:
    return Path(root or Path.cwd()).resolve()


def current_case_path(root: Path | str | None = None) -> Path:
    return repository_root(root) / ACTIVE_CASE_FILE


def support_directory(case_id: str, root: Path | str | None = None) -> Path:
    return repository_root(root) / CASE_STATE_ROOT / case_id


def events_path(case_id: str, root: Path | str | None = None) -> Path:
    return support_directory(case_id, root) / "events.json"


def anomaly_history_path(case_id: str, root: Path | str | None = None) -> Path:
    return support_directory(case_id, root) / "anomaly_history.json"


def threat_history_path(case_id: str, root: Path | str | None = None) -> Path:
    return support_directory(case_id, root) / "threat_history.json"


def system_status_path(case_id: str, root: Path | str | None = None) -> Path:
    return support_directory(case_id, root) / "system_status.json"


def relationships_path(case_id: str, root: Path | str | None = None) -> Path:
    return support_directory(case_id, root) / "relationships.json"


def atomic_write_text(path: Path, content: str) -> None:
    """Write a complete replacement next to the destination, then atomically swap."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def backup_malformed_file(path: Path, now: datetime | None = None) -> Path:
    stamp = iso_timestamp(now).replace(":", "").replace("-", "")
    backup = path.with_name(f"{path.stem}.malformed-{stamp}{path.suffix}")
    counter = 1
    while backup.exists():
        backup = path.with_name(
            f"{path.stem}.malformed-{stamp}-{counter}{path.suffix}"
        )
        counter += 1
    shutil.copy2(path, backup)
    return backup


def load_json_document(path: Path, *, missing_ok: bool = False) -> dict[str, Any] | None:
    if not path.exists():
        if missing_ok:
            return None
        raise CaseStateError(f"Required state file is missing: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as error:
        backup = backup_malformed_file(path)
        raise MalformedStateError(
            f"Malformed JSON preserved at {backup}; original state was not replaced."
        ) from error
    except OSError as error:
        raise CaseStateError(f"Unable to read {path}: {error}") from error
    if not isinstance(payload, dict):
        raise StateValidationError(f"{path} must contain a JSON object.")
    return payload


def normalize_case_metadata(
    case: dict[str, Any], now: datetime | None = None
) -> tuple[dict[str, Any], bool]:
    """Add only the minimum lifecycle fields needed by Subsystem #8.

    Existing production fields are retained unchanged. Legacy cases are
    explicitly migrated at the current UTC time because their original schema
    contained only a date, not a trustworthy creation timestamp.
    """

    now_stamp = iso_timestamp(now)
    normalized = copy.deepcopy(case)
    changed = False

    terminal_from_legacy_status = str(normalized.get("status", "")).upper()
    default_lifecycle = (
        terminal_from_legacy_status
        if terminal_from_legacy_status in TERMINAL_STATES
        else ACTIVE_LIFECYCLE_STATUS
    )
    defaults: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_stamp,
        "updated_at": now_stamp,
        "current_stage": "CASE_SCAN",
        "stage_updated_at": now_stamp,
        "lifecycle_status": default_lifecycle,
        "terminal_state": default_lifecycle
        if default_lifecycle in TERMINAL_STATES
        else None,
        "terminal_at": now_stamp
        if default_lifecycle in TERMINAL_STATES
        else None,
        "archive_status": "PENDING"
        if default_lifecycle in TERMINAL_STATES
        else "NOT_REQUIRED",
        "archived_at": None,
        "assessment_completed_at": None,
        "problem_review_outcome": default_lifecycle
        if default_lifecycle in TERMINAL_STATES
        else None,
        "problem_reviewed_at": None,
        "state_revision": 1,
    }
    for field, default in defaults.items():
        if field not in normalized:
            normalized[field] = default
            changed = True

    if changed:
        normalized["state_migrated_at"] = now_stamp
    return normalized, changed


def validate_active_case(
    case: dict[str, Any],
    *,
    previous: dict[str, Any] | None = None,
) -> None:
    missing = [field for field in REQUIRED_CASE_FIELDS if field not in case]
    if missing:
        raise StateValidationError(f"Active case is missing required fields: {missing}")

    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not CASE_ID_PATTERN.fullmatch(case_id):
        raise StateValidationError(f"Invalid case_id: {case_id!r}")
    campaign_id = case.get("campaign_id")
    if not isinstance(campaign_id, str) or not CAMPAIGN_ID_PATTERN.fullmatch(campaign_id):
        raise StateValidationError(f"Invalid campaign_id: {campaign_id!r}")

    for field in NUMERIC_CASE_FIELDS:
        value = case.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise StateValidationError(f"{field} must be a nonnegative integer.")
    for field in ("confidence", "risk_score"):
        if case[field] > 100:
            raise StateValidationError(f"{field} must be in the 0-100 range.")

    if case.get("schema_version") != SCHEMA_VERSION:
        raise StateValidationError(
            f"Unsupported active-case schema_version: {case.get('schema_version')!r}"
        )
    stage = case.get("current_stage")
    if stage not in WORKFLOW_STAGES:
        raise StateValidationError(f"Invalid current_stage: {stage!r}")
    lifecycle_status = case.get("lifecycle_status")
    if lifecycle_status not in {ACTIVE_LIFECYCLE_STATUS, *TERMINAL_STATES}:
        raise StateValidationError(f"Invalid lifecycle_status: {lifecycle_status!r}")
    terminal_state = case.get("terminal_state")
    archive_status = case.get("archive_status")
    if archive_status not in {"NOT_REQUIRED", "PENDING", "ARCHIVED"}:
        raise StateValidationError(f"Invalid archive_status: {archive_status!r}")
    if lifecycle_status in TERMINAL_STATES:
        if not case.get("terminal_at"):
            raise StateValidationError("A terminal lifecycle_status requires terminal_at.")
        if terminal_state != lifecycle_status:
            raise StateValidationError(
                "terminal_state must exactly match terminal lifecycle_status."
            )
        if case.get("problem_review_outcome") != lifecycle_status:
            raise StateValidationError(
                "A terminal lifecycle_status requires the same problem_review_outcome."
            )
        if archive_status not in {"PENDING", "ARCHIVED"}:
            raise StateValidationError("Terminal cases require PENDING or ARCHIVED status.")
    else:
        if terminal_state is not None or case.get("terminal_at") is not None:
            raise StateValidationError("Active cases cannot carry terminal state metadata.")
        if archive_status != "NOT_REQUIRED":
            raise StateValidationError("Active cases must have archive_status NOT_REQUIRED.")

    state_revision = case.get("state_revision")
    if not isinstance(state_revision, int) or isinstance(state_revision, bool) or state_revision < 1:
        raise StateValidationError("state_revision must be a positive integer.")

    created = parse_timestamp(case.get("created_at"), "created_at")
    updated = parse_timestamp(case.get("updated_at"), "updated_at")
    stage_updated = parse_timestamp(case.get("stage_updated_at"), "stage_updated_at")
    if updated < created or stage_updated < created:
        raise StateValidationError("Authoritative timestamps may not move backward.")
    for optional_field in (
        "terminal_at",
        "archived_at",
        "assessment_completed_at",
        "problem_reviewed_at",
    ):
        if case.get(optional_field) is not None:
            optional_timestamp = parse_timestamp(case[optional_field], optional_field)
            if optional_timestamp < created:
                raise StateValidationError(f"{optional_field} predates created_at.")

    if previous is not None:
        if case_id != previous.get("case_id"):
            raise StateValidationError("An active-case save cannot change case_id.")
        previous_updated = parse_timestamp(previous["updated_at"], "previous.updated_at")
        if updated < previous_updated:
            raise StateValidationError("updated_at cannot move backward.")
        previous_revision = int(previous.get("state_revision", 1))
        if state_revision < previous_revision:
            raise StateValidationError("state_revision cannot move backward.")

        def semantic_payload(value: dict[str, Any]) -> dict[str, Any]:
            payload = copy.deepcopy(value)
            payload.pop("updated_at", None)
            payload.pop("state_revision", None)
            return payload

        if semantic_payload(case) == semantic_payload(previous):
            if state_revision != previous_revision:
                raise StateValidationError(
                    "An idempotent active-case save must retain state_revision."
                )
            if updated != previous_updated:
                raise StateValidationError(
                    "An idempotent active-case save must retain updated_at."
                )
        elif state_revision != previous_revision + 1:
            raise StateValidationError(
                "A meaningful active-case change must increment state_revision by one."
            )


def load_active_case(root: Path | str | None = None) -> dict[str, Any] | None:
    return load_json_document(current_case_path(root), missing_ok=True)


def save_active_case(
    case: dict[str, Any],
    root: Path | str | None = None,
    *,
    previous: dict[str, Any] | None = None,
) -> None:
    validate_active_case(case, previous=previous)
    atomic_write_json(current_case_path(root), case)


def load_support_document(
    path: Path, case_id: str, collection_key: str
) -> dict[str, Any]:
    payload = load_json_document(path, missing_ok=True)
    if payload is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "case_id": case_id,
            collection_key: [],
            "updated_at": None,
        }
    if payload.get("case_id") != case_id:
        raise StaleDataError(f"{path} does not belong to active case {case_id}.")
    collection = payload.get(collection_key)
    if not isinstance(collection, list):
        raise StateValidationError(f"{path} has invalid {collection_key}.")
    return payload


def append_case_event(
    case: dict[str, Any],
    *,
    event_type: str,
    message: str,
    severity: str | None = None,
    source: str = "case_lifecycle",
    intensity: int | None = None,
    idempotency_key: str,
    timestamp: datetime | None = None,
    root: Path | str | None = None,
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    path = events_path(case_id, root)
    document = load_support_document(path, case_id, "events")
    events = document["events"]

    _validate_event_records(events, case_id)
    for event in events:
        if event.get("idempotency_key") == idempotency_key:
            return event

    resolved_severity = str(severity or case.get("severity", "MODERATE")).upper()
    if resolved_severity not in EVENT_SEVERITIES:
        raise StateValidationError(
            f"Event severity must be one of {sorted(EVENT_SEVERITIES)}."
        )
    if not isinstance(event_type, str) or not event_type.strip():
        raise StateValidationError("Event type must be a populated string.")
    if not isinstance(message, str) or not message.strip():
        raise StateValidationError("Event message must be a populated string.")
    if not isinstance(source, str) or not source.strip():
        raise StateValidationError("Event source must be a populated string.")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise StateValidationError("Event idempotency_key must be a populated string.")

    event_timestamp = iso_timestamp(timestamp)
    if events:
        prior_timestamp = parse_timestamp(
            events[-1].get("timestamp"), "previous event.timestamp"
        )
        if parse_timestamp(event_timestamp, "event.timestamp") < prior_timestamp:
            raise StateValidationError("Event timestamps must not move backward.")

    sequence = len(events) + 1
    resolved_intensity = intensity
    if resolved_intensity is None:
        severity_base = {
            "LOW": 25,
            "MODERATE": 45,
            "MEDIUM": 45,
            "ELEVATED": 58,
            "HIGH": 65,
            "CRITICAL": 85,
            "INFO": 30,
        }.get(resolved_severity, 40)
        resolved_intensity = max(0, min(100, severity_base))
    if not isinstance(resolved_intensity, int) or not 0 <= resolved_intensity <= 100:
        raise StateValidationError("Event intensity must be an integer in the 0-100 range.")

    event = {
        "event_id": f"{case_id}-EVT-{sequence:04d}",
        "case_id": case_id,
        "sequence": sequence,
        "timestamp": event_timestamp,
        "event_type": event_type,
        "message": message,
        "severity": resolved_severity,
        "source": source,
        "zone": case.get("network_zone", "UNKNOWN"),
        "intensity": resolved_intensity,
        "idempotency_key": idempotency_key,
    }
    events.append(event)
    document["updated_at"] = event["timestamp"]
    atomic_write_json(path, document)
    return event


def synchronize_anomaly_history(
    case: dict[str, Any], root: Path | str | None = None
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    event_document = load_support_document(events_path(case_id, root), case_id, "events")
    history_path = anomaly_history_path(case_id, root)
    history = load_support_document(history_path, case_id, "samples")
    known_event_ids = {sample.get("source_event_id") for sample in history["samples"]}
    changed = False
    for event in event_document["events"]:
        event_id = event.get("event_id")
        if event_id in known_event_ids:
            continue
        history["samples"].append(
            {
                "case_id": case_id,
                "timestamp": event["timestamp"],
                "value": event["intensity"],
                "source_event_id": event_id,
                "event_type": event["event_type"],
                "source": "derived_case_event",
            }
        )
        known_event_ids.add(event_id)
        changed = True
    if changed:
        history["updated_at"] = iso_timestamp()
        atomic_write_json(history_path, history)
    return history


def csharp_level(score: int) -> str:
    if score >= 85:
        return "CRITICAL"
    if score >= 70:
        return "HIGH"
    if score >= 45:
        return "ELEVATED"
    if score >= 20:
        return "GUARDED"
    return "LOW"


def threat_display_level(score: int) -> str:
    """Explicit frozen-#6 compatibility label; it is not a second score."""

    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"


def load_normalized_csharp_threat(
    case: dict[str, Any], root: Path | str | None = None
) -> dict[str, Any] | None:
    path = repository_root(root) / CSHARP_THREAT_REPORT
    report = load_json_document(path, missing_ok=True)
    if report is None:
        return None
    investigation = report.get("investigation")
    assessment = report.get("assessment")
    if not isinstance(investigation, dict) or not isinstance(assessment, dict):
        raise StateValidationError("C# threat report is missing investigation or assessment.")

    report_case_id = investigation.get("caseId")
    report_campaign_id = investigation.get("campaignId")
    if report_case_id != case["case_id"] or report_campaign_id != case["campaign_id"]:
        raise StaleDataError(
            "C# threat report case/campaign linkage does not match the active case."
        )
    report_revision = investigation.get("caseRevision")
    if not isinstance(report_revision, int) or report_revision != case["state_revision"]:
        raise StaleDataError(
            "C# threat report state revision does not match the active case."
        )

    score = assessment.get("overallScore")
    level = assessment.get("overallLevel")
    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
        raise StateValidationError("C# threat score must be an integer in the 0-100 range.")
    if level != csharp_level(score):
        raise StateValidationError(
            "C# threat classification is inconsistent with the canonical C# thresholds."
        )
    generated_at = parse_csharp_timestamp(report.get("generatedAt"))
    # Legacy C# reports have minute precision, so retain a one-minute tolerance
    # during migration while still rejecting genuinely older reports.
    if generated_at + timedelta(minutes=1) < parse_timestamp(
        case["created_at"], "created_at"
    ):
        raise StaleDataError("C# threat report predates the active case.")
    return {
        "case_id": case["case_id"],
        "campaign_id": case["campaign_id"],
        "case_revision": report_revision,
        "timestamp": iso_timestamp(generated_at),
        "score": score,
        "canonical_classification": level,
        "display_level_for_subsystem_06": threat_display_level(score),
        "source": THREAT_SOURCE,
        "report_path": str(CSHARP_THREAT_REPORT).replace("\\", "/"),
    }


def synchronize_threat_history(
    case: dict[str, Any], root: Path | str | None = None
) -> dict[str, Any] | None:
    threat = load_normalized_csharp_threat(case, root)
    if threat is None:
        return None
    path = threat_history_path(case["case_id"], root)
    history = load_support_document(path, case["case_id"], "samples")
    source_key = (
        f"{threat['case_id']}|{threat['case_revision']}|"
        f"{threat['score']}|{threat['canonical_classification']}"
    )
    if not any(sample.get("source_key") == source_key for sample in history["samples"]):
        history["samples"].append({**threat, "source_key": source_key})
        history["updated_at"] = iso_timestamp()
        atomic_write_json(path, history)
    return threat


def _stable_digest(*parts: object) -> int:
    joined = "|".join(str(part) for part in parts)
    return int(hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12], 16)


def _status_samples(
    value: int, seed: int, *, maximum: int | None
) -> list[int]:
    samples = [max(0, value + (((seed >> (index % 20)) % 7) - 3)) for index in range(12)]
    if maximum is None:
        return samples
    return [min(maximum, sample) for sample in samples]


def build_system_status(
    case: dict[str, Any],
    *,
    event_count: int,
    threat: dict[str, Any] | None,
) -> dict[str, Any]:
    score = int(threat["score"]) if threat else int(case["risk_score"])
    digest = _stable_digest(
        case["case_id"],
        case["state_revision"],
        case["current_stage"],
        event_count,
        score,
    )
    values = {
        "cpu_percent": 28 + digest % 34,
        "memory_percent": 34 + (digest >> 7) % 36,
        "network_percent": 22 + (digest >> 13) % 45,
        "disk_percent": 30 + (digest >> 19) % 33,
        "queue_depth": 1 + (digest >> 25) % 8,
    }
    health = max(0, min(100, 96 - score // 12 - event_count // 8))
    subsystem_names = (
        "evidence_pipeline",
        "correlation_engine",
        "case_store",
        "threat_assessment",
    )
    subsystems = {}
    for index, name in enumerate(subsystem_names):
        subsystem_health = max(0, min(100, health - index * 2 + (digest >> index) % 4))
        subsystems[name] = {
            "status": "NOMINAL" if subsystem_health >= 80 else "DEGRADED",
            "health": subsystem_health,
            "led_state": "STEADY" if subsystem_health >= 80 else "AMBER",
            "led_intensity": max(0.0, min(1.0, subsystem_health / 100)),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case["case_id"],
        "state_revision": case["state_revision"],
        "telemetry_source": "SIMULATED",
        "measurement_status": "SIMULATED",
        "source_fingerprint": hashlib.sha256(
            json.dumps(
                {
                    "case_id": case["case_id"],
                    "state_revision": case["state_revision"],
                    "stage": case["current_stage"],
                    "event_count": event_count,
                    "score": score,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest(),
        "subsystems": subsystems,
        "telemetry": {
            key: {
                "unit": SYSTEM_STATUS_METRIC_UNITS[key],
                "samples": _status_samples(
                    value,
                    digest >> index,
                    maximum=100 if SYSTEM_STATUS_METRIC_UNITS[key] == "percent" else None,
                ),
            }
            for index, (key, value) in enumerate(values.items())
        },
    }


def synchronize_system_status(
    case: dict[str, Any],
    root: Path | str | None = None,
    *,
    threat: dict[str, Any] | None = None,
) -> dict[str, Any]:
    case_id = case["case_id"]
    events = load_support_document(events_path(case_id, root), case_id, "events")
    path = system_status_path(case_id, root)
    existing = load_json_document(path, missing_ok=True)
    candidate = build_system_status(
        case,
        event_count=len(events["events"]),
        threat=threat,
    )
    if (
        isinstance(existing, dict)
        and existing.get("case_id") == case_id
        and existing.get("source_fingerprint") == candidate["source_fingerprint"]
    ):
        return existing
    candidate["updated_at"] = iso_timestamp()
    atomic_write_json(path, candidate)
    return candidate


def _relationship(
    case_id: str,
    source: str,
    target: str,
    relationship_type: str,
    attributes: dict[str, Any],
) -> dict[str, Any]:
    relationship_id = hashlib.sha256(
        f"{case_id}|{source}|{target}|{relationship_type}".encode("utf-8")
    ).hexdigest()[:16]
    return {
        "relationship_id": f"{case_id}-REL-{relationship_id}",
        "case_id": case_id,
        "source": source,
        "target": target,
        "relationship_type": relationship_type,
        "attributes": attributes,
    }


def relationship_fingerprint(candidate: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(candidate, sort_keys=True).encode("utf-8")
    ).hexdigest()


def build_relationships(
    case: dict[str, Any],
    *,
    evidence_count: int | None = None,
    correlation_count: int | None = None,
    threat: dict[str, Any] | None = None,
) -> dict[str, Any]:
    case_id = case["case_id"]
    relationships: list[dict[str, Any]] = []
    nodes: list[dict[str, str]] = [
        {"node_id": f"case:{case_id}", "node_type": "case", "label": case_id}
    ]

    def add_node(node_id: str, node_type: str, label: str) -> None:
        nodes.append({"node_id": node_id, "node_type": node_type, "label": label})

    campaign_id = str(case.get("campaign_id", "")).strip()
    if campaign_id:
        target = f"campaign:{campaign_id}"
        add_node(target, "campaign", campaign_id)
        relationships.append(
            _relationship(case_id, f"case:{case_id}", target, "BELONGS_TO", {})
        )
    platform = str(case.get("affected_platform", "")).strip()
    if platform:
        target = f"platform:{platform}"
        add_node(target, "platform", platform)
        relationships.append(
            _relationship(case_id, f"case:{case_id}", target, "AFFECTS_PLATFORM", {})
        )
    zone = str(case.get("network_zone", "")).strip()
    if zone:
        target = f"zone:{zone}"
        add_node(target, "network_zone", zone)
        relationships.append(
            _relationship(case_id, f"case:{case_id}", target, "OBSERVED_IN_ZONE", {})
        )
    if evidence_count is not None and evidence_count > 0:
        target = f"evidence:{case_id}"
        add_node(target, "evidence_collection", "Evidence Collection")
        relationships.append(
            _relationship(
                case_id,
                f"case:{case_id}",
                target,
                "HAS_EVIDENCE",
                {"count": evidence_count},
            )
        )
    if correlation_count is not None and correlation_count > 0:
        target = f"correlations:{case_id}"
        add_node(target, "correlation_set", "Evidence Correlations")
        relationships.append(
            _relationship(
                case_id,
                f"case:{case_id}",
                target,
                "HAS_CORRELATIONS",
                {"count": correlation_count},
            )
        )
    if threat is not None:
        target = f"threat:{case_id}"
        add_node(target, "threat_assessment", "C# Threat Assessment")
        relationships.append(
            _relationship(
                case_id,
                f"case:{case_id}",
                target,
                "HAS_THREAT_ASSESSMENT",
                {
                    "score": threat["score"],
                    "classification": threat["canonical_classification"],
                },
            )
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "state_revision": case["state_revision"],
        "nodes": nodes,
        "relationships": relationships,
    }


def synchronize_relationships(
    case: dict[str, Any],
    root: Path | str | None = None,
    *,
    evidence_count: int | None = None,
    correlation_count: int | None = None,
    threat: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = build_relationships(
        case,
        evidence_count=evidence_count,
        correlation_count=correlation_count,
        threat=threat,
    )
    path = relationships_path(case["case_id"], root)
    existing = load_json_document(path, missing_ok=True)
    fingerprint = relationship_fingerprint(candidate)
    if (
        isinstance(existing, dict)
        and existing.get("case_id") == case["case_id"]
        and existing.get("source_fingerprint") == fingerprint
    ):
        return existing
    candidate["source_fingerprint"] = fingerprint
    candidate["updated_at"] = iso_timestamp()
    atomic_write_json(path, candidate)
    return candidate


def _validate_event_records(events: list[dict[str, Any]], case_id: str) -> None:
    prior_event_time: datetime | None = None
    seen_event_ids: set[str] = set()
    seen_event_keys: set[str] = set()
    for expected_sequence, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            raise StateValidationError("An event record must be an object.")
        if event.get("case_id") != case_id:
            raise StateValidationError("An event belongs to a different case.")
        if event.get("sequence") != expected_sequence:
            raise StateValidationError("Event sequences must be contiguous and ordered.")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id or event_id in seen_event_ids:
            raise StateValidationError("Event identifiers must be populated and unique.")
        seen_event_ids.add(event_id)
        event_key = event.get("idempotency_key")
        if (
            not isinstance(event_key, str)
            or not event_key
            or event_key in seen_event_keys
        ):
            raise StateValidationError(
                "Event idempotency keys must be populated and unique."
            )
        seen_event_keys.add(event_key)
        event_time = parse_timestamp(event.get("timestamp"), "event.timestamp")
        if prior_event_time is not None and event_time < prior_event_time:
            raise StateValidationError("Event timestamps must not move backward.")
        prior_event_time = event_time
        if event.get("severity") not in EVENT_SEVERITIES:
            raise StateValidationError("Event severity is not in the canonical vocabulary.")
        if not isinstance(event.get("event_type"), str) or not event["event_type"]:
            raise StateValidationError("Event type must be populated.")
        if not isinstance(event.get("message"), str) or not event["message"]:
            raise StateValidationError("Event message must be populated.")
        if not isinstance(event.get("source"), str) or not event["source"]:
            raise StateValidationError("Event source must be populated.")
        if not isinstance(event.get("zone"), str) or not event["zone"]:
            raise StateValidationError("Event zone must be populated.")
        if not isinstance(event.get("intensity"), int) or not 0 <= event["intensity"] <= 100:
            raise StateValidationError("Event intensity must be in the 0-100 range.")


def validate_relationship_document(
    case: dict[str, Any],
    document: dict[str, Any],
    *,
    evidence_count: int | None,
    correlation_count: int | None,
    threat: dict[str, Any] | None,
) -> None:
    expected = build_relationships(
        case,
        evidence_count=evidence_count,
        correlation_count=correlation_count,
        threat=threat,
    )
    if (
        document.get("case_id") != case["case_id"]
        or document.get("state_revision") != case["state_revision"]
        or document.get("nodes") != expected["nodes"]
        or document.get("relationships") != expected["relationships"]
        or document.get("source_fingerprint") != relationship_fingerprint(expected)
    ):
        raise StateValidationError(
            "Relationship state is not the deterministic derivation of active artifacts."
        )


def validate_support_state(
    case: dict[str, Any],
    root: Path | str | None = None,
    *,
    evidence_count: int | None = None,
    correlation_count: int | None = None,
    threat: dict[str, Any] | None = None,
    validate_relationship_inputs: bool = False,
) -> None:
    case_id = case["case_id"]
    event_document = load_support_document(events_path(case_id, root), case_id, "events")
    _validate_event_records(event_document["events"], case_id)
    seen_event_ids = {event["event_id"] for event in event_document["events"]}

    anomaly = load_support_document(
        anomaly_history_path(case_id, root), case_id, "samples"
    )
    prior_anomaly_time: datetime | None = None
    known_event_ids = seen_event_ids
    seen_anomaly_sources: set[str] = set()
    for sample in anomaly["samples"]:
        if sample.get("case_id", case_id) != case_id:
            raise StateValidationError("An anomaly sample belongs to a different case.")
        sample_time = parse_timestamp(sample.get("timestamp"), "anomaly.timestamp")
        if prior_anomaly_time is not None and sample_time < prior_anomaly_time:
            raise StateValidationError("Anomaly timestamps must not move backward.")
        prior_anomaly_time = sample_time
        if sample.get("source_event_id") not in known_event_ids:
            raise StateValidationError("An anomaly sample must derive from a case event.")
        if sample.get("source_event_id") in seen_anomaly_sources:
            raise StateValidationError(
                "Anomaly history may contain at most one sample per source event."
            )
        seen_anomaly_sources.add(sample["source_event_id"])
        if not isinstance(sample.get("value"), int) or not 0 <= sample["value"] <= 100:
            raise StateValidationError("Anomaly history values must be in the 0-100 range.")

    threat_document = load_support_document(
        threat_history_path(case_id, root), case_id, "samples"
    )
    prior_threat_time: datetime | None = None
    seen_threat_keys: set[str] = set()
    for sample in threat_document["samples"]:
        if sample.get("case_id") != case_id:
            raise StateValidationError("A threat-history sample belongs to a different case.")
        sample_time = parse_timestamp(sample.get("timestamp"), "threat.timestamp")
        if prior_threat_time is not None and sample_time < prior_threat_time:
            raise StateValidationError("Threat-history timestamps must not move backward.")
        prior_threat_time = sample_time
        score = sample.get("score")
        if not isinstance(score, int) or not 0 <= score <= 100:
            raise StateValidationError("Threat history scores must be in the 0-100 range.")
        if sample.get("canonical_classification") != csharp_level(score):
            raise StateValidationError("Threat history classification is inconsistent.")
        if (
            sample.get("display_level_for_subsystem_06")
            != threat_display_level(score)
        ):
            raise StateValidationError(
                "Threat history display compatibility label is inconsistent."
            )
        source_key = sample.get("source_key")
        if (
            not isinstance(source_key, str)
            or not source_key
            or source_key in seen_threat_keys
        ):
            raise StateValidationError(
                "Threat history source keys must be populated and unique."
            )
        seen_threat_keys.add(source_key)

    system = load_json_document(system_status_path(case_id, root), missing_ok=True)
    if system is not None:
        if system.get("case_id") != case_id:
            raise StateValidationError("System status belongs to another case.")
        if system.get("state_revision") != case["state_revision"]:
            raise StaleDataError("System status is stale for the active case revision.")
        if system.get("telemetry_source") not in {"SIMULATED", "MEASURED"}:
            raise StateValidationError("System status must declare SIMULATED or MEASURED.")
        if system.get("measurement_status") != system.get("telemetry_source"):
            raise StateValidationError(
                "System status measurement_status must match telemetry_source."
            )
        parse_timestamp(system.get("updated_at"), "system_status.updated_at")
        telemetry = system.get("telemetry")
        if not isinstance(telemetry, dict):
            raise StateValidationError("System status telemetry must be an object.")
        if set(telemetry) != set(SYSTEM_STATUS_METRIC_UNITS):
            raise StateValidationError(
                "System status telemetry keys do not match the canonical contract."
            )
        for metric_name, expected_unit in SYSTEM_STATUS_METRIC_UNITS.items():
            metric = telemetry.get(metric_name)
            if not isinstance(metric, dict) or metric.get("unit") != expected_unit:
                raise StateValidationError(
                    f"System status {metric_name} must use unit {expected_unit!r}."
                )
            samples = metric.get("samples")
            if (
                not isinstance(samples, list)
                or not samples
            ):
                raise StateValidationError(
                    "System status telemetry samples must be populated integer values."
                )
            if expected_unit == "percent" and any(
                not isinstance(value, int) or not 0 <= value <= 100
                for value in samples
            ):
                raise StateValidationError(
                    f"System status {metric_name} percentage samples must be 0-100."
                )
            if expected_unit == "count" and any(
                not isinstance(value, int) or value < 0 for value in samples
            ):
                raise StateValidationError(
                    f"System status {metric_name} count samples must be nonnegative."
                )

    relationships = load_json_document(relationships_path(case_id, root), missing_ok=True)
    if relationships is not None:
        if relationships.get("case_id") != case_id:
            raise StateValidationError("Relationship state belongs to another case.")
        if relationships.get("state_revision") != case["state_revision"]:
            raise StaleDataError("Relationship state is stale for the active case revision.")
        parse_timestamp(relationships.get("updated_at"), "relationships.updated_at")
        records = relationships.get("relationships")
        if not isinstance(records, list):
            raise StateValidationError("Relationship state must contain a relationships list.")
        for relationship in records:
            if relationship.get("case_id") != case_id:
                raise StateValidationError("A relationship belongs to another case.")
        if validate_relationship_inputs:
            validate_relationship_document(
                case,
                relationships,
                evidence_count=evidence_count,
                correlation_count=correlation_count,
                threat=threat,
            )


def load_documents_for_case(
    case: dict[str, Any], root: Path | str | None = None
) -> dict[str, Any]:
    """Return existing support documents without manufacturing missing history."""

    case_id = case["case_id"]
    return {
        "events": load_support_document(events_path(case_id, root), case_id, "events"),
        "anomaly_history": load_support_document(
            anomaly_history_path(case_id, root), case_id, "samples"
        ),
        "threat_history": load_support_document(
            threat_history_path(case_id, root), case_id, "samples"
        ),
        "system_status": load_json_document(system_status_path(case_id, root), missing_ok=True),
        "relationships": load_json_document(relationships_path(case_id, root), missing_ok=True),
    }
