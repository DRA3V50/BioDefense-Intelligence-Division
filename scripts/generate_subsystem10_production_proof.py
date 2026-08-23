#!/usr/bin/env python3
"""Generate repeatable Subsystem #10 proof and cross-panel consistency records."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


FRAME_INDICES = (0, 20, 40, 60, 80, 100, 119)
MOTION_INDICES = tuple(range(0, 120, 10))


def repository_root(value: Path | None = None) -> Path:
    return (value or Path(__file__).resolve().parents[1]).resolve()


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_document(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def decode_gif(path: Path) -> tuple[dict[str, Any], list[Image.Image]]:
    frames: list[Image.Image] = []
    hashes: list[str] = []
    full_canvas = 0
    disposal_2 = 0
    duration_50 = 0
    with Image.open(path) as image:
        metadata = {
            "format": image.format,
            "dimensions": list(image.size),
            "frame_count": image.n_frames,
            "duration_per_frame_ms": int(image.info.get("duration", 0)),
            "loop": int(image.info.get("loop", -1)),
        }
        for index in range(image.n_frames):
            image.seek(index)
            tile = image.tile[0][1] if image.tile else None
            if tuple(tile or ()) == (0, 0, 1727, 911):
                full_canvas += 1
            if int(getattr(image, "disposal_method", 0)) == 2:
                disposal_2 += 1
            if int(image.info.get("duration", 0)) == 50:
                duration_50 += 1
            decoded = image.convert("RGB").copy()
            frames.append(decoded)
            hashes.append(hashlib.sha256(decoded.tobytes()).hexdigest())
    metadata.update(
        {
            "full_canvas_frames": full_canvas,
            "disposal_2_frames": disposal_2,
            "duration_50ms_frames": duration_50,
            "unique_decoded_frames": len(set(hashes)),
        }
    )
    return metadata, frames


def make_contact_sheet(
    frames: list[Image.Image], indices: tuple[int, ...], path: Path, label: str
) -> None:
    scale = 0.25
    width = round(frames[0].width * scale)
    height = round(frames[0].height * scale)
    label_height = 26
    padding = 10
    columns = 3
    rows = (len(indices) + columns - 1) // columns
    canvas = Image.new(
        "RGB",
        (padding + columns * (width + padding), padding + rows * (height + label_height + padding)),
        (5, 8, 10),
    )
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for position, frame_index in enumerate(indices):
        row, column = divmod(position, columns)
        left = padding + column * (width + padding)
        top = padding + row * (height + label_height + padding)
        frame = frames[frame_index].resize((width, height), Image.Resampling.LANCZOS)
        canvas.paste(frame, (left, top))
        draw.text((left, top + height + 5), f"{label} {frame_index:03d}", fill=(226, 230, 233), font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def build_consistency(root: Path, gif_metadata: dict[str, Any]) -> dict[str, Any]:
    case = load_document(root / "data" / "current_case.json")
    case_id = str(case["case_id"])
    campaign_id = str(case["campaign_id"])
    evidence_root = root / "evidence" / case_id
    state_root = root / "cases" / "state" / case_id
    operation = load_document(root / "operations" / "active_operation.json")
    csharp = load_document(root / "reports" / "bioterror_threat_score_csharp.json")
    manifest = load_document(evidence_root / "evidence_manifest.json")
    correlations = load_document(evidence_root / "evidence_correlations.json")
    events = load_document(state_root / "events.json")
    anomaly = load_document(state_root / "anomaly_history.json")
    threat_history = load_document(state_root / "threat_history.json")
    system_status = load_document(state_root / "system_status.json")
    relationships = load_document(state_root / "relationships.json")
    candidate_consistency = load_document(
        root / "assets" / "deployment_candidate" / "full_dashboard_data_consistency.json"
    )
    candidate_qc = load_document(
        root / "assets" / "deployment_candidate" / "subsystem_10_candidate_qc.json"
    )
    deployed_gif = root / "assets" / "biodefense-case-scan.gif"
    deployed_png = root / "assets" / "biodefense-dashboard-current.png"
    candidate_gif = root / "assets" / "deployment_candidate" / "biodefense-case-scan.gif"
    candidate_png = root / "assets" / "deployment_candidate" / "biodefense-dashboard-current.png"
    if not all(path.is_file() for path in (deployed_gif, deployed_png, candidate_gif, candidate_png)):
        raise ValueError("The verified candidate/deployed dashboard asset set is incomplete.")
    with Image.open(deployed_png) as image:
        deployed_png_dimensions = list(image.size)
        deployed_png_format = image.format
    investigation = csharp.get("investigation", {})
    assessment = csharp.get("assessment", {})
    evidence_items = manifest.get("evidence_items", [])
    correlation_items = correlations.get("correlations", [])
    event_items = events.get("events", [])
    anomaly_samples = anomaly.get("samples", [])
    threat_samples = threat_history.get("samples", [])
    relation_items = relationships.get("relationships", [])
    score = assessment.get("overallScore")
    classification = assessment.get("overallLevel")
    revision = case.get("state_revision")
    current_revision_threat_samples = [
        item
        for item in threat_samples
        if isinstance(item, dict) and item.get("case_revision") == revision
    ]

    checks = {
        "same_case_id_everywhere": all(
            value == case_id
            for value in (
                manifest.get("case_id"),
                correlations.get("case_id"),
                events.get("case_id"),
                anomaly.get("case_id"),
                threat_history.get("case_id"),
                system_status.get("case_id"),
                relationships.get("case_id"),
                investigation.get("caseId"),
                candidate_consistency.get("case_id"),
            )
        ),
        "same_campaign_id_everywhere": all(
            value == campaign_id
            for value in (
                operation.get("campaign_id"),
                investigation.get("campaignId"),
                candidate_consistency.get("campaign_id"),
            )
        ) and all(sample.get("campaign_id") == campaign_id for sample in threat_samples),
        "same_current_stage": candidate_consistency.get("current_stage") == case.get("current_stage"),
        "same_lifecycle_status": candidate_consistency.get("lifecycle_status") == case.get("lifecycle_status"),
        "same_evidence_count": (
            case.get("evidence_count") == manifest.get("evidence_count") == len(evidence_items)
            and correlations.get("correlation_count") == len(correlation_items) == len(evidence_items)
            and candidate_consistency.get("evidence_count") == case.get("evidence_count")
        ),
        "same_severity": investigation.get("severity") == case.get("severity"),
        "same_priority": investigation.get("priority") == case.get("priority"),
        "same_lead_analyst": candidate_consistency.get("lead_analyst") == case.get("lead_analyst"),
        "same_threat_score": candidate_consistency.get("threat_score") == score,
        "same_canonical_classification": (
            candidate_consistency.get("canonical_threat_classification") == classification
        ),
        "same_state_revision": all(
            value == revision
            for value in (
                investigation.get("caseRevision"),
                system_status.get("state_revision"),
                relationships.get("state_revision"),
                candidate_consistency.get("state_revision"),
            )
        ) and bool(current_revision_threat_samples),
        "feed_event_case_ids_match": all(item.get("case_id") == case_id for item in event_items),
        "evidence_case_ids_match": all(item.get("case_id") == case_id for item in evidence_items),
        "correlation_case_ids_match": all(item.get("case_id") == case_id for item in correlation_items),
        "anomaly_history_matches": all(item.get("case_id") == case_id for item in anomaly_samples),
        "threat_history_matches": all(
            item.get("case_id") == case_id
            and item.get("campaign_id") == campaign_id
            for item in threat_samples
        ) and all(
            item.get("score") == score
            and item.get("canonical_classification") == classification
            for item in current_revision_threat_samples
        ) and candidate_qc.get("threat_history_projection", {}).get(
            "authoritative_sample_count"
        ) == len(threat_samples) and candidate_qc.get(
            "threat_history_projection", {}
        ).get("projected_current_revision_sample_count") == len(
            current_revision_threat_samples
        ),
        "system_status_matches": (
            system_status.get("case_id") == case_id
            and system_status.get("state_revision") == revision
            and system_status.get("telemetry_source") in {"SIMULATED", "MEASURED"}
        ),
        "relationships_match": (
            relationships.get("case_id") == case_id
            and relationships.get("state_revision") == revision
            and len(relation_items) == 6
            and all(item.get("case_id") == case_id for item in relation_items)
        ),
        "workflow_state_matches": candidate_consistency.get("current_stage") == case.get("current_stage"),
        "campaign_linkage_matches": operation.get("campaign_id") == campaign_id,
        "gif_contract_matches": gif_metadata == {
            "format": "GIF",
            "dimensions": [1727, 911],
            "frame_count": 120,
            "duration_per_frame_ms": 50,
            "loop": 0,
            "full_canvas_frames": 120,
            "disposal_2_frames": 120,
            "duration_50ms_frames": 120,
            "unique_decoded_frames": 120,
        },
        "deployed_png_contract_matches": (
            deployed_png_format == "PNG" and deployed_png_dimensions == [1727, 911]
        ),
        "candidate_deployment_hashes_match": (
            sha256_path(candidate_gif) == sha256_path(deployed_gif)
            and sha256_path(candidate_png) == sha256_path(deployed_png)
            and candidate_qc.get("verification", {}).get("gif_sha256") == sha256_path(deployed_gif)
            and candidate_qc.get("verification", {}).get("png_sha256") == sha256_path(deployed_png)
        ),
    }
    failures = [key for key, value in checks.items() if not value]
    if failures:
        raise ValueError("Production data consistency failed: " + ", ".join(failures))

    source_paths = {
        "active_case": root / "data" / "current_case.json",
        "active_operation": root / "operations" / "active_operation.json",
        "csharp_report": root / "reports" / "bioterror_threat_score_csharp.json",
        "evidence_manifest": evidence_root / "evidence_manifest.json",
        "evidence_correlations": evidence_root / "evidence_correlations.json",
        "events": state_root / "events.json",
        "anomaly_history": state_root / "anomaly_history.json",
        "threat_history": state_root / "threat_history.json",
        "system_status": state_root / "system_status.json",
        "relationships": state_root / "relationships.json",
        "production_gif": root / "assets" / "biodefense-case-scan.gif",
        "production_png": root / "assets" / "biodefense-dashboard-current.png",
        "candidate_gif": candidate_gif,
        "candidate_png": candidate_png,
        "candidate_qc": root / "assets" / "deployment_candidate" / "subsystem_10_candidate_qc.json",
    }
    return {
        "schema_version": 1,
        "case_id": case_id,
        "campaign_id": campaign_id,
        "current_stage": case["current_stage"],
        "lifecycle_status": case["lifecycle_status"],
        "state_revision": revision,
        "severity": case["severity"],
        "priority": case["priority"],
        "lead_analyst": case["lead_analyst"],
        "evidence_count": case["evidence_count"],
        "event_count": len(event_items),
        "correlation_count": len(correlation_items),
        "threat_score": score,
        "canonical_classification": classification,
        "event_ids": [item.get("event_id") or item.get("id") for item in event_items],
        "evidence_ids": [item.get("evidence_id") for item in evidence_items],
        "correlation_evidence_ids": [item.get("evidence_id") for item in correlation_items],
        "checks": checks,
        "renderer_consistency": candidate_consistency,
        "gif_metadata": gif_metadata,
        "deployed_png_metadata": {
            "format": deployed_png_format,
            "dimensions": deployed_png_dimensions,
        },
        "source_hashes": {name: sha256_path(path) for name, path in source_paths.items()},
    }


def generate(root: Path | None = None) -> dict[str, Any]:
    root = repository_root(root)
    deployed_gif = root / "assets" / "biodefense-case-scan.gif"
    proof_dir = root / "reports" / "subsystem_10_production_proof"
    metadata, frames = decode_gif(deployed_gif)
    if metadata["frame_count"] != 120:
        raise ValueError("Production GIF is not the required 120-frame dashboard loop.")
    proof_dir.mkdir(parents=True, exist_ok=True)
    for index in FRAME_INDICES:
        frames[index].save(proof_dir / f"production_dashboard_frame_{index:03d}.png")
    make_contact_sheet(
        frames, FRAME_INDICES, proof_dir / "production_dashboard_contact_sheet.png", "DECODED FRAME"
    )
    make_contact_sheet(
        frames, MOTION_INDICES, proof_dir / "production_dashboard_motion_audit.png", "DECODED FRAME"
    )
    consistency = build_consistency(root, metadata)
    report_path = root / "reports" / "subsystem_10_data_consistency.json"
    atomic_write_json(report_path, consistency)
    return {
        "proof_directory": str(proof_dir.relative_to(root)).replace("\\", "/"),
        "proof_frames": [f"production_dashboard_frame_{index:03d}.png" for index in FRAME_INDICES],
        "data_consistency": str(report_path.relative_to(root)).replace("\\", "/"),
        "case_id": consistency["case_id"],
        "gif_metadata": metadata,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create Subsystem #10 production proof artifacts.")
    parser.add_argument("--root", type=Path, default=None, help="Repository root.")
    args = parser.parse_args()
    print(json.dumps(generate(args.root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
