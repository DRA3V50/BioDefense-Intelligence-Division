#!/usr/bin/env python3
"""Animate the approved #7 Proposal B central-hub Case Overview in isolation.

The approved central-hub PNG is the only visual base.  Each of the sixty
frames starts from that exact raster and receives fresh, strictly local
overlays.  No static geometry is regenerated, moved, or repainted here.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_NAME = SCRIPT_PATH.name

SOURCE_PNG = ROOT / "case_overview_proposal_b_central_hub_output" / "case_overview_proposal_b_central_hub_static_reference.png"
STATIC_RENDERER = ROOT / "case_overview_proposal_b_central_hub.py"
STATIC_OUTPUT_DIR = SOURCE_PNG.parent
OUT_DIR = ROOT / "case_overview_proposal_b_central_hub_animation_output"

POPULATED_PATH = ROOT / "APPROVED_POPULATED_LAYOUT.png"
CLEAR_PATH = ROOT / "APPROVED_CLEAR_BASE_LAYOUT.png"
BIOHAZARD_REFERENCE_PATH = ROOT / "BIOHAZARD_REFERENCE.png"
GENERATE_CASE_BANNER_PATH = ROOT / "generate_case_banner.py"

EXPECTED_SOURCE_SHA256 = "6fb176d5777ba79dfcf0d3984188757d9961db413cda1bb6e47a018f73486aab"
EXPECTED_STATIC_RENDERER_SHA256 = "a824a166d2e298c022b20363ee3229d8c510ed079df919af939c7006a9202a48"
EXPECTED_MASTER_SHA256 = {
    POPULATED_PATH: "90a223d08555853fd58c7bc7c0c30eadecfa7df3b5320db23e373462735312c4",
    CLEAR_PATH: "168d5b6ba745de5431f8fbaa9c5d5e4a95464b9e150f6aa23b862e4800d68f38",
    BIOHAZARD_REFERENCE_PATH: "ec0eb4cd38db13d34c0259f8ba920e4d9a1d2783feeb2f0d25e4ea2b0bf52ba5",
}
EXPECTED_GENERATE_CASE_BANNER_SHA256 = "7f55235c485f3f3a3c7eeddd66aa8aece965979cc2ebccf9047a00b4fd51213a"

PANEL_SIZE = (451, 272)
PANEL_BOUNDS_GLOBAL = (1269, 273, 1720, 545)
FRAME_COUNT = 60
FRAME_DURATION_MS = 100
KEYFRAME_INDICES = (0, 8, 16, 24, 32, 40, 48, 56)
MOTION_AUDIT_INDICES = (0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55)
DRAW_SCALE = 4
PACKET_CENTER_CLEARANCE = 11
# The rendered packet core is still <= 3 px from the approved polyline.  This
# 5 px audit tube includes one anti-aliased downsample fringe while retaining
# at least 6 px clearance from every module/hub/arrowhead.
PACKET_TUBE_RADIUS = 5


@dataclass(frozen=True)
class RouteSpec:
    key: str
    source: str
    destination: str
    points: tuple[tuple[int, int], ...]
    color: tuple[int, int, int]
    start: int
    duration: int


# These exact local polylines and directions are the approved Proposal B
# geometry.  They are never recomputed from card bounds or altered per frame.
ROUTES = (
    RouteSpec("evidence_to_case", "EVIDENCE", "ACTIVE CASE FILE", ((115, 75), (205, 75), (205, 97)), (255, 92, 66), 56, 18),
    RouteSpec("access_to_case", "ACCESS LOGS", "ACTIVE CASE FILE", ((115, 145), (169, 145)), (244, 171, 86), 7, 18),
    RouteSpec("timeline_to_case", "TIMELINE", "ACTIVE CASE FILE", ((115, 215), (205, 215), (205, 193)), (250, 72, 56), 16, 18),
    RouteSpec("case_to_intelligence", "ACTIVE CASE FILE", "INTELLIGENCE", ((246, 100), (246, 75), (333, 75)), (93, 177, 222), 26, 18),
    RouteSpec("case_to_correlation", "ACTIVE CASE FILE", "CORRELATION", ((279, 145), (333, 145)), (255, 105, 70), 37, 18),
    RouteSpec("case_to_datastore", "ACTIVE CASE FILE", "CASE DATA STORE", ((246, 190), (246, 215), (333, 215)), (102, 220, 143), 46, 18),
)
ROUTE_BY_KEY = {route.key: route for route in ROUTES}

# Exact approved static module/hub bounds.  These form protected geometry;
# only the separate small source-graphic response masks can change inside them.
MODULE_BOUNDS = {
    "evidence": (15, 53, 115, 97),
    "access": (15, 123, 115, 167),
    "timeline": (15, 193, 115, 237),
    "intelligence": (336, 53, 436, 97),
    "correlation": (336, 123, 436, 167),
    "datastore": (336, 193, 436, 237),
}
HUB_BOUNDS = (172, 100, 279, 190)
ARROWHEAD_BOUNDS = {
    "evidence_to_case": (202, 92, 209, 98),
    "access_to_case": (164, 142, 170, 149),
    "timeline_to_case": (202, 193, 209, 199),
    "case_to_intelligence": (328, 72, 334, 79),
    "case_to_correlation": (328, 142, 334, 149),
    "case_to_datastore": (328, 212, 334, 219),
}

# Every local response zone is deliberately clear of text and borders.  The
# datastore_fill mask is a cylinder-only scan/fill, never a text redraw.
COMPONENT_BOUNDS = {
    "evidence_document": (88, 69, 106, 90),
    "access_key": (87, 142, 110, 158),
    "timeline_waveform": (19, 222, 111, 234),
    "intelligence_bars": (397, 70, 431, 90),
    "correlation_graph": (397, 138, 431, 163),
    "datastore_cylinder": (405, 208, 429, 233),
    "datastore_fill": (411, 215, 424, 226),
    "hub_rail": (177, 107, 184, 184),
    "hub_verified_led": (268, 108, 277, 117),
    "hub_signature": (186, 173, 246, 184),
    "evidence_indicator": (19, 56, 40, 59),
    "access_indicator": (19, 126, 40, 129),
    "timeline_indicator": (19, 196, 40, 199),
    "intelligence_indicator": (340, 56, 361, 59),
    "correlation_indicator": (340, 126, 361, 129),
    "datastore_indicator": (340, 196, 361, 199),
}

# A deterministic one-case preview contract.  It is intentionally not live
# data; later integration must provide this same active case's persisted data.
CASE_OVERVIEW_ANIMATION_PREVIEW = {
    "case_id": "BID-2026-9147",
    "current_stage": "VALIDATION",
    "relationship_sequence": tuple(route.key for route in ROUTES),
}

FROZEN_ARCHIVE_ROOT = ROOT / "approved_subsystems"
FROZEN_ARCHIVE_NAMES = (
    "subsystem_01_biohazard_APPROVED",
    "subsystem_02_evidence_magnifier_APPROVED",
    "approved_subsystem_03_workflow",
    "approved_subsystem_04_active_case_feed",
    "approved_subsystem_05_system_status",
    "approved_subsystem_06_threat_monitor",
)
FROZEN_WORKING_SCRIPT_ARCHIVES = {
    ROOT / "biohazard_test.py": FROZEN_ARCHIVE_ROOT / "subsystem_01_biohazard_APPROVED" / "biohazard_test.py",
    ROOT / "magnifying_glass_test.py": FROZEN_ARCHIVE_ROOT / "subsystem_02_evidence_magnifier_APPROVED" / "magnifying_glass_test.py",
    ROOT / "workflow_strip_test.py": FROZEN_ARCHIVE_ROOT / "approved_subsystem_03_workflow" / "workflow_strip_test.py",
    ROOT / "active_case_feed_test.py": FROZEN_ARCHIVE_ROOT / "approved_subsystem_04_active_case_feed" / "active_case_feed_test.py",
    ROOT / "system_status_test.py": FROZEN_ARCHIVE_ROOT / "approved_subsystem_05_system_status" / "system_status_test.py",
    ROOT / "threat_monitor_test.py": FROZEN_ARCHIVE_ROOT / "approved_subsystem_06_threat_monitor" / "threat_monitor_test.py",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_array(array: np.ndarray) -> str:
    return sha256_bytes(np.ascontiguousarray(array).tobytes())


def snapshot_tree(directory: Path) -> dict[str, str]:
    if not directory.is_dir():
        raise AssertionError(f"Missing directory: {directory}")
    return {
        str(path.relative_to(ROOT)): sha256_path(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def snapshot_file_or_tree(path: Path) -> dict[str, str]:
    if path.is_file():
        return {str(path.relative_to(ROOT)): sha256_path(path)}
    if path.is_dir():
        return snapshot_tree(path)
    raise AssertionError(f"Missing preserved reference: {path}")


def assert_unchanged(before: dict[str, str], after: dict[str, str], label: str) -> None:
    if before != after:
        changed = sorted(set(before).symmetric_difference(after))
        changed.extend(key for key in sorted(set(before).intersection(after)) if before[key] != after[key])
        raise AssertionError(f"{label} changed unexpectedly: {', '.join(changed[:8])}")


def parse_manifest(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise AssertionError(f"Missing frozen manifest: {path}")
    records: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        digest, name = line.split("  ", 1)
        if len(digest) != 64 or not name or name in records:
            raise AssertionError(f"Invalid frozen manifest: {path.name}")
        records[name] = digest
    if not records:
        raise AssertionError(f"Frozen manifest is empty: {path.name}")
    return records


def verify_frozen_archives() -> dict[str, int]:
    counts: dict[str, int] = {}
    for archive_name in FROZEN_ARCHIVE_NAMES:
        archive = FROZEN_ARCHIVE_ROOT / archive_name
        manifest = parse_manifest(archive / "SHA256SUMS.txt")
        for filename, digest in manifest.items():
            payload = archive / filename
            if not payload.is_file() or sha256_path(payload) != digest:
                raise AssertionError(f"Frozen archive mismatch: {archive_name}/{filename}")
        counts[archive_name] = len(manifest)
    return counts


def verify_frozen_working_scripts() -> None:
    for working, archived in FROZEN_WORKING_SCRIPT_ARCHIVES.items():
        if not working.is_file() or not archived.is_file() or sha256_path(working) != sha256_path(archived):
            raise AssertionError(f"Frozen working script changed: {working.name}")


@lru_cache(maxsize=None)
def proof_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        "C:/Windows/Fonts/bahnschrift.ttf" if bold else "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def rect_mask(bounds: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = bounds
    if x1 < 0 or y1 < 0 or x2 > PANEL_SIZE[0] or y2 > PANEL_SIZE[1] or x1 >= x2 or y1 >= y2:
        raise AssertionError(f"Invalid local bounds: {bounds}")
    mask = np.zeros((PANEL_SIZE[1], PANEL_SIZE[0]), dtype=bool)
    mask[y1:y2, x1:x2] = True
    return mask


def rasterize_orthogonal_polyline(points: Sequence[tuple[int, int]]) -> np.ndarray:
    result: list[tuple[int, int]] = []
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if x1 != x2 and y1 != y2:
            raise AssertionError("Approved route geometry must remain orthogonal")
        if x1 == x2:
            step = 1 if y2 >= y1 else -1
            segment = [(x1, y) for y in range(y1, y2 + step, step)]
        else:
            step = 1 if x2 >= x1 else -1
            segment = [(x, y1) for x in range(x1, x2 + step, step)]
        result.extend(segment[1:] if result else segment)
    array = np.asarray(result, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise AssertionError("Invalid route rasterization")
    return array


def rounded_dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    expanded = np.zeros_like(mask)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy > radius * radius:
                continue
            source_y1, source_y2 = max(0, -dy), min(mask.shape[0], mask.shape[0] - dy)
            source_x1, source_x2 = max(0, -dx), min(mask.shape[1], mask.shape[1] - dx)
            target_y1, target_y2 = max(0, dy), min(mask.shape[0], mask.shape[0] + dy)
            target_x1, target_x2 = max(0, dx), min(mask.shape[1], mask.shape[1] + dx)
            expanded[target_y1:target_y2, target_x1:target_x2] |= mask[source_y1:source_y2, source_x1:source_x2]
    return expanded


def source_pixels(source: np.ndarray, bounds: tuple[int, int, int, int], mode: str = "bright") -> np.ndarray:
    region = rect_mask(bounds)
    red = source[:, :, 0].astype(np.int16)
    green = source[:, :, 1].astype(np.int16)
    blue = source[:, :, 2].astype(np.int16)
    if mode == "red":
        keep = (red >= 48) & (red > green + 22) & (red > blue + 22)
    elif mode == "green":
        keep = (green >= 48) & (green > red + 14) & (green > blue + 10)
    elif mode == "blue":
        keep = (blue >= 55) & (blue > red + 16) & (green > red + 6)
    elif mode == "bright":
        keep = np.maximum(np.maximum(red, green), blue) >= 78
    else:
        raise AssertionError(f"Unknown source-pixel mode: {mode}")
    return region & keep


def build_masks(source: np.ndarray) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    route_masks: dict[str, np.ndarray] = {}
    route_paths: dict[str, np.ndarray] = {}
    all_module_mask = np.zeros((PANEL_SIZE[1], PANEL_SIZE[0]), dtype=bool)
    for bounds in (*MODULE_BOUNDS.values(), HUB_BOUNDS):
        all_module_mask |= rect_mask(bounds)
    for route in ROUTES:
        full_path = rasterize_orthogonal_polyline(route.points)
        if len(full_path) <= PACKET_CENTER_CLEARANCE * 2:
            raise AssertionError(f"Approved route is too short for safe packet travel: {route.key}")
        safe_path = full_path[PACKET_CENTER_CLEARANCE:-PACKET_CENTER_CLEARANCE]
        center_mask = np.zeros((PANEL_SIZE[1], PANEL_SIZE[0]), dtype=bool)
        center_mask[safe_path[:, 1].astype(int), safe_path[:, 0].astype(int)] = True
        tube = rounded_dilate(center_mask, PACKET_TUBE_RADIUS)
        if np.any(tube & all_module_mask):
            raise AssertionError(f"Packet corridor touches approved card/hub geometry: {route.key}")
        route_masks[route.key] = tube
        route_paths[route.key] = safe_path
    if sum(np.any(first & second) for index, first in enumerate(route_masks.values()) for second in list(route_masks.values())[index + 1 :]):
        raise AssertionError("Approved packet corridors overlap")

    component_modes = {
        "evidence_document": "bright",
        "access_key": "bright",
        "timeline_waveform": "red",
        "intelligence_bars": "blue",
        "correlation_graph": "red",
        "datastore_cylinder": "bright",
        "hub_rail": "red",
        "hub_verified_led": "green",
        "hub_signature": "red",
        "evidence_indicator": "red",
        "access_indicator": "red",
        "timeline_indicator": "red",
        "intelligence_indicator": "blue",
        "correlation_indicator": "red",
        "datastore_indicator": "green",
    }
    component_masks = {key: source_pixels(source, COMPONENT_BOUNDS[key], mode) for key, mode in component_modes.items()}
    component_masks["datastore_fill"] = rect_mask(COMPONENT_BOUNDS["datastore_fill"])
    for name, mask in component_masks.items():
        if not np.any(mask):
            raise AssertionError(f"Empty approved local response mask: {name}")

    route_union = np.logical_or.reduce(tuple(route_masks.values()))
    component_union = np.logical_or.reduce(tuple(component_masks.values()))
    authorized = route_union | component_union
    protected_text_and_geometry = ~authorized
    module_static = all_module_mask & ~component_union
    arrowhead_mask = np.logical_or.reduce(tuple(rect_mask(bounds) for bounds in ARROWHEAD_BOUNDS.values()))
    if np.any(authorized & arrowhead_mask):
        raise AssertionError("Animation authorization reaches a static route arrowhead")
    return route_paths, route_masks, component_masks, authorized, protected_text_and_geometry, module_static | arrowhead_mask


def smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def event_state(route: RouteSpec, frame_index: int) -> tuple[float, float] | None:
    """Return monotonic source-to-destination progress and a tapered alpha."""
    age = (frame_index - route.start) % FRAME_COUNT
    if age >= route.duration:
        return None
    normal = age / (route.duration - 1)
    progress = smoothstep(normal)
    strength = math.sin(math.pi * normal) ** 0.72
    if strength <= 0.002:
        return None
    return progress, strength


def point_on_path(path: np.ndarray, progress: float) -> tuple[float, float]:
    index = min(len(path) - 1, max(0.0, progress * (len(path) - 1)))
    lower = int(math.floor(index))
    upper = min(len(path) - 1, lower + 1)
    fraction = index - lower
    point = path[lower] * (1.0 - fraction) + path[upper] * fraction
    return float(point[0]), float(point[1])


def draw_scaled_disk(draw: ImageDraw.ImageDraw, point: tuple[float, float], radius: float, color: tuple[int, int, int], alpha: int) -> None:
    x, y = point
    factor = DRAW_SCALE
    draw.ellipse(
        (
            int(round((x - radius) * factor)),
            int(round((y - radius) * factor)),
            int(round((x + radius) * factor)),
            int(round((y + radius) * factor)),
        ),
        fill=(*color, max(0, min(255, alpha))),
    )


def draw_packet(overlay: Image.Image, path: np.ndarray, progress: float, strength: float, color: tuple[int, int, int]) -> tuple[float, float]:
    """Draw a compact, round-head packet with a path-following tapered tail."""
    high = overlay.resize((PANEL_SIZE[0] * DRAW_SCALE, PANEL_SIZE[1] * DRAW_SCALE), Image.Resampling.NEAREST)
    # This function receives a transparent native overlay.  Work on an
    # upscaled temporary surface for fractional positions, then replace it.
    draw = ImageDraw.Draw(high, "RGBA")
    tail_span = 0.115
    samples = 12
    for index in range(samples):
        fraction = index / (samples - 1)
        local_progress = max(0.0, progress - tail_span * (1.0 - fraction))
        point = point_on_path(path, local_progress)
        alpha = int((16 + 70 * fraction) * strength)
        radius = 0.70 + 0.55 * fraction
        draw_scaled_disk(draw, point, radius, color, alpha)
    head = point_on_path(path, progress)
    draw_scaled_disk(draw, head, 2.25, color, int(42 * strength))
    draw_scaled_disk(draw, head, 1.10, color, int(228 * strength))
    overlay.paste(high.resize(PANEL_SIZE, Image.Resampling.LANCZOS), (0, 0))
    return head


def blend_mask(panel: np.ndarray, mask: np.ndarray, color: tuple[int, int, int], amount: float) -> np.ndarray:
    if amount <= 0.0 or not np.any(mask):
        return panel
    amount = min(0.78, amount)
    result = panel.copy()
    source = result[mask].astype(np.float64)
    target = np.asarray(color, dtype=np.float64)
    result[mask] = np.rint(source * (1.0 - amount) + target * amount).astype(np.uint8)
    return result


def response_amount(progress: float, strength: float, *, arrival: bool = False, outbound_start: bool = False) -> float:
    if arrival:
        return strength * smoothstep((progress - 0.56) / 0.28)
    if outbound_start:
        return strength * (1.0 - smoothstep((progress - 0.42) / 0.26))
    return strength * (1.0 - smoothstep((progress - 0.52) / 0.25))


def render_frame(
    source: np.ndarray,
    route_paths: dict[str, np.ndarray],
    component_masks: dict[str, np.ndarray],
    authorized: np.ndarray,
    frame_index: int,
) -> tuple[np.ndarray, dict[str, object], np.ndarray]:
    """Fresh source frame + one discarded local overlay; no prior frame reuse."""
    panel = source.copy()
    overlay = Image.new("RGBA", PANEL_SIZE, (0, 0, 0, 0))
    component_strength: dict[str, float] = {name: 0.0 for name in component_masks}
    records: list[dict[str, object]] = []

    # A near-imperceptible periodic hub life signal means the map never feels
    # dormant, yet f60 exactly repeats f0 and no hub text or border changes.
    phase = 2.0 * math.pi * (frame_index % FRAME_COUNT) / FRAME_COUNT
    idle = 0.045 + 0.035 * ((math.sin(phase) + 1.0) * 0.5)
    component_strength["hub_verified_led"] = idle
    component_strength["hub_signature"] = idle * 0.80

    for route in ROUTES:
        state = event_state(route, frame_index)
        if state is None:
            continue
        progress, strength = state
        head = draw_packet(overlay, route_paths[route.key], progress, strength, route.color)
        records.append({
            "route": route.key,
            "source": route.source,
            "destination": route.destination,
            "progress": progress,
            "strength": strength,
            "head": head,
        })
        if route.key == "evidence_to_case":
            component_strength["evidence_document"] = max(component_strength["evidence_document"], response_amount(progress, strength))
            component_strength["evidence_indicator"] = max(component_strength["evidence_indicator"], response_amount(progress, strength) * 0.70)
        elif route.key == "access_to_case":
            component_strength["access_key"] = max(component_strength["access_key"], response_amount(progress, strength))
            component_strength["access_indicator"] = max(component_strength["access_indicator"], response_amount(progress, strength) * 0.70)
        elif route.key == "timeline_to_case":
            component_strength["timeline_waveform"] = max(component_strength["timeline_waveform"], response_amount(progress, strength))
            component_strength["timeline_indicator"] = max(component_strength["timeline_indicator"], response_amount(progress, strength) * 0.65)

        if route.key in {"evidence_to_case", "access_to_case", "timeline_to_case"}:
            arrival = response_amount(progress, strength, arrival=True)
            component_strength["hub_rail"] = max(component_strength["hub_rail"], arrival * 0.62)
            component_strength["hub_verified_led"] = max(component_strength["hub_verified_led"], arrival)
            component_strength["hub_signature"] = max(component_strength["hub_signature"], arrival * 0.72)
        elif route.key == "case_to_intelligence":
            start = response_amount(progress, strength, outbound_start=True)
            arrival = response_amount(progress, strength, arrival=True)
            component_strength["hub_rail"] = max(component_strength["hub_rail"], start * 0.42)
            component_strength["hub_signature"] = max(component_strength["hub_signature"], start * 0.85)
            component_strength["intelligence_bars"] = max(component_strength["intelligence_bars"], arrival)
            component_strength["intelligence_indicator"] = max(component_strength["intelligence_indicator"], arrival * 0.65)
        elif route.key == "case_to_correlation":
            start = response_amount(progress, strength, outbound_start=True)
            arrival = response_amount(progress, strength, arrival=True)
            component_strength["hub_rail"] = max(component_strength["hub_rail"], start * 0.42)
            component_strength["hub_signature"] = max(component_strength["hub_signature"], start * 0.85)
            component_strength["correlation_graph"] = max(component_strength["correlation_graph"], arrival)
            component_strength["correlation_indicator"] = max(component_strength["correlation_indicator"], arrival * 0.65)
        elif route.key == "case_to_datastore":
            start = response_amount(progress, strength, outbound_start=True)
            arrival = response_amount(progress, strength, arrival=True)
            component_strength["hub_rail"] = max(component_strength["hub_rail"], start * 0.42)
            component_strength["hub_signature"] = max(component_strength["hub_signature"], start * 0.85)
            component_strength["datastore_cylinder"] = max(component_strength["datastore_cylinder"], arrival)
            component_strength["datastore_fill"] = max(component_strength["datastore_fill"], arrival * 0.76)
            component_strength["datastore_indicator"] = max(component_strength["datastore_indicator"], arrival * 0.78)

    # The packet overlay is composited once over a fresh source copy.  It is
    # never fed into another frame, eliminating cumulative GIF/render drift.
    if overlay.getbbox() is not None:
        panel = np.array(Image.alpha_composite(Image.fromarray(panel, "RGB").convert("RGBA"), overlay).convert("RGB"))

    target_colors = {
        "evidence_document": (255, 104, 72), "access_key": (255, 184, 100), "timeline_waveform": (255, 88, 65),
        "intelligence_bars": (105, 190, 235), "correlation_graph": (255, 100, 70), "datastore_cylinder": (123, 245, 165),
        "datastore_fill": (43, 152, 88), "hub_rail": (255, 87, 66), "hub_verified_led": (148, 255, 182),
        "hub_signature": (255, 88, 66), "evidence_indicator": (255, 100, 70), "access_indicator": (255, 180, 100),
        "timeline_indicator": (255, 88, 66), "intelligence_indicator": (105, 190, 235),
        "correlation_indicator": (255, 100, 70), "datastore_indicator": (123, 245, 165),
    }
    component_amounts = {
        "evidence_document": 0.38, "access_key": 0.38, "timeline_waveform": 0.38,
        "intelligence_bars": 0.42, "correlation_graph": 0.40, "datastore_cylinder": 0.50,
        "datastore_fill": 0.72, "hub_rail": 0.34, "hub_verified_led": 0.42, "hub_signature": 0.36,
        "evidence_indicator": 0.28, "access_indicator": 0.28, "timeline_indicator": 0.28,
        "intelligence_indicator": 0.30, "correlation_indicator": 0.30, "datastore_indicator": 0.34,
    }
    for name, strength in component_strength.items():
        panel = blend_mask(panel, component_masks[name], target_colors[name], strength * component_amounts[name])

    changed = np.any(panel != source, axis=2)
    if np.any(changed & ~authorized):
        count = int(np.count_nonzero(changed & ~authorized))
        raise AssertionError(f"Frame {frame_index} escaped the approved animation masks: {count} pixels")
    return panel, {"frame": frame_index, "active_routes": tuple(records), "component_strength": component_strength}, changed


def parse_gif(path: Path) -> tuple[tuple[int, int], list[tuple[int, int, int, int, bool, bool, int, int, bool]], bytes]:
    data = path.read_bytes()
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise AssertionError("Output is not a valid GIF stream")
    position = 6
    width = int.from_bytes(data[position:position + 2], "little")
    height = int.from_bytes(data[position + 2:position + 4], "little")
    packed = data[position + 4]
    position += 7
    global_palette = b""
    if packed & 0x80:
        palette_length = 3 * (2 ** ((packed & 0x07) + 1))
        global_palette = data[position:position + palette_length]
        position += palette_length
    pending_disposal, pending_delay, pending_transparent = 0, 0, False
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
                block_size = data[position]
                position += 1
                control = data[position:position + block_size]
                position += block_size + 1
                pending_disposal = (control[0] >> 2) & 0x07
                pending_delay = int.from_bytes(control[1:3], "little")
                pending_transparent = bool(control[0] & 0x01)
            else:
                while True:
                    block_size = data[position]
                    position += 1
                    if block_size == 0:
                        break
                    position += block_size
            continue
        if marker != 0x2C:
            raise AssertionError(f"Unexpected GIF block marker: 0x{marker:02x}")
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
        position += 1  # LZW minimum code size
        while True:
            block_size = data[position]
            position += 1
            if block_size == 0:
                break
            position += block_size
        descriptors.append((left, top, frame_width, frame_height, local_palette, interlaced, pending_disposal, pending_delay, pending_transparent))
        pending_disposal, pending_delay, pending_transparent = 0, 0, False
    return (width, height), descriptors, global_palette


def make_sheet(frames: Sequence[np.ndarray], indices: Sequence[int], labels: dict[int, str], path: Path) -> tuple[int, int]:
    columns, scale = 4, 1
    width, height = PANEL_SIZE[0] * scale, PANEL_SIZE[1] * scale
    margin, title_h, label_h = 14, 34, 23
    rows = math.ceil(len(indices) / columns)
    sheet = Image.new("RGB", (margin + columns * (width + margin), title_h + rows * (height + label_h + margin)), (3, 5, 5))
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 8), "CASE OVERVIEW // PROPOSAL B // DECODED GIF PROGRESSION", font=proof_font(15, True), fill=(239, 53, 38))
    for ordinal, frame_index in enumerate(indices):
        row, column = divmod(ordinal, columns)
        x = margin + column * (width + margin)
        y = title_h + row * (height + label_h + margin)
        sheet.paste(Image.fromarray(frames[frame_index], "RGB"), (x, y))
        draw.rectangle((x - 1, y - 1, x + width, y + height), outline=(133, 35, 30), width=1)
        draw.text((x, y + height + 4), labels[frame_index], font=proof_font(9), fill=(215, 217, 211))
    sheet.save(path)
    return sheet.size


def make_mask_proof(source: np.ndarray, route_masks: dict[str, np.ndarray], component_masks: dict[str, np.ndarray], protected_static: np.ndarray, path: Path) -> tuple[int, int]:
    base = Image.fromarray(source, "RGB").convert("RGBA")
    overlay = np.zeros((PANEL_SIZE[1], PANEL_SIZE[0], 4), dtype=np.uint8)
    route_union = np.logical_or.reduce(tuple(route_masks.values()))
    component_union = np.logical_or.reduce(tuple(component_masks.values()))
    overlay[route_union] = (248, 69, 47, 130)
    overlay[component_union] = (75, 159, 205, 145)
    visual = Image.alpha_composite(base, Image.fromarray(overlay, "RGBA"))
    draw = ImageDraw.Draw(visual)
    # Fine outlines mark untouched static card/hub geometry only in this proof.
    for bounds in (*MODULE_BOUNDS.values(), HUB_BOUNDS):
        x1, y1, x2, y2 = bounds
        draw.rectangle((x1, y1, x2 - 1, y2 - 1), outline=(76, 205, 144, 255), width=1)
    visual = visual.convert("RGB").resize((PANEL_SIZE[0] * 2, PANEL_SIZE[1] * 2), Image.Resampling.NEAREST)
    proof = Image.new("RGB", (visual.width, visual.height + 34), (3, 5, 5))
    proof.paste(visual, (0, 34))
    draw = ImageDraw.Draw(proof)
    draw.text((10, 7), "PROPOSAL B // AUTHORIZED PACKET TUBES (RED) / LOCAL RESPONSE ZONES (BLUE) / FIXED GEOMETRY (GREEN)", font=proof_font(10), fill=(239, 53, 38))
    draw.text((10, 20), f"protected static pixels: {int(np.count_nonzero(protected_static))}  |  all labels, borders, grid, routes, arrowheads remain fixed", font=proof_font(8), fill=(139, 147, 143))
    proof.save(path)
    return proof.size


def make_activity_proof(decoded_frames: Sequence[np.ndarray], quantized_source: np.ndarray, path: Path) -> tuple[int, int]:
    indices, columns, scale = (0, 16, 32, 48), 2, 2
    width, height = PANEL_SIZE[0] * scale, PANEL_SIZE[1] * scale
    margin, title_h, label_h = 14, 34, 20
    proof = Image.new("RGB", (margin + columns * (width + margin), title_h + 2 * (height + label_h + margin)), (3, 5, 5))
    draw = ImageDraw.Draw(proof)
    draw.text((margin, 8), "PROPOSAL B // ACTUAL DECODED GIF OVERLAY ACTIVITY", font=proof_font(15, True), fill=(239, 53, 38))
    for ordinal, frame_index in enumerate(indices):
        row, column = divmod(ordinal, columns)
        x = margin + column * (width + margin)
        y = title_h + row * (height + label_h + margin)
        changed = np.any(decoded_frames[frame_index] != quantized_source, axis=2)
        visual = np.rint(quantized_source.astype(np.float64) * 0.24).astype(np.uint8)
        visual[changed] = np.maximum(decoded_frames[frame_index][changed], np.asarray((255, 96, 70), dtype=np.uint8))
        proof.paste(Image.fromarray(visual, "RGB").resize((width, height), Image.Resampling.NEAREST), (x, y))
        draw.rectangle((x - 1, y - 1, x + width, y + height), outline=(133, 35, 30), width=1)
        draw.text((x, y + height + 3), f"F{frame_index:03d} decoded changed pixels", font=proof_font(9), fill=(215, 217, 211))
    proof.save(path)
    return proof.size


def inspect_png(path: Path, expected_size: tuple[int, int] | None = None) -> tuple[int, int]:
    with Image.open(path) as image:
        if image.format != "PNG":
            raise AssertionError(f"Output is not a PNG: {path.name}")
        if expected_size is not None and image.size != expected_size:
            raise AssertionError(f"Unexpected PNG dimensions: {path.name} / {image.size}")
        return image.size


def main() -> None:
    # Baselines protect every approved asset and all earlier unapproved #7 work.
    frozen_before = snapshot_tree(FROZEN_ARCHIVE_ROOT)
    frozen_counts = verify_frozen_archives()
    verify_frozen_working_scripts()
    protected_references = (
        STATIC_RENDERER,
        STATIC_OUTPUT_DIR,
        ROOT / "case_overview_design_proposals.py",
        ROOT / "case_overview_design_proposals_output",
        ROOT / "case_overview_proposal_a_animation.py",
        ROOT / "case_overview_proposal_a_animation_output",
        ROOT / "case_overview_correlation_board_animation.py",
        ROOT / "case_overview_correlation_board_animation_output",
        ROOT / "case_overview_test.py",
        ROOT / "case_overview_test_output",
        ROOT / "RECOVERY_STATUS.md",
    )
    protected_before = {str(path.relative_to(ROOT)): snapshot_file_or_tree(path) for path in protected_references}
    master_before = {path: sha256_path(path) for path in EXPECTED_MASTER_SHA256}
    for path, expected in EXPECTED_MASTER_SHA256.items():
        if master_before[path] != expected:
            raise AssertionError(f"Approved master changed before #7 animation: {path.name}")
    banner_before = sha256_path(GENERATE_CASE_BANNER_PATH)
    if banner_before != EXPECTED_GENERATE_CASE_BANNER_SHA256:
        raise AssertionError("generate_case_banner.py changed before #7 animation")
    if sha256_path(STATIC_RENDERER) != EXPECTED_STATIC_RENDERER_SHA256:
        raise AssertionError("Approved Proposal B static renderer changed")
    source_hash_before = sha256_path(SOURCE_PNG)
    if source_hash_before != EXPECTED_SOURCE_SHA256:
        raise AssertionError("Approved Proposal B static PNG changed")
    with Image.open(SOURCE_PNG) as source_image:
        source_rgb = source_image.convert("RGB")
    if source_rgb.size != PANEL_SIZE:
        raise AssertionError("Approved Proposal B static PNG dimensions changed")
    source = np.array(source_rgb)

    route_paths, route_masks, component_masks, authorized, protected_static, module_static = build_masks(source)
    # Verify the actual cyclic schedule independently of its rendering: each
    # packet's active positions advance monotonically from source to destination.
    for route in ROUTES:
        route_progress = []
        for age in range(route.duration):
            state = event_state(route, (route.start + age) % FRAME_COUNT)
            if state is not None:
                route_progress.append(state[0])
        if len(route_progress) < 10 or any(later <= earlier for earlier, later in zip(route_progress, route_progress[1:])):
            raise AssertionError(f"Route progress is not monotonic source-to-destination: {route.key}")
    raw_frames: list[np.ndarray] = []
    raw_changes: list[np.ndarray] = []
    frame_records: list[dict[str, object]] = []
    route_visible_frames = {route.key: 0 for route in ROUTES}
    for frame_index in range(FRAME_COUNT):
        panel, record, changed = render_frame(source, route_paths, component_masks, authorized, frame_index)
        if np.any(changed & ~authorized) or np.any(changed & protected_static):
            raise AssertionError(f"Raw frame {frame_index} changed protected static pixels")
        if np.any(changed & module_static):
            raise AssertionError(f"Raw frame {frame_index} moved/changed a module or hub outside its local response zones")
        for active in record["active_routes"]:
            route_visible_frames[str(active["route"])] += 1
            head_x, head_y = active["head"]
            route_mask = route_masks[str(active["route"])]
            ix, iy = int(round(head_x)), int(round(head_y))
            if not route_mask[iy, ix]:
                raise AssertionError(f"Packet head escaped fixed route corridor: {active['route']}")
        raw_frames.append(panel)
        raw_changes.append(changed)
        frame_records.append(record)
    if any(count < 10 for count in route_visible_frames.values()):
        raise AssertionError(f"A fixed relationship route did not visibly activate enough: {route_visible_frames}")
    if max(len(record["active_routes"]) for record in frame_records) > 2:
        raise AssertionError("More than two routes animate simultaneously; staggered plan violated")
    closure_frame, closure_record, closure_change = render_frame(source, route_paths, component_masks, authorized, FRAME_COUNT)
    if not np.array_equal(closure_frame, raw_frames[0]) or closure_record["active_routes"] != frame_records[0]["active_routes"]:
        raise AssertionError("Frame 60 does not match frame 0 for seamless loop closure")
    if not all(np.array_equal(frame[~authorized], source[~authorized]) for frame in raw_frames):
        raise AssertionError("Raw frame altered pixels outside approved #7 animation masks")
    raw_unique = len({sha256_array(frame) for frame in raw_frames})
    if raw_unique != FRAME_COUNT or any(np.array_equal(raw_frames[index], raw_frames[index - 1]) for index in range(1, FRAME_COUNT)):
        raise AssertionError("Raw Case Overview animation does not have 60 progressive frames")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    expected_output_names = {
        "case_overview_proposal_b_central_hub_static_reference.png",
        "case_overview_proposal_b_central_hub_preview_6s.gif",
        *(f"case_overview_proposal_b_central_hub_frame_{index:03d}.png" for index in KEYFRAME_INDICES),
        "case_overview_proposal_b_central_hub_keyframe_progression_sheet.png",
        "case_overview_proposal_b_central_hub_motion_audit_12frames.png",
        "case_overview_proposal_b_central_hub_animation_masks_proof.png",
        "case_overview_proposal_b_central_hub_decoded_activity_proof.png",
        "case_overview_proposal_b_central_hub_qc.txt",
    }
    existing_names = {path.name for path in OUT_DIR.iterdir() if path.is_file()}
    if existing_names and not existing_names <= expected_output_names:
        raise AssertionError("Refusing to overwrite unrelated #7 animation output")

    reference_path = OUT_DIR / "case_overview_proposal_b_central_hub_static_reference.png"
    gif_path = OUT_DIR / "case_overview_proposal_b_central_hub_preview_6s.gif"
    staging_path = OUT_DIR / ".case_overview_proposal_b_central_hub_preview_6s.staging.gif"
    Image.fromarray(source, "RGB").save(reference_path)
    if not np.array_equal(np.array(Image.open(reference_path).convert("RGB")), source):
        raise AssertionError("New static reference does not decode to the approved Proposal B source")

    # One global fixed palette keeps static source pixels stable while preserving
    # the restrained coloured packet/response overlays through GIF decoding.
    source_repetitions, frame_repetitions = 8, 2
    palette_source = Image.new("RGB", (PANEL_SIZE[0], PANEL_SIZE[1] * (source_repetitions + FRAME_COUNT * frame_repetitions)))
    row = 0
    for _ in range(source_repetitions):
        palette_source.paste(Image.fromarray(source, "RGB"), (0, row * PANEL_SIZE[1]))
        row += 1
    for _ in range(frame_repetitions):
        for panel in raw_frames:
            palette_source.paste(Image.fromarray(panel, "RGB"), (0, row * PANEL_SIZE[1]))
            row += 1
    palette = palette_source.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette_bytes = bytes(palette.getpalette() or [])
    if len(palette_bytes) != 768:
        raise AssertionError("GIF palette is not a 256-entry global palette")
    encoded_frames = [Image.fromarray(panel, "RGB").quantize(palette=palette, dither=Image.Dither.NONE) for panel in raw_frames]
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
        gif_format != "GIF" or gif_size != PANEL_SIZE or logical_size != PANEL_SIZE or gif_count != FRAME_COUNT
        or len(descriptors) != FRAME_COUNT or gif_loop != 0 or set(durations) != {FRAME_DURATION_MS}
        or sum(durations) != FRAME_COUNT * FRAME_DURATION_MS or set(disposals) != {2}
    ):
        raise AssertionError("GIF metadata/loop/frame-count validation failed")
    if any(descriptor[4] or descriptor[5] or descriptor[6] != 2 or descriptor[7] != FRAME_DURATION_MS // 10 or descriptor[8] for descriptor in descriptors):
        raise AssertionError("GIF contains a local palette, interlacing, transparency, or bad disposal/delay")
    if any(descriptor[:4] != (0, 0, PANEL_SIZE[0], PANEL_SIZE[1]) for descriptor in descriptors):
        raise AssertionError("GIF uses cropped or repositioned delta frames")
    if encoded_palette != palette_bytes:
        raise AssertionError("GIF global palette changed during export")
    expected_decoded = [np.array(frame.convert("RGB")) for frame in encoded_frames]
    if not all(np.array_equal(actual, expected) for actual, expected in zip(decoded_frames, expected_decoded)):
        raise AssertionError("Decoded GIF frames differ from fixed full-canvas encoded frames")
    decoded_unique = len({sha256_array(frame) for frame in decoded_frames})
    if decoded_unique != FRAME_COUNT or any(np.array_equal(decoded_frames[index], decoded_frames[index - 1]) for index in range(1, FRAME_COUNT)):
        raise AssertionError("GIF does not contain 60 distinct decoded frames")
    quantized_source = np.array(Image.fromarray(source, "RGB").quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB"))
    if not all(np.array_equal(frame[~authorized], quantized_source[~authorized]) for frame in decoded_frames):
        raise AssertionError("Decoded GIF changed a static pixel outside the authorized animation masks")
    decoded_temporal_outside = sum(
        int(np.count_nonzero(np.any(decoded_frames[index] != decoded_frames[(index - 1) % FRAME_COUNT], axis=2) & ~authorized))
        for index in range(FRAME_COUNT)
    )
    decoded_module_static_temporal = sum(
        int(np.count_nonzero(np.any(decoded_frames[index] != decoded_frames[(index - 1) % FRAME_COUNT], axis=2) & module_static))
        for index in range(FRAME_COUNT)
    )
    if decoded_temporal_outside or decoded_module_static_temporal:
        raise AssertionError("Decoded GIF moved protected static Case Overview geometry")
    staging_path.replace(gif_path)

    keyframe_paths: list[Path] = []
    for frame_index in KEYFRAME_INDICES:
        path = OUT_DIR / f"case_overview_proposal_b_central_hub_frame_{frame_index:03d}.png"
        Image.fromarray(decoded_frames[frame_index], "RGB").save(path)
        if not np.array_equal(np.array(Image.open(path).convert("RGB")), decoded_frames[frame_index]):
            raise AssertionError(f"Keyframe PNG differs from decoded GIF frame {frame_index}")
        keyframe_paths.append(path)
    labels = {
        0: "F000  0.0s  CASE MAP / CYCLE HANDOFF",
        8: "F008  0.8s  EVIDENCE + ACCESS INGEST",
        16: "F016  1.6s  ACCESS + TIMELINE HANDOFF",
        24: "F024  2.4s  TIMELINE + INTELLIGENCE",
        32: "F032  3.2s  INTELLIGENCE DISTRIBUTION",
        40: "F040  4.0s  CORRELATION ANALYSIS",
        48: "F048  4.8s  CORRELATION + STORE COMMIT",
        56: "F056  5.6s  STORE ACK + NEXT EVIDENCE CYCLE",
    }
    motion_labels = {index: f"F{index:03d}  {index * FRAME_DURATION_MS / 1000.0:.1f}s" for index in MOTION_AUDIT_INDICES}
    progression_path = OUT_DIR / "case_overview_proposal_b_central_hub_keyframe_progression_sheet.png"
    motion_audit_path = OUT_DIR / "case_overview_proposal_b_central_hub_motion_audit_12frames.png"
    mask_proof_path = OUT_DIR / "case_overview_proposal_b_central_hub_animation_masks_proof.png"
    activity_proof_path = OUT_DIR / "case_overview_proposal_b_central_hub_decoded_activity_proof.png"
    progression_size = make_sheet(decoded_frames, KEYFRAME_INDICES, labels, progression_path)
    motion_audit_size = make_sheet(decoded_frames, MOTION_AUDIT_INDICES, motion_labels, motion_audit_path)
    mask_proof_size = make_mask_proof(source, route_masks, component_masks, protected_static, mask_proof_path)
    activity_proof_size = make_activity_proof(decoded_frames, quantized_source, activity_proof_path)

    for path, expected in EXPECTED_MASTER_SHA256.items():
        if sha256_path(path) != expected or sha256_path(path) != master_before[path]:
            raise AssertionError(f"Approved master changed during #7 animation: {path.name}")
    if sha256_path(GENERATE_CASE_BANNER_PATH) != banner_before:
        raise AssertionError("generate_case_banner.py changed during #7 animation")
    if sha256_path(STATIC_RENDERER) != EXPECTED_STATIC_RENDERER_SHA256 or sha256_path(SOURCE_PNG) != source_hash_before:
        raise AssertionError("Approved Proposal B static implementation changed during animation")
    assert_unchanged(frozen_before, snapshot_tree(FROZEN_ARCHIVE_ROOT), "Frozen subsystem archives")
    if verify_frozen_archives() != frozen_counts:
        raise AssertionError("Frozen archive manifests changed during #7 animation")
    verify_frozen_working_scripts()
    for path in protected_references:
        key = str(path.relative_to(ROOT))
        assert_unchanged(protected_before[key], snapshot_file_or_tree(path), f"Protected reference {key}")

    raw_outside = sum(int(np.count_nonzero(changed & ~authorized)) for changed in raw_changes)
    raw_module_static = sum(int(np.count_nonzero(changed & module_static)) for changed in raw_changes)
    changed_counts = [int(np.count_nonzero(changed)) for changed in raw_changes]
    output_paths = [reference_path, gif_path, *keyframe_paths, progression_path, motion_audit_path, mask_proof_path, activity_proof_path]
    output_hashes = {path.name: sha256_path(path) for path in output_paths}
    qc_path = OUT_DIR / "case_overview_proposal_b_central_hub_qc.txt"
    qc_lines = (
        "Subsystem #7 Case Overview Proposal-B Central-Hub isolated animation QC",
        "status=NOT_APPROVED_ANIMATION_VISUAL_REVIEW_ONLY",
        f"script_used={SCRIPT_NAME} sha256={sha256_path(SCRIPT_PATH)}",
        f"approved_static_source={SOURCE_PNG} sha256={source_hash_before} dimensions={PANEL_SIZE[0]}x{PANEL_SIZE[1]}",
        f"approved_static_renderer={STATIC_RENDERER.name} sha256={EXPECTED_STATIC_RENDERER_SHA256}",
        f"panel_bounds_global={PANEL_BOUNDS_GLOBAL}",
        "source_frame_reset_each_frame=True previous_frame_pixels_reused=False overlay_only=True static_geometry_redraw=False",
        f"preview_data_variable=CASE_OVERVIEW_ANIMATION_PREVIEW case_id={CASE_OVERVIEW_ANIMATION_PREVIEW['case_id']} current_stage={CASE_OVERVIEW_ANIMATION_PREVIEW['current_stage']} deterministic=True random_generation=False live_data_integration=False",
        "fixed_routes=" + "; ".join(f"{route.key}:{route.points} {route.source}->{route.destination}" for route in ROUTES),
        f"packet_center_clearance_px={PACKET_CENTER_CLEARANCE} packet_tube_radius_px={PACKET_TUBE_RADIUS} arrowheads_untouched=True",
        f"route_packet_visible_frames={route_visible_frames} maximum_simultaneous_routes={max(len(record['active_routes']) for record in frame_records)}",
        f"authorized_animation_pixels={int(np.count_nonzero(authorized))} local_component_masks={ {name: int(np.count_nonzero(mask)) for name, mask in component_masks.items()} }",
        "protected_static=header,outer_frame,CASE_OVERVIEW,CASE_FILE_MAP,all_text,all_card_and_hub_borders,grid,static_route_baselines,static_arrowheads",
        f"raw_outside_authorized_mask_pixel_differences={raw_outside} raw_module_card_static_pixel_differences={raw_module_static}",
        f"raw_changed_pixels_per_frame=min:{min(changed_counts)} max:{max(changed_counts)} raw_unique_frames={raw_unique}/{FRAME_COUNT} closure_frame_60_equals_frame_0=True",
        f"gif_real=True format=GIF dimensions={PANEL_SIZE[0]}x{PANEL_SIZE[1]} frame_count={FRAME_COUNT} duration_per_frame={FRAME_DURATION_MS}ms total_duration={FRAME_COUNT * FRAME_DURATION_MS}ms loop=0",
        f"gif_full_canvas_frames_verified={sum(descriptor[:4] == (0, 0, PANEL_SIZE[0], PANEL_SIZE[1]) for descriptor in descriptors)}/{FRAME_COUNT} cropped_delta_frames=0 optimize=False disposal=2 local_palettes=0 interlaced=False transparency=False",
        f"decoded_unique_frames={decoded_unique}/{FRAME_COUNT} adjacent_duplicate_frames=0 decoded_temporal_outside_authorized_mask_pixel_differences={decoded_temporal_outside}",
        f"decoded_module_card_static_temporal_pixel_differences={decoded_module_static_temporal} decoded_static_pixels_match_same_palette_source_outside_authorized=True",
        "route_direction_verified=True route_progress_monotonic_source_to_destination=True route_geometry_fixed=True module_positions_fixed=True hub_position_fixed=True",
        f"keyframes={tuple(KEYFRAME_INDICES)} files={tuple(path.name for path in keyframe_paths)} progression_sheet={progression_path.name} dimensions={progression_size[0]}x{progression_size[1]}",
        f"motion_audit={motion_audit_path.name} dimensions={motion_audit_size[0]}x{motion_audit_size[1]} mask_proof={mask_proof_path.name} dimensions={mask_proof_size[0]}x{mask_proof_size[1]} decoded_activity_proof={activity_proof_path.name} dimensions={activity_proof_size[0]}x{activity_proof_size[1]}",
        f"approved_populated_master_unchanged=True sha256={master_before[POPULATED_PATH]}",
        f"approved_clear_master_unchanged=True sha256={master_before[CLEAR_PATH]}",
        f"biohazard_reference_unchanged=True sha256={master_before[BIOHAZARD_REFERENCE_PATH]}",
        f"generate_case_banner_unchanged=True sha256={banner_before}",
        f"frozen_subsystems_01_to_06_unchanged=True archive_manifests={frozen_counts} working_scripts_match_archives=True",
        "approved_proposal_b_geometry_unchanged=True proposal_a_c_and_legacy_case_overview_untouched=True full_dashboard_integration=False",
        "output_sha256=" + ",".join(f"{name}:{digest}" for name, digest in output_hashes.items()),
        "next_action=STOP_FOR_USER_VISUAL_APPROVAL_BEFORE_FREEZING_SUBSYSTEM_07",
        "",
    )
    qc_path.write_text("\n".join(qc_lines), encoding="utf-8")
    if {path.name for path in OUT_DIR.iterdir() if path.is_file()} != expected_output_names:
        raise AssertionError("#7 animation output folder does not match expected isolated deliverables")
    for path in output_paths:
        if path.suffix.lower() == ".png":
            inspect_png(path)

    print(f"approved source: {SOURCE_PNG}")
    print(f"GIF preview: {gif_path}")
    print("keyframes: " + ", ".join(str(path) for path in keyframe_paths))


if __name__ == "__main__":
    main()
