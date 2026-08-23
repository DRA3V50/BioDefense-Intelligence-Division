#!/usr/bin/env python3
"""Read-only normalized adapter for the frozen dashboard subsystems.

No renderer is imported here and no lifecycle transition is performed here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from case_lifecycle import load_validated_artifact_snapshot
from case_state import (
    CSHARP_THREAT_REPORT,
    CaseStateError,
    StaleDataError,
    StateValidationError,
    load_active_case,
    load_documents_for_case,
    load_json_document,
    load_normalized_csharp_threat,
    repository_root,
    csharp_level,
    threat_display_level,
    validate_active_case,
    validate_support_state,
)


ACTIVE_OPERATION_FILE = Path("operations/active_operation.json")

CROSS_PANEL_MAPPING = {
    "shared.case_id": ["Subsystem #2", "Subsystem #3", "Subsystem #4", "Subsystem #5", "Subsystem #6", "Subsystem #7"],
    "shared.campaign_id": ["Subsystem #3", "Subsystem #7"],
    "workflow.current_stage": ["Subsystem #3 Workflow Strip"],
    "active_case_feed.events": ["Subsystem #4 Active Case Feed"],
    "active_case_feed.event_intensity_history": ["Subsystem #4 Active Case Feed"],
    "evidence_package.manifest": ["Subsystem #2 Evidence Package"],
    "system_status": ["Subsystem #5 System Status"],
    "threat_monitor.score_and_history": ["Subsystem #6 Threat Monitor"],
    "case_overview.relationships": ["Subsystem #7 Case Overview"],
}


def _operation_context(case: dict[str, Any], root: Path | str | None) -> dict[str, Any]:
    operation = load_json_document(
        repository_root(root) / ACTIVE_OPERATION_FILE, missing_ok=True
    )
    if operation is None:
        return {}
    campaign_id = operation.get("campaign_id")
    if campaign_id and campaign_id != case["campaign_id"]:
        raise StaleDataError("Active operation campaign_id does not match active case.")
    return {
        "campaign_id": case["campaign_id"],
        "operation": operation.get("operation"),
        "campaign_phase": operation.get("campaign_phase"),
        "containment_level": operation.get("containment_level"),
        "next_objective": operation.get("next_objective"),
    }


def _shared_case_fields(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "campaign_id": case["campaign_id"],
        "lifecycle_status": case["lifecycle_status"],
        "current_stage": case["current_stage"],
        "severity": case["severity"],
        "priority": case["priority"],
        "lead_analyst": case["lead_analyst"],
        "evidence_count": case["evidence_count"],
        "ioc_count": case["ioc_count"],
        "updated_at": case["updated_at"],
        "state_revision": case["state_revision"],
    }


def build_dashboard_state(root: Path | str | None = None) -> dict[str, Any]:
    """Build one coherent dashboard input from one validated active case."""

    case = load_active_case(root)
    if case is None:
        raise CaseStateError("No persistent active case is available.")
    validate_active_case(case)

    artifacts = load_validated_artifact_snapshot(case, root)
    threat = load_normalized_csharp_threat(case, root)
    if threat is None:
        raise StateValidationError(
            "A current C# threat report is required for a complete dashboard state."
        )
    validate_support_state(
        case,
        root,
        evidence_count=artifacts.evidence_count,
        correlation_count=artifacts.correlation_count,
        threat=threat,
        validate_relationship_inputs=True,
    )
    documents = load_documents_for_case(case, root)
    system_status = documents["system_status"]
    relationships = documents["relationships"]
    if system_status is None:
        raise StateValidationError("System status has not been synchronized.")
    if relationships is None:
        raise StateValidationError("Case-overview relationships have not been synchronized.")

    shared = _shared_case_fields(case)
    state = {
        "schema_version": 1,
        "shared": shared,
        "operation_context": _operation_context(case, root),
        "workflow": {
            "case_id": case["case_id"],
            "current_stage": case["current_stage"],
        },
        "active_case_feed": {
            "case_id": case["case_id"],
            "events": documents["events"]["events"],
            "event_intensity_history": documents["anomaly_history"]["samples"],
        },
        "evidence_package": {
            "case_id": case["case_id"],
            "evidence_count": artifacts.evidence_count,
            "manifest": {
                "path": f"evidence/{case['case_id']}/evidence_manifest.json",
                "items": artifacts.evidence_items,
            },
        },
        "system_status": system_status,
        "threat_monitor": {
            "case_id": case["case_id"],
            "canonical_threat_score_source": "C# scorer",
            "threat": {
                "score": threat["score"],
                "canonical_classification": threat["canonical_classification"],
                "display_level_for_subsystem_06": threat[
                    "display_level_for_subsystem_06"
                ],
                "display_level_role": (
                    "Frozen Subsystem #6 compatibility vocabulary derived "
                    "from the same canonical score; not an authoritative "
                    "classification."
                ),
            },
            "anomaly_history": documents["anomaly_history"]["samples"],
            "threat_history": documents["threat_history"]["samples"],
            "source_report": threat["report_path"],
        },
        "case_overview": {
            "case_id": case["case_id"],
            "relationships": relationships["relationships"],
            "nodes": relationships["nodes"],
        },
        "provenance": {
            "active_case_path": "data/current_case.json",
            "threat_report_path": str(CSHARP_THREAT_REPORT).replace("\\", "/"),
            "system_status_source": system_status["telemetry_source"],
            "frozen_renderer_invoked": False,
        },
    }
    validate_dashboard_state(state)
    return state


def validate_dashboard_state(state: dict[str, Any]) -> None:
    shared = state.get("shared")
    if not isinstance(shared, dict):
        raise StateValidationError("Dashboard state must contain shared fields.")
    case_id = shared.get("case_id")
    if not isinstance(case_id, str):
        raise StateValidationError("Dashboard shared case_id is required.")

    branches = (
        state.get("workflow"),
        state.get("active_case_feed"),
        state.get("evidence_package"),
        state.get("threat_monitor"),
        state.get("case_overview"),
    )
    for branch in branches:
        if not isinstance(branch, dict) or branch.get("case_id") != case_id:
            raise StateValidationError("Every dashboard branch must use the active case_id.")

    if state["workflow"].get("current_stage") != shared.get("current_stage"):
        raise StateValidationError("Workflow stage must come from shared active-case state.")
    if state["evidence_package"].get("evidence_count") != shared.get("evidence_count"):
        raise StateValidationError("Evidence count must remain cross-panel consistent.")
    threat = state["threat_monitor"].get("threat")
    if not isinstance(threat, dict):
        raise StateValidationError("Threat Monitor must contain a canonical threat object.")
    score = threat.get("score")
    if score not in range(0, 101):
        raise StateValidationError("Threat Monitor score must be in the 0-100 range.")
    if threat.get("canonical_classification") != csharp_level(score):
        raise StateValidationError(
            "Threat Monitor canonical classification must match the C# score."
        )
    if threat.get("display_level_for_subsystem_06") != threat_display_level(score):
        raise StateValidationError(
            "Threat Monitor display compatibility level must derive from the same score."
        )
    if state["system_status"].get("case_id") != case_id:
        raise StateValidationError("System status must belong to the active case.")
    if state["system_status"].get("telemetry_source") not in {"SIMULATED", "MEASURED"}:
        raise StateValidationError("System status source must be truthfully declared.")


if __name__ == "__main__":
    print(json.dumps(build_dashboard_state(), indent=2))
