#!/usr/bin/env python3
"""Render only the Threat Monitor panel as a deterministic isolated preview."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
POPULATED_PATH = ROOT / "APPROVED_POPULATED_LAYOUT.png"
CLEAR_PATH = ROOT / "APPROVED_CLEAR_BASE_LAYOUT.png"
BIOHAZARD_REFERENCE_PATH = ROOT / "BIOHAZARD_REFERENCE.png"
GENERATE_CASE_BANNER_PATH = ROOT / "generate_case_banner.py"
OUT_DIR = ROOT / "threat_monitor_test_output"
SCRIPT_NAME = Path(__file__).name

EXPECTED_MASTER_SHA256 = {
    POPULATED_PATH: "90a223d08555853fd58c7bc7c0c30eadecfa7df3b5320db23e373462735312c4",
    CLEAR_PATH: "168d5b6ba745de5431f8fbaa9c5d5e4a95464b9e150f6aa23b862e4800d68f38",
    BIOHAZARD_REFERENCE_PATH: "ec0eb4cd38db13d34c0259f8ba920e4d9a1d2783feeb2f0d25e4ea2b0bf52ba5",
}
EXPECTED_GENERATE_CASE_BANNER_SHA256 = "7f55235c485f3f3a3c7eeddd66aa8aece965979cc2ebccf9047a00b4fd51213a"

FROZEN_ARCHIVE_ROOT = ROOT / "approved_subsystems"
FROZEN_WORKING_SCRIPT_ARCHIVES = {
    ROOT / "biohazard_test.py": FROZEN_ARCHIVE_ROOT / "subsystem_01_biohazard_APPROVED" / "biohazard_test.py",
    ROOT / "magnifying_glass_test.py": FROZEN_ARCHIVE_ROOT / "subsystem_02_evidence_magnifier_APPROVED" / "magnifying_glass_test.py",
    ROOT / "workflow_strip_test.py": FROZEN_ARCHIVE_ROOT / "approved_subsystem_03_workflow" / "workflow_strip_test.py",
    ROOT / "active_case_feed_test.py": FROZEN_ARCHIVE_ROOT / "approved_subsystem_04_active_case_feed" / "active_case_feed_test.py",
    ROOT / "system_status_test.py": FROZEN_ARCHIVE_ROOT / "approved_subsystem_05_system_status" / "system_status_test.py",
}

# The populated source crop retains all approved static text, graph shell,
# score, threshold guide, summary, separators, and panel border untouched.
PANEL_BOUNDS = (836, 555, 1284, 822)
PANEL_SIZE = (PANEL_BOUNDS[2] - PANEL_BOUNDS[0], PANEL_BOUNDS[3] - PANEL_BOUNDS[1])
EXPECTED_PANEL_SHA256 = "d445b4a21ce7fca199f4f5d02d28b7d0b9c4bc79e7cf092ff807cce3ffcd8cb3"

# Fixed graph shell / strict dynamic work bounds, all half-open master pixels.
AXIS_BOX = (955, 609, 1240, 666)
WORKBOX = (955, 610, 1238, 662)
DRAW_CLIP = (956, 612, 1237, 660)
# The dynamic mask remains fixed.  The white source Y-axis is replaced only
# inside this authorized static right-scale region.  The final static restore
# starts at x=1236, leaving x=1235 as the final visible telemetry column and
# a one-pixel gutter before the new discrete scale ticks.
# Clear the complete former scale fringe through x=1244 before rebuilding the
# new scale.  The earlier narrower repair left a few anti-aliased neutral
# source dashes immediately beside the intentional red ticks.
RIGHT_SCALE_CLEAR_BOUNDS = (1236, 609, 1245, 666)
RIGHT_SCALE_STATIC_BOUNDS = (1236, 609, 1245, 666)
RIGHT_SCALE_GUTTER_BOUNDS = (1236, 612, 1237, 660)
RIGHT_AXIS_PROTECTED_START_X = DRAW_CLIP[2]
VISIBLE_SIGNAL_TERMINAL_X = RIGHT_SCALE_STATIC_BOUNDS[0] - 1
# Static graph-presentation redraw is expressly limited to this existing
# Threat Monitor graph/scale/label region. It begins below the immutable
# LIVE SIGNAL heading and ends above the immutable panel separator.
GRAPH_PRESENTATION_BOUNDS = (955, 605, 1283, 688)
GRAPH_LABEL_CLEAR_BOUNDS = (
    (956, 669, 994, 684),
    (1018, 669, 1050, 684),
    (1086, 669, 1118, 684),
    (1153, 669, 1183, 684),
    (1213, 669, 1247, 684),
    (1055, 678, 1150, 688),
    # Keep these scale-label repairs locally bounded.  A single tall inpaint
    # hole produced a visible gray diffusion wedge; these overlapping source
    # cleanup bounds remove each legacy/new-label footprint without that drift.
    (1245, 605, 1280, 621),
    (1245, 617, 1265, 631),
    (1245, 630, 1280, 647),
    (1245, 647, 1265, 661),
    (1245, 657, 1280, 672),
)
X_TICK_ANCHORS = (956, 1026, 1096, 1166, 1235)
Y_SCALE_VALUES = (100, 75, 50, 25, 0)
Y_SCALE_TICK_GLOBAL_Y = (615, 625, 635, 645, 655)
Y_SCALE_TICK_GLOBAL_X = (1237, 1244)
Y_SCALE_TICK_RGB = (133, 45, 42)
Y_SCALE_LABEL_RGB = (184, 174, 172)
Y_SCALE_LABELS = (
    (1247, 610, "100", Y_SCALE_LABEL_RGB),
    (1247, 620, "75", Y_SCALE_LABEL_RGB),
    (1247, 630, "50", Y_SCALE_LABEL_RGB),
    (1247, 640, "25", Y_SCALE_LABEL_RGB),
    (1247, 650, "0", Y_SCALE_LABEL_RGB),
)
RIGHT_SCALE_NEUTRAL_RESIDUAL_AUDIT_BOUNDS = (1236, 609, 1245, 666)
RIGHT_SCALE_NEUTRAL_MAX_SATURATION = 30
RIGHT_SCALE_NEUTRAL_MIN_BRIGHTNESS = 25
LEGACY_Y_WORD_AUDIT_BOUNDS = (
    (1266, 605, 1280, 621),
    (1263, 630, 1280, 647),
    (1259, 657, 1280, 672),
)
AREA_FILL_RGB = (145, 24, 21)
# Peak alpha is deliberately stronger than the prior 48 so the existing
# fading field remains visibly dark red after fixed-palette GIF decoding.
AREA_FILL_MAX_ALPHA = 80
AREA_FILL_HALO_OFFSET = 3
AREA_FILL_FLOOR_OFFSET = 7
AREA_FILL_POWER = 1.45
DECODED_AREA_HEAD_MIN_ALPHA = 40
DECODED_AREA_MIN_RED_CHROMA_GAIN = 12
DECODED_AREA_HEAD_MIN_COVERAGE = 0.99
DECODED_AREA_ALL_MIN_COVERAGE = 0.55
EXPECTED_SOURCE_SIGNAL_PIXELS = 3533
EXPECTED_CLEANUP_PIXELS = 6449
EXPECTED_SOURCE_SIGNAL_BBOX = (955, 613, 1238, 659)
EXPECTED_CLEANUP_BBOX = (955, 610, 1238, 662)
EXPECTED_SOURCE_TRACE_FILL_PIXELS = 8618
EXPECTED_SOURCE_TRACE_FILL_BBOX = (955, 611, 1238, 662)
EXPECTED_TRACE_FILL_CLEANUP_PIXELS = 9153
EXPECTED_TRACE_FILL_CLEANUP_BBOX = (955, 610, 1238, 662)
WEAK_TRACE_FILL_RED_MIN = 3
WEAK_TRACE_FILL_RED_DELTA = 1
TRACE_FILL_RESIDUAL_RED_MIN = 6
TRACE_FILL_RESIDUAL_RED_DELTA = 3
EXPECTED_INPAINT_SEED_GUARD_PIXELS = 1068
RIGHT_EDGE_WEDGE_AUDIT = (1215, 620, 1237, 645)
RIGHT_EDGE_GUARD_RGB = (3, 5, 6)
RIGHT_EDGE_NEUTRAL_MIN_BRIGHTNESS = 40
RIGHT_EDGE_AXIS_GUARD = (1215, 610, 1240, 662)
RIGHT_EDGE_AXIS_GUARD_MIN_BRIGHTNESS = 20
EXPECTED_RIGHT_EDGE_AXIS_GUARD_PIXELS = 136
EXPECTED_RESTORED_RIGHT_EDGE_AXIS_GUARD_PIXELS = 118

FRAME_COUNT = 60
FRAME_DURATION_MS = 100
KEYFRAME_INDICES = (0, 12, 24, 36, 48, 59)
MOTION_AUDIT_INDICES = (0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 59)
EXPECTED_PREVIEW_PROFILE_SHA256 = "8c4903b32dba7550e6394ad552e7b3be73825bab73662091b3fff90e9b6d8056"
EXPECTED_SIGNAL_Y_VALUES_SHA256 = "999ef9d328426c7cf71cdd2103e0fdc6541e580dca34d7313e9ab512b6bfc357"

# Public renderer data contract: anomaly_history is chronological external
# telemetry in the normalized 0-100 domain, ending at NOW.  Drawing code
# never seeds it at 50, randomizes it, or persists it.  Production will pass
# the active case's saved history here; a newly created case is initialized
# upstream from that case's state and later samples are persisted upstream.
ANOMALY_HISTORY_MIN = 0.0
ANOMALY_HISTORY_MAX = 100.0
ANOMALY_HISTORY_FIELD = "anomaly_history"

THRESHOLD_GUIDE = (
    ("CRITICAL", 80, 100),
    ("HIGH", 60, 79),
    ("MEDIUM", 30, 59),
    ("LOW", 0, 29),
)

# This is intentionally structured preview data.  The renderer receives a
# frame-specific threat_monitor object derived from it rather than inventing
# score or telemetry values in drawing code.  Future integration can replace
# this factory with data from the persistent active case.
THREAT_MONITOR_PREVIEW: dict[str, object] = {
    "case_id": "BID-2026-9147",
    "preview_only": True,
    "threat_score": 87,
    "threat_level": "CRITICAL",
    "threshold_guide": THRESHOLD_GUIDE,
    "controlled_events": (
        ("baseline", 0.00, "elevated baseline telemetry"),
        ("medium_anomaly", 0.20, "localized anomaly rise"),
        ("high_anomaly", 0.42, "sustained anomaly expansion"),
        ("critical_spike", 0.60, "critical sensor spike"),
        ("recovery", 0.80, "partial recovery and stabilization"),
    ),
    "threat_summary": (
        "Elevated insider activity detected",
        "Data tampering attempt in progress",
        "Multiple sensor integrity violations",
        "Lateral movement indicators observed",
        "Containment protocols engaged",
    ),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_array(array: np.ndarray) -> str:
    return sha256_bytes(np.ascontiguousarray(array).tobytes())


def snapshot_tree(directory: Path) -> dict[str, str]:
    if not directory.is_dir():
        raise AssertionError(f"Missing frozen archive root: {directory}")
    return {
        str(path.relative_to(ROOT)): sha256_bytes(path.read_bytes())
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def verify_frozen_archives() -> dict[str, int]:
    """Verify every archived payload against its frozen SHA-256 manifest."""
    counts: dict[str, int] = {}
    for archive in sorted(path for path in FROZEN_ARCHIVE_ROOT.iterdir() if path.is_dir()):
        manifest = archive / "SHA256SUMS.txt"
        if not manifest.is_file():
            raise AssertionError(f"Missing frozen manifest: {manifest}")
        count = 0
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            expected, name = line.split("  ", 1)
            payload = archive / name
            if not payload.is_file() or sha256_bytes(payload.read_bytes()) != expected:
                raise AssertionError(f"Frozen payload changed: {archive.name}/{name}")
            count += 1
        counts[archive.name] = count
    if set(counts) != {
        "subsystem_01_biohazard_APPROVED",
        "subsystem_02_evidence_magnifier_APPROVED",
        "approved_subsystem_03_workflow",
        "approved_subsystem_04_active_case_feed",
        "approved_subsystem_05_system_status",
    }:
        raise AssertionError("Frozen archive set changed before Threat Monitor render")
    return counts


def verify_frozen_working_scripts() -> None:
    for working_path, archive_path in FROZEN_WORKING_SCRIPT_ARCHIVES.items():
        if not working_path.is_file() or not archive_path.is_file():
            raise AssertionError(f"Missing frozen subsystem script: {working_path.name}")
        if sha256_bytes(working_path.read_bytes()) != sha256_bytes(archive_path.read_bytes()):
            raise AssertionError(f"Frozen subsystem script changed: {working_path.name}")


def local_bounds(global_bounds: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return (
        global_bounds[0] - PANEL_BOUNDS[0],
        global_bounds[1] - PANEL_BOUNDS[1],
        global_bounds[2] - PANEL_BOUNDS[0],
        global_bounds[3] - PANEL_BOUNDS[1],
    )


def mask_bbox_global(mask: np.ndarray) -> tuple[int, int, int, int]:
    yy, xx = np.where(mask)
    if not len(xx):
        raise AssertionError("Expected non-empty Threat Monitor mask")
    return (
        int(np.min(xx)) + PANEL_BOUNDS[0],
        int(np.min(yy)) + PANEL_BOUNDS[1],
        int(np.max(xx)) + PANEL_BOUNDS[0] + 1,
        int(np.max(yy)) + PANEL_BOUNDS[1] + 1,
    )


def rectangular_mask(bounds: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = local_bounds(bounds)
    mask = np.zeros((PANEL_SIZE[1], PANEL_SIZE[0]), dtype=bool)
    mask[y1:y2, x1:x2] = True
    return mask


def right_scale_light_neutral_residual_mask(panel: np.ndarray) -> np.ndarray:
    """Locate unintended light-neutral pixels in the rebuilt tick/gutter core."""
    x1, y1, x2, y2 = local_bounds(RIGHT_SCALE_NEUTRAL_RESIDUAL_AUDIT_BOUNDS)
    region = panel[y1:y2, x1:x2].astype(np.int16)
    residual = (
        (np.max(region, axis=2) - np.min(region, axis=2) <= RIGHT_SCALE_NEUTRAL_MAX_SATURATION)
        & (np.mean(region, axis=2) >= RIGHT_SCALE_NEUTRAL_MIN_BRIGHTNESS)
    )
    # The five deliberate muted-red ticks are explicitly excluded from the
    # neutral audit even though their chroma already keeps them out of it.
    tick_x1 = Y_SCALE_TICK_GLOBAL_X[0] - RIGHT_SCALE_NEUTRAL_RESIDUAL_AUDIT_BOUNDS[0]
    tick_x2 = Y_SCALE_TICK_GLOBAL_X[1] - RIGHT_SCALE_NEUTRAL_RESIDUAL_AUDIT_BOUNDS[0]
    for global_y in Y_SCALE_TICK_GLOBAL_Y:
        y = global_y - RIGHT_SCALE_NEUTRAL_RESIDUAL_AUDIT_BOUNDS[1]
        residual[y, tick_x1:tick_x2] = False
    full_mask = np.zeros(panel.shape[:2], dtype=bool)
    full_mask[y1:y2, x1:x2] = residual
    return full_mask


def right_scale_light_neutral_residual_count(panel: np.ndarray) -> int:
    return int(np.count_nonzero(right_scale_light_neutral_residual_mask(panel)))


def build_graph_shell_plate(
    source_plate: np.ndarray,
    draw_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Create the authorized static graph-shell/label overlay on a local plate."""
    presentation_mask = rectangular_mask(GRAPH_PRESENTATION_BOUNDS)
    label_clear_mask = np.zeros(source_plate.shape[:2], dtype=bool)
    for bounds in GRAPH_LABEL_CLEAR_BOUNDS:
        x1, y1, x2, y2 = local_bounds(bounds)
        label_clear_mask[y1:y2, x1:x2] = True
    if np.any(label_clear_mask & draw_mask) or np.any(label_clear_mask & ~presentation_mask):
        raise AssertionError("Threat Monitor graph label redraw escaped its authorized region")

    right_scale_clear_mask = rectangular_mask(RIGHT_SCALE_CLEAR_BOUNDS)
    right_scale_gutter_mask = rectangular_mask(RIGHT_SCALE_GUTTER_BOUNDS)
    if (
        np.any((right_scale_clear_mask & draw_mask) & ~right_scale_gutter_mask)
        or np.any(right_scale_clear_mask & ~presentation_mask)
    ):
        raise AssertionError("Threat Monitor right-scale redraw escaped its authorized static region")
    shell_clear_mask = label_clear_mask | right_scale_clear_mask

    # Remove the legacy labels and the bright continuous source Y-axis with
    # local inpainting. This retains the approved dark grunge/background
    # instead of placing an opaque replacement rectangle.
    plate = cv2.inpaint(
        source_plate,
        (shell_clear_mask.astype(np.uint8) * 255),
        2,
        cv2.INPAINT_NS,
    )
    # NS inpainting can retain a handful of low-saturation antialias values at
    # the lower former-scale edge.  Replace only those detector hits from the
    # adjacent dark reconstructed background; this is not a rectangular cover.
    right_scale_neutral_residue = right_scale_light_neutral_residual_mask(plate)
    right_scale_targeted_neutral_scrub_pixels = int(np.count_nonzero(right_scale_neutral_residue))
    if right_scale_targeted_neutral_scrub_pixels:
        _, _, scale_x2, _ = local_bounds(RIGHT_SCALE_NEUTRAL_RESIDUAL_AUDIT_BOUNDS)
        reference_x = scale_x2 - 1
        yy, xx = np.where(right_scale_neutral_residue)
        for y, x in zip(yy, xx):
            if x == reference_x:
                raise AssertionError("Threat Monitor right-scale neutral scrub lost its background source")
            plate[y, x] = plate[y, reference_x]
    if right_scale_light_neutral_residual_count(plate):
        raise AssertionError("Threat Monitor right-scale neutral source remnants remain after cleanup")

    top_y = 609 - PANEL_BOUNDS[1]
    top_inner_y = 610 - PANEL_BOUNDS[1]
    bottom_y = 664 - PANEL_BOUNDS[1]
    bottom_inner_y = 665 - PANEL_BOUNDS[1]
    left_x = 956 - PANEL_BOUNDS[0]
    right_inner_x = 1235 - PANEL_BOUNDS[0]
    # Restrained paired rules and bracket corners strengthen the shell without
    # introducing a bright red rectangle or changing the signal canvas.
    cv2.line(plate, (left_x, top_y), (right_inner_x, top_y), (71, 24, 25), 1, cv2.LINE_8)
    cv2.line(plate, (left_x, top_inner_y), (right_inner_x, top_inner_y), (123, 40, 38), 1, cv2.LINE_8)
    cv2.line(plate, (left_x, bottom_y), (right_inner_x, bottom_y), (136, 43, 40), 1, cv2.LINE_8)
    cv2.line(plate, (left_x, bottom_inner_y), (right_inner_x, bottom_inner_y), (63, 20, 21), 1, cv2.LINE_8)
    cv2.line(plate, (left_x, top_y), (left_x + 11, top_y), (157, 52, 47), 1, cv2.LINE_8)
    cv2.line(plate, (left_x, top_y), (left_x, top_y + 2), (157, 52, 47), 1, cv2.LINE_8)
    cv2.line(plate, (left_x, bottom_inner_y), (left_x + 11, bottom_inner_y), (157, 52, 47), 1, cv2.LINE_8)
    cv2.line(plate, (left_x, bottom_inner_y - 2), (left_x, bottom_inner_y), (157, 52, 47), 1, cv2.LINE_8)
    cv2.line(plate, (right_inner_x - 11, top_y), (right_inner_x, top_y), (157, 52, 47), 1, cv2.LINE_8)
    cv2.line(plate, (right_inner_x - 11, bottom_inner_y), (right_inner_x, bottom_inner_y), (157, 52, 47), 1, cv2.LINE_8)
    for global_x in X_TICK_ANCHORS:
        x = global_x - PANEL_BOUNDS[0]
        cv2.line(plate, (x, bottom_y), (x, bottom_inner_y + 2), (149, 50, 46), 1, cv2.LINE_8)
    for global_y in Y_SCALE_TICK_GLOBAL_Y:
        y = global_y - PANEL_BOUNDS[1]
        cv2.line(
            plate,
            (Y_SCALE_TICK_GLOBAL_X[0] - PANEL_BOUNDS[0], y),
            (Y_SCALE_TICK_GLOBAL_X[1] - PANEL_BOUNDS[0] - 1, y),
            Y_SCALE_TICK_RGB,
            1,
            cv2.LINE_8,
        )

    # Compact labels retain the original chronology while making the history
    # direction and 0-100 anomaly scale immediately readable.
    image = Image.fromarray(plate, "RGB")
    text = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=8)
    x_label_y = 669 - PANEL_BOUNDS[1]
    x_labels = (
        (956 - PANEL_BOUNDS[0], "60m AGO"),
        (1018 - PANEL_BOUNDS[0], "45m"),
        (1089 - PANEL_BOUNDS[0], "30m"),
        (1159 - PANEL_BOUNDS[0], "15m"),
        (1217 - PANEL_BOUNDS[0], "NOW"),
    )
    for x, label in x_labels:
        text.text((x, x_label_y), label, fill=(205, 199, 198), font=font)
    text.text((1065 - PANEL_BOUNDS[0], 677 - PANEL_BOUNDS[1]), "HISTORY > LIVE", fill=(148, 57, 53), font=font)

    for global_x, global_y, label, color in Y_SCALE_LABELS:
        text.text(
            (global_x - PANEL_BOUNDS[0], global_y - PANEL_BOUNDS[1]),
            label,
            fill=color,
            font=font,
        )
    plate = np.array(image, dtype=np.uint8)

    static_changes = np.any(plate != source_plate, axis=2)
    if np.any(static_changes & ~presentation_mask):
        raise AssertionError("Threat Monitor graph shell changed pixels outside its authorized presentation region")
    if np.any((static_changes & draw_mask) & ~right_scale_gutter_mask):
        raise AssertionError("Threat Monitor graph shell changed the approved dynamic signal canvas")
    final_static_mask = (static_changes & ~draw_mask) | rectangular_mask(RIGHT_SCALE_STATIC_BOUNDS)
    if np.any(final_static_mask & ~presentation_mask):
        raise AssertionError("Threat Monitor final shell restore escaped its authorized presentation region")
    return plate, presentation_mask, static_changes, final_static_mask, right_scale_targeted_neutral_scrub_pixels


def source_signal_masks(source_panel: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Locate and bound the baked source signal using populated pixels only."""
    axis_x1, axis_y1, axis_x2, axis_y2 = local_bounds(AXIS_BOX)
    axis = source_panel[axis_y1:axis_y2, axis_x1:axis_x2].astype(np.int16)
    red_candidates = (
        (axis[:, :, 0] >= 45)
        & (axis[:, :, 0] - np.maximum(axis[:, :, 1], axis[:, :, 2]) >= 18)
    )
    labels_count, labels, stats, _ = cv2.connectedComponentsWithStats(red_candidates.astype(np.uint8), connectivity=8)
    if labels_count < 2:
        raise AssertionError("Baked Threat Monitor signal was not found")
    largest_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    main_component = labels == largest_label
    if int(np.count_nonzero(main_component)) != 3476:
        raise AssertionError("Threat Monitor source component geometry changed")
    near_main_component = cv2.dilate(
        main_component.astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)),
        iterations=1,
    ).astype(bool)
    source_signal = np.zeros(source_panel.shape[:2], dtype=bool)
    source_signal[axis_y1:axis_y2, axis_x1:axis_x2] = red_candidates & near_main_component
    if (
        int(np.count_nonzero(source_signal)) != EXPECTED_SOURCE_SIGNAL_PIXELS
        or mask_bbox_global(source_signal) != EXPECTED_SOURCE_SIGNAL_BBOX
    ):
        raise AssertionError("Threat Monitor source-signal geometry changed")

    workbox = rectangular_mask(WORKBOX)
    cleanup = cv2.dilate(
        source_signal.astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
        iterations=1,
    ).astype(bool) & workbox
    if (
        int(np.count_nonzero(cleanup)) != EXPECTED_CLEANUP_PIXELS
        or mask_bbox_global(cleanup) != EXPECTED_CLEANUP_BBOX
        or np.any(cleanup & ~workbox)
    ):
        raise AssertionError("Threat Monitor cleanup mask escaped its graph workbox")
    return source_signal, cleanup, workbox, rectangular_mask(DRAW_CLIP)


def build_source_derived_plot_plate(
    source_panel: np.ndarray,
    source_signal: np.ndarray,
    line_cleanup_mask: np.ndarray,
    workbox_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, int, int, int, np.ndarray]:
    """Remove the baked signal/fill while retaining the source-derived plot texture."""
    if not np.array_equal(workbox_mask, rectangular_mask(WORKBOX)):
        raise AssertionError("Threat Monitor graph workbox geometry changed")

    # The populated source contains a low-opacity red historical fill under
    # the bright source waveform.  Identify only the connected weak-red
    # component attached to that waveform, rather than flattening the full
    # graph workbox.  This preserves the surrounding source-derived texture
    # and dotted grid before the unchanged fresh signal is rendered.
    source_values = source_panel.astype(np.int16)
    weak_trace_fill_all = (
        (source_values[:, :, 0] >= WEAK_TRACE_FILL_RED_MIN)
        & (
            source_values[:, :, 0]
            - np.maximum(source_values[:, :, 1], source_values[:, :, 2])
            >= WEAK_TRACE_FILL_RED_DELTA
        )
    )
    weak_trace_fill = weak_trace_fill_all & workbox_mask
    label_count, labels, stats, _ = cv2.connectedComponentsWithStats(
        weak_trace_fill.astype(np.uint8),
        connectivity=8,
    )
    attached_labels = [
        label
        for label in range(1, label_count)
        if np.any((labels == label) & source_signal)
    ]
    if len(attached_labels) != 1:
        raise AssertionError("Threat Monitor source trace/fill component is not uniquely connected")
    source_trace_fill = labels == attached_labels[0]
    if (
        int(np.count_nonzero(source_trace_fill)) != EXPECTED_SOURCE_TRACE_FILL_PIXELS
        or mask_bbox_global(source_trace_fill) != EXPECTED_SOURCE_TRACE_FILL_BBOX
        or np.any(source_signal & ~source_trace_fill)
    ):
        raise AssertionError("Threat Monitor source trace/fill component geometry changed")
    trace_fill_cleanup_mask = line_cleanup_mask | source_trace_fill
    if (
        int(np.count_nonzero(trace_fill_cleanup_mask)) != EXPECTED_TRACE_FILL_CLEANUP_PIXELS
        or mask_bbox_global(trace_fill_cleanup_mask) != EXPECTED_TRACE_FILL_CLEANUP_BBOX
        or np.any(trace_fill_cleanup_mask & ~workbox_mask)
    ):
        raise AssertionError("Threat Monitor source trace/fill cleanup mask escaped its graph workbox")

    # NS inpainting would otherwise sample the remaining source-red fill
    # directly beside the repair mask.  Guard those temporary seed pixels,
    # then restore them verbatim after inpainting; this is not a solid plot
    # patch and leaves all source pixels outside the exact repair mask intact.
    inpaint_seed = source_panel.copy()
    seed_guard = weak_trace_fill_all & rectangular_mask(AXIS_BOX) & ~trace_fill_cleanup_mask
    if int(np.count_nonzero(seed_guard)) != EXPECTED_INPAINT_SEED_GUARD_PIXELS:
        raise AssertionError("Threat Monitor temporary inpaint seed guard geometry changed")
    inpaint_seed[seed_guard] = RIGHT_EDGE_GUARD_RGB

    # The cleanup reaches immediately beside the bright static right axis at
    # global x=1238.  Without this inpaint-only guard, NS can pull that axis
    # gray into the cleanup and create a wedge beside NOW.  The guard column is
    # restored verbatim before output, so it is never an animated or changed
    # pixel and it cannot alter the static axis.
    work_x1, work_y1, work_x2, work_y2 = local_bounds(WORKBOX)
    guard_x = work_x2
    if guard_x != 402 or guard_x >= source_panel.shape[1]:
        raise AssertionError("Threat Monitor right-axis guard geometry changed")
    guard_source = source_panel[work_y1:work_y2, guard_x].copy()
    inpaint_seed[work_y1:work_y2, guard_x] = RIGHT_EDGE_GUARD_RGB

    # The static y-scale, its ticks, and its antialias fringe are also
    # inpaint sources beside the cleanup. Shield them only in the temporary
    # seed, then restore their original source pixels after inpainting.
    axis_x1, axis_y1, axis_x2, axis_y2 = local_bounds(RIGHT_EDGE_AXIS_GUARD)
    axis_pixels = source_panel[axis_y1:axis_y2, axis_x1:axis_x2].astype(np.int16)
    static_axis_guard_all = np.zeros(source_panel.shape[:2], dtype=bool)
    static_axis_guard_all[axis_y1:axis_y2, axis_x1:axis_x2] = (
        (np.max(axis_pixels, axis=2) - np.min(axis_pixels, axis=2) <= 18)
        & (np.mean(axis_pixels, axis=2) >= RIGHT_EDGE_AXIS_GUARD_MIN_BRIGHTNESS)
    )
    if int(np.count_nonzero(static_axis_guard_all)) != EXPECTED_RIGHT_EDGE_AXIS_GUARD_PIXELS:
        raise AssertionError("Threat Monitor static right-axis guard geometry changed")
    # Restore every true Y-axis/tick pixel at and beyond the protected axis
    # start.  In the one-pixel gutter, restore only source axis-fringe pixels
    # outside the repair mask, so actual old trace/fill pixels are removed.
    protected_axis_columns = np.zeros(source_panel.shape[:2], dtype=bool)
    protected_axis_columns[:, RIGHT_AXIS_PROTECTED_START_X - PANEL_BOUNDS[0]:] = True
    static_axis_guard = static_axis_guard_all & (protected_axis_columns | ~trace_fill_cleanup_mask)
    if int(np.count_nonzero(static_axis_guard)) != EXPECTED_RESTORED_RIGHT_EDGE_AXIS_GUARD_PIXELS:
        raise AssertionError("Threat Monitor restored right-axis guard geometry changed")
    inpaint_seed[static_axis_guard_all] = RIGHT_EDGE_GUARD_RGB
    plate = cv2.inpaint(
        inpaint_seed,
        (trace_fill_cleanup_mask.astype(np.uint8) * 255),
        2,
        cv2.INPAINT_NS,
    )
    plate[~trace_fill_cleanup_mask] = source_panel[~trace_fill_cleanup_mask]
    plate[work_y1:work_y2, guard_x] = guard_source
    plate[seed_guard] = source_panel[seed_guard]
    plate[static_axis_guard] = source_panel[static_axis_guard]
    if not np.array_equal(plate[~trace_fill_cleanup_mask], source_panel[~trace_fill_cleanup_mask]):
        raise AssertionError("Source-derived graph plate changed pixels outside cleanup mask")
    if not np.array_equal(plate[work_y1:work_y2, guard_x], source_panel[work_y1:work_y2, guard_x]):
        raise AssertionError("Threat Monitor static right axis changed during graph cleanup")
    if not np.array_equal(plate[static_axis_guard], source_panel[static_axis_guard]):
        raise AssertionError("Threat Monitor static scale/tick pixels changed during graph cleanup")

    axis_x1, axis_y1, axis_x2, axis_y2 = local_bounds(AXIS_BOX)
    axis = plate[axis_y1:axis_y2, axis_x1:axis_x2].astype(np.int16)
    residual_candidates = (
        (axis[:, :, 0] >= 45)
        & (axis[:, :, 0] - np.maximum(axis[:, :, 1], axis[:, :, 2]) >= 18)
    )
    residual_mask = np.zeros(source_panel.shape[:2], dtype=bool)
    residual_mask[axis_y1:axis_y2, axis_x1:axis_x2] = residual_candidates
    source_signal_residuals = int(np.count_nonzero(residual_mask & source_signal))
    if source_signal_residuals:
        raise AssertionError("Baked red Threat Monitor signal remains after cleanup")
    plate_values = plate.astype(np.int16)
    residual_trace_fill_candidates = (
        (plate_values[:, :, 0] >= TRACE_FILL_RESIDUAL_RED_MIN)
        & (
            plate_values[:, :, 0]
            - np.maximum(plate_values[:, :, 1], plate_values[:, :, 2])
            >= TRACE_FILL_RESIDUAL_RED_DELTA
        )
    )
    obsolete_trace_fill_pixels = int(
        np.count_nonzero(residual_trace_fill_candidates & source_trace_fill & ~static_axis_guard)
    )
    if obsolete_trace_fill_pixels:
        raise AssertionError("Obsolete red Threat Monitor trace/fill remains in fresh graph draw region")
    changed_pixels = int(np.count_nonzero(np.any(plate != source_panel, axis=2)))
    wedge_x1, wedge_y1, wedge_x2, wedge_y2 = local_bounds(RIGHT_EDGE_WEDGE_AUDIT)
    wedge = plate[wedge_y1:wedge_y2, wedge_x1:wedge_x2].astype(np.int16)
    source = source_panel[wedge_y1:wedge_y2, wedge_x1:wedge_x2]
    bright_neutral = (
        (np.max(wedge, axis=2) - np.min(wedge, axis=2) <= 18)
        & (np.mean(wedge, axis=2) >= RIGHT_EDGE_NEUTRAL_MIN_BRIGHTNESS)
    )
    changed_wedge = np.any(wedge != source, axis=2)
    right_edge_neutral_artifacts = int(np.count_nonzero(bright_neutral & changed_wedge))
    if right_edge_neutral_artifacts > 2:
        raise AssertionError("Right-edge NOW wedge remains after source-plate cleanup")
    return (
        plate,
        trace_fill_cleanup_mask,
        source_trace_fill,
        seed_guard,
        source_signal_residuals,
        obsolete_trace_fill_pixels,
        changed_pixels,
        right_edge_neutral_artifacts,
        static_axis_guard,
    )


def wrapped_distance(values: np.ndarray | float, center: float) -> np.ndarray:
    values_array = np.asarray(values, dtype=np.float64)
    return np.abs((values_array - center + 0.5) % 1.0 - 0.5)


def wrapped_gaussian(values: np.ndarray | float, center: float, sigma: float) -> np.ndarray:
    return np.exp(-0.5 * (wrapped_distance(values, center) / sigma) ** 2)


def classification_for_score(score: int) -> str:
    for level, lower, upper in THRESHOLD_GUIDE:
        if lower <= score <= upper:
            return level
    raise AssertionError(f"Threat score outside approved threshold guide: {score}")


def deterministic_preview_history_0_to_100_for_frame(frame_index: int, sample_count: int) -> np.ndarray:
    """Return the isolated deterministic preview history in the public 0-100 domain."""
    if sample_count < 8:
        raise AssertionError("Threat history needs a full fixed graph width")
    t = (frame_index % FRAME_COUNT) / FRAME_COUNT
    u = np.linspace(0.0, 1.0, sample_count, endpoint=True)

    # This world-coordinate baseline moves left as fresh data enters at NOW.
    world = (u + t) % 1.0
    baseline = (
        0.39
        + 0.037 * np.sin(math.tau * (1.05 * world + 0.17))
        + 0.021 * np.sin(math.tau * (4.20 * world + 0.31))
        + 0.012 * np.sin(math.tau * (10.0 * world + 0.08))
    )
    stable_history = (
        0.070 * wrapped_gaussian(world, 0.18, 0.040)
        + 0.105 * wrapped_gaussian(world, 0.48, 0.037)
        + 0.065 * wrapped_gaussian(world, 0.76, 0.047)
        - 0.030 * wrapped_gaussian(world, 0.54, 0.050)
    )

    # One deterministic case event enters at NOW, progresses from medium to
    # high to critical while travelling left, then recovers before the loop.
    activity = (
        0.018
        + 0.170 * wrapped_gaussian(t, 0.20, 0.070)
        + 0.310 * wrapped_gaussian(t, 0.42, 0.085)
        + 0.470 * wrapped_gaussian(t, 0.60, 0.075)
        + 0.110 * wrapped_gaussian(t, 0.80, 0.085)
    )
    event_center = (0.97 - t) % 1.0
    event = activity * wrapped_gaussian(u, event_center, 0.050)
    recovery = -0.095 * activity * wrapped_gaussian(u, (event_center + 0.070) % 1.0, 0.060)
    return (100.0 * np.clip(baseline + stable_history + event + recovery, 0.08, 0.95)).astype(np.float64)


def coerce_anomaly_history_0_to_100(history: object) -> np.ndarray:
    """Validate caller-supplied chronological active-case signal history."""
    values = np.asarray(history, dtype=np.float64)
    if (
        values.ndim != 1
        or values.size < 1
        or not np.all(np.isfinite(values))
        or np.any(values < ANOMALY_HISTORY_MIN)
        or np.any(values > ANOMALY_HISTORY_MAX)
    ):
        raise AssertionError("Threat Monitor anomaly history must be a finite 0-100 time series")
    return values


def resample_anomaly_history_for_draw(history: object, sample_count: int) -> np.ndarray:
    """Map an external chronology to the fixed graph width while preserving NOW."""
    if sample_count < 2:
        raise AssertionError("Threat Monitor graph width must support a time series")
    values = coerce_anomaly_history_0_to_100(history)
    if values.size == sample_count:
        return values.copy()
    if values.size == 1:
        return np.full(sample_count, values[0], dtype=np.float64)
    source_positions = np.linspace(0.0, 1.0, values.size, endpoint=True)
    draw_positions = np.linspace(0.0, 1.0, sample_count, endpoint=True)
    resampled = np.interp(draw_positions, source_positions, values)
    if resampled[0] != values[0] or resampled[-1] != values[-1]:
        raise AssertionError("Threat Monitor history resampling shifted chronology endpoints")
    return resampled


def verify_external_history_contract() -> None:
    """Exercise the production-shaped 0-100 contract without live integration."""
    width = DRAW_CLIP[2] - DRAW_CLIP[0]
    probe = (7.0, 41.0, 96.0)
    first = resample_anomaly_history_for_draw(probe, width)
    second = resample_anomaly_history_for_draw(probe, width)
    if first[0] != 7.0 or first[-1] != 96.0 or not np.array_equal(first, second):
        raise AssertionError("External Threat Monitor history contract is not deterministic")
    if np.all(first == 50.0):
        raise AssertionError("External Threat Monitor history was incorrectly reset to 50")
    persistent_case_probe = dict(THREAT_MONITOR_PREVIEW)
    persistent_case_probe.update(
        {
            "case_id": "CASE-CONTRACT-PROBE",
            "preview_only": False,
            ANOMALY_HISTORY_FIELD: probe,
        }
    )
    persistent_case_probe.pop("controlled_events")
    validate_threat_monitor(persistent_case_probe)
    for invalid in ((-0.1,), (100.1,), (float("nan"),)):
        try:
            coerce_anomaly_history_0_to_100(invalid)
        except AssertionError:
            continue
        raise AssertionError("Out-of-range external Threat Monitor history was accepted")


def threat_monitor_preview_for_frame(frame_index: int) -> dict[str, object]:
    """Return structured deterministic preview data passed into the renderer."""
    width = DRAW_CLIP[2] - DRAW_CLIP[0]
    preview = dict(THREAT_MONITOR_PREVIEW)
    preview[ANOMALY_HISTORY_FIELD] = tuple(
        float(value) for value in deterministic_preview_history_0_to_100_for_frame(frame_index, width)
    )
    preview["frame_index"] = frame_index
    return preview


def validate_threat_monitor(threat_monitor: dict[str, object]) -> None:
    score = int(threat_monitor.get("threat_score", -1))
    level = str(threat_monitor.get("threat_level", ""))
    preview_only = threat_monitor.get("preview_only", False)
    if not str(threat_monitor.get("case_id", "")) or not isinstance(preview_only, bool):
        raise AssertionError("Threat Monitor input lacks case metadata")
    if level != classification_for_score(score) or tuple(threat_monitor.get("threshold_guide", ())) != THRESHOLD_GUIDE:
        raise AssertionError("Threat score does not match the static threshold guide")
    coerce_anomaly_history_0_to_100(threat_monitor.get(ANOMALY_HISTORY_FIELD, ()))
    events = threat_monitor.get("controlled_events")
    summary = threat_monitor.get("threat_summary")
    if (
        not isinstance(summary, tuple)
        or len(summary) != 5
        or (preview_only and (not isinstance(events, tuple) or len(events) != 5))
    ):
        raise AssertionError("Threat Monitor structured preview is incomplete")


def signal_y_values_for_samples(values: np.ndarray, height: int) -> np.ndarray:
    """Map normalized input values to the fixed approved local signal geometry."""
    top = 3
    bottom = height - 5
    drawable_height = bottom - top
    normalized_values = (values - ANOMALY_HISTORY_MIN) / (ANOMALY_HISTORY_MAX - ANOMALY_HISTORY_MIN)
    y_values = np.rint(bottom - normalized_values * drawable_height).astype(np.int32)
    return np.clip(y_values, top, bottom)


def area_fill_alpha_for_y_values(y_values: np.ndarray, height: int, width: int) -> np.ndarray:
    """Build a local, transparent dark-red area field below the fixed signal trace."""
    if y_values.shape != (width,):
        raise AssertionError("Threat Monitor area fill does not match the fixed signal width")
    fill_floor = height - AREA_FILL_FLOOR_OFFSET
    y_virtual = np.concatenate((y_values, y_values[-1:]))
    rows = np.arange(height, dtype=np.float32)[:, None]
    start = y_virtual[None, :].astype(np.float32) + AREA_FILL_HALO_OFFSET
    span = np.maximum(fill_floor - start, 1.0)
    progress = np.clip((rows - start) / span, 0.0, 1.0)
    inside = (start < fill_floor) & (rows >= start) & (rows < fill_floor)
    alpha = np.where(
        inside,
        np.rint(AREA_FILL_MAX_ALPHA * np.power(1.0 - progress, AREA_FILL_POWER)),
        0,
    ).astype(np.uint8)
    if alpha.shape != (height, width + 1):
        raise AssertionError("Threat Monitor area fill canvas geometry changed")
    # The last composited draw column is the preserved x=1236 NOW gutter;
    # keep the visible area field strictly left of the final static scale.
    alpha[:, width - 1] = 0
    return alpha


def draw_signal_patch(
    plot_plate: np.ndarray,
    samples: Sequence[float],
    *,
    include_area_fill: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Render the fixed signal plus a clipped fading dark-red area field."""
    height, width = plot_plate.shape[:2]
    values = np.asarray(samples, dtype=np.float64)
    if (
        values.shape != (width,)
        or not np.all(np.isfinite(values))
        or np.any(values < ANOMALY_HISTORY_MIN)
        or np.any(values > ANOMALY_HISTORY_MAX)
    ):
        raise AssertionError("Threat history does not match the fixed 0-100 graph interior")

    y_values = signal_y_values_for_samples(values, height)
    points = [(int(x), int(y)) for x, y in enumerate(y_values)]

    base = Image.fromarray(plot_plate, "RGB").convert("RGBA")
    # Draw one virtual column beyond the composited graph interior. Its only
    # purpose is to avoid a butt cap before the final source-derived axis-strip
    # restoration; the virtual column is discarded before compositing.
    virtual_overlay = Image.new("RGBA", (width + 1, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(virtual_overlay)

    # The fill is a true per-column area layer, strongest just below the
    # existing five-pixel halo and progressively transparent toward baseline.
    # It is composited locally before the unchanged red line operations.
    area_alpha_virtual = area_fill_alpha_for_y_values(y_values, height, width)
    area_rgba = np.zeros((height, width + 1, 4), dtype=np.uint8)
    area_rgba[:, :, :3] = AREA_FILL_RGB
    area_rgba[:, :, 3] = area_alpha_virtual
    if include_area_fill:
        area_layer = Image.fromarray(area_rgba, "RGBA").crop((0, 0, width, height))
        base = Image.alpha_composite(base, area_layer)

    terminal_points = [*points, (width, int(y_values[-1]))]
    draw.line(terminal_points, fill=(196, 28, 24, 48), width=5)
    draw.line(terminal_points, fill=(229, 47, 40, 235), width=2)
    overlay = virtual_overlay.crop((0, 0, width, height))
    rendered = np.array(Image.alpha_composite(base, overlay).convert("RGB"), dtype=np.uint8)
    foreground = np.any(rendered != plot_plate, axis=2)
    return rendered, foreground, y_values, area_alpha_virtual[:, :width]


def restore_final_static_shell(
    panel: np.ndarray,
    graph_shell_plate: np.ndarray,
    final_static_mask: np.ndarray,
) -> None:
    """Restore the static shell, labels, and right-axis strip after signal draw."""
    panel[final_static_mask] = graph_shell_plate[final_static_mask]


def render_full_frame(
    populated_rgb: np.ndarray,
    source_panel: np.ndarray,
    graph_shell_plate: np.ndarray,
    cleanup_mask: np.ndarray,
    static_shell_changes: np.ndarray,
    draw_mask: np.ndarray,
    final_static_mask: np.ndarray,
    threat_monitor: dict[str, object],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Render one fresh source-reset frame from structured preview data."""
    validate_threat_monitor(threat_monitor)
    full_frame = populated_rgb.copy()
    panel = graph_shell_plate.copy()
    x1, y1, x2, y2 = local_bounds(DRAW_CLIP)
    draw_history = resample_anomaly_history_for_draw(
        threat_monitor[ANOMALY_HISTORY_FIELD],
        x2 - x1,
    )
    patch, _foreground_local, y_values, area_alpha = draw_signal_patch(
        graph_shell_plate[y1:y2, x1:x2].copy(),
        draw_history,
    )
    panel[y1:y2, x1:x2] = patch
    # This must be the final panel compositing operation: it restores the
    # redesigned shell/labels and source-derived right-axis strip, leaving
    # the one-pixel visual gutter at x=1236.
    restore_final_static_shell(panel, graph_shell_plate, final_static_mask)
    foreground = np.any(panel != graph_shell_plate, axis=2)
    if np.any(foreground & ~draw_mask):
        raise AssertionError("Fresh Threat Monitor signal escaped its local graph canvas")
    frame_allowed = cleanup_mask | static_shell_changes | foreground
    changed = np.any(panel != source_panel, axis=2)
    if np.any(changed & ~frame_allowed):
        raise AssertionError("Threat Monitor raw frame changed protected panel pixels")
    if not np.array_equal(panel[~frame_allowed], source_panel[~frame_allowed]):
        raise AssertionError("Threat Monitor protected panel pixels no longer match source")
    px1, py1, px2, py2 = PANEL_BOUNDS
    full_frame[py1:py2, px1:px2] = panel
    return full_frame, panel, foreground, y_values, area_alpha


def parse_gif(path: Path) -> tuple[tuple[int, int], list[tuple[int, int, int, int, bool, bool, int, int, bool]], bytes]:
    data = path.read_bytes()
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise AssertionError("Output is not a GIF stream")
    position = 6
    width = int.from_bytes(data[position:position + 2], "little")
    height = int.from_bytes(data[position + 2:position + 4], "little")
    packed = data[position + 4]
    position += 7
    global_palette = b""
    if packed & 0x80:
        length = 3 * (2 ** ((packed & 0x07) + 1))
        global_palette = data[position:position + length]
        position += length
    pending = (0, 0, False)
    descriptors: list[tuple[int, int, int, int, bool, bool, int, int, bool]] = []
    while position < len(data):
        marker = data[position]
        position += 1
        if marker == 0x3B:
            break
        if marker == 0x21:
            label = data[position]
            position += 1
            if label == 0xF9:
                size = data[position]
                position += 1
                control = data[position:position + size]
                position += size + 1
                pending = ((control[0] >> 2) & 0x07, int.from_bytes(control[1:3], "little"), bool(control[0] & 0x01))
            else:
                while True:
                    size = data[position]
                    position += 1
                    if size == 0:
                        break
                    position += size
            continue
        if marker != 0x2C:
            raise AssertionError(f"Unexpected GIF marker 0x{marker:02x}")
        left = int.from_bytes(data[position:position + 2], "little")
        top = int.from_bytes(data[position + 2:position + 4], "little")
        frame_width = int.from_bytes(data[position + 4:position + 6], "little")
        frame_height = int.from_bytes(data[position + 6:position + 8], "little")
        image_packed = data[position + 8]
        position += 9
        local_palette = bool(image_packed & 0x80)
        interlaced = bool(image_packed & 0x40)
        if local_palette:
            position += 3 * (2 ** ((image_packed & 0x07) + 1))
        position += 1
        while True:
            size = data[position]
            position += 1
            if size == 0:
                break
            position += size
        descriptors.append((left, top, frame_width, frame_height, local_palette, interlaced, pending[0], pending[1], pending[2]))
        pending = (0, 0, False)
    return (width, height), descriptors, global_palette


def make_preview_sheet(
    decoded_frames: Sequence[np.ndarray],
    indices: Sequence[int],
    labels: dict[int, str],
    title: str,
    columns: int,
    scale: float,
    path: Path,
) -> tuple[int, int]:
    if not indices or columns < 1 or not 0.0 < scale <= 1.0:
        raise AssertionError("Invalid Threat Monitor proof-sheet layout")
    frame_width = max(1, int(round(PANEL_SIZE[0] * scale)))
    frame_height = max(1, int(round(PANEL_SIZE[1] * scale)))
    label_height = 18
    title_height = 24
    margin = 8
    rows = int(math.ceil(len(indices) / columns))
    width = margin + columns * frame_width + (columns - 1) * margin + margin
    height = title_height + rows * (frame_height + label_height) + (rows + 1) * margin
    sheet = Image.new("RGB", (width, height), (5, 8, 12))
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 5), title, fill=(220, 228, 235))
    for panel_index, frame_index in enumerate(indices):
        row = panel_index // columns
        column = panel_index % columns
        x = margin + column * (frame_width + margin)
        y = title_height + margin + row * (frame_height + label_height + margin)
        frame = Image.fromarray(decoded_frames[frame_index], "RGB")
        if frame.size != (frame_width, frame_height):
            frame = frame.resize((frame_width, frame_height), Image.Resampling.LANCZOS)
        sheet.paste(frame, (x, y))
        draw.rectangle((x - 1, y - 1, x + frame_width, y + frame_height), outline=(164, 52, 48), width=1)
        draw.text((x, y + frame_height + 3), labels[frame_index], fill=(185, 195, 205))
    sheet.save(path)
    reopened = Image.open(path).convert("RGB")
    if reopened.size != sheet.size or not np.array_equal(np.array(reopened), np.array(sheet)):
        raise AssertionError(f"Proof sheet verification failed: {path.name}")
    return sheet.size


def make_mask_proof(
    source_panel: np.ndarray,
    source_signal: np.ndarray,
    trace_fill_cleanup_mask: np.ndarray,
    draw_mask: np.ndarray,
    path: Path,
) -> tuple[int, int]:
    """Write a proof-only view of source cleanup and fresh-draw containment."""
    scale = 2
    source = Image.fromarray(source_panel, "RGB").resize(
        (PANEL_SIZE[0] * scale, PANEL_SIZE[1] * scale),
        Image.Resampling.NEAREST,
    ).convert("RGBA")
    overlay = Image.new("RGBA", source.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for mask, color, label in (
        (trace_fill_cleanup_mask, (255, 107, 42, 210), "SOURCE TRACE/FILL CLEANUP"),
        (draw_mask, (255, 57, 50, 245), "FRESH DRAW CLIP"),
    ):
        x1, y1, x2, y2 = local_bounds(mask_bbox_global(mask))
        draw.rectangle((x1 * scale, y1 * scale, x2 * scale - 1, y2 * scale - 1), outline=color, width=1)
        draw.text((x1 * scale + 2, max(0, y1 * scale - 12)), label, fill=color)
    yy, xx = np.where(source_signal)
    for x, y in zip(xx, yy):
        draw.point((int(x) * scale, int(y) * scale), fill=(255, 189, 55, 200))
    composited = Image.alpha_composite(source, overlay).convert("RGB")
    title_height = 22
    proof = Image.new("RGB", (composited.width, composited.height + title_height), (5, 8, 12))
    proof.paste(composited, (0, title_height))
    ImageDraw.Draw(proof).text((6, 5), "THREAT MONITOR - SOURCE CLEANUP AND FRESH DRAW MASKS", fill=(220, 228, 235))
    proof.save(path)
    reopened = Image.open(path).convert("RGB")
    if reopened.size != proof.size or not np.array_equal(np.array(reopened), np.array(proof)):
        raise AssertionError(f"Mask proof verification failed: {path.name}")
    return proof.size


def load_existing_decoded_gif_keyframe(path: Path, frame_index: int) -> np.ndarray | None:
    """Load the prior decoded keyframe for a focused before/after proof."""
    if not path.is_file():
        return None
    try:
        with Image.open(path) as gif:
            if gif.format != "GIF" or gif.size != PANEL_SIZE or gif.n_frames <= frame_index:
                return None
            gif.seek(frame_index)
            return np.array(gif.convert("RGB"))
    except OSError:
        return None


def make_right_edge_proof(
    prior_decoded_frame: np.ndarray | None,
    decoded_frames: Sequence[np.ndarray],
    path: Path,
) -> tuple[int, int]:
    """Create an enlarged decoded before/after proof of right-scale cleanup."""
    crop = (392, 50, PANEL_SIZE[0], 112)
    scale = 7
    crop_width = (crop[2] - crop[0]) * scale
    crop_height = (crop[3] - crop[1]) * scale
    margin = 8
    title_height = 24
    label_height = 18
    items: tuple[tuple[str, np.ndarray], ...] = (
        (
            "BEFORE F036 - PRIOR DECODED GIF",
            prior_decoded_frame if prior_decoded_frame is not None else decoded_frames[36],
        ),
        ("AFTER F036 - DECODED GIF", decoded_frames[36]),
        ("AFTER F000 - DECODED GIF", decoded_frames[0]),
        ("AFTER F059 - DECODED GIF", decoded_frames[59]),
    )
    columns = 2
    rows = int(math.ceil(len(items) / columns))
    proof = Image.new(
        "RGB",
        (
            margin + columns * crop_width + (columns - 1) * margin + margin,
            title_height + rows * (crop_height + label_height) + (rows + 1) * margin,
        ),
        (5, 8, 12),
    )
    draw = ImageDraw.Draw(proof)
    draw.text((margin, 5), "THREAT MONITOR - DECODED RIGHT-SCALE CLEANUP BEFORE / AFTER", fill=(220, 228, 235))
    for item, (label, frame) in enumerate(items):
        row = item // columns
        column = item % columns
        x = margin + column * (crop_width + margin)
        y = title_height + margin + row * (crop_height + label_height + margin)
        enlarged = Image.fromarray(frame, "RGB").crop(crop).resize(
            (crop_width, crop_height),
            Image.Resampling.NEAREST,
        )
        proof.paste(enlarged, (x, y))
        draw.rectangle((x - 1, y - 1, x + crop_width, y + crop_height), outline=(229, 58, 48), width=1)
        draw.text((x, y + crop_height + 3), label, fill=(185, 195, 205))
    proof.save(path)
    reopened = Image.open(path).convert("RGB")
    if reopened.size != proof.size or not np.array_equal(np.array(reopened), np.array(proof)):
        raise AssertionError(f"NOW-edge proof verification failed: {path.name}")
    return proof.size


def make_decoded_fill_proof(
    decoded_frames: Sequence[np.ndarray],
    decoded_line_only_frames: Sequence[np.ndarray],
    path: Path,
) -> tuple[int, int]:
    """Show that the legal area field remains visible after GIF decoding."""
    crop = (112, 42, 408, 112)
    scale = 3
    crop_width = (crop[2] - crop[0]) * scale
    crop_height = (crop[3] - crop[1]) * scale
    margin = 8
    title_height = 24
    label_height = 18
    items: tuple[tuple[str, np.ndarray], ...] = (
        ("F036 PALETTE CONTROL - LINE ONLY", decoded_line_only_frames[36]),
        ("F036 DECODED GIF - DARK-RED AREA", decoded_frames[36]),
        ("F000 DECODED GIF - DARK-RED AREA", decoded_frames[0]),
        ("F059 DECODED GIF - DARK-RED AREA", decoded_frames[59]),
    )
    columns = 2
    rows = int(math.ceil(len(items) / columns))
    proof = Image.new(
        "RGB",
        (
            margin + columns * crop_width + (columns - 1) * margin + margin,
            title_height + rows * (crop_height + label_height) + (rows + 1) * margin,
        ),
        (5, 8, 12),
    )
    draw = ImageDraw.Draw(proof)
    draw.text((margin, 5), "THREAT MONITOR - UNDER-TRACE FILL SURVIVES ACTUAL GIF DECODING", fill=(220, 228, 235))
    for item, (label, frame) in enumerate(items):
        row = item // columns
        column = item % columns
        x = margin + column * (crop_width + margin)
        y = title_height + margin + row * (crop_height + label_height + margin)
        enlarged = Image.fromarray(frame, "RGB").crop(crop).resize(
            (crop_width, crop_height),
            Image.Resampling.NEAREST,
        )
        proof.paste(enlarged, (x, y))
        draw.rectangle((x - 1, y - 1, x + crop_width, y + crop_height), outline=(174, 55, 50), width=1)
        draw.text((x, y + crop_height + 3), label, fill=(185, 195, 205))
    proof.save(path)
    reopened = Image.open(path).convert("RGB")
    if reopened.size != proof.size or not np.array_equal(np.array(reopened), np.array(proof)):
        raise AssertionError(f"Decoded-fill proof verification failed: {path.name}")
    return proof.size


def make_graph_presentation_proof(
    static_reference: np.ndarray,
    decoded_frames: Sequence[np.ndarray],
    path: Path,
) -> tuple[int, int]:
    """Create an enlarged proof of the revised static graph shell and labels."""
    crop = (112, 42, 447, 136)
    scale = 2
    crop_width = (crop[2] - crop[0]) * scale
    crop_height = (crop[3] - crop[1]) * scale
    margin = 8
    title_height = 24
    label_height = 18
    items: tuple[tuple[str, np.ndarray], ...] = (
        ("STATIC GRAPH SHELL", static_reference),
        ("F000", decoded_frames[0]),
        ("F036", decoded_frames[36]),
        ("F059", decoded_frames[59]),
    )
    columns = 2
    rows = 2
    proof = Image.new(
        "RGB",
        (
            margin + columns * crop_width + (columns - 1) * margin + margin,
            title_height + rows * (crop_height + label_height) + (rows + 1) * margin,
        ),
        (5, 8, 12),
    )
    draw = ImageDraw.Draw(proof)
    draw.text((margin, 5), "THREAT MONITOR - REVISED X/Y GRAPH PRESENTATION", fill=(220, 228, 235))
    for item, (label, frame) in enumerate(items):
        row = item // columns
        column = item % columns
        x = margin + column * (crop_width + margin)
        y = title_height + margin + row * (crop_height + label_height + margin)
        enlarged = Image.fromarray(frame, "RGB").crop(crop).resize(
            (crop_width, crop_height),
            Image.Resampling.NEAREST,
        )
        proof.paste(enlarged, (x, y))
        draw.rectangle((x - 1, y - 1, x + crop_width, y + crop_height), outline=(174, 55, 50), width=1)
        draw.text((x, y + crop_height + 3), label, fill=(185, 195, 205))
    proof.save(path)
    reopened = Image.open(path).convert("RGB")
    if reopened.size != proof.size or not np.array_equal(np.array(reopened), np.array(proof)):
        raise AssertionError(f"Graph-presentation proof verification failed: {path.name}")
    return proof.size


def main() -> None:
    frozen_before = snapshot_tree(FROZEN_ARCHIVE_ROOT)
    frozen_manifest_counts = verify_frozen_archives()
    verify_frozen_working_scripts()
    verify_external_history_contract()
    master_hashes = {path: sha256_bytes(path.read_bytes()) for path in EXPECTED_MASTER_SHA256}
    for path, expected in EXPECTED_MASTER_SHA256.items():
        if master_hashes[path] != expected:
            raise AssertionError(f"Approved master changed: {path.name}")
    generator_hash_before = sha256_bytes(GENERATE_CASE_BANNER_PATH.read_bytes())
    if generator_hash_before != EXPECTED_GENERATE_CASE_BANNER_SHA256:
        raise AssertionError("generate_case_banner.py changed before Threat Monitor render")

    populated = Image.open(POPULATED_PATH).convert("RGB")
    if populated.size != (1727, 911):
        raise AssertionError("Approved populated master dimensions changed")
    populated_rgb = np.array(populated)
    px1, py1, px2, py2 = PANEL_BOUNDS
    source_panel = populated_rgb[py1:py2, px1:px2].copy()
    if source_panel.shape != (PANEL_SIZE[1], PANEL_SIZE[0], 3) or sha256_array(source_panel) != EXPECTED_PANEL_SHA256:
        raise AssertionError("Approved Threat Monitor panel pixels changed")

    source_signal, line_cleanup_mask, workbox_mask, draw_mask = source_signal_masks(source_panel)
    source_plate, trace_fill_cleanup_mask, source_trace_fill, inpaint_seed_guard, source_signal_residuals, obsolete_trace_fill_pixels, cleanup_changed_pixels, right_edge_neutral_artifacts, right_edge_axis_guard = build_source_derived_plot_plate(
        source_panel,
        source_signal,
        line_cleanup_mask,
        workbox_mask,
    )
    if source_signal_residuals != 0 or obsolete_trace_fill_pixels != 0:
        raise AssertionError("Threat Monitor source trace/fill cleanup failed")
    graph_shell_plate, graph_presentation_mask, static_shell_changes, final_static_shell_mask, right_scale_targeted_neutral_scrub_pixels = build_graph_shell_plate(
        source_plate,
        draw_mask,
    )
    right_edge_axis_guard_pixels = int(np.count_nonzero(right_edge_axis_guard))
    right_scale_static_mask = rectangular_mask(RIGHT_SCALE_STATIC_BOUNDS)
    right_scale_clear_mask = rectangular_mask(RIGHT_SCALE_CLEAR_BOUNDS)
    right_scale_gutter_mask = rectangular_mask(RIGHT_SCALE_GUTTER_BOUNDS)
    scale_x1, scale_y1, scale_x2, scale_y2 = local_bounds(RIGHT_SCALE_STATIC_BOUNDS)
    protected_axis_local_start = RIGHT_AXIS_PROTECTED_START_X - PANEL_BOUNDS[0]
    visible_terminal_local_x = VISIBLE_SIGNAL_TERMINAL_X - PANEL_BOUNDS[0]
    draw_x1, draw_y1, draw_x2, draw_y2 = local_bounds(DRAW_CLIP)
    if (
        (scale_x1, scale_y1, scale_x2, scale_y2) != (400, 54, 409, 111)
        or VISIBLE_SIGNAL_TERMINAL_X != RIGHT_SCALE_STATIC_BOUNDS[0] - 1
        or RIGHT_SCALE_STATIC_BOUNDS[0] != RIGHT_AXIS_PROTECTED_START_X - 1
        or not np.array_equal(right_scale_clear_mask & draw_mask, right_scale_gutter_mask)
        or np.any(right_scale_static_mask & ~final_static_shell_mask)
    ):
        raise AssertionError("Threat Monitor right-scale static geometry changed")

    right_scale_tick_mask = np.zeros(source_panel.shape[:2], dtype=bool)
    right_scale_tick_mismatches = 0
    tick_x1 = Y_SCALE_TICK_GLOBAL_X[0] - PANEL_BOUNDS[0]
    tick_x2 = Y_SCALE_TICK_GLOBAL_X[1] - PANEL_BOUNDS[0]
    for global_y in Y_SCALE_TICK_GLOBAL_Y:
        y = global_y - PANEL_BOUNDS[1]
        right_scale_tick_mask[y, tick_x1:tick_x2] = True
        right_scale_tick_mismatches += int(
            np.count_nonzero(
                np.any(
                    graph_shell_plate[y, tick_x1:tick_x2] != np.asarray(Y_SCALE_TICK_RGB, dtype=np.uint8),
                    axis=1,
                )
            )
        )
    right_scale_tick_spacing = tuple(int(value) for value in np.diff(Y_SCALE_TICK_GLOBAL_Y))
    if right_scale_tick_spacing != (10, 10, 10, 10) or right_scale_tick_mismatches:
        raise AssertionError("Threat Monitor right-scale ticks no longer match the fixed 0-100 mapping")

    right_scale_light_neutral_residual_pixels = right_scale_light_neutral_residual_count(graph_shell_plate)
    if right_scale_light_neutral_residual_pixels:
        raise AssertionError("Threat Monitor light-neutral right-scale residue remains after static redraw")

    legacy_word_mask = np.zeros(source_panel.shape[:2], dtype=bool)
    for bounds in LEGACY_Y_WORD_AUDIT_BOUNDS:
        x1, y1, x2, y2 = local_bounds(bounds)
        legacy_word_mask[y1:y2, x1:x2] = True
    legacy_word_values = graph_shell_plate.astype(np.int16)
    legacy_word_ink_pixels = int(
        np.count_nonzero(
            legacy_word_mask
            & (legacy_word_values[:, :, 0] >= 100)
            & (legacy_word_values[:, :, 0] > legacy_word_values[:, :, 1] + 30)
            & (legacy_word_values[:, :, 0] > legacy_word_values[:, :, 2] + 30)
        )
    )
    if legacy_word_ink_pixels:
        raise AssertionError("Threat Monitor legacy CRIT/ELEV/BASE glyph ink remains")

    raw_panels: list[np.ndarray] = []
    raw_foregrounds: list[np.ndarray] = []
    raw_signal_y_values: list[np.ndarray] = []
    raw_area_alphas: list[np.ndarray] = []
    preview_frames: list[dict[str, object]] = []
    profiles: list[np.ndarray] = []
    for frame_index in range(FRAME_COUNT):
        threat_monitor = threat_monitor_preview_for_frame(frame_index)
        full_frame, panel, foreground, signal_y_values, area_alpha = render_full_frame(
            populated_rgb,
            source_panel,
            graph_shell_plate,
            trace_fill_cleanup_mask,
            static_shell_changes,
            draw_mask,
            final_static_shell_mask,
            threat_monitor,
        )
        master_allowed = np.zeros(populated_rgb.shape[:2], dtype=bool)
        master_allowed[py1:py2, px1:px2] = graph_presentation_mask | trace_fill_cleanup_mask
        changed = np.any(full_frame != populated_rgb, axis=2)
        if np.any(changed & ~master_allowed):
            raise AssertionError("Raw full frame changed pixels outside Threat Monitor graph presentation region")
        if np.any(foreground & ~draw_mask):
            raise AssertionError("Rendered Threat Monitor trace escaped its exact draw clip")
        raw_panels.append(panel)
        raw_foregrounds.append(foreground)
        raw_signal_y_values.append(signal_y_values)
        raw_area_alphas.append(area_alpha)
        preview_frames.append(threat_monitor)
        profiles.append(
            resample_anomaly_history_for_draw(
                threat_monitor[ANOMALY_HISTORY_FIELD],
                DRAW_CLIP[2] - DRAW_CLIP[0],
            )
        )

    # This palette-matched line-only control is proof/QC-only.  It uses the
    # identical samples and line operations, making any decoded difference in
    # the legal area mask attributable exclusively to the under-trace field.
    line_only_panels: list[np.ndarray] = []
    for profile, expected_y_values, expected_area_alpha in zip(profiles, raw_signal_y_values, raw_area_alphas):
        line_only_patch, _line_only_foreground, line_only_y_values, line_only_area_alpha = draw_signal_patch(
            graph_shell_plate[draw_y1:draw_y2, draw_x1:draw_x2].copy(),
            profile,
            include_area_fill=False,
        )
        if (
            not np.array_equal(line_only_y_values, expected_y_values)
            or not np.array_equal(line_only_area_alpha, expected_area_alpha)
        ):
            raise AssertionError("Threat Monitor decoded-fill control changed signal geometry")
        line_only_panel = graph_shell_plate.copy()
        line_only_panel[draw_y1:draw_y2, draw_x1:draw_x2] = line_only_patch
        restore_final_static_shell(line_only_panel, graph_shell_plate, final_static_shell_mask)
        line_only_panels.append(line_only_panel)

    closure_preview = threat_monitor_preview_for_frame(FRAME_COUNT)
    _, closure_panel, closure_foreground, closure_signal_y_values, closure_area_alpha = render_full_frame(
        populated_rgb,
        source_panel,
        graph_shell_plate,
        trace_fill_cleanup_mask,
        static_shell_changes,
        draw_mask,
        final_static_shell_mask,
        closure_preview,
    )
    if (
        not np.array_equal(closure_panel, raw_panels[0])
        or not np.array_equal(closure_foreground, raw_foregrounds[0])
        or not np.array_equal(closure_signal_y_values, raw_signal_y_values[0])
        or not np.array_equal(closure_area_alpha, raw_area_alphas[0])
    ):
        raise AssertionError("Threat Monitor loop does not close cleanly at frame 60")

    closure_profile = resample_anomaly_history_for_draw(
        closure_preview[ANOMALY_HISTORY_FIELD],
        DRAW_CLIP[2] - DRAW_CLIP[0],
    )
    profile_sequence = np.vstack((*profiles, closure_profile))
    max_profile_step = float(np.max(np.abs(np.diff(profile_sequence, axis=0))))
    if max_profile_step > 22.0:
        raise AssertionError("Threat Monitor signal changes too abruptly between frames")
    profile_unique_states = len({sha256_array(profile) for profile in profiles})
    if profile_unique_states != FRAME_COUNT:
        raise AssertionError("Threat Monitor preview history did not evolve across all frames")
    preview_profile_sha256 = sha256_array(np.vstack(profiles))
    if preview_profile_sha256 != EXPECTED_PREVIEW_PROFILE_SHA256:
        raise AssertionError("Threat Monitor preview telemetry behavior changed")

    signal_y_values_sha256 = sha256_array(np.vstack(raw_signal_y_values))
    if signal_y_values_sha256 != EXPECTED_SIGNAL_Y_VALUES_SHA256:
        raise AssertionError("Threat Monitor rendered signal geometry changed")

    area_fill_floor = (draw_y2 - draw_y1) - AREA_FILL_FLOOR_OFFSET
    area_fill_exists_frames = 0
    area_fill_columns_covered = 0
    area_fill_pixels_at_or_above_signal_halo = 0
    area_fill_pixels_at_or_below_floor = 0
    area_fill_gradient_monotonicity_errors = 0
    area_fill_opaque_pixels = 0
    area_fill_alpha_levels: set[int] = set()
    for signal_y_values, area_alpha in zip(raw_signal_y_values, raw_area_alphas):
        if area_alpha.shape != (draw_y2 - draw_y1, draw_x2 - draw_x1):
            raise AssertionError("Threat Monitor rendered area field escaped the fixed draw canvas")
        area_mask = area_alpha > 0
        area_fill_exists_frames += int(np.any(area_mask))
        area_fill_columns_covered = max(area_fill_columns_covered, int(np.count_nonzero(np.any(area_mask, axis=0))))
        rows = np.arange(area_alpha.shape[0])[:, None]
        area_fill_pixels_at_or_above_signal_halo += int(
            np.count_nonzero(area_mask & (rows <= signal_y_values[None, :] + AREA_FILL_HALO_OFFSET - 1))
        )
        area_fill_pixels_at_or_below_floor += int(np.count_nonzero(area_mask[area_fill_floor:]))
        area_fill_opaque_pixels += int(np.count_nonzero(area_alpha >= 255))
        area_fill_alpha_levels.update(int(value) for value in np.unique(area_alpha[area_mask]))
        for column_index in range(area_alpha.shape[1]):
            alpha_column = area_alpha[:, column_index]
            nonzero_rows = np.flatnonzero(alpha_column)
            if not len(nonzero_rows):
                continue
            expected_start = int(signal_y_values[column_index]) + AREA_FILL_HALO_OFFSET
            area_fill_gradient_monotonicity_errors += int(nonzero_rows[0] != expected_start)
            area_fill_gradient_monotonicity_errors += int(
                np.any(np.diff(alpha_column[nonzero_rows].astype(np.int16)) > 0)
            )
    if (
        area_fill_exists_frames != FRAME_COUNT
        or area_fill_columns_covered != (draw_x2 - draw_x1 - 1)
        or area_fill_pixels_at_or_above_signal_halo
        or area_fill_pixels_at_or_below_floor
        or area_fill_gradient_monotonicity_errors
        or area_fill_opaque_pixels
        or not area_fill_alpha_levels
        or max(area_fill_alpha_levels) != AREA_FILL_MAX_ALPHA
        or len(area_fill_alpha_levels) < 8
    ):
        raise AssertionError("Threat Monitor area shading no longer follows the fixed signal geometry")

    raster_values = [panel[draw_mask] for panel in raw_panels]
    raster_unique_states = len({sha256_array(value) for value in raster_values})
    raster_adjacent_changes = sum(
        not np.array_equal(raster_values[index], raster_values[index - 1])
        for index in range(1, FRAME_COUNT)
    ) + int(not np.array_equal(closure_panel[draw_mask], raster_values[-1]))
    if raster_unique_states < 50 or raster_adjacent_changes < 50:
        raise AssertionError("Threat Monitor signal is too static after rasterization")

    # Static shell changes are fixed inside the authorized graph-presentation
    # region; the only per-frame changes remain the local signal foreground.
    raw_outside_graph_presentation = 0
    raw_outside_frame_authorization = 0
    trace_pixels_outside_draw_clip = 0
    static_shell_frame_mismatches = 0
    dynamic_pixels_in_final_static_shell = 0
    protected_axis_dynamic_changes = 0
    right_scale_static_mismatches = 0
    dynamic_pixels_in_right_scale_static = 0
    visible_terminal_foreground_frames = 0
    for panel, foreground in zip(raw_panels, raw_foregrounds):
        frame_allowed = trace_fill_cleanup_mask | static_shell_changes | foreground
        changed = np.any(panel != source_panel, axis=2)
        raw_outside_graph_presentation += int(np.count_nonzero(changed & ~(graph_presentation_mask | trace_fill_cleanup_mask)))
        raw_outside_frame_authorization += int(np.count_nonzero(changed & ~frame_allowed))
        trace_pixels_outside_draw_clip += int(np.count_nonzero(foreground & ~draw_mask))
        static_shell_frame_mismatches += int(
            np.count_nonzero(np.any(panel[final_static_shell_mask] != graph_shell_plate[final_static_shell_mask], axis=1))
        )
        dynamic_pixels_in_final_static_shell += int(np.count_nonzero(foreground & final_static_shell_mask))
        protected_axis_dynamic_changes += int(
            np.count_nonzero(
                np.any(
                    panel[:, RIGHT_AXIS_PROTECTED_START_X - PANEL_BOUNDS[0]:]
                    != graph_shell_plate[:, RIGHT_AXIS_PROTECTED_START_X - PANEL_BOUNDS[0]:],
                    axis=2,
                )
            )
        )
        right_scale_static_mismatches += int(
            np.count_nonzero(
                np.any(
                    panel[scale_y1:scale_y2, scale_x1:scale_x2]
                    != graph_shell_plate[scale_y1:scale_y2, scale_x1:scale_x2],
                    axis=2,
                )
            )
        )
        dynamic_pixels_in_right_scale_static += int(np.count_nonzero(foreground & right_scale_static_mask))
        visible_terminal_foreground_frames += int(np.any(foreground[:, visible_terminal_local_x]))
        if not np.array_equal(panel[~frame_allowed], source_panel[~frame_allowed]):
            raise AssertionError("Protected Threat Monitor static pixels shifted")
    if raw_outside_graph_presentation or raw_outside_frame_authorization or trace_pixels_outside_draw_clip:
        raise AssertionError("Threat Monitor raw isolation validation failed")
    if (
        static_shell_frame_mismatches
        or dynamic_pixels_in_final_static_shell
        or protected_axis_dynamic_changes
        or right_scale_static_mismatches
        or dynamic_pixels_in_right_scale_static
        or visible_terminal_foreground_frames != FRAME_COUNT
    ):
        raise AssertionError(
            "Threat Monitor endpoint did not preserve the static right-scale gutter: "
            f"shell={static_shell_frame_mismatches} dynamic_shell={dynamic_pixels_in_final_static_shell} "
            f"axis={protected_axis_dynamic_changes} scale={right_scale_static_mismatches} "
            f"dynamic_scale={dynamic_pixels_in_right_scale_static} "
            f"terminal={visible_terminal_foreground_frames}"
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reference_path = OUT_DIR / "threat_monitor_static_reference.png"
    gif_path = OUT_DIR / "threat_monitor_preview_6s.gif"
    staging_path = OUT_DIR / ".threat_monitor_preview_6s.staging.gif"
    prior_decoded_right_scale_frame = load_existing_decoded_gif_keyframe(gif_path, 36)
    prior_right_scale_light_neutral_residual_pixels = (
        right_scale_light_neutral_residual_count(prior_decoded_right_scale_frame)
        if prior_decoded_right_scale_frame is not None
        else None
    )
    Image.fromarray(graph_shell_plate, "RGB").save(reference_path)
    if not np.array_equal(np.array(Image.open(reference_path).convert("RGB")), graph_shell_plate):
        raise AssertionError("Static Threat Monitor graph-shell reference verification failed")

    # One fixed palette plus full-size descriptors prevents GIF optimisation,
    # cropped delta frames, and static-region placement drift.
    palette_source = Image.new("RGB", (PANEL_SIZE[0], PANEL_SIZE[1] * (FRAME_COUNT + 1)))
    palette_source.paste(Image.fromarray(graph_shell_plate, "RGB"), (0, 0))
    for row, panel in enumerate(raw_panels, start=1):
        palette_source.paste(Image.fromarray(panel, "RGB"), (0, row * PANEL_SIZE[1]))
    palette = palette_source.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette_bytes = bytes(palette.getpalette() or [])
    if len(palette_bytes) != 768:
        raise AssertionError("Threat Monitor GIF palette is not 256 colors")
    encoded_frames = [Image.fromarray(panel, "RGB").quantize(palette=palette, dither=Image.Dither.NONE) for panel in raw_panels]
    encoded_line_only_frames = [
        Image.fromarray(panel, "RGB").quantize(palette=palette, dither=Image.Dither.NONE)
        for panel in line_only_panels
    ]
    encoded_frames[0].save(
        staging_path,
        format="GIF",
        save_all=True,
        append_images=encoded_frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=False,
        disposal=2,
        palette=palette_bytes,
    )

    decoded_frames: list[np.ndarray] = []
    durations: list[int] = []
    disposals: list[int] = []
    with Image.open(staging_path) as gif:
        gif_format = gif.format
        gif_size = gif.size
        gif_count = gif.n_frames
        gif_loop = gif.info.get("loop")
        for frame_index in range(gif.n_frames):
            gif.seek(frame_index)
            durations.append(int(gif.info.get("duration", 0)))
            disposals.append(int(getattr(gif, "disposal_method", 0)))
            decoded_frames.append(np.array(gif.convert("RGB")))
    logical_size, descriptors, encoded_palette = parse_gif(staging_path)
    if (
        gif_format != "GIF"
        or gif_size != PANEL_SIZE
        or logical_size != PANEL_SIZE
        or gif_count != FRAME_COUNT
        or len(descriptors) != FRAME_COUNT
        or gif_loop != 0
        or set(durations) != {FRAME_DURATION_MS}
        or sum(durations) != FRAME_COUNT * FRAME_DURATION_MS
        or set(disposals) != {2}
    ):
        raise AssertionError("Threat Monitor GIF metadata validation failed")
    if any(descriptor[4] or descriptor[5] or descriptor[6] != 2 or descriptor[7] != FRAME_DURATION_MS // 10 or descriptor[8] for descriptor in descriptors):
        raise AssertionError("Threat Monitor GIF palette/interlace/disposal/transparency validation failed")
    if encoded_palette != palette_bytes:
        raise AssertionError("Threat Monitor GIF global palette changed")
    if any(descriptor[:4] != (0, 0, PANEL_SIZE[0], PANEL_SIZE[1]) for descriptor in descriptors):
        raise AssertionError("Threat Monitor GIF contains cropped delta frames")
    expected_decoded = [np.array(frame.convert("RGB")) for frame in encoded_frames]
    if not all(np.array_equal(actual, expected) for actual, expected in zip(decoded_frames, expected_decoded)):
        raise AssertionError("Decoded Threat Monitor GIF differs from intended full-canvas frames")
    decoded_line_only_frames = [np.array(frame.convert("RGB")) for frame in encoded_line_only_frames]
    if len({sha256_array(frame) for frame in decoded_frames}) != FRAME_COUNT:
        raise AssertionError("Threat Monitor GIF does not contain 60 unique decoded frames")
    if any(np.array_equal(decoded_frames[index], decoded_frames[index - 1]) for index in range(1, FRAME_COUNT)):
        raise AssertionError("Threat Monitor GIF has adjacent duplicate frames")
    decoded_temporal_outside_workbox = sum(
        int(np.count_nonzero(np.any(decoded_frames[index] != decoded_frames[index - 1], axis=2) & ~workbox_mask))
        for index in range(1, FRAME_COUNT)
    )
    if decoded_temporal_outside_workbox != 0:
        raise AssertionError("Decoded Threat Monitor GIF shimmered outside graph workbox")
    decoded_protected_axis_temporal_changes = sum(
        int(
            np.count_nonzero(
                np.any(
                    decoded_frames[index][:, protected_axis_local_start:]
                    != decoded_frames[index - 1][:, protected_axis_local_start:],
                    axis=2,
                )
            )
        )
        for index in range(1, FRAME_COUNT)
    )
    decoded_static_shell_temporal_changes = sum(
        int(
            np.count_nonzero(
                np.any(
                    decoded_frames[index][final_static_shell_mask]
                    != decoded_frames[index - 1][final_static_shell_mask],
                    axis=1,
                )
            )
        )
        for index in range(1, FRAME_COUNT)
    )
    decoded_right_scale_static_temporal_changes = sum(
        int(
            np.count_nonzero(
                np.any(
                    decoded_frames[index][scale_y1:scale_y2, scale_x1:scale_x2]
                    != decoded_frames[index - 1][scale_y1:scale_y2, scale_x1:scale_x2],
                    axis=2,
                )
            )
        )
        for index in range(1, FRAME_COUNT)
    )
    decoded_visible_terminal_red_frames = sum(
        int(
            np.any(
                (decoded_frames[index][draw_y1:draw_y2, visible_terminal_local_x, 0] >= 150)
                & (
                    decoded_frames[index][draw_y1:draw_y2, visible_terminal_local_x, 0]
                    > decoded_frames[index][draw_y1:draw_y2, visible_terminal_local_x, 1] + 40
                )
                & (
                    decoded_frames[index][draw_y1:draw_y2, visible_terminal_local_x, 0]
                    > decoded_frames[index][draw_y1:draw_y2, visible_terminal_local_x, 2] + 40
                )
            )
        )
        for index in range(FRAME_COUNT)
    )
    decoded_right_scale_light_neutral_residual_pixels = tuple(
        right_scale_light_neutral_residual_count(frame)
        for frame in decoded_frames
    )
    decoded_area_fill_visible_frames = 0
    decoded_area_fill_difference_pixels_min: int | None = None
    decoded_area_fill_head_coverage_min = 1.0
    decoded_area_fill_all_coverage_min = 1.0
    decoded_area_fill_differences_outside_legal_mask = 0
    for decoded_frame, line_only_frame, area_alpha in zip(
        decoded_frames,
        decoded_line_only_frames,
        raw_area_alphas,
    ):
        decoded_patch = decoded_frame[draw_y1:draw_y2, draw_x1:draw_x2].astype(np.int16)
        decoded_line_only_patch = line_only_frame[draw_y1:draw_y2, draw_x1:draw_x2].astype(np.int16)
        legal_area_mask = area_alpha > 0
        head_area_mask = area_alpha >= DECODED_AREA_HEAD_MIN_ALPHA
        if not np.any(head_area_mask):
            raise AssertionError("Threat Monitor decoded-fill audit has no near-trace head")
        decoded_chroma = decoded_patch[:, :, 0] - np.maximum(decoded_patch[:, :, 1], decoded_patch[:, :, 2])
        line_only_chroma = (
            decoded_line_only_patch[:, :, 0]
            - np.maximum(decoded_line_only_patch[:, :, 1], decoded_line_only_patch[:, :, 2])
        )
        decoded_area_difference = np.any(decoded_patch != decoded_line_only_patch, axis=2)
        decoded_area_fill_differences_outside_legal_mask += int(
            np.count_nonzero(decoded_area_difference & ~legal_area_mask)
        )
        visible_dark_red = (decoded_chroma - line_only_chroma) >= DECODED_AREA_MIN_RED_CHROMA_GAIN
        visible_pixels = int(np.count_nonzero(visible_dark_red & legal_area_mask))
        decoded_area_fill_visible_frames += int(visible_pixels > 0)
        decoded_area_fill_difference_pixels_min = (
            visible_pixels
            if decoded_area_fill_difference_pixels_min is None
            else min(decoded_area_fill_difference_pixels_min, visible_pixels)
        )
        decoded_area_fill_head_coverage_min = min(
            decoded_area_fill_head_coverage_min,
            float(np.count_nonzero(visible_dark_red & head_area_mask)) / float(np.count_nonzero(head_area_mask)),
        )
        decoded_area_fill_all_coverage_min = min(
            decoded_area_fill_all_coverage_min,
            float(visible_pixels) / float(np.count_nonzero(legal_area_mask)),
        )
    if (
        any(decoded_right_scale_light_neutral_residual_pixels)
        or decoded_area_fill_visible_frames != FRAME_COUNT
        or decoded_area_fill_difference_pixels_min is None
        or decoded_area_fill_head_coverage_min < DECODED_AREA_HEAD_MIN_COVERAGE
        or decoded_area_fill_all_coverage_min < DECODED_AREA_ALL_MIN_COVERAGE
        or decoded_area_fill_differences_outside_legal_mask
    ):
        raise AssertionError("Decoded Threat Monitor GIF failed right-scale or under-trace area verification")
    if (
        decoded_protected_axis_temporal_changes
        or decoded_static_shell_temporal_changes
        or decoded_right_scale_static_temporal_changes
        or decoded_visible_terminal_red_frames != FRAME_COUNT
    ):
        raise AssertionError("Decoded Threat Monitor GIF failed static-scale terminal verification")
    staging_path.replace(gif_path)

    keyframe_paths: list[Path] = []
    for frame_index in KEYFRAME_INDICES:
        path = OUT_DIR / f"threat_monitor_frame_{frame_index:03d}.png"
        Image.fromarray(decoded_frames[frame_index], "RGB").save(path)
        if not np.array_equal(np.array(Image.open(path).convert("RGB")), decoded_frames[frame_index]):
            raise AssertionError(f"Keyframe PNG differs from decoded GIF frame {frame_index}")
        keyframe_paths.append(path)

    keyframe_labels = {
        0: "F000  baseline window",
        12: "F012  early activity",
        24: "F024  medium anomaly",
        36: "F036  critical spike",
        48: "F048  recovery",
        59: "F059  clean loop return",
    }
    motion_labels = {index: f"F{index:03d}  {index * FRAME_DURATION_MS / 1000.0:.1f}s" for index in MOTION_AUDIT_INDICES}
    contact_sheet_path = OUT_DIR / "threat_monitor_keyframe_contact_sheet.png"
    motion_audit_path = OUT_DIR / "threat_monitor_motion_audit_12frames.png"
    mask_proof_path = OUT_DIR / "threat_monitor_animation_masks_proof.png"
    right_edge_proof_path = OUT_DIR / "threat_monitor_right_edge_now_proof.png"
    decoded_fill_proof_path = OUT_DIR / "threat_monitor_decoded_fill_proof.png"
    graph_presentation_proof_path = OUT_DIR / "threat_monitor_graph_presentation_proof.png"
    contact_sheet_size = make_preview_sheet(
        decoded_frames,
        KEYFRAME_INDICES,
        keyframe_labels,
        "THREAT MONITOR - DECODED GIF KEYFRAMES",
        columns=3,
        scale=0.78,
        path=contact_sheet_path,
    )
    motion_audit_size = make_preview_sheet(
        decoded_frames,
        MOTION_AUDIT_INDICES,
        motion_labels,
        "THREAT MONITOR - 12-FRAME MOTION AUDIT",
        columns=4,
        scale=0.56,
        path=motion_audit_path,
    )
    mask_proof_size = make_mask_proof(
        source_panel,
        source_signal,
        trace_fill_cleanup_mask,
        draw_mask,
        mask_proof_path,
    )
    right_edge_proof_size = make_right_edge_proof(
        prior_decoded_right_scale_frame,
        decoded_frames,
        right_edge_proof_path,
    )
    decoded_fill_proof_size = make_decoded_fill_proof(
        decoded_frames,
        decoded_line_only_frames,
        decoded_fill_proof_path,
    )
    graph_presentation_proof_size = make_graph_presentation_proof(
        graph_shell_plate,
        decoded_frames,
        graph_presentation_proof_path,
    )

    frozen_after = snapshot_tree(FROZEN_ARCHIVE_ROOT)
    if frozen_after != frozen_before:
        raise AssertionError("A frozen approved subsystem archive changed during Threat Monitor rendering")
    frozen_manifest_counts_after = verify_frozen_archives()
    if frozen_manifest_counts_after != frozen_manifest_counts:
        raise AssertionError("Frozen archive manifest entries changed during Threat Monitor rendering")
    verify_frozen_working_scripts()
    for path, expected in EXPECTED_MASTER_SHA256.items():
        if sha256_bytes(path.read_bytes()) != expected:
            raise AssertionError(f"Approved master changed during Threat Monitor render: {path.name}")
    if sha256_bytes(GENERATE_CASE_BANNER_PATH.read_bytes()) != generator_hash_before:
        raise AssertionError("generate_case_banner.py changed during Threat Monitor render")

    qc_path = OUT_DIR / "threat_monitor_qc.txt"
    output_names = {
        reference_path.name,
        gif_path.name,
        qc_path.name,
        contact_sheet_path.name,
        motion_audit_path.name,
        mask_proof_path.name,
        right_edge_proof_path.name,
        decoded_fill_proof_path.name,
        graph_presentation_proof_path.name,
        *(path.name for path in keyframe_paths),
    }
    existing_outputs = {path.name for path in OUT_DIR.iterdir() if path.is_file()}
    if not existing_outputs <= output_names:
        raise AssertionError("Unexpected Threat Monitor output file exists")

    score_values = {int(frame["threat_score"]) for frame in preview_frames}
    level_values = {str(frame["threat_level"]) for frame in preview_frames}
    qc_lines = (
        "Subsystem #6 Threat Monitor isolated QC",
        f"script_used={SCRIPT_NAME}",
        f"workspace_root={ROOT}",
        f"output_directory={OUT_DIR}",
        f"approved_populated_master={POPULATED_PATH.name} role=authoritative static pixels and geometry sha256={master_hashes[POPULATED_PATH]}",
        f"approved_clear_master={CLEAR_PATH.name} role=hash-verified only; direct_panel_patch_used=False sha256={master_hashes[CLEAR_PATH]}",
        f"biohazard_reference={BIOHAZARD_REFERENCE_PATH.name} role=hash-verified frozen reference only sha256={master_hashes[BIOHAZARD_REFERENCE_PATH]}",
        f"panel_bounds_global={PANEL_BOUNDS} dimensions={PANEL_SIZE[0]}x{PANEL_SIZE[1]} source_panel_sha256={sha256_array(source_panel)}",
        f"axis_box_global={AXIS_BOX} graph_shell_redesign_authorized_inside_graph_presentation_only=True",
        f"graph_workbox_global={WORKBOX} local={local_bounds(WORKBOX)} pixels={int(np.count_nonzero(workbox_mask))}",
        f"graph_presentation_bounds_global={GRAPH_PRESENTATION_BOUNDS} local={local_bounds(GRAPH_PRESENTATION_BOUNDS)} static_shell_changed_pixels={int(np.count_nonzero(static_shell_changes))} static_shell_changed_inside_draw_clip={int(np.count_nonzero(static_shell_changes & draw_mask))} final_static_restore_pixels={int(np.count_nonzero(final_static_shell_mask))}",
        f"fresh_signal_draw_clip_global={DRAW_CLIP} local={local_bounds(DRAW_CLIP)} pixels={int(np.count_nonzero(draw_mask))}",
        f"right_scale_clear_bounds_global={RIGHT_SCALE_CLEAR_BOUNDS} final_static_bounds_global={RIGHT_SCALE_STATIC_BOUNDS} final_composite_source=graph_shell_plate continuous_bright_white_y_axis_removed=True visible_signal_terminal_global_x={VISIBLE_SIGNAL_TERMINAL_X} protected_scale_start_global_x={RIGHT_AXIS_PROTECTED_START_X}",
        f"legacy_crit_elev_base_ink_pixels_remaining={legacy_word_ink_pixels} right_scale_numeric_labels={tuple(label for _x, _y, label, _color in Y_SCALE_LABELS)} right_scale_tick_values={Y_SCALE_VALUES} right_scale_tick_y_global={Y_SCALE_TICK_GLOBAL_Y} right_scale_tick_spacing_px={right_scale_tick_spacing} right_scale_tick_length_px={Y_SCALE_TICK_GLOBAL_X[1] - Y_SCALE_TICK_GLOBAL_X[0]} right_scale_tick_rgb={Y_SCALE_TICK_RGB} right_scale_tick_raw_mismatches={right_scale_tick_mismatches} right_scale_static_raw_mismatches={right_scale_static_mismatches} dynamic_pixels_in_right_scale_static_mask={dynamic_pixels_in_right_scale_static} visible_terminal_foreground_frames={visible_terminal_foreground_frames}/{FRAME_COUNT} protected_scale_dynamic_changes={protected_axis_dynamic_changes}",
        f"right_scale_neutral_cleanup_core_global={RIGHT_SCALE_NEUTRAL_RESIDUAL_AUDIT_BOUNDS} detector=max_channel_delta<={RIGHT_SCALE_NEUTRAL_MAX_SATURATION},mean_brightness>={RIGHT_SCALE_NEUTRAL_MIN_BRIGHTNESS},intentional_red_ticks_excluded=True targeted_post_inpaint_scrub_pixels={right_scale_targeted_neutral_scrub_pixels} raw_light_neutral_residual_pixels={right_scale_light_neutral_residual_pixels} prior_decoded_frame_036_light_neutral_residual_pixels={prior_right_scale_light_neutral_residual_pixels if prior_right_scale_light_neutral_residual_pixels is not None else 'not_available'} decoded_light_neutral_residual_total={sum(decoded_right_scale_light_neutral_residual_pixels)} decoded_light_neutral_residual_max_per_frame={max(decoded_right_scale_light_neutral_residual_pixels)}",
        f"source_signal_mask_global_bbox={mask_bbox_global(source_signal)} pixels={int(np.count_nonzero(source_signal))}",
        f"source_trace_fill_component_global_bbox={mask_bbox_global(source_trace_fill)} pixels={int(np.count_nonzero(source_trace_fill))} weak_red_detector=R>={WEAK_TRACE_FILL_RED_MIN},R-max(G,B)>={WEAK_TRACE_FILL_RED_DELTA},connected_to_source_signal=True inpaint_seed_guard_pixels={int(np.count_nonzero(inpaint_seed_guard))}",
        f"source_line_cleanup_mask_global_bbox={mask_bbox_global(line_cleanup_mask)} pixels={int(np.count_nonzero(line_cleanup_mask))} source_trace_fill_cleanup_mask_global_bbox={mask_bbox_global(trace_fill_cleanup_mask)} pixels={int(np.count_nonzero(trace_fill_cleanup_mask))} source_plate_changed_pixels={cleanup_changed_pixels}",
        f"right_edge_guard_global_x=1238 temporary_inpaint_seed_rgb={RIGHT_EDGE_GUARD_RGB} restored_before_output=True source_cleanup_axis_guard_global={RIGHT_EDGE_AXIS_GUARD} pixels={right_edge_axis_guard_pixels} right_edge_wedge_audit_global={RIGHT_EDGE_WEDGE_AUDIT} bright_neutral_changed_pixels={right_edge_neutral_artifacts}",
        f"obsolete_source_bright_trace_pixels_remaining_in_fresh_graph_draw_region={source_signal_residuals} obsolete_source_trace_fill_pixels_remaining_in_fresh_graph_draw_region={obsolete_trace_fill_pixels} residual_detector=R>={TRACE_FILL_RESIDUAL_RED_MIN},R-max(G,B)>={TRACE_FILL_RESIDUAL_RED_DELTA}",
        "source_frame_reset_each_frame=True prior_frame_pixels_used=False local_graph_canvas=True alpha_composite_only=True",
        f"input_contract={ANOMALY_HISTORY_FIELD}=external chronological 0-100 time-series ending_at_NOW=True deterministic_resample_to_draw_width=True",
        "production_data_contract=persisted active-case signal history is caller-supplied; renderer never starts/resets history at 50 and never randomizes it; new-case initialization and later persistence occur upstream during final integration",
        "threat_score_and_anomaly_signal=distinct renderer metrics; both may derive from the same persisted active-case data during final integration",
        "preview_data_variable=THREAT_MONITOR_PREVIEW factory=threat_monitor_preview_for_frame structured_input=threat_monitor external_history_contract_test=passed",
        f"preview_case_id={THREAT_MONITOR_PREVIEW['case_id']} deterministic=True random_generation=False controlled_events={tuple(event[0] for event in THREAT_MONITOR_PREVIEW['controlled_events'])}",
        f"threat_score_values={tuple(sorted(score_values))} classification_values={tuple(sorted(level_values))} threshold_mapping={THRESHOLD_GUIDE} score_animation=False",
        f"profile_unique_states={profile_unique_states}/{FRAME_COUNT} preview_profile_sha256={preview_profile_sha256} signal_y_values_sha256={signal_y_values_sha256} telemetry_max_adjacent_sample_delta_0_to_100={max_profile_step:.6f} raster_unique_states={raster_unique_states}/{FRAME_COUNT} raster_adjacent_changes_including_loop_seam={raster_adjacent_changes}",
        f"area_shading_rgb={AREA_FILL_RGB} max_alpha={AREA_FILL_MAX_ALPHA} alpha_levels={len(area_fill_alpha_levels)} frames_with_visible_area={area_fill_exists_frames}/{FRAME_COUNT} columns_covered={area_fill_columns_covered}/{draw_x2 - draw_x1 - 1} only_below_signal_halo_pixel_violations={area_fill_pixels_at_or_above_signal_halo} at_or_below_floor_pixel_violations={area_fill_pixels_at_or_below_floor} gradient_monotonicity_errors={area_fill_gradient_monotonicity_errors} opaque_area_pixels={area_fill_opaque_pixels} area_layer_clipped_to_fresh_draw_canvas=True alpha_composite_only=True",
        f"decoded_area_fill_control=palette_matched_line_only_same_signal_geometry=True decoded_area_fill_visible_frames={decoded_area_fill_visible_frames}/{FRAME_COUNT} decoded_area_fill_min_visible_dark_red_pixels={decoded_area_fill_difference_pixels_min} decoded_area_fill_head_alpha_threshold={DECODED_AREA_HEAD_MIN_ALPHA} decoded_area_fill_red_chroma_gain_threshold={DECODED_AREA_MIN_RED_CHROMA_GAIN} decoded_area_fill_head_coverage_min={decoded_area_fill_head_coverage_min:.4f} required>={DECODED_AREA_HEAD_MIN_COVERAGE:.2f} decoded_area_fill_all_legal_coverage_min={decoded_area_fill_all_coverage_min:.4f} required>={DECODED_AREA_ALL_MIN_COVERAGE:.2f} decoded_area_fill_differences_outside_legal_mask={decoded_area_fill_differences_outside_legal_mask}",
        f"trace_pixels_outside_fresh_draw_clip={trace_pixels_outside_draw_clip}",
        f"outside_graph_presentation_raw_pixel_differences={raw_outside_graph_presentation} outside_frame_authorization_raw_pixel_differences={raw_outside_frame_authorization} static_shell_frame_mismatches={static_shell_frame_mismatches} dynamic_pixels_in_final_static_shell={dynamic_pixels_in_final_static_shell}",
        "threat_score_title_threshold_guide_summary_panel_border_neighboring_panels_fixed=True graph_shell_axes_ticks_x_y_labels_redesigned_only_within_authorized_graph_presentation=True no_text_overlap_with_signal=True",
        "dark_rectangle_artifact=False source_derived_graph_plate=True opaque_black_plot_patch_used=False graph_pixels_overlap_text_or_labels=False",
        f"frame_count={FRAME_COUNT} duration_per_frame={FRAME_DURATION_MS}ms total_duration={FRAME_COUNT * FRAME_DURATION_MS}ms loop=0",
        f"gif_real=True format=GIF dimensions={PANEL_SIZE[0]}x{PANEL_SIZE[1]} decoded_unique_frames={len({sha256_array(frame) for frame in decoded_frames})}/{FRAME_COUNT} full_canvas_frames_verified={FRAME_COUNT}/{FRAME_COUNT} disposal=2",
        f"decoded_temporal_outside_workbox_pixel_differences={decoded_temporal_outside_workbox}",
        f"decoded_protected_right_scale_temporal_changes={decoded_protected_axis_temporal_changes} decoded_static_shell_temporal_changes={decoded_static_shell_temporal_changes} decoded_right_scale_static_temporal_changes={decoded_right_scale_static_temporal_changes} decoded_visible_terminal_red_frames={decoded_visible_terminal_red_frames}/{FRAME_COUNT}",
        f"decoded_keyframes={KEYFRAME_INDICES} files={tuple(path.name for path in keyframe_paths)}",
        f"static_reference={reference_path.name} source_derived_graph_shell_plate=True sha256={sha256_array(graph_shell_plate)} contact_sheet={contact_sheet_path.name} dimensions={contact_sheet_size[0]}x{contact_sheet_size[1]}",
        f"motion_audit={motion_audit_path.name} dimensions={motion_audit_size[0]}x{motion_audit_size[1]} mask_proof={mask_proof_path.name} dimensions={mask_proof_size[0]}x{mask_proof_size[1]}",
        f"right_edge_now_proof={right_edge_proof_path.name} dimensions={right_edge_proof_size[0]}x{right_edge_proof_size[1]} prior_decoded_frame_036_compared_to_after_frames=(0, 36, 59)",
        f"decoded_fill_proof={decoded_fill_proof_path.name} dimensions={decoded_fill_proof_size[0]}x{decoded_fill_proof_size[1]} actual_decoded_frames=(0, 36, 59)",
        f"graph_presentation_proof={graph_presentation_proof_path.name} dimensions={graph_presentation_proof_size[0]}x{graph_presentation_proof_size[1]} static_plus_frames=(0, 36, 59)",
        f"frozen_manifest_payload_counts={frozen_manifest_counts_after} approved_png_masters_unchanged=True frozen_subsystems_01_to_05_unchanged=True frozen_working_scripts_match_archives=True",
        "generate_case_banner_unchanged=True live_repository_api_database_network_logic_added=False final_data_integration=False",
        "limitation=deterministic preview-only threat data; persistent active-case integration is intentionally deferred",
    )
    qc_path.write_text("\n".join(qc_lines) + "\n", encoding="utf-8")
    if {path.name for path in OUT_DIR.iterdir() if path.is_file()} != output_names:
        raise AssertionError("Threat Monitor output manifest changed after QC write")

    print(f"static reference: {reference_path}")
    print(f"GIF preview: {gif_path}")
    print("keyframes: " + ", ".join(str(path) for path in keyframe_paths))
    print(f"mask proof: {mask_proof_path}")
    print(f"keyframe contact sheet: {contact_sheet_path}")
    print(f"motion audit sheet: {motion_audit_path}")
    print(f"right-edge proof: {right_edge_proof_path}")
    print(f"decoded-fill proof: {decoded_fill_proof_path}")
    print(f"graph-presentation proof: {graph_presentation_proof_path}")
    print(f"QC note: {qc_path}")
    print(f"GIF size: {gif_path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
