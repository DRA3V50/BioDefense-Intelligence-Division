#!/usr/bin/env python3
"""Synchronize frozen Subsystem #8 sidecars without evaluating lifecycle.

The production workflow runs this after the canonical C# score has been
refreshed.  It intentionally does not save or otherwise alter the active-case
document, so a post-score synchronization cannot cause a second lifecycle
transition in one workflow run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from case_lifecycle import load_validated_artifact_snapshot
from case_state import (
    CaseStateError,
    StateValidationError,
    load_active_case,
    load_normalized_csharp_threat,
    synchronize_anomaly_history,
    synchronize_relationships,
    synchronize_system_status,
    synchronize_threat_history,
    validate_active_case,
    validate_support_state,
)


def repository_root(value: Path | None = None) -> Path:
    return (value or Path(__file__).resolve().parents[1]).resolve()


def synchronize_case_support_state(root: Path | None = None) -> dict[str, Any]:
    """Refresh derived sidecars for one validated active case, never lifecycle."""

    root = repository_root(root)
    case = load_active_case(root)
    if case is None:
        raise CaseStateError("Cannot synchronize support state without an active case.")
    validate_active_case(case)
    artifacts = load_validated_artifact_snapshot(case, root)
    threat = load_normalized_csharp_threat(case, root)
    if threat is None:
        raise StateValidationError(
            "A current C# threat report is required before support-state synchronization."
        )

    anomaly = synchronize_anomaly_history(case, root)
    threat_history = synchronize_threat_history(case, root)
    system_status = synchronize_system_status(case, root, threat=threat)
    relationships = synchronize_relationships(
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
    return {
        "case_id": case["case_id"],
        "campaign_id": case["campaign_id"],
        "state_revision": case["state_revision"],
        "current_stage": case["current_stage"],
        "lifecycle_status": case["lifecycle_status"],
        "evidence_count": artifacts.evidence_count,
        "correlation_count": artifacts.correlation_count,
        "threat_score": threat["score"],
        "canonical_classification": threat["canonical_classification"],
        "anomaly_samples": len(anomaly["samples"]),
        "threat_history_synced": threat_history is not None,
        "system_status_source": system_status["telemetry_source"],
        "relationship_count": len(relationships["relationships"]),
        "active_case_mutated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize #8 sidecars without evaluating lifecycle."
    )
    parser.add_argument(
        "--root", type=Path, default=None, help="Repository root (defaults to this script's parent)."
    )
    args = parser.parse_args()
    print(json.dumps(synchronize_case_support_state(args.root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
