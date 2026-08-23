#!/usr/bin/env python3
"""Maintain a safe compatibility index for per-case evidence.

The per-case manifest is authoritative. This aggregate CSV remains a
repository-friendly compatibility index and is migrated without truncating its
legacy history.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from case_state import atomic_write_json, atomic_write_text


EVIDENCE_FILE = Path("evidence/evidence_log.csv")
LEGACY_HEADER = [
    "EvidenceID",
    "Date",
    "CaseID",
    "ArtifactType",
    "Description",
]
V2_HEADER = LEGACY_HEADER + [
    "Operation",
    "Classification",
    "Platform",
    "Device",
    "CollectedBy",
    "Status",
    "SchemaVersion",
]


def utc_stamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def csv_text(rows: list[list[str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(rows)
    return buffer.getvalue()


def _v2_from_legacy(row: list[str]) -> list[str]:
    return row + ["", "", "", "", "", "", "2"]


def _v2_from_previous_writer(row: list[str]) -> list[str]:
    # Historical writer order:
    # Evidence ID, Case ID, Date, Operation, Classification, Artifact Type,
    # Platform, Device, Collected By, Status
    return [
        row[0],
        row[2],
        row[1],
        row[5],
        "",
        row[3],
        row[4],
        row[6],
        row[7],
        row[8],
        row[9],
        "2",
    ]


def ensure_compatible_evidence_log(path: Path = EVIDENCE_FILE) -> tuple[list[list[str]], bool]:
    """Safely migrate only the known five/ten-column hybrid format."""

    if not path.exists():
        return [], False
    raw = path.read_bytes()
    rows = list(csv.reader(raw.decode("utf-8").splitlines()))
    if not rows:
        return [], False
    header, body = rows[0], rows[1:]
    if header == V2_HEADER:
        if any(len(row) != len(V2_HEADER) for row in body):
            raise ValueError("V2 evidence log has an invalid row width; it was not changed.")
        return body, False
    if header != LEGACY_HEADER:
        raise ValueError("Unknown evidence-log header; it was not changed.")

    migrated: list[list[str]] = []
    for row in body:
        if len(row) == len(LEGACY_HEADER):
            migrated.append(_v2_from_legacy(row))
        elif len(row) == 10:
            migrated.append(_v2_from_previous_writer(row))
        else:
            raise ValueError(
                f"Unknown evidence-log row width {len(row)}; source was not changed."
            )
    source_hash = hashlib.sha256(raw).hexdigest()
    stamp = utc_stamp().replace(":", "").replace("-", "")
    backup = path.with_name(
        f"{path.name}.pre-v2-{stamp}-{source_hash[:12]}.bak"
    )
    if backup.exists():
        raise ValueError(f"Refusing to replace evidence log; backup already exists: {backup}")
    backup.write_bytes(raw)
    atomic_write_text(path, csv_text([V2_HEADER, *migrated]))
    reloaded = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    if not reloaded or reloaded[0] != V2_HEADER or len(reloaded) - 1 != len(migrated):
        raise RuntimeError("Evidence-log migration verification failed after atomic replace.")
    atomic_write_json(
        path.with_name(f"{path.name}.migration-receipt.json"),
        {
            "schema_version": 2,
            "timestamp": utc_stamp(),
            "source_sha256": source_hash,
            "backup_path": str(backup).replace("\\", "/"),
            "legacy_rows": sum(len(row) == 5 for row in body),
            "previous_ten_column_rows": sum(len(row) == 10 for row in body),
            "target_rows": len(migrated),
            "target_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        },
    )
    return migrated, True


def next_evidence_id(rows: list[list[str]]) -> str:
    numbers = []
    for row in rows:
        if row and row[0].startswith("EV-") and row[0][3:].isdigit():
            numbers.append(int(row[0][3:]))
    return f"EV-{(max(numbers, default=0) + 1):05d}"


def append_case_index(case: dict, path: Path = EVIDENCE_FILE) -> str | None:
    rows, _ = ensure_compatible_evidence_log(path)
    existing_case_ids = {row[2] for row in rows if len(row) == len(V2_HEADER)}
    if case["case_id"] in existing_case_ids:
        return None
    artifact = {
        "Unauthorized Research System Access": "Authentication Logs",
        "Synthetic Genome Theft": "Research Database Export",
        "Memory Artifact Investigation": "Memory Capture",
        "Laboratory Network Intrusion": "Network Packet Capture",
        "Biomedical Data Exfiltration": "Data Archive",
        "Embedded Device Exposure": "Embedded Device Image",
        "Unauthorized Firmware Modification": "Firmware Binary",
        "Firmware Integrity Alert": "Firmware Image",
    }.get(case["classification"], "Digital Evidence")
    evidence_id = next_evidence_id(rows)
    row = [
        evidence_id,
        case["date"],
        case["case_id"],
        artifact,
        "",
        case["operation"],
        case["classification"],
        case["affected_platform"],
        case["device_family"],
        case["lead_analyst"],
        "Collected",
        "2",
    ]
    atomic_write_text(path, csv_text([V2_HEADER, *rows, row]))
    return evidence_id


def main() -> None:
    with open("data/current_case.json", "r", encoding="utf-8") as handle:
        case = json.load(handle)
    evidence_id = append_case_index(case)
    if evidence_id is None:
        print(f"Evidence compatibility index already contains {case['case_id']}.")
    else:
        print(f"Evidence compatibility index recorded: {evidence_id}")


if __name__ == "__main__":
    main()
