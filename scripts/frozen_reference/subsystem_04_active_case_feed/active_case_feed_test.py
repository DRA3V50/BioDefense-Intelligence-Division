#!/usr/bin/env python3
"""Render only the Active Case Feed as a deterministic isolated preview."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
POPULATED_PATH = ROOT / "APPROVED_POPULATED_LAYOUT.png"
CLEAR_PATH = ROOT / "APPROVED_CLEAR_BASE_LAYOUT.png"
BIOHAZARD_REFERENCE_PATH = ROOT / "BIOHAZARD_REFERENCE.png"
OUT_DIR = ROOT / "active_case_feed_test_output"
SCRIPT_NAME = Path(__file__).name

EXPECTED_MASTER_SHA256 = {
    POPULATED_PATH: "90a223d08555853fd58c7bc7c0c30eadecfa7df3b5320db23e373462735312c4",
    CLEAR_PATH: "168d5b6ba745de5431f8fbaa9c5d5e4a95464b9e150f6aa23b862e4800d68f38",
    BIOHAZARD_REFERENCE_PATH: "ec0eb4cd38db13d34c0259f8ba920e4d9a1d2783feeb2f0d25e4ea2b0bf52ba5",
}
FROZEN_ARCHIVE_ROOT = ROOT / "approved_subsystems"
FROZEN_WORKING_SCRIPT_ARCHIVES = {
    ROOT / "biohazard_test.py": FROZEN_ARCHIVE_ROOT / "subsystem_01_biohazard_APPROVED" / "biohazard_test.py",
    ROOT / "magnifying_glass_test.py": FROZEN_ARCHIVE_ROOT / "subsystem_02_evidence_magnifier_APPROVED" / "magnifying_glass_test.py",
    ROOT / "workflow_strip_test.py": FROZEN_ARCHIVE_ROOT / "approved_subsystem_03_workflow" / "workflow_strip_test.py",
}

# Exact populated-master panel crop. It includes the approved border, heading,
# rows, axes, labels, and graph grid so their fixed geometry is visible.
PANEL_BOUNDS = (12, 555, 450, 821)
PANEL_SIZE = (PANEL_BOUNDS[2] - PANEL_BOUNDS[0], PANEL_BOUNDS[3] - PANEL_BOUNDS[1])
EXPECTED_PANEL_SHA256 = "42e974fb764591f41df971699f28406d0ee69064469aac6f65be63b8a24e355f"

LIVE_ROI_GLOBAL = (204, 566, 248, 584)
# The six baked rows remain in their approved positions.  Only the five
# deterministic preview events can receive a narrow under-row processing cue
# and a same-location severity illumination.
EVENT_SEVERITY_ROIS_GLOBAL = (
    (380, 592, 416, 603),
    (380, 609, 416, 620),
    (380, 626, 416, 637),
    (380, 643, 416, 654),
    (380, 660, 416, 671),
)
EVENT_ROW_ACTIVITY_BOUNDS_GLOBAL = (
    (52, 590, 374, 606),
    (52, 607, 374, 623),
    (52, 624, 374, 640),
    (52, 641, 374, 657),
    (52, 658, 374, 674),
)
GRAPH_INTERIOR_GLOBAL = (59, 712, 421, 787)
# The approved clear master has a bar-free graph, but its full dashboard layout
# differs from the populated master.  This exact clear graph raster is locally
# registered only beneath the populated chart's histogram columns; all target
# axes, labels, and grid pixels retain their approved populated geometry.
CLEAR_GRAPH_SOURCE_BOUNDS_GLOBAL = (55, 696, 435, 789)
GRAPH_PLATE_GLOBAL = GRAPH_INTERIOR_GLOBAL
# Full fixed bar field: every approved bar column from -60m through NOW is
# freshly rendered from telemetry values, while the surrounding graph geometry
# stays source-identical.
GRAPH_ANIMATION_ENVELOPE_GLOBAL = (69, 712, 420, 787)
BAR_BODY_RGB = (225, 36, 31)
BAR_HIGHLIGHT_RGB = (250, 59, 48)

EXPECTED_LIVE_MASK_COUNT = 181
EXPECTED_LIVE_MASK_BBOX = (206, 570, 246, 582)
EXPECTED_BAR_GROUPS = (
    (69, 75), (79, 84), (88, 93), (97, 102), (105, 110), (114, 120),
    (123, 128), (132, 137), (140, 145), (149, 155), (158, 163), (167, 172),
    (176, 182), (185, 191), (194, 200), (203, 209), (212, 218), (222, 227),
    (231, 236), (241, 246), (250, 255), (259, 264), (268, 274), (277, 283),
    (286, 292), (296, 301), (305, 310), (314, 319), (323, 328), (331, 337),
    (341, 346), (350, 355), (359, 364), (368, 373), (377, 383), (386, 391),
    (396, 401), (406, 411), (415, 419),
)
EXPECTED_GRAPH_BASELINE = 786
GRAPH_BAR_HEIGHT = EXPECTED_GRAPH_BASELINE - GRAPH_INTERIOR_GLOBAL[1] + 1

FRAME_COUNT = 60
FRAME_DURATION_MS = 100
KEYFRAME_INDICES = (0, 10, 28, 45, 59)
KEYFRAME_LABELS = {
    0: "frame_000_early",
    10: "frame_010_event_arrival",
    28: "frame_028_later",
    45: "frame_045_active_high",
    59: "frame_059_final",
}
MOTION_AUDIT_INDICES = (0, 5, 11, 16, 21, 27, 32, 37, 43, 48, 53, 59)

# Isolated, deterministic preview only. This object deliberately has no
# repository/API/database/network source and maps cleanly to later case data.
ACTIVE_CASE_FEED_PREVIEW = {
    "case_id": "CASE-7B-7742",
    "events": (
        {
            "case_id": "CASE-7B-7742",
            "ordering": 0,
            "timestamp": "18:21",
            "message": "Sensor anomaly detected - Zone 7B",
            "severity": "HIGH",
            "severity_level": 3,
            "graph_intensity": 0.88,
        },
        {
            "case_id": "CASE-7B-7742",
            "ordering": 1,
            "timestamp": "18:07",
            "message": "Unauthorized access attempt blocked",
            "severity": "HIGH",
            "severity_level": 3,
            "graph_intensity": 0.72,
        },
        {
            "case_id": "CASE-7B-7742",
            "ordering": 2,
            "timestamp": "17:53",
            "message": "Cold chain data integrity mismatch",
            "severity": "MEDIUM",
            "severity_level": 2,
            "graph_intensity": 0.49,
        },
        {
            "case_id": "CASE-7B-7742",
            "ordering": 3,
            "timestamp": "17:38",
            "message": "New IOC matched to insider profile",
            "severity": "HIGH",
            "severity_level": 3,
            "graph_intensity": 0.76,
        },
        {
            "case_id": "CASE-7B-7742",
            "ordering": 4,
            "timestamp": "17:22",
            "message": "Evidence ingested: log_bundle_7742",
            "severity": "LOW",
            "severity_level": 1,
            "graph_intensity": 0.31,
        },
    ),
    # A finite preview timeline tells the story of one monitored case: a
    # lower-priority evidence event, then validation concern, then a high
    # severity sensor anomaly.  It begins and ends settled for a clean loop.
    "arrival_timeline": (
        {"event_ordering": 4, "row_index": 4, "start_frame": 6, "end_frame": 16, "telemetry_center": 10},
        {"event_ordering": 2, "row_index": 2, "start_frame": 22, "end_frame": 32, "telemetry_center": 22},
        {"event_ordering": 0, "row_index": 0, "start_frame": 39, "end_frame": 51, "telemetry_center": 34},
    ),
    "telemetry_event_sigma_bars": 6.5,
    # Closed, hand-authored regional activity states.  Neighboring states
    # crossfade smoothly and retain the supplied bar silhouette as history;
    # this avoids generic whole-field sine breathing or random flicker.
    "telemetry_snapshots": (
        (0.36, 0.55, 0.43, 0.58, 0.34, 0.49, 0.41),
        (0.44, 0.46, 0.61, 0.37, 0.52, 0.40, 0.56),
        (0.32, 0.59, 0.48, 0.43, 0.62, 0.35, 0.47),
        (0.51, 0.38, 0.54, 0.60, 0.42, 0.57, 0.34),
        (0.39, 0.52, 0.35, 0.56, 0.50, 0.42, 0.61),
        (0.47, 0.41, 0.58, 0.32, 0.60, 0.49, 0.38),
    ),
    "telemetry_seed_weight": 0.78,
    "telemetry_regional_weight": 22.0,
    "telemetry_floor": 4.0,
    "telemetry_event_weight": 10.0,
    "telemetry_minimum": 5.0,
    "telemetry_maximum": 94.0,
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


def verify_frozen_working_scripts() -> None:
    """Prove the three frozen working implementations still match archives."""
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


def red_mask(array: np.ndarray, minimum_red: int, minimum_margin: int) -> np.ndarray:
    red = array[:, :, 0].astype(np.int16)
    green = array[:, :, 1].astype(np.int16)
    blue = array[:, :, 2].astype(np.int16)
    return (red >= minimum_red) & (red - np.maximum(green, blue) >= minimum_margin)


def mask_bbox_global(mask: np.ndarray) -> tuple[int, int, int, int]:
    yy, xx = np.where(mask)
    if not len(xx):
        raise AssertionError("Active Case Feed mask is empty")
    return (
        int(np.min(xx)) + PANEL_BOUNDS[0],
        int(np.min(yy)) + PANEL_BOUNDS[1],
        int(np.max(xx)) + 1 + PANEL_BOUNDS[0],
        int(np.max(yy)) + 1 + PANEL_BOUNDS[1],
    )


def full_mask_from_roi(
    source_panel: np.ndarray,
    roi_global: tuple[int, int, int, int],
    minimum_red: int,
    minimum_margin: int,
) -> np.ndarray:
    x1, y1, x2, y2 = local_bounds(roi_global)
    mask = np.zeros(source_panel.shape[:2], dtype=bool)
    mask[y1:y2, x1:x2] = red_mask(
        source_panel[y1:y2, x1:x2],
        minimum_red,
        minimum_margin,
    )
    return mask


def signal_mask_from_roi(
    source_panel: np.ndarray,
    roi_global: tuple[int, int, int, int],
) -> np.ndarray:
    """Select only the baked severity glyphs inside one fixed row ROI."""
    x1, y1, x2, y2 = local_bounds(roi_global)
    roi = source_panel[y1:y2, x1:x2]
    channels = roi.astype(np.int16)
    signal = (np.max(channels, axis=2) >= 45) & (
        np.max(channels, axis=2) - np.min(channels, axis=2) >= 12
    )
    mask = np.zeros(source_panel.shape[:2], dtype=bool)
    mask[y1:y2, x1:x2] = signal
    if not np.any(mask):
        raise AssertionError(f"Active Case Feed severity signal missing in {roi_global}")
    return mask


def detect_bars(source_panel: np.ndarray) -> tuple[list[tuple[int, int]], list[int], np.ndarray]:
    x1, y1, x2, y2 = local_bounds(GRAPH_INTERIOR_GLOBAL)
    graph = source_panel[y1:y2, x1:x2]
    graph_red = red_mask(graph, 100, 35)
    counts = graph_red.sum(axis=0)
    xs = np.where(counts >= 5)[0] + GRAPH_INTERIOR_GLOBAL[0]
    groups: list[tuple[int, int]] = []
    if len(xs):
        start = previous = int(xs[0])
        for value in xs[1:]:
            value = int(value)
            if value == previous + 1:
                previous = value
            else:
                groups.append((start, previous))
                start = previous = value
        groups.append((start, previous))
    if tuple(groups) != EXPECTED_BAR_GROUPS:
        raise AssertionError(f"Approved graph bar geometry changed: {groups}")
    bar_tops: list[int] = []
    baseline = 0
    for xa, xb in groups:
        local = graph_red[:, xa - GRAPH_INTERIOR_GLOBAL[0]:xb - GRAPH_INTERIOR_GLOBAL[0] + 1]
        yy, _ = np.where(local)
        top = GRAPH_INTERIOR_GLOBAL[1] + int(np.min(yy))
        bottom = GRAPH_INTERIOR_GLOBAL[1] + int(np.max(yy))
        baseline = max(baseline, bottom)
        bar_tops.append(top)
    if baseline != EXPECTED_GRAPH_BASELINE:
        raise AssertionError(f"Approved graph baseline changed: {baseline}")
    # Erase each original bar's complete visual footprint, not only its bright
    # interior.  The populated master includes faint red edge/shadow pixels
    # that would otherwise remain visible behind a shorter live value.
    source_histogram_mask = np.zeros(source_panel.shape[:2], dtype=bool)
    baseline_local = baseline - PANEL_BOUNDS[1]
    for (xa, xb), top in zip(groups, bar_tops):
        # Include the one-pixel antialiased top edge above the bright bar body.
        top_local = max(GRAPH_INTERIOR_GLOBAL[1], top - 1) - PANEL_BOUNDS[1]
        source_histogram_mask[top_local:baseline_local + 1, xa - PANEL_BOUNDS[0]:xb - PANEL_BOUNDS[0] + 1] = True
    return groups, bar_tops, source_histogram_mask


def build_masks(
    source_panel: np.ndarray,
) -> tuple[
    np.ndarray,
    list[np.ndarray],
    list[np.ndarray],
    list[tuple[int, int]],
    list[int],
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    live_mask = full_mask_from_roi(source_panel, LIVE_ROI_GLOBAL, 50, 15)
    if int(np.count_nonzero(live_mask)) != EXPECTED_LIVE_MASK_COUNT or mask_bbox_global(live_mask) != EXPECTED_LIVE_MASK_BBOX:
        raise AssertionError("Approved LIVE indicator geometry changed")

    severity_masks = [signal_mask_from_roi(source_panel, roi) for roi in EVENT_SEVERITY_ROIS_GLOBAL]
    row_activity_masks: list[np.ndarray] = []
    for bounds in EVENT_ROW_ACTIVITY_BOUNDS_GLOBAL:
        x1, y1, x2, y2 = local_bounds(bounds)
        mask = np.zeros(source_panel.shape[:2], dtype=bool)
        mask[y1:y2, x1:x2] = True
        row_activity_masks.append(mask)

    bars, bar_tops, source_histogram_mask = detect_bars(source_panel)
    # The complete graph plate is authorized for clear-plate restoration.  The
    # actual live histogram occupies only the original 39 fixed x columns,
    # preserving all gutters, axes, labels, and panel geometry.
    graph_plate_mask = np.zeros(source_panel.shape[:2], dtype=bool)
    plate_x1, plate_y1, plate_x2, plate_y2 = local_bounds(GRAPH_PLATE_GLOBAL)
    graph_plate_mask[plate_y1:plate_y2, plate_x1:plate_x2] = True
    bar_field_mask = np.zeros(source_panel.shape[:2], dtype=bool)
    _, gy1, _, gy2 = local_bounds(GRAPH_ANIMATION_ENVELOPE_GLOBAL)
    for xa, xb in bars:
        lx1 = xa - PANEL_BOUNDS[0]
        lx2 = xb - PANEL_BOUNDS[0] + 1
        bar_field_mask[gy1:gy2, lx1:lx2] = True
    authorized_mask = live_mask | graph_plate_mask
    for mask in (*severity_masks, *row_activity_masks):
        authorized_mask |= mask
    return (
        live_mask,
        severity_masks,
        row_activity_masks,
        bars,
        bar_tops,
        source_histogram_mask,
        bar_field_mask,
        graph_plate_mask,
        authorized_mask,
    )


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def build_empty_graph_plate(
    source_panel: np.ndarray,
    clear_rgb: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a same-coordinate red-bar-free graph plate from approved rasters."""
    clear_x1, clear_y1, clear_x2, clear_y2 = CLEAR_GRAPH_SOURCE_BOUNDS_GLOBAL
    clear_graph = clear_rgb[clear_y1:clear_y2, clear_x1:clear_x2]
    graph_x1, graph_y1, graph_x2, graph_y2 = local_bounds(GRAPH_PLATE_GLOBAL)
    graph_width = graph_x2 - graph_x1
    graph_height = graph_y2 - graph_y1
    if clear_graph.shape[:2] != (clear_y2 - clear_y1, clear_x2 - clear_x1):
        raise AssertionError("Approved clear graph crop is unavailable")
    if np.any(red_mask(clear_graph, 100, 35)):
        raise AssertionError("Approved clear graph crop unexpectedly contains histogram-red pixels")

    # The two approved dashboards are not globally pixel-registered.  Resize
    # only the empty clear graph foundation to the existing populated graph
    # coordinate system.  The complete target graph interior then comes from
    # the clear source before any fresh telemetry bars are drawn.
    registered_clear_graph = np.array(
        Image.fromarray(clear_graph, "RGB").resize(
            (graph_width, graph_height),
            Image.Resampling.BILINEAR,
        )
    )
    if np.any(red_mask(registered_clear_graph, 100, 35)):
        raise AssertionError("Registered clear graph introduced histogram-red pixels")
    empty_graph_panel = source_panel.copy()
    empty_graph_panel[graph_y1:graph_y2, graph_x1:graph_x2] = registered_clear_graph
    graph_plate_mask = np.zeros(source_panel.shape[:2], dtype=bool)
    graph_plate_mask[graph_y1:graph_y2, graph_x1:graph_x2] = True
    if not np.array_equal(empty_graph_panel[~graph_plate_mask], source_panel[~graph_plate_mask]):
        raise AssertionError("Empty graph plate disturbed approved non-graph geometry")
    return empty_graph_panel, registered_clear_graph


def seed_values_from_source_tops(source_bar_tops: Sequence[int]) -> np.ndarray:
    """Convert the approved populated silhouette into numeric preview seeds once."""
    if len(source_bar_tops) != len(EXPECTED_BAR_GROUPS):
        raise AssertionError("Unexpected source seed count")
    values = np.asarray(
        [
            100.0 * (EXPECTED_GRAPH_BASELINE - int(top) + 1) / GRAPH_BAR_HEIGHT
            for top in source_bar_tops
        ],
        dtype=np.float64,
    )
    if not np.all(np.isfinite(values)) or np.any(values < 0.0) or np.any(values > 100.0):
        raise AssertionError("Source bar seeds are outside the telemetry range")
    return values


def event_activity(
    preview: dict[str, object],
    frame_index: int,
) -> tuple[dict[str, object] | None, float, float]:
    """Return the sole controlled preview event currently being processed."""
    events = {int(event["ordering"]): event for event in preview["events"]}
    frame = frame_index % FRAME_COUNT
    active: list[tuple[dict[str, object], float, float]] = []
    for transition in preview["arrival_timeline"]:
        start = int(transition["start_frame"])
        end = int(transition["end_frame"])
        if not (start < frame < end):
            continue
        progress = (frame - start) / (end - start)
        # A quick but soft arrival settles back to the baseline rather than
        # becoming a continuous flashing row.
        strength = math.sin(math.pi * progress) ** 1.35
        event = dict(events[int(transition["event_ordering"])])
        event["row_index"] = int(transition["row_index"])
        event["telemetry_center"] = int(transition["telemetry_center"])
        active.append((event, strength, progress))
    if len(active) > 1:
        raise AssertionError("Preview timeline activates more than one event at once")
    return active[0] if active else (None, 0.0, 0.0)


def blend_pixels(
    frame: np.ndarray,
    mask: np.ndarray,
    color: tuple[float, float, float],
    opacity: float,
) -> None:
    if not np.any(mask):
        return
    original = frame[mask].astype(np.float64)
    frame[mask] = np.rint(
        np.clip(original * (1.0 - opacity) + np.asarray(color) * opacity, 0.0, 255.0)
    ).astype(np.uint8)


def recolor_red_mask(
    frame: np.ndarray,
    source_panel: np.ndarray,
    mask: np.ndarray,
    gain: float,
) -> None:
    source = source_panel[mask].astype(np.float64)
    boosted = source.copy()
    boosted[:, 0] = np.clip(boosted[:, 0] * gain, 0.0, 255.0)
    boosted[:, 1] = np.clip(boosted[:, 1] * (0.94 + 0.06 * gain), 0.0, 255.0)
    boosted[:, 2] = np.clip(boosted[:, 2] * (0.94 + 0.06 * gain), 0.0, 255.0)
    frame[mask] = np.rint(boosted).astype(np.uint8)


def brighten_source_mask(
    frame: np.ndarray,
    source_panel: np.ndarray,
    mask: np.ndarray,
    gain: float,
) -> None:
    """Boost a baked glyph while retaining its actual severity hue."""
    source = source_panel[mask].astype(np.float64)
    frame[mask] = np.rint(np.clip(source * gain, 0.0, 255.0)).astype(np.uint8)


def blend_weighted_pixels(
    frame: np.ndarray,
    mask: np.ndarray,
    color: tuple[float, float, float],
    weights: np.ndarray,
) -> None:
    """Apply a finite glint only to its predeclared fixed row strip."""
    original = frame[mask].astype(np.float64)
    alpha = np.clip(weights, 0.0, 1.0)[:, None]
    frame[mask] = np.rint(
        np.clip(original * (1.0 - alpha) + np.asarray(color) * alpha, 0.0, 255.0)
    ).astype(np.uint8)


def telemetry_components(
    preview: dict[str, object],
    bar_index: int,
    bar_count: int,
    t: float,
    event: dict[str, object] | None,
    event_strength: float,
) -> tuple[float, float]:
    """Return the correlated regional state and local event response."""
    position = bar_index / max(1, bar_count - 1)
    states = tuple(tuple(float(value) for value in state) for state in preview["telemetry_snapshots"])
    state_position = (t % 1.0) * len(states)
    current_index = int(math.floor(state_position)) % len(states)
    next_index = (current_index + 1) % len(states)
    state_blend = smoothstep(state_position - math.floor(state_position))

    def spatial_state_value(state: tuple[float, ...]) -> float:
        anchor_position = position * (len(state) - 1)
        left = int(math.floor(anchor_position))
        right = min(left + 1, len(state) - 1)
        spatial_blend = smoothstep(anchor_position - left)
        return (1.0 - spatial_blend) * state[left] + spatial_blend * state[right]

    regional = (1.0 - state_blend) * spatial_state_value(states[current_index]) + state_blend * spatial_state_value(states[next_index])
    event_contribution = 0.0
    if event is not None:
        center = int(event["telemetry_center"])
        sigma = float(preview["telemetry_event_sigma_bars"])
        local = math.exp(-0.5 * ((bar_index - center) / sigma) ** 2)
        event_contribution = float(event["graph_intensity"]) * event_strength * (0.18 + 0.82 * local)
    return regional, event_contribution


def telemetry_values_for_frame(
    preview: dict[str, object],
    frame_index: int,
    seed_values: Sequence[float],
) -> tuple[np.ndarray, dict[str, object] | None, float, float]:
    """Produce one complete deterministic 39-value [0,100] telemetry snapshot."""
    if len(seed_values) != len(EXPECTED_BAR_GROUPS):
        raise AssertionError("Telemetry snapshot does not cover all approved bar positions")
    event, strength, progress = event_activity(preview, frame_index)
    t = (frame_index % FRAME_COUNT) / FRAME_COUNT
    values = np.empty(len(seed_values), dtype=np.float64)
    for bar_index, seed in enumerate(seed_values):
        regional, event_contribution = telemetry_components(
            preview,
            bar_index,
            len(seed_values),
            t,
            event,
            strength,
        )
        values[bar_index] = np.clip(
            float(preview["telemetry_seed_weight"]) * float(seed)
            + float(preview["telemetry_regional_weight"]) * regional
            + float(preview["telemetry_floor"])
            + float(preview["telemetry_event_weight"]) * event_contribution,
            float(preview["telemetry_minimum"]),
            float(preview["telemetry_maximum"]),
        )
    if not np.all(np.isfinite(values)) or np.any(values < 0.0) or np.any(values > 100.0):
        raise AssertionError("Generated telemetry values are outside [0,100]")
    return values, event, strength, progress


def histogram_layout(
    values: Sequence[float],
    bars: Sequence[tuple[int, int]],
) -> tuple[list[int], list[int]]:
    """Map current data values to one complete baseline-anchored bar per slot."""
    if len(values) != len(bars) or len(bars) != len(EXPECTED_BAR_GROUPS):
        raise AssertionError("Histogram needs exactly 39 values and 39 approved slots")
    tops: list[int] = []
    heights: list[int] = []
    for value in values:
        numeric = float(value)
        if not math.isfinite(numeric) or not 0.0 <= numeric <= 100.0:
            raise AssertionError("Histogram value is outside [0,100]")
        height = int(round(numeric * GRAPH_BAR_HEIGHT / 100.0))
        height = max(0, min(GRAPH_BAR_HEIGHT, height))
        top = EXPECTED_GRAPH_BASELINE - height + 1 if height else EXPECTED_GRAPH_BASELINE + 1
        tops.append(top)
        heights.append(height)
    return tops, heights


def render_histogram(
    frame: np.ndarray,
    values: Sequence[float],
    bars: Sequence[tuple[int, int]],
) -> tuple[list[int], list[int]]:
    """Render all complete, fresh live bars from the approved baseline."""
    tops, heights = histogram_layout(values, bars)
    baseline_local = EXPECTED_GRAPH_BASELINE - PANEL_BOUNDS[1]
    for (xa, xb), top, height in zip(bars, tops, heights):
        if not height:
            continue
        lx1 = xa - PANEL_BOUNDS[0]
        lx2 = xb - PANEL_BOUNDS[0] + 1
        ly1 = top - PANEL_BOUNDS[1]
        frame[ly1:baseline_local + 1, lx1:lx2] = BAR_BODY_RGB
        frame[ly1:ly1 + 1, lx1:lx2] = BAR_HIGHLIGHT_RGB
    return tops, heights


def render_frame(
    empty_graph_panel: np.ndarray,
    source_panel: np.ndarray,
    live_mask: np.ndarray,
    severity_masks: list[np.ndarray],
    row_activity_masks: list[np.ndarray],
    bars: list[tuple[int, int]],
    telemetry_values: Sequence[float],
    event: dict[str, object] | None,
    strength: float,
    progress: float,
    frame_index: int,
) -> tuple[np.ndarray, list[int], list[int]]:
    """Render one constrained preview frame from the immutable panel plate."""
    # Every frame starts fresh from the immutable empty clear-derived graph
    # plate, so no populated histogram pixels can persist underneath live data.
    frame = empty_graph_panel.copy()
    # All preview motion is explicitly periodic: frame 60 is the same pose as
    # frame 0, while the encoded loop contains the non-duplicated 0..59 poses.
    t = (frame_index % FRAME_COUNT) / FRAME_COUNT
    live_pulse = 0.5 - 0.5 * math.cos(math.tau * t)
    # The indicator breathes in place, and gains only a small extra lift while
    # the currently scheduled event is being processed.
    recolor_red_mask(frame, source_panel, live_mask, 0.98 + 0.07 * live_pulse + 0.035 * strength)
    # A low-amplitude illumination phase travels within the existing bullet and
    # LIVE glyphs.  The glyph coordinates themselves never move; this merely
    # preserves a visible, non-flashing live-state pulse after GIF quantizing.
    live_y, live_x = np.where(live_mask)
    sheen = 0.018 + 0.050 * (
        0.5 + 0.5 * np.sin(math.tau * t + (live_x - np.min(live_x)) * 0.72)
    )
    blend_weighted_pixels(frame, live_mask, (244.0, 45.0, 38.0), sheen)
    if event is not None:
        row_index = int(event["row_index"])
        severity = str(event["severity"])
        severity_color = {
            "HIGH": (236.0, 46.0, 38.0),
            "MEDIUM": (234.0, 141.0, 34.0),
            "LOW": (73.0, 168.0, 95.0),
        }[severity]

        # One fixed row receives a brief source-aligned scan.  It never moves
        # text, timestamps, or dividers; only its current intensity varies.
        row_mask = row_activity_masks[row_index]
        yy, xx = np.where(row_mask)
        left = int(np.min(xx))
        right = int(np.max(xx))
        glint_center = left + 18.0 + (right - left - 36.0) * smoothstep(progress)
        glint = np.exp(-0.5 * ((xx.astype(np.float64) - glint_center) / 11.0) ** 2)
        blend_weighted_pixels(
            frame,
            row_mask,
            severity_color,
            (0.025 + 0.070 * strength) * glint,
        )
        brighten_source_mask(frame, source_panel, severity_masks[row_index], 1.0 + 0.22 * strength)

    tops, heights = render_histogram(frame, telemetry_values, bars)
    return frame, tops, heights


def verify_histogram_frame(
    frame: np.ndarray,
    empty_graph_panel: np.ndarray,
    bars: Sequence[tuple[int, int]],
    tops: Sequence[int],
    heights: Sequence[int],
) -> tuple[int, int]:
    """Count ghost pixels and discontinuities against the red-bar-free plate."""
    if not (len(bars) == len(tops) == len(heights) == len(EXPECTED_BAR_GROUPS)):
        raise AssertionError("Histogram QC received incomplete bar geometry")
    ghost_pixels = 0
    disconnected_pixels = 0
    graph_top = GRAPH_INTERIOR_GLOBAL[1]
    baseline = EXPECTED_GRAPH_BASELINE
    for (xa, xb), top, height in zip(bars, tops, heights):
        lx1 = xa - PANEL_BOUNDS[0]
        lx2 = xb - PANEL_BOUNDS[0] + 1
        above_end = min(max(int(top), graph_top), baseline + 1)
        if above_end > graph_top:
            actual_above = frame[graph_top - PANEL_BOUNDS[1]:above_end - PANEL_BOUNDS[1], lx1:lx2]
            plate_above = empty_graph_panel[graph_top - PANEL_BOUNDS[1]:above_end - PANEL_BOUNDS[1], lx1:lx2]
            ghost_pixels += int(np.count_nonzero(np.any(actual_above != plate_above, axis=2)))
        if not height:
            continue
        top_local = int(top) - PANEL_BOUNDS[1]
        baseline_local = baseline - PANEL_BOUNDS[1]
        expected = np.empty((baseline_local - top_local + 1, lx2 - lx1, 3), dtype=np.uint8)
        expected[:, :] = BAR_BODY_RGB
        expected[0:1, :] = BAR_HIGHLIGHT_RGB
        actual = frame[top_local:baseline_local + 1, lx1:lx2]
        disconnected_pixels += int(np.count_nonzero(np.any(actual != expected, axis=2)))
    return ghost_pixels, disconnected_pixels


def ghost_pixels_above_tops(
    frame: np.ndarray,
    empty_graph_panel: np.ndarray,
    bars: Sequence[tuple[int, int]],
    tops: Sequence[int],
) -> int:
    """Compare each bar's clear region above its current top to the plate."""
    if len(bars) != len(tops):
        raise AssertionError("Ghost-bar QC received mismatched geometry")
    graph_top = GRAPH_INTERIOR_GLOBAL[1]
    baseline = EXPECTED_GRAPH_BASELINE
    pixels = 0
    for (xa, xb), top in zip(bars, tops):
        lx1 = xa - PANEL_BOUNDS[0]
        lx2 = xb - PANEL_BOUNDS[0] + 1
        above_end = min(max(int(top), graph_top), baseline + 1)
        if above_end <= graph_top:
            continue
        actual = frame[graph_top - PANEL_BOUNDS[1]:above_end - PANEL_BOUNDS[1], lx1:lx2]
        plate = empty_graph_panel[graph_top - PANEL_BOUNDS[1]:above_end - PANEL_BOUNDS[1], lx1:lx2]
        pixels += int(np.count_nonzero(np.any(actual != plate, axis=2)))
    return pixels


def nonred_pixels_inside_bar_bodies(
    frame: np.ndarray,
    bars: Sequence[tuple[int, int]],
    tops: Sequence[int],
    heights: Sequence[int],
) -> int:
    """Count any decoded body holes using the approved bar-red classification."""
    if not (len(bars) == len(tops) == len(heights)):
        raise AssertionError("Decoded histogram QC received mismatched geometry")
    baseline_local = EXPECTED_GRAPH_BASELINE - PANEL_BOUNDS[1]
    pixels = 0
    for (xa, xb), top, height in zip(bars, tops, heights):
        if not height:
            continue
        lx1 = xa - PANEL_BOUNDS[0]
        lx2 = xb - PANEL_BOUNDS[0] + 1
        top_local = int(top) - PANEL_BOUNDS[1]
        pixels += int(np.count_nonzero(~red_mask(frame[top_local:baseline_local + 1, lx1:lx2], 100, 35)))
    return pixels


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


def array_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    yy, xx = np.where(mask)
    if not len(xx):
        raise AssertionError("Adjacent GIF frames unexpectedly identical")
    return int(np.min(xx)), int(np.min(yy)), int(np.max(xx)) + 1, int(np.max(yy)) + 1


def make_preview_sheet(
    decoded_frames: list[np.ndarray],
    indices: tuple[int, ...],
    labels: dict[int, str],
    title: str,
    columns: int,
    scale: float,
    path: Path,
) -> tuple[int, int]:
    """Create proof-only contacts from decoded GIF frames, never render inputs."""
    if not indices or columns < 1 or not 0.0 < scale <= 1.0:
        raise AssertionError("Invalid Active Case Feed proof-sheet layout")
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
        preview = Image.fromarray(decoded_frames[frame_index], "RGB")
        if preview.size != (frame_width, frame_height):
            preview = preview.resize((frame_width, frame_height), Image.Resampling.LANCZOS)
        sheet.paste(preview, (x, y))
        draw.rectangle((x - 1, y - 1, x + frame_width, y + frame_height), outline=(125, 38, 34), width=1)
        label = labels.get(frame_index, f"frame_{frame_index:03d}")
        draw.text((x, y + frame_height + 3), label, fill=(185, 195, 205))
    sheet.save(path)
    reopened = Image.open(path).convert("RGB")
    if reopened.size != sheet.size or not np.array_equal(np.array(reopened), np.array(sheet)):
        raise AssertionError(f"Proof sheet verification failed: {path.name}")
    return sheet.size


def make_bar_replacement_proof(
    panels: Sequence[tuple[str, np.ndarray]],
    path: Path,
) -> tuple[int, int]:
    """Create a proof-only comparison of empty and freshly rendered graphs."""
    if len(panels) < 5:
        raise AssertionError("Bar-replacement proof needs all requested comparison panels")
    proof_x1, proof_y1, proof_x2, proof_y2 = local_bounds((45, 694, 435, 806))
    scale = 2
    crop_width = (proof_x2 - proof_x1) * scale
    crop_height = (proof_y2 - proof_y1) * scale
    columns = 2
    label_height = 20
    title_height = 24
    margin = 8
    rows = int(math.ceil(len(panels) / columns))
    width = margin + columns * crop_width + (columns - 1) * margin + margin
    height = title_height + rows * (crop_height + label_height) + (rows + 1) * margin
    sheet = Image.new("RGB", (width, height), (5, 8, 12))
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 5), "ACTIVE CASE FEED - BAR REPLACEMENT PROOF", fill=(220, 228, 235))
    for index, (label, panel) in enumerate(panels):
        if panel.shape != (PANEL_SIZE[1], PANEL_SIZE[0], 3):
            raise AssertionError("Bar-replacement proof received a non-panel image")
        row = index // columns
        column = index % columns
        x = margin + column * (crop_width + margin)
        y = title_height + margin + row * (crop_height + label_height + margin)
        crop = Image.fromarray(panel[proof_y1:proof_y2, proof_x1:proof_x2], "RGB").resize(
            (crop_width, crop_height),
            Image.Resampling.NEAREST,
        )
        sheet.paste(crop, (x, y))
        draw.rectangle((x - 1, y - 1, x + crop_width, y + crop_height), outline=(125, 38, 34), width=1)
        draw.text((x, y + crop_height + 3), label, fill=(185, 195, 205))
    sheet.save(path)
    reopened = Image.open(path).convert("RGB")
    if reopened.size != sheet.size or not np.array_equal(np.array(reopened), np.array(sheet)):
        raise AssertionError(f"Bar-replacement proof verification failed: {path.name}")
    return sheet.size


def main() -> None:
    frozen_before = snapshot_tree(FROZEN_ARCHIVE_ROOT)
    verify_frozen_working_scripts()
    master_hashes = {path: sha256_bytes(path.read_bytes()) for path in EXPECTED_MASTER_SHA256}
    for path, expected in EXPECTED_MASTER_SHA256.items():
        if master_hashes[path] != expected:
            raise AssertionError(f"Approved master changed: {path.name}")

    populated = Image.open(POPULATED_PATH).convert("RGB")
    clear = Image.open(CLEAR_PATH).convert("RGB")
    if populated.size != (1727, 911) or clear.size != (1727, 911):
        raise AssertionError("Approved master dimensions changed")
    populated_rgb = np.array(populated)
    clear_rgb = np.array(clear)
    px1, py1, px2, py2 = PANEL_BOUNDS
    source_panel = populated_rgb[py1:py2, px1:px2].copy()
    if source_panel.shape[:2] != (PANEL_SIZE[1], PANEL_SIZE[0]) or sha256_array(source_panel) != EXPECTED_PANEL_SHA256:
        raise AssertionError("Approved Active Case Feed panel pixels changed")

    (
        live_mask,
        severity_masks,
        row_activity_masks,
        bars,
        source_bar_tops,
        source_histogram_mask,
        bar_field_mask,
        graph_plate_mask,
        authorized_mask,
    ) = build_masks(source_panel)
    empty_graph_panel, registered_clear_graph = build_empty_graph_plate(
        source_panel,
        clear_rgb,
    )
    populated_bar_pixels_remaining_in_empty_graph_plate = int(np.count_nonzero(
        red_mask(empty_graph_panel, 100, 35) & source_histogram_mask
    ))
    if populated_bar_pixels_remaining_in_empty_graph_plate != 0:
        raise AssertionError("Populated histogram pixels remain in the empty graph plate")
    empty_graph_red_histogram_pixels = int(np.count_nonzero(
        red_mask(empty_graph_panel, 100, 35) & graph_plate_mask
    ))
    if empty_graph_red_histogram_pixels != 0:
        raise AssertionError("Empty graph plate still contains red histogram pixels")
    if not np.array_equal(empty_graph_panel[~graph_plate_mask], source_panel[~graph_plate_mask]):
        raise AssertionError("Empty graph plate changed pixels outside the approved graph region")

    seed_values = seed_values_from_source_tops(source_bar_tops)
    if not str(ACTIVE_CASE_FEED_PREVIEW["case_id"]):
        raise AssertionError("Preview case continuity requires a case_id")
    preview_events = {int(event["ordering"]): event for event in ACTIVE_CASE_FEED_PREVIEW["events"]}
    if any(str(event.get("case_id")) != str(ACTIVE_CASE_FEED_PREVIEW["case_id"]) for event in preview_events.values()):
        raise AssertionError("Preview events do not belong to the same active case")
    timeline = tuple(ACTIVE_CASE_FEED_PREVIEW["arrival_timeline"])
    if any(
        int(item["event_ordering"]) not in preview_events
        or not 0 <= int(item["row_index"]) < len(EVENT_SEVERITY_ROIS_GLOBAL)
        or not 0 <= int(item["telemetry_center"]) < len(bars)
        or not 0 <= int(item["start_frame"]) < int(item["end_frame"]) < FRAME_COUNT
        for item in timeline
    ):
        raise AssertionError("Preview event timeline is not a valid controlled case sequence")

    raw_frames: list[np.ndarray] = []
    telemetry_values_by_frame: list[np.ndarray] = []
    dynamic_tops_by_frame: list[list[int]] = []
    dynamic_heights_by_frame: list[list[int]] = []
    for index in range(FRAME_COUNT):
        values, event, strength, progress = telemetry_values_for_frame(
            ACTIVE_CASE_FEED_PREVIEW,
            index,
            seed_values,
        )
        frame, tops, heights = render_frame(
            empty_graph_panel,
            source_panel,
            live_mask,
            severity_masks,
            row_activity_masks,
            bars,
            values,
            event,
            strength,
            progress,
            index,
        )
        raw_frames.append(frame)
        telemetry_values_by_frame.append(values)
        dynamic_tops_by_frame.append(tops)
        dynamic_heights_by_frame.append(heights)

    closure_values, closure_event, closure_strength, closure_progress = telemetry_values_for_frame(
        ACTIVE_CASE_FEED_PREVIEW,
        FRAME_COUNT,
        seed_values,
    )
    closure, closure_tops, closure_heights = render_frame(
        empty_graph_panel,
        source_panel,
        live_mask,
        severity_masks,
        row_activity_masks,
        bars,
        closure_values,
        closure_event,
        closure_strength,
        closure_progress,
        FRAME_COUNT,
    )
    if (
        not np.array_equal(closure_values, telemetry_values_by_frame[0])
        or closure_tops != dynamic_tops_by_frame[0]
        or closure_heights != dynamic_heights_by_frame[0]
        or not np.array_equal(closure, raw_frames[0])
    ):
        raise AssertionError("Active Case Feed preview does not close at its controlled sequence start")

    frame_masks: list[np.ndarray] = []
    for index in range(FRAME_COUNT):
        event, _, _ = event_activity(ACTIVE_CASE_FEED_PREVIEW, index)
        frame_mask = live_mask | graph_plate_mask
        if event is not None:
            row_index = int(event["row_index"])
            frame_mask |= severity_masks[row_index] | row_activity_masks[row_index]
        frame_masks.append(frame_mask)
    if not all(np.array_equal(frame[~mask], source_panel[~mask]) for frame, mask in zip(raw_frames, frame_masks)):
        raise AssertionError("Raw Active Case Feed frame changed pixels outside its current event mask")
    if not all(np.array_equal(frame[~authorized_mask], source_panel[~authorized_mask]) for frame in raw_frames):
        raise AssertionError("Raw Active Case Feed frame changed pixels outside authorized masks")

    # Full-width telemetry proof: every approved column is freshly rendered
    # from a data value, reaches NOW, and remains inside the fixed graph field.
    bar_field_masks: list[np.ndarray] = []
    _, graph_y1, _, graph_y2 = local_bounds(GRAPH_ANIMATION_ENVELOPE_GLOBAL)
    for xa, xb in bars:
        mask = np.zeros(source_panel.shape[:2], dtype=bool)
        mask[graph_y1:graph_y2, xa - PANEL_BOUNDS[0]:xb - PANEL_BOUNDS[0] + 1] = True
        bar_field_masks.append(mask)
    graph_differences = [np.any(frame != empty_graph_panel, axis=2) & bar_field_mask for frame in raw_frames]
    animated_bar_counts = [sum(bool(np.any(difference & mask)) for mask in bar_field_masks) for difference in graph_differences]
    if min(animated_bar_counts) != len(bars):
        raise AssertionError("Full telemetry does not animate every approved bar position")
    graph_changed_union = np.logical_or.reduce(graph_differences)
    changed_y, changed_x = np.where(graph_changed_union)
    graph_changed_span_global = (
        int(np.min(changed_x)) + PANEL_BOUNDS[0],
        int(np.min(changed_y)) + PANEL_BOUNDS[1],
        int(np.max(changed_x)) + PANEL_BOUNDS[0],
        int(np.max(changed_y)) + PANEL_BOUNDS[1],
    )
    if (
        graph_changed_span_global[0] != bars[0][0]
        or graph_changed_span_global[2] != bars[-1][1]
        or graph_changed_span_global[1] < GRAPH_INTERIOR_GLOBAL[1]
        or graph_changed_span_global[3] >= GRAPH_INTERIOR_GLOBAL[3]
        or not all(np.any(difference & bar_field_masks[-1]) for difference in graph_differences)
    ):
        raise AssertionError("Full telemetry span, NOW coverage, or graph containment failed")
    graph_sequence_hashes = {sha256_array(frame[bar_field_mask]) for frame in raw_frames}
    if len(graph_sequence_hashes) < FRAME_COUNT - 1:
        raise AssertionError("Full telemetry graph did not produce genuinely evolving frames")

    telemetry_matrix = np.vstack(telemetry_values_by_frame)
    height_matrix = np.asarray(dynamic_heights_by_frame, dtype=np.int16)
    height_loop = np.vstack((height_matrix, np.asarray(closure_heights, dtype=np.int16)))
    max_telemetry_step = int(np.max(np.abs(np.diff(height_loop, axis=0))))
    if max_telemetry_step > 2:
        raise AssertionError("Telemetry bar heights change too abruptly between preview frames")
    temporal_bar_positions = int(np.count_nonzero(np.ptp(height_matrix, axis=0) > 0))
    if temporal_bar_positions < len(bars) - 1:
        raise AssertionError("Too few complete bar heights evolve across the loop")
    regional_change_counts = {
        "historical": int(np.count_nonzero(np.ptp(height_matrix[:, :13], axis=0) > 0)),
        "middle": int(np.count_nonzero(np.ptp(height_matrix[:, 13:26], axis=0) > 0)),
        "recent": int(np.count_nonzero(np.ptp(height_matrix[:, 26:], axis=0) > 0)),
    }
    if any(count == 0 for count in regional_change_counts.values()):
        raise AssertionError("Historical, middle, and recent telemetry must all evolve")

    ghost_bar_pixels = 0
    disconnected_or_floating_bar_segments = 0
    for frame, tops, heights in zip(raw_frames, dynamic_tops_by_frame, dynamic_heights_by_frame):
        ghosts, disconnected = verify_histogram_frame(frame, empty_graph_panel, bars, tops, heights)
        ghost_bar_pixels += ghosts
        disconnected_or_floating_bar_segments += disconnected
    if ghost_bar_pixels != 0 or disconnected_or_floating_bar_segments != 0:
        raise AssertionError("Fresh histogram ghost-bar or continuity QC failed")

    # Proof-only low values deliberately shorten every meaningful source peak.
    # They are never encoded into the animation; this one still proves that a
    # shorter data value clears the tall populated raster beneath it.
    lower_values = np.clip(0.18 * seed_values + 4.0, 5.0, 14.0)
    lower_value_frame = empty_graph_panel.copy()
    lower_tops, lower_heights = render_histogram(lower_value_frame, lower_values, bars)
    lower_ghosts, lower_disconnected = verify_histogram_frame(
        lower_value_frame,
        empty_graph_panel,
        bars,
        lower_tops,
        lower_heights,
    )
    source_heights = np.asarray(
        [EXPECTED_GRAPH_BASELINE - top + 1 for top in source_bar_tops],
        dtype=np.int16,
    )
    lower_heights_array = np.asarray(lower_heights, dtype=np.int16)
    significant_source_peaks = source_heights >= 20
    if (
        lower_ghosts != 0
        or lower_disconnected != 0
        or not np.any(significant_source_peaks)
        or not np.all(lower_heights_array[significant_source_peaks] < source_heights[significant_source_peaks])
    ):
        raise AssertionError("Lower-value proof does not clear the populated source peaks")

    master_mask = np.zeros(populated_rgb.shape[:2], dtype=bool)
    master_mask[py1:py2, px1:px2] = authorized_mask
    for frame in raw_frames:
        full_frame = populated_rgb.copy()
        full_frame[py1:py2, px1:px2] = frame
        if not np.array_equal(full_frame[~master_mask], populated_rgb[~master_mask]):
            raise AssertionError("A full source frame changed pixels outside Active Case Feed masks")

    representative_indices = tuple(sorted(set((*KEYFRAME_INDICES, 6, 10, 22, 28, 32, 40, 45, 51, 54))))
    palette_source = Image.new("RGB", (PANEL_SIZE[0], PANEL_SIZE[1] * (len(representative_indices) + 1)))
    palette_source.paste(Image.fromarray(empty_graph_panel, "RGB"), (0, 0))
    for row, index in enumerate(representative_indices, start=1):
        palette_source.paste(Image.fromarray(raw_frames[index], "RGB"), (0, row * PANEL_SIZE[1]))
    palette = palette_source.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette_bytes = bytes(palette.getpalette() or [])
    if len(palette_bytes) != 768:
        raise AssertionError("Active Case Feed palette is not 256 colors")
    encoded_frames = [Image.fromarray(frame, "RGB").quantize(palette=palette, dither=Image.Dither.NONE) for frame in raw_frames]
    encoded_empty_graph_panel = Image.fromarray(empty_graph_panel, "RGB").quantize(palette=palette, dither=Image.Dither.NONE)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reference_path = OUT_DIR / "active_case_feed_static_reference.png"
    gif_path = OUT_DIR / "active_case_feed_preview_6s.gif"
    staging_path = OUT_DIR / ".active_case_feed_preview_6s.staging.gif"
    Image.fromarray(source_panel, "RGB").save(reference_path)
    encoded_frames[0].save(
        staging_path,
        format="GIF",
        save_all=True,
        append_images=encoded_frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=False,
        # Full-canvas overwrite frames prevent renderer-specific delta-frame
        # disposal artifacts in an otherwise fixed panel.
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
        for index in range(gif.n_frames):
            gif.seek(index)
            durations.append(int(gif.info.get("duration", 0)))
            disposals.append(int(getattr(gif, "disposal_method", 0)))
            decoded_frames.append(np.array(gif.convert("RGB")))

    logical_size, descriptors, encoded_palette = parse_gif(staging_path)
    if (
        gif_format != "GIF" or gif_size != PANEL_SIZE or logical_size != PANEL_SIZE
        or gif_count != FRAME_COUNT or len(descriptors) != FRAME_COUNT
        or gif_loop != 0 or set(durations) != {FRAME_DURATION_MS}
        or sum(durations) != FRAME_COUNT * FRAME_DURATION_MS or set(disposals) != {2}
    ):
        raise AssertionError("Active Case Feed GIF metadata validation failed")
    if any(descriptor[4] or descriptor[5] or descriptor[6] != 2 or descriptor[7] != FRAME_DURATION_MS // 10 or descriptor[8] for descriptor in descriptors):
        raise AssertionError("Active Case Feed GIF palette/interlace/disposal/transparency failed")
    if encoded_palette != palette_bytes:
        raise AssertionError("Active Case Feed GIF global palette changed")
    expected_decoded = [np.array(frame.convert("RGB")) for frame in encoded_frames]
    decoded_empty_graph_panel = np.array(encoded_empty_graph_panel.convert("RGB"))
    if not all(np.array_equal(actual, expected) for actual, expected in zip(decoded_frames, expected_decoded)):
        raise AssertionError("Decoded GIF differs from the intended quantized frames")
    if not all(not np.array_equal(decoded_frames[index], decoded_frames[index - 1]) for index in range(1, FRAME_COUNT)):
        raise AssertionError("Active Case Feed GIF contains adjacent duplicate frames")
    if len({sha256_array(frame) for frame in decoded_frames}) < FRAME_COUNT - 2:
        raise AssertionError("Active Case Feed GIF encoded too few distinct activity frames")
    if not all(np.array_equal(frame[~authorized_mask], decoded_frames[0][~authorized_mask]) for frame in decoded_frames[1:]):
        raise AssertionError("Decoded GIF shimmered outside Active Case Feed masks")
    decoded_ghost_bar_pixels = sum(
        ghost_pixels_above_tops(frame, decoded_empty_graph_panel, bars, tops)
        for frame, tops in zip(decoded_frames, dynamic_tops_by_frame)
    )
    if decoded_ghost_bar_pixels != 0:
        raise AssertionError("Decoded GIF contains pixels above dynamic bar tops that differ from the clear plate")
    decoded_disconnected_or_floating_bar_segments = sum(
        nonred_pixels_inside_bar_bodies(frame, bars, tops, heights)
        for frame, tops, heights in zip(decoded_frames, dynamic_tops_by_frame, dynamic_heights_by_frame)
    )
    if decoded_disconnected_or_floating_bar_segments != 0:
        raise AssertionError("Decoded GIF contains disconnected or floating bar body pixels")
    for index, descriptor in enumerate(descriptors):
        left, top, width, height = descriptor[:4]
        rectangle = (left, top, left + width, top + height)
        if rectangle != (0, 0, PANEL_SIZE[0], PANEL_SIZE[1]):
            raise AssertionError(f"Active Case Feed GIF frame {index} is not a full canvas")
    staging_path.replace(gif_path)
    # Fixed full canvases trade a small amount of compression for portable,
    # deterministic playback.  Four MiB remains compact for a 438x266, 6 s
    # isolated preview without restoring unsafe delta-frame behavior.
    if gif_path.stat().st_size > 4 * 1024 * 1024:
        raise AssertionError(f"Active Case Feed GIF is not lightweight: {gif_path.stat().st_size} bytes")

    keyframe_paths: list[Path] = []
    for index in KEYFRAME_INDICES:
        path = OUT_DIR / f"active_case_feed_{KEYFRAME_LABELS[index]}.png"
        Image.fromarray(decoded_frames[index], "RGB").save(path)
        if not np.array_equal(np.array(Image.open(path).convert("RGB")), decoded_frames[index]):
            raise AssertionError(f"Keyframe PNG differs from decoded GIF frame {index}")
        keyframe_paths.append(path)

    empty_graph_proof_path = OUT_DIR / "active_case_feed_empty_graph_proof.png"
    Image.fromarray(empty_graph_panel, "RGB").save(empty_graph_proof_path)
    if not np.array_equal(np.array(Image.open(empty_graph_proof_path).convert("RGB")), empty_graph_panel):
        raise AssertionError("Empty graph proof differs from the clear-derived working plate")
    if np.any(red_mask(np.array(Image.open(empty_graph_proof_path).convert("RGB")), 100, 35) & bar_field_mask):
        raise AssertionError("Empty graph proof unexpectedly contains red histogram pixels")

    bar_replacement_proof_path = OUT_DIR / "active_case_feed_bar_replacement_proof.png"
    bar_replacement_proof_size = make_bar_replacement_proof(
        (
            ("1 populated source / baked bars", source_panel),
            ("2 empty clear-derived graph plate", empty_graph_panel),
            ("3 frame 000 / fresh data bars", decoded_frames[0]),
            ("4 deliberately lower values / no ghosts", lower_value_frame),
            ("5 frame 045 / high recent response", decoded_frames[45]),
            ("6 frame 059 / loop final", decoded_frames[59]),
        ),
        bar_replacement_proof_path,
    )

    keyframe_proof_labels = {
        0: "F000  0.0s  early / settled",
        10: "F010  1.0s  event arrival",
        28: "F028  2.8s  middle loop",
        45: "F045  4.5s  high / recent response",
        59: "F059  5.9s  final / loop settle",
    }
    motion_audit_labels = {
        index: f"F{index:03d}  {index * FRAME_DURATION_MS / 1000.0:.1f}s"
        for index in MOTION_AUDIT_INDICES
    }
    keyframe_sheet_path = OUT_DIR / "active_case_feed_keyframe_contact_sheet.png"
    motion_audit_path = OUT_DIR / "active_case_feed_motion_audit_12frames.png"
    keyframe_sheet_size = make_preview_sheet(
        decoded_frames,
        KEYFRAME_INDICES,
        keyframe_proof_labels,
        "ACTIVE CASE FEED - DECODED GIF KEYFRAMES",
        columns=3,
        scale=0.65,
        path=keyframe_sheet_path,
    )
    motion_audit_sheet_size = make_preview_sheet(
        decoded_frames,
        MOTION_AUDIT_INDICES,
        motion_audit_labels,
        "ACTIVE CASE FEED - 12-FRAME MOTION AUDIT",
        columns=4,
        scale=0.50,
        path=motion_audit_path,
    )

    qc_path = OUT_DIR / "active_case_feed_qc.txt"
    output_names = {
        reference_path.name,
        gif_path.name,
        qc_path.name,
        empty_graph_proof_path.name,
        bar_replacement_proof_path.name,
        keyframe_sheet_path.name,
        motion_audit_path.name,
        *(path.name for path in keyframe_paths),
    }
    if not {path.name for path in OUT_DIR.iterdir() if path.is_file()} <= output_names:
        raise AssertionError("Unexpected Active Case Feed output manifest")
    frozen_after = snapshot_tree(FROZEN_ARCHIVE_ROOT)
    if frozen_after != frozen_before:
        raise AssertionError("A frozen approved subsystem changed during Active Case Feed rendering")
    verify_frozen_working_scripts()
    for path, expected in EXPECTED_MASTER_SHA256.items():
        if sha256_bytes(path.read_bytes()) != expected:
            raise AssertionError(f"Approved master changed during render: {path.name}")

    qc_lines = (
        "Subsystem #4 Active Case Feed isolated QC",
        f"script_used={SCRIPT_NAME}",
        f"workspace_root={ROOT}",
        f"output_directory={OUT_DIR}",
        f"approved_populated_master={POPULATED_PATH.name} role=static panel geometry/style plus numeric seed extraction only; no populated histogram raster retained sha256={master_hashes[POPULATED_PATH]}",
        f"approved_clear_master={CLEAR_PATH.name} role=bar-free graph foundation composited into the same-coordinate empty graph plate each frame sha256={master_hashes[CLEAR_PATH]}",
        f"biohazard_reference={BIOHAZARD_REFERENCE_PATH.name} role=hash-verified frozen reference only; not read into Subsystem_04 rendering sha256={master_hashes[BIOHAZARD_REFERENCE_PATH]}",
        f"graph_base_source={CLEAR_PATH.name} clear_graph_source_bounds_global={CLEAR_GRAPH_SOURCE_BOUNDS_GLOBAL} target_graph_bounds_global={GRAPH_PLATE_GLOBAL} registered_clear_graph_sha256={sha256_array(registered_clear_graph)}",
        "populated_histogram_used_as_background=False",
        "all_39_bars_rendered_fresh_from_data_each_frame=True",
        f"populated_bar_pixels_remaining_in_empty_graph_plate={populated_bar_pixels_remaining_in_empty_graph_plate} empty_graph_red_histogram_pixels={empty_graph_red_histogram_pixels}",
        f"ghost_bar_pixels_above_dynamic_tops={ghost_bar_pixels} decoded_ghost_bar_pixels_above_dynamic_tops={decoded_ghost_bar_pixels}",
        f"disconnected_or_floating_bar_segments={disconnected_or_floating_bar_segments} decoded_disconnected_or_floating_bar_segments={decoded_disconnected_or_floating_bar_segments}",
        "preview_data_variable=ACTIVE_CASE_FEED_PREVIEW",
        f"preview_case_id={ACTIVE_CASE_FEED_PREVIEW['case_id']} preview_event_count={len(ACTIVE_CASE_FEED_PREVIEW['events'])} same_case_id_across_preview_events=True deterministic=True random_generation=False",
        f"controlled_arrival_timeline={tuple((item['event_ordering'], item['row_index'], item['start_frame'], item['end_frame'], item['telemetry_center']) for item in timeline)} active_events_per_frame_max=1",
        f"panel_bounds_global={PANEL_BOUNDS} dimensions={PANEL_SIZE[0]}x{PANEL_SIZE[1]}",
        f"live_indicator_mask_global={EXPECTED_LIVE_MASK_BBOX} pixels={int(np.count_nonzero(live_mask))}",
        f"event_activity_regions_global=severity_rois:{EVENT_SEVERITY_ROIS_GLOBAL}; row_scans:{EVENT_ROW_ACTIVITY_BOUNDS_GLOBAL}",
        f"graph_interior_global={GRAPH_INTERIOR_GLOBAL} graph_animation_bounds_global={GRAPH_ANIMATION_ENVELOPE_GLOBAL} fresh_bar_positions={len(bars)}/{len(bars)} animated_x_span={bars[0][0]}..{bars[-1][1]} baseline={EXPECTED_GRAPH_BASELINE} full_height={GRAPH_BAR_HEIGHT}",
        f"full_width_telemetry=True per_frame_rendered_bar_positions={min(animated_bar_counts)}..{max(animated_bar_counts)}/{len(bars)} temporal_bar_heights={temporal_bar_positions}/{len(bars)} regional_height_changes={regional_change_counts} changed_graph_span_global={graph_changed_span_global} rightmost_NOW_bar_changed=True graph_unique_raw_states={len(graph_sequence_hashes)}/{FRAME_COUNT} max_height_step={max_telemetry_step}px seam_closed=True",
        f"telemetry_data_function=telemetry_values_for_frame histogram_renderer=render_histogram telemetry_snapshots={len(ACTIVE_CASE_FEED_PREVIEW['telemetry_snapshots'])} value_range={float(np.min(telemetry_matrix)):.3f}..{float(np.max(telemetry_matrix)):.3f} spatially_correlated=True generic_sine_histogram=False event_gaussian_mapping=True",
        f"authorized_animation_pixels={int(np.count_nonzero(authorized_mask))} frame_specific_masking=True outside_mask_raw_pixel_differences=0 outside_mask_decoded_temporal_differences=0",
        f"frame_count={FRAME_COUNT} duration_per_frame={FRAME_DURATION_MS}ms total_duration={FRAME_COUNT * FRAME_DURATION_MS}ms loop=0",
        f"gif_real=True format=GIF multiple_frames=True decoded_unique_frames={len({sha256_array(frame) for frame in decoded_frames})}/{FRAME_COUNT} full_canvas_frames_verified={FRAME_COUNT}/{FRAME_COUNT} disposal=2 size_bytes={gif_path.stat().st_size}",
        f"empty_graph_proof={empty_graph_proof_path.name} zero_red_histogram_bars=True bar_replacement_proof={bar_replacement_proof_path.name} dimensions={bar_replacement_proof_size[0]}x{bar_replacement_proof_size[1]} lower_value_test_max={float(np.max(lower_values)):.3f}",
        f"decoded_keyframes={tuple(KEYFRAME_INDICES)} files={tuple(path.name for path in keyframe_paths)} contact_sheet={keyframe_sheet_path.name} dimensions={keyframe_sheet_size[0]}x{keyframe_sheet_size[1]}",
        f"motion_audit_indices={MOTION_AUDIT_INDICES} file={motion_audit_path.name} dimensions={motion_audit_sheet_size[0]}x{motion_audit_sheet_size[1]}",
        "live_repository_api_database_network_logic_added=False final_data_integration=False",
        "feed_rows_heading_axes_labels_grid_panel_border_fixed=True graph_scale_fixed=True no_scroll_or_coordinate_drift=True no_overflow_outside_panel=True",
        "frozen_subsystems_01_to_03_unchanged=True frozen_working_scripts_match_archives=True approved_png_masters_unchanged=True",
        "limitation=deterministic preview-only activity; persistent active-case data integration is intentionally deferred",
    )
    qc_path.write_text("\n".join(qc_lines) + "\n", encoding="utf-8")
    if {path.name for path in OUT_DIR.iterdir() if path.is_file()} != output_names:
        raise AssertionError("Active Case Feed output manifest changed after QC write")

    print(f"static reference: {reference_path}")
    print(f"GIF preview: {gif_path}")
    print("keyframes: " + ", ".join(str(path) for path in keyframe_paths))
    print(f"empty graph proof: {empty_graph_proof_path}")
    print(f"bar replacement proof: {bar_replacement_proof_path}")
    print(f"keyframe contact sheet: {keyframe_sheet_path}")
    print(f"motion audit sheet: {motion_audit_path}")
    print(f"QC note: {qc_path}")
    print(f"GIF size: {gif_path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
