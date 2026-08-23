#!/usr/bin/env python3
"""Repair legacy evidence-correlation case linkage without recalculating it.

Subsystem #10 uses this one-purpose, idempotent migration before frozen
Subsystem #8 lifecycle validation.  It preserves the authoritative correlation
payload exactly except for adding a missing per-record ``case_id`` field.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from case_state import atomic_write_json


def repository_root(value: Path | None = None) -> Path:
    return (value or Path(__file__).resolve().parents[1]).resolve()


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_backup(source: Path, destination: Path) -> None:
    """Preserve the exact pre-migration bytes before an authoritative edit."""

    payload = source.read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def migrate_legacy_correlation_linkage(root: Path | None = None) -> dict[str, Any]:
    """Add only missing same-case record links and return an audit record."""

    root = repository_root(root)
    case_path = root / "data" / "current_case.json"
    with case_path.open("r", encoding="utf-8") as handle:
        case = json.load(handle)
    case_id = case.get("case_id") if isinstance(case, dict) else None
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("Current case must provide a non-empty case_id before migration.")

    correlation_path = root / "evidence" / case_id / "evidence_correlations.json"
    if not correlation_path.is_file():
        raise FileNotFoundError(f"Missing authoritative correlation file: {correlation_path}")
    before_hash = sha256_path(correlation_path)
    with correlation_path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict):
        raise ValueError("Correlation document must be a JSON object.")
    if document.get("case_id") != case_id:
        raise ValueError("Correlation document case_id does not match the active case.")
    correlations = document.get("correlations")
    if not isinstance(correlations, list):
        raise ValueError("Correlation document correlations must be a list.")
    if document.get("correlation_count") != len(correlations):
        raise ValueError("Correlation count does not match correlation records.")

    added_links = 0
    for index, record in enumerate(correlations):
        if not isinstance(record, dict):
            raise ValueError(f"Correlation record {index} is not an object.")
        evidence_id = record.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id.startswith(f"{case_id}-EV-"):
            raise ValueError(
                f"Correlation record {index} evidence_id does not belong to {case_id}."
            )
        existing_case_id = record.get("case_id")
        if existing_case_id in (None, ""):
            record["case_id"] = case_id
            added_links += 1
        elif existing_case_id != case_id:
            raise ValueError(
                f"Correlation record {index} is linked to another case: {existing_case_id!r}"
            )

    backup_path = correlation_path.with_name(
        "evidence_correlations.pre_subsystem10_backup.json"
    )
    if added_links:
        if backup_path.exists():
            if sha256_path(backup_path) != before_hash:
                raise ValueError(
                    "Existing pre-Subsystem #10 correlation backup does not match "
                    "the authoritative pre-migration payload."
                )
        else:
            atomic_backup(correlation_path, backup_path)
        atomic_write_json(correlation_path, document)

    after_hash = sha256_path(correlation_path)
    return {
        "root": str(root),
        "case_id": case_id,
        "correlation_path": str(correlation_path),
        "backup_path": str(backup_path) if backup_path.exists() else None,
        "record_count_before": len(correlations),
        "record_count_after": len(correlations),
        "added_case_id_links": added_links,
        "before_sha256": before_hash,
        "after_sha256": after_hash,
        "backup_sha256": sha256_path(backup_path) if backup_path.exists() else None,
        "all_records_linked_to_active_case": all(
            record.get("case_id") == case_id for record in correlations
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate missing case_id links in a legacy correlation file."
    )
    parser.add_argument(
        "--root", type=Path, default=None, help="Repository root (defaults to this script's parent)."
    )
    args = parser.parse_args()
    print(json.dumps(migrate_legacy_correlation_linkage(args.root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
