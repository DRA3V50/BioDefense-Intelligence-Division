#!/usr/bin/env python3
"""Render only the System Status panel as a deterministic isolated preview."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
POPULATED_PATH = ROOT / "APPROVED_POPULATED_LAYOUT.png"
CLEAR_PATH = ROOT / "APPROVED_CLEAR_BASE_LAYOUT.png"
BIOHAZARD_REFERENCE_PATH = ROOT / "BIOHAZARD_REFERENCE.png"
GENERATE_CASE_BANNER_PATH = ROOT / "generate_case_banner.py"
OUT_DIR = ROOT / "system_status_test_output"
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
}
FROZEN_FEED_OUTPUT_ARCHIVE = FROZEN_ARCHIVE_ROOT / "approved_subsystem_04_active_case_feed"
FROZEN_FEED_OUTPUT_DIR = ROOT / "active_case_feed_test_output"

# Authoritative populated-master crop.  It retains every approved row, label,
# value, separator, diagnostic frame, and border in its original location.
PANEL_BOUNDS = (459, 555, 827, 822)
PANEL_SIZE = (PANEL_BOUNDS[2] - PANEL_BOUNDS[0], PANEL_BOUNDS[3] - PANEL_BOUNDS[1])
EXPECTED_PANEL_SHA256 = "43b4c8b53954a839e0f5b3df12c6bfde6fd6867a866bcddf394415c9b6850647"

FRAME_COUNT = 60
FRAME_DURATION_MS = 100
KEYFRAME_INDICES = (0, 15, 30, 45, 59)
MOTION_AUDIT_INDICES = (0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 59)

# These source-derived LEDs retain their original silhouette and never receive
# a halo, translation, or resize.  Bounds are half-open master coordinates.
LED_SPECS = (
    ("system_integrity", (723, 609, 734, 620), 40, (725, 612, 732, 619)),
    ("data_pipeline", (723, 631, 734, 641), 43, (725, 633, 732, 640)),
    ("api_services", (723, 653, 734, 663), 43, (725, 654, 732, 662)),
    ("network_security", (723, 675, 734, 685), 41, (725, 676, 732, 683)),
    ("threat_intel_feed", (723, 697, 734, 707), 43, (725, 698, 732, 706)),
)

# The immutable tile frames/labels/values sit outside these conservative trace
# clips.  New telemetry is built in local images of exactly these dimensions.
TRACE_SPECS = (
    ("cpu", (475, 786, 526, 801), (55, 132, 193)),
    ("memory", (540, 786, 592, 801), (48, 120, 183)),
    ("network", (606, 786, 665, 801), (63, 143, 203)),
    ("disk", (679, 786, 733, 801), (50, 124, 187)),
    ("uptime", (746, 786, 809, 801), (42, 105, 165)),
)

EXPECTED_LED_MASK_COUNTS = (40, 43, 43, 41, 43)
EXPECTED_TRACE_PIXEL_COUNT = sum(
    (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
    for _, bounds, _ in TRACE_SPECS
)
EXPECTED_AUTHORIZED_PIXEL_COUNT = sum(EXPECTED_LED_MASK_COUNTS) + EXPECTED_TRACE_PIXEL_COUNT


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
    for working_path, archive_path in FROZEN_WORKING_SCRIPT_ARCHIVES.items():
        if not working_path.is_file() or not archive_path.is_file():
            raise AssertionError(f"Missing frozen subsystem script: {working_path.name}")
        if sha256_bytes(working_path.read_bytes()) != sha256_bytes(archive_path.read_bytes()):
            raise AssertionError(f"Frozen subsystem script changed: {working_path.name}")


def verify_frozen_active_case_feed_outputs() -> None:
    manifest = FROZEN_FEED_OUTPUT_ARCHIVE / "SHA256SUMS.txt"
    if not manifest.is_file():
        raise AssertionError("Missing frozen Active Case Feed manifest")
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        expected, name = line.split("  ", 1)
        if name == "active_case_feed_test.py":
            working = ROOT / name
        else:
            working = FROZEN_FEED_OUTPUT_DIR / name
        archived = FROZEN_FEED_OUTPUT_ARCHIVE / name
        if not working.is_file() or not archived.is_file():
            raise AssertionError(f"Missing frozen Active Case Feed payload: {name}")
        if sha256_bytes(working.read_bytes()) != expected or sha256_bytes(archived.read_bytes()) != expected:
            raise AssertionError(f"Frozen Active Case Feed payload changed: {name}")


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
        raise AssertionError("Expected non-empty System Status mask")
    return (
        int(np.min(xx)) + PANEL_BOUNDS[0],
        int(np.min(yy)) + PANEL_BOUNDS[1],
        int(np.max(xx)) + PANEL_BOUNDS[0] + 1,
        int(np.max(yy)) + PANEL_BOUNDS[1] + 1,
    )


def source_led_mask(source_panel: np.ndarray, roi_global: tuple[int, int, int, int]) -> np.ndarray:
    """Select the existing green LED core only; never a rectangular halo."""
    x1, y1, x2, y2 = local_bounds(roi_global)
    roi = source_panel[y1:y2, x1:x2].astype(np.int16)
    green = (
        (roi[:, :, 1] >= 125)
        & (roi[:, :, 1] - roi[:, :, 0] >= 20)
        & (roi[:, :, 1] - roi[:, :, 2] >= 10)
    )
    mask = np.zeros(source_panel.shape[:2], dtype=bool)
    mask[y1:y2, x1:x2] = green
    return mask


def source_trace_signal_mask(source_panel: np.ndarray, trace_bounds: tuple[int, int, int, int]) -> np.ndarray:
    """Identify the baked cyan raster that must be cleared before redrawing."""
    x1, y1, x2, y2 = local_bounds(trace_bounds)
    roi = source_panel[y1:y2, x1:x2].astype(np.int16)
    cyan = (
        (roi[:, :, 2] >= 20)
        & (roi[:, :, 2] - roi[:, :, 0] >= 8)
        & (roi[:, :, 1] - roi[:, :, 0] >= 3)
    )
    # One pixel of source-local dilation catches the original antialias fringe
    # without reaching labels, values, or the fixed tile frame.
    cyan = cv2.dilate(cyan.astype(np.uint8), np.ones((3, 3), dtype=np.uint8), iterations=1).astype(bool)
    mask = np.zeros(source_panel.shape[:2], dtype=bool)
    mask[y1:y2, x1:x2] = cyan
    return mask


def build_masks(source_panel: np.ndarray) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray], np.ndarray]:
    led_masks: list[np.ndarray] = []
    for (_, roi, expected_count, expected_bbox) in LED_SPECS:
        mask = source_led_mask(source_panel, roi)
        if int(np.count_nonzero(mask)) != expected_count or mask_bbox_global(mask) != expected_bbox:
            raise AssertionError("Approved System Status LED geometry changed")
        led_masks.append(mask)

    trace_masks: list[np.ndarray] = []
    trace_clear_masks: list[np.ndarray] = []
    for _, bounds, _ in TRACE_SPECS:
        x1, y1, x2, y2 = local_bounds(bounds)
        trace_mask = np.zeros(source_panel.shape[:2], dtype=bool)
        trace_mask[y1:y2, x1:x2] = True
        clear_mask = source_trace_signal_mask(source_panel, bounds)
        if not np.any(clear_mask) or np.any(clear_mask & ~trace_mask):
            raise AssertionError("Trace-clearing mask escaped its tile interior")
        trace_masks.append(trace_mask)
        trace_clear_masks.append(clear_mask)

    authorized = np.zeros(source_panel.shape[:2], dtype=bool)
    for mask in (*led_masks, *trace_masks):
        authorized |= mask
    if int(np.count_nonzero(authorized)) != EXPECTED_AUTHORIZED_PIXEL_COUNT:
        raise AssertionError("System Status authorized surface changed")
    return led_masks, trace_masks, trace_clear_masks, authorized


def cyan_signal_mask(array: np.ndarray) -> np.ndarray:
    values = array.astype(np.int16)
    return (
        (values[:, :, 2] >= 20)
        & (values[:, :, 2] - values[:, :, 0] >= 8)
        & (values[:, :, 1] - values[:, :, 0] >= 3)
    )


def build_trace_plate(source_panel: np.ndarray, trace_clear_masks: Sequence[np.ndarray]) -> tuple[np.ndarray, int]:
    """Create one source-derived, trace-free plate without touching fixed art."""
    plate = source_panel.copy()
    union = np.zeros(source_panel.shape[:2], dtype=bool)
    for (_, bounds, _), clear_mask in zip(TRACE_SPECS, trace_clear_masks):
        x1, y1, x2, y2 = local_bounds(bounds)
        local_mask = clear_mask[y1:y2, x1:x2]
        union |= clear_mask
        inpainted = cv2.inpaint(
            plate[y1:y2, x1:x2],
            (local_mask.astype(np.uint8) * 255),
            2,
            cv2.INPAINT_TELEA,
        )
        current = plate[y1:y2, x1:x2]
        current[local_mask] = inpainted[local_mask]
        plate[y1:y2, x1:x2] = current
    if not np.array_equal(plate[~union], source_panel[~union]):
        raise AssertionError("Trace plate changed pixels outside source trace raster")
    ghosts = int(np.count_nonzero(cyan_signal_mask(plate) & union))
    if ghosts:
        raise AssertionError("Source trace raster remains in the trace-free plate")
    return plate, ghosts


def wrapped_distance(values: np.ndarray, center: float) -> np.ndarray:
    return np.abs((values - center + 0.5) % 1.0 - 0.5)


def wrapped_gaussian(values: np.ndarray, center: float, sigma: float) -> np.ndarray:
    return np.exp(-0.5 * (wrapped_distance(values, center) / sigma) ** 2)


def telemetry_samples(kind: str, sample_count: int, t: float) -> np.ndarray:
    """Return one bounded, periodic, deterministic diagnostic trace profile."""
    if sample_count < 2:
        raise AssertionError("Diagnostic trace needs at least two samples")
    u = np.linspace(0.0, 1.0, sample_count, endpoint=True)
    # Every temporal term is periodic at t=1.0 so the omitted frame 60 is an
    # exact frame-0 closure rather than a hidden end-of-loop jump.
    shared = wrapped_gaussian(u, (0.16 + t) % 1.0, 0.055)
    if kind == "cpu":
        values = (
            0.42
            + 0.09 * np.sin(math.tau * (1.20 * u - t + 0.08))
            + 0.045 * np.sin(math.tau * (3.60 * u - 2.0 * t))
            + 0.22 * wrapped_gaussian(u, (0.64 + t) % 1.0, 0.045)
            + 0.11 * shared
        )
    elif kind == "memory":
        values = (
            0.54
            + 0.075 * np.sin(math.tau * (0.72 * u + 0.08 * math.sin(math.tau * t) + 0.19))
            + 0.032 * np.sin(math.tau * (2.10 * u + 0.035 * math.sin(math.tau * t + 0.31) + 0.31))
            + 0.045 * wrapped_gaussian(u, (0.33 + t) % 1.0, 0.130)
        )
    elif kind == "network":
        values = (
            0.29
            + 0.060 * np.sin(math.tau * (2.60 * u - t + 0.07))
            + 0.27 * wrapped_gaussian(u, (0.22 + t) % 1.0, 0.045)
            + 0.14 * wrapped_gaussian(u, (0.76 + 2.0 * t) % 1.0, 0.065)
            + 0.18 * shared
        )
    elif kind == "disk":
        values = (
            0.27
            + 0.035 * np.sin(math.tau * (1.70 * u - t + 0.11))
            + 0.25 * wrapped_gaussian(u, (0.48 + t) % 1.0, 0.026)
            + 0.13 * wrapped_gaussian(u, (0.86 + 2.0 * t) % 1.0, 0.038)
        )
    elif kind == "uptime":
        values = (
            0.18
            + 0.030 * np.sin(math.tau * (0.88 * u + 0.040 * math.sin(math.tau * t) + 0.41))
            + 0.020 * np.sin(math.tau * (3.20 * u + 0.025 * math.sin(math.tau * t + 0.09) + 0.09))
            + 0.075 * wrapped_gaussian(u, (0.38 + t) % 1.0, 0.055)
        )
    else:
        raise AssertionError(f"Unknown diagnostic kind: {kind}")
    return np.clip(values, 0.04, 0.93).astype(np.float64)


def preview_system_status_for_frame(frame_index: int) -> dict[str, object]:
    """Build deterministic preview data outside the drawing implementation."""
    t = (frame_index % FRAME_COUNT) / FRAME_COUNT
    row_data = (
        ("system_integrity", "VERIFIED", 98.6, 0.985, 0.045, 0.03),
        ("data_pipeline", "STABLE", 97.2, 0.980, 0.040, 0.24),
        ("api_services", "ONLINE", 96.1, 0.982, 0.038, 0.47),
        ("network_security", "SECINE", 97.8, 0.979, 0.043, 0.68),
        ("threat_intel_feed", "ACTIVE", 95.4, 0.983, 0.046, 0.84),
    )
    subsystems: dict[str, dict[str, object]] = {}
    for key, status, health, base, amplitude, phase in row_data:
        # Each stable indicator has an independently phased, very small gain.
        intensity = base + amplitude * (0.5 - 0.5 * math.cos(math.tau * (t + phase)))
        subsystems[key] = {
            "status": status,
            "health": health,
            "led_state": "healthy",
            "led_intensity": intensity,
        }

    telemetry: dict[str, dict[str, object]] = {}
    for key, bounds, _ in TRACE_SPECS:
        telemetry[key] = {
            "samples": tuple(float(value) for value in telemetry_samples(key, bounds[2] - bounds[0], t)),
        }
    return {
        "case_id": "CASE-7B-7742",
        "preview_only": True,
        "subsystems": subsystems,
        "telemetry": telemetry,
    }


def validate_system_status(system_status: dict[str, object]) -> None:
    if not str(system_status.get("case_id", "")):
        raise AssertionError("System Status preview requires a case id")
    subsystems = system_status.get("subsystems")
    telemetry = system_status.get("telemetry")
    if not isinstance(subsystems, dict) or not isinstance(telemetry, dict):
        raise AssertionError("System Status structure is incomplete")
    for key, _, _, _ in LED_SPECS:
        row = subsystems.get(key)
        if not isinstance(row, dict):
            raise AssertionError(f"Missing subsystem preview row: {key}")
        health = float(row.get("health", -1.0))
        intensity = float(row.get("led_intensity", -1.0))
        if not str(row.get("status", "")) or not 0.0 <= health <= 100.0 or not 0.90 <= intensity <= 1.08:
            raise AssertionError(f"Invalid structured status preview: {key}")
    for key, bounds, _ in TRACE_SPECS:
        record = telemetry.get(key)
        if not isinstance(record, dict):
            raise AssertionError(f"Missing diagnostic telemetry: {key}")
        samples = np.asarray(record.get("samples", ()), dtype=np.float64)
        if samples.shape != (bounds[2] - bounds[0],) or not np.all(np.isfinite(samples)) or np.any(samples < 0.0) or np.any(samples > 1.0):
            raise AssertionError(f"Invalid diagnostic telemetry: {key}")


def draw_trace_patch(
    patch: np.ndarray,
    samples: Sequence[float],
    color: tuple[int, int, int],
) -> tuple[np.ndarray, np.ndarray]:
    """Draw a clipped 1px diagnostic trace and return its exact foreground mask."""
    height, width = patch.shape[:2]
    values = np.asarray(samples, dtype=np.float64)
    if values.shape != (width,):
        raise AssertionError("Trace sample count does not match its fixed tile interior")
    bottom = height - 2
    drawable_height = height - 5
    y_values = np.rint(bottom - np.clip(values, 0.0, 1.0) * drawable_height).astype(np.int32)
    y_values = np.clip(y_values, 2, bottom)
    points = [(int(x), int(y)) for x, y in enumerate(y_values)]
    trace_image = Image.fromarray(patch, "RGB")
    trace_mask_image = Image.new("L", (width, height), 0)
    ImageDraw.Draw(trace_image).line(points, fill=color, width=1)
    ImageDraw.Draw(trace_mask_image).line(points, fill=255, width=1)
    foreground = np.array(trace_mask_image, dtype=np.uint8) > 0
    # The sampled trace deliberately spans the full horizontal interior, but
    # it must keep vertical clearance from the tile frame and metric text.
    if np.any(foreground[[0, -1], :]):
        raise AssertionError("Diagnostic trace reached a tile's vertical edge")
    return np.array(trace_image, dtype=np.uint8), foreground


def render_full_frame(
    populated_rgb: np.ndarray,
    source_panel: np.ndarray,
    trace_plate: np.ndarray,
    led_masks: Sequence[np.ndarray],
    system_status: dict[str, object],
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
    """Render one frame from the immutable populated master and structured data."""
    validate_system_status(system_status)
    full_frame = populated_rgb.copy()
    panel = trace_plate.copy()
    subsystems = system_status["subsystems"]
    telemetry = system_status["telemetry"]

    for (key, _, _, _), led_mask in zip(LED_SPECS, led_masks):
        source_pixels = source_panel[led_mask].astype(np.float64)
        gain = float(subsystems[key]["led_intensity"])
        panel[led_mask] = np.rint(np.clip(source_pixels * gain, 0.0, 255.0)).astype(np.uint8)

    trace_foregrounds: list[np.ndarray] = []
    for key, bounds, color in TRACE_SPECS:
        x1, y1, x2, y2 = local_bounds(bounds)
        patch, foreground = draw_trace_patch(
            panel[y1:y2, x1:x2].copy(),
            telemetry[key]["samples"],
            color,
        )
        panel[y1:y2, x1:x2] = patch
        full_mask = np.zeros(panel.shape[:2], dtype=bool)
        full_mask[y1:y2, x1:x2] = foreground
        trace_foregrounds.append(full_mask)

    px1, py1, px2, py2 = PANEL_BOUNDS
    full_frame[py1:py2, px1:px2] = panel
    return full_frame, panel, trace_foregrounds


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
        raise AssertionError("Invalid System Status proof-sheet layout")
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
        draw.rectangle((x - 1, y - 1, x + frame_width, y + frame_height), outline=(44, 105, 165), width=1)
        draw.text((x, y + frame_height + 3), labels[frame_index], fill=(185, 195, 205))
    sheet.save(path)
    reopened = Image.open(path).convert("RGB")
    if reopened.size != sheet.size or not np.array_equal(np.array(reopened), np.array(sheet)):
        raise AssertionError(f"Proof sheet verification failed: {path.name}")
    return sheet.size


def make_mask_proof(
    source_panel: np.ndarray,
    led_masks: Sequence[np.ndarray],
    trace_masks: Sequence[np.ndarray],
    path: Path,
) -> tuple[int, int]:
    """Make a proof-only view of the exact authorized islands."""
    scale = 2
    source = Image.fromarray(source_panel, "RGB").resize(
        (PANEL_SIZE[0] * scale, PANEL_SIZE[1] * scale),
        Image.Resampling.NEAREST,
    ).convert("RGBA")
    overlay = Image.new("RGBA", source.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for (key, _, _, _), mask in zip(LED_SPECS, led_masks):
        yy, xx = np.where(mask)
        for x, y in zip(xx, yy):
            draw.point((int(x) * scale, int(y) * scale), fill=(92, 255, 135, 255))
    for (key, bounds, _), mask in zip(TRACE_SPECS, trace_masks):
        x1, y1, x2, y2 = local_bounds(bounds)
        draw.rectangle((x1 * scale, y1 * scale, x2 * scale - 1, y2 * scale - 1), outline=(55, 188, 255, 235), width=1)
        draw.text((x1 * scale + 2, y1 * scale - 12), key.upper(), fill=(105, 205, 255, 255))
    composited = Image.alpha_composite(source, overlay).convert("RGB")
    title_height = 22
    proof = Image.new("RGB", (composited.width, composited.height + title_height), (5, 8, 12))
    proof.paste(composited, (0, title_height))
    ImageDraw.Draw(proof).text((6, 5), "SYSTEM STATUS - AUTHORIZED LED AND TRACE MASKS", fill=(220, 228, 235))
    proof.save(path)
    reopened = Image.open(path).convert("RGB")
    if reopened.size != proof.size or not np.array_equal(np.array(reopened), np.array(proof)):
        raise AssertionError(f"Mask proof verification failed: {path.name}")
    return proof.size


def main() -> None:
    frozen_before = snapshot_tree(FROZEN_ARCHIVE_ROOT)
    verify_frozen_working_scripts()
    verify_frozen_active_case_feed_outputs()
    master_hashes = {path: sha256_bytes(path.read_bytes()) for path in EXPECTED_MASTER_SHA256}
    for path, expected in EXPECTED_MASTER_SHA256.items():
        if master_hashes[path] != expected:
            raise AssertionError(f"Approved master changed: {path.name}")
    generate_case_banner_before = sha256_bytes(GENERATE_CASE_BANNER_PATH.read_bytes())
    if generate_case_banner_before != EXPECTED_GENERATE_CASE_BANNER_SHA256:
        raise AssertionError("generate_case_banner.py changed before System Status render")

    populated = Image.open(POPULATED_PATH).convert("RGB")
    if populated.size != (1727, 911):
        raise AssertionError("Approved populated master dimensions changed")
    populated_rgb = np.array(populated)
    px1, py1, px2, py2 = PANEL_BOUNDS
    source_panel = populated_rgb[py1:py2, px1:px2].copy()
    if source_panel.shape != (PANEL_SIZE[1], PANEL_SIZE[0], 3) or sha256_array(source_panel) != EXPECTED_PANEL_SHA256:
        raise AssertionError("Approved System Status panel pixels changed")

    led_masks, trace_masks, trace_clear_masks, authorized_mask = build_masks(source_panel)
    trace_plate, source_trace_ghost_pixels_remaining = build_trace_plate(source_panel, trace_clear_masks)
    if source_trace_ghost_pixels_remaining != 0:
        raise AssertionError("Source trace ghosts remain after source-derived reconstruction")
    trace_clear_union = np.logical_or.reduce(trace_clear_masks)

    master_authorized_mask = np.zeros(populated_rgb.shape[:2], dtype=bool)
    master_authorized_mask[py1:py2, px1:px2] = authorized_mask
    raw_panels: list[np.ndarray] = []
    raw_trace_foregrounds: list[list[np.ndarray]] = []
    preview_frames: list[dict[str, object]] = []
    telemetry_by_kind: dict[str, list[np.ndarray]] = {key: [] for key, _, _ in TRACE_SPECS}
    led_gains_by_frame: list[list[float]] = []

    for frame_index in range(FRAME_COUNT):
        system_status = preview_system_status_for_frame(frame_index)
        full_frame, panel, trace_foregrounds = render_full_frame(
            populated_rgb,
            source_panel,
            trace_plate,
            led_masks,
            system_status,
        )
        changed = np.any(full_frame != populated_rgb, axis=2)
        if np.any(changed & ~master_authorized_mask):
            raise AssertionError("Raw frame changed pixels outside authorized System Status islands")
        for foreground, trace_mask in zip(trace_foregrounds, trace_masks):
            if np.any(foreground & ~trace_mask):
                raise AssertionError("Diagnostic trace escaped its assigned tile interior")
        raw_panels.append(panel)
        raw_trace_foregrounds.append(trace_foregrounds)
        preview_frames.append(system_status)
        led_gains_by_frame.append([
            float(system_status["subsystems"][key]["led_intensity"])
            for key, _, _, _ in LED_SPECS
        ])
        for key, _, _ in TRACE_SPECS:
            telemetry_by_kind[key].append(np.asarray(system_status["telemetry"][key]["samples"], dtype=np.float64))

    closure_status = preview_system_status_for_frame(FRAME_COUNT)
    closure_full, closure_panel, _ = render_full_frame(
        populated_rgb,
        source_panel,
        trace_plate,
        led_masks,
        closure_status,
    )
    if closure_full.shape != populated_rgb.shape:
        raise AssertionError("System Status closure frame has an invalid full canvas")
    if not np.array_equal(closure_panel, raw_panels[0]):
        raise AssertionError("System Status preview does not close at frame 60")

    # Deterministic telemetry has bounded per-frame evolution and every trace
    # remains distinct from the others, including the small shared CPU/NET event.
    telemetry_step_max = 0.0
    trace_sequence_hashes: dict[str, int] = {}
    for key, arrays in telemetry_by_kind.items():
        sequence = np.vstack((*arrays, np.asarray(closure_status["telemetry"][key]["samples"], dtype=np.float64)))
        telemetry_step_max = max(telemetry_step_max, float(np.max(np.abs(np.diff(sequence, axis=0)))))
        trace_sequence_hashes[key] = len({sha256_array(values) for values in arrays})
        if trace_sequence_hashes[key] < FRAME_COUNT - 1:
            raise AssertionError(f"Diagnostic trace did not evolve: {key}")
    first_profiles = [telemetry_by_kind[key][0] for key, _, _ in TRACE_SPECS]
    if any(np.array_equal(first_profiles[left], first_profiles[right]) for left in range(len(first_profiles)) for right in range(left + 1, len(first_profiles))):
        raise AssertionError("Diagnostic profiles are not distinct")
    if telemetry_step_max > 0.18:
        raise AssertionError("Diagnostic telemetry changes too abruptly between frames")
    trace_raster_unique_states: dict[str, int] = {}
    trace_raster_adjacent_changes: dict[str, int] = {}
    for (key, _, _), trace_mask in zip(TRACE_SPECS, trace_masks):
        rendered = [panel[trace_mask] for panel in raw_panels]
        trace_raster_unique_states[key] = len({sha256_array(values) for values in rendered})
        trace_raster_adjacent_changes[key] = sum(
            not np.array_equal(rendered[index], rendered[index - 1])
            for index in range(1, FRAME_COUNT)
        ) + int(not np.array_equal(closure_panel[trace_mask], rendered[-1]))
        if trace_raster_unique_states[key] < 20 or trace_raster_adjacent_changes[key] < 20:
            raise AssertionError(f"Diagnostic trace is too static after rasterization: {key}")
    gain_matrix = np.asarray(led_gains_by_frame, dtype=np.float64)
    if float(np.min(gain_matrix)) < 0.97 or float(np.max(gain_matrix)) > 1.03:
        raise AssertionError("Status LED pulse exceeds the restrained healthy range")
    high_leds_per_frame = np.sum(gain_matrix > 1.015, axis=1)
    if int(np.max(high_leds_per_frame)) > 2:
        raise AssertionError("Too many System Status LEDs pulse together")

    # Raw panel isolation: every protected row label, status, health value,
    # border, frame, and neighboring pixel remains byte-identical to source.
    if not all(np.array_equal(panel[~authorized_mask], source_panel[~authorized_mask]) for panel in raw_panels):
        raise AssertionError("Raw System Status panel changed static geometry or text")
    trace_pixels_outside_assigned_clip = sum(
        int(np.count_nonzero(foreground & ~trace_mask))
        for foregrounds in raw_trace_foregrounds
        for foreground, trace_mask in zip(foregrounds, trace_masks)
    )
    if trace_pixels_outside_assigned_clip != 0:
        raise AssertionError("Trace pixels escaped their assigned clip")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    reference_path = OUT_DIR / "system_status_static_reference.png"
    gif_path = OUT_DIR / "system_status_preview_6s.gif"
    staging_path = OUT_DIR / ".system_status_preview_6s.staging.gif"
    Image.fromarray(source_panel, "RGB").save(reference_path)
    if not np.array_equal(np.array(Image.open(reference_path).convert("RGB")), source_panel):
        raise AssertionError("Static System Status reference does not match populated master crop")

    palette_source = Image.new("RGB", (PANEL_SIZE[0], PANEL_SIZE[1] * (FRAME_COUNT + 1)))
    palette_source.paste(Image.fromarray(source_panel, "RGB"), (0, 0))
    for row, panel in enumerate(raw_panels, start=1):
        palette_source.paste(Image.fromarray(panel, "RGB"), (0, row * PANEL_SIZE[1]))
    palette = palette_source.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette_bytes = bytes(palette.getpalette() or [])
    if len(palette_bytes) != 768:
        raise AssertionError("System Status GIF palette is not 256 colors")
    encoded_frames = [Image.fromarray(panel, "RGB").quantize(palette=palette, dither=Image.Dither.NONE) for panel in raw_panels]
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
        raise AssertionError("System Status GIF metadata validation failed")
    if any(descriptor[4] or descriptor[5] or descriptor[6] != 2 or descriptor[7] != FRAME_DURATION_MS // 10 or descriptor[8] for descriptor in descriptors):
        raise AssertionError("System Status GIF palette/interlace/disposal/transparency validation failed")
    if encoded_palette != palette_bytes:
        raise AssertionError("System Status GIF global palette changed")
    if any(descriptor[:4] != (0, 0, PANEL_SIZE[0], PANEL_SIZE[1]) for descriptor in descriptors):
        raise AssertionError("System Status GIF contains cropped delta frames")
    expected_decoded = [np.array(frame.convert("RGB")) for frame in encoded_frames]
    if not all(np.array_equal(actual, expected) for actual, expected in zip(decoded_frames, expected_decoded)):
        raise AssertionError("Decoded GIF differs from intended full-canvas frames")
    if len({sha256_array(frame) for frame in decoded_frames}) != FRAME_COUNT:
        raise AssertionError("System Status GIF does not contain 60 unique decoded frames")
    if any(np.array_equal(decoded_frames[index], decoded_frames[index - 1]) for index in range(1, FRAME_COUNT)):
        raise AssertionError("System Status GIF has adjacent duplicate frames")
    if not all(np.array_equal(frame[~authorized_mask], decoded_frames[0][~authorized_mask]) for frame in decoded_frames[1:]):
        raise AssertionError("Decoded GIF changed static pixels outside authorized islands")
    decoded_temporal_outside_authorized = sum(
        int(np.count_nonzero(np.any(decoded_frames[index] != decoded_frames[index - 1], axis=2) & ~authorized_mask))
        for index in range(1, FRAME_COUNT)
    )
    if decoded_temporal_outside_authorized != 0:
        raise AssertionError("Decoded GIF shimmered outside authorized System Status islands")
    staging_path.replace(gif_path)

    keyframe_paths: list[Path] = []
    for frame_index in KEYFRAME_INDICES:
        path = OUT_DIR / f"system_status_frame_{frame_index:03d}.png"
        Image.fromarray(decoded_frames[frame_index], "RGB").save(path)
        if not np.array_equal(np.array(Image.open(path).convert("RGB")), decoded_frames[frame_index]):
            raise AssertionError(f"Keyframe PNG differs from decoded GIF frame {frame_index}")
        keyframe_paths.append(path)

    keyframe_labels = {
        0: "F000  0.0s",
        15: "F015  1.5s",
        30: "F030  3.0s",
        45: "F045  4.5s",
        59: "F059  5.9s",
    }
    motion_labels = {index: f"F{index:03d}  {index * FRAME_DURATION_MS / 1000.0:.1f}s" for index in MOTION_AUDIT_INDICES}
    contact_sheet_path = OUT_DIR / "system_status_keyframe_contact_sheet.png"
    motion_audit_path = OUT_DIR / "system_status_motion_audit_12frames.png"
    mask_proof_path = OUT_DIR / "system_status_animation_masks_proof.png"
    contact_sheet_size = make_preview_sheet(
        decoded_frames,
        KEYFRAME_INDICES,
        keyframe_labels,
        "SYSTEM STATUS - DECODED GIF KEYFRAMES",
        columns=3,
        scale=0.80,
        path=contact_sheet_path,
    )
    motion_audit_size = make_preview_sheet(
        decoded_frames,
        MOTION_AUDIT_INDICES,
        motion_labels,
        "SYSTEM STATUS - 12-FRAME MOTION AUDIT",
        columns=4,
        scale=0.58,
        path=motion_audit_path,
    )
    mask_proof_size = make_mask_proof(source_panel, led_masks, trace_masks, mask_proof_path)

    frozen_after = snapshot_tree(FROZEN_ARCHIVE_ROOT)
    if frozen_after != frozen_before:
        raise AssertionError("A frozen approved subsystem archive changed during System Status rendering")
    verify_frozen_working_scripts()
    verify_frozen_active_case_feed_outputs()
    for path, expected in EXPECTED_MASTER_SHA256.items():
        if sha256_bytes(path.read_bytes()) != expected:
            raise AssertionError(f"Approved master changed during System Status render: {path.name}")
    if sha256_bytes(GENERATE_CASE_BANNER_PATH.read_bytes()) != generate_case_banner_before:
        raise AssertionError("generate_case_banner.py changed during System Status render")

    qc_path = OUT_DIR / "system_status_qc.txt"
    output_names = {
        reference_path.name,
        gif_path.name,
        qc_path.name,
        contact_sheet_path.name,
        motion_audit_path.name,
        mask_proof_path.name,
        *(path.name for path in keyframe_paths),
    }
    existing_outputs = {path.name for path in OUT_DIR.iterdir() if path.is_file()}
    if not existing_outputs <= output_names:
        raise AssertionError("Unexpected System Status output file exists")

    led_mask_records = tuple(
        (key, mask_bbox_global(mask), int(np.count_nonzero(mask)))
        for (key, _, _, _), mask in zip(LED_SPECS, led_masks)
    )
    trace_mask_records = tuple(
        (key, bounds, int(np.count_nonzero(mask)))
        for (key, bounds, _), mask in zip(TRACE_SPECS, trace_masks)
    )
    raw_outside_authorized = sum(
        int(np.count_nonzero(np.any(panel != source_panel, axis=2) & ~authorized_mask))
        for panel in raw_panels
    )
    if raw_outside_authorized != 0:
        raise AssertionError("Raw System Status frames changed pixels outside authorization")
    qc_lines = (
        "Subsystem #5 System Status isolated QC",
        f"script_used={SCRIPT_NAME}",
        f"workspace_root={ROOT}",
        f"output_directory={OUT_DIR}",
        f"approved_populated_master={POPULATED_PATH.name} role=authoritative static pixels and geometry sha256={master_hashes[POPULATED_PATH]}",
        f"approved_clear_master={CLEAR_PATH.name} role=hash-verified only; direct_panel_patch_used=False sha256={master_hashes[CLEAR_PATH]}",
        f"biohazard_reference={BIOHAZARD_REFERENCE_PATH.name} role=hash-verified frozen reference only sha256={master_hashes[BIOHAZARD_REFERENCE_PATH]}",
        f"panel_bounds_global={PANEL_BOUNDS} dimensions={PANEL_SIZE[0]}x{PANEL_SIZE[1]} source_panel_sha256={sha256_array(source_panel)}",
        f"exact_led_masks_global={led_mask_records} total_led_pixels={sum(int(np.count_nonzero(mask)) for mask in led_masks)}",
        f"exact_diagnostic_trace_masks_global={trace_mask_records} total_trace_clip_pixels={sum(int(np.count_nonzero(mask)) for mask in trace_masks)}",
        f"authorized_animation_pixels={int(np.count_nonzero(authorized_mask))} expected_authorized_pixels={EXPECTED_AUTHORIZED_PIXEL_COUNT}",
        f"source_trace_clear_pixels={int(np.count_nonzero(trace_clear_union))} source_trace_ghost_pixels_remaining={source_trace_ghost_pixels_remaining}",
        "source_frame_reset_each_frame=True prior_frame_pixels_used=False",
        "clear_base_panel_direct_patch_used=False legacy_donor_geometry_used=False",
        "preview_data_variable=SYSTEM_STATUS_PREVIEW factory=preview_system_status_for_frame structured_input=system_status",
        "preview_case_id=CASE-7B-7742 deterministic=True random_generation=False",
        f"subsystem_rows={tuple(key for key, _, _, _ in LED_SPECS)} diagnostics={tuple(key for key, _, _ in TRACE_SPECS)}",
        f"trace_profile_unique_states={trace_sequence_hashes} telemetry_max_adjacent_sample_delta={telemetry_step_max:.6f}",
        f"trace_raster_unique_states={trace_raster_unique_states} trace_raster_adjacent_changes={trace_raster_adjacent_changes}",
        f"led_gain_range={float(np.min(gain_matrix)):.6f}..{float(np.max(gain_matrix)):.6f} max_simultaneously_elevated_leds={int(np.max(high_leds_per_frame))}",
        f"trace_pixels_outside_assigned_clip={trace_pixels_outside_assigned_clip}",
        f"outside_authorized_mask_raw_pixel_differences={raw_outside_authorized}",
        "row_text_health_values_tile_borders_fixed=True panel_title_separators_neighboring_panels_fixed=True",
        f"frame_count={FRAME_COUNT} duration_per_frame={FRAME_DURATION_MS}ms total_duration={FRAME_COUNT * FRAME_DURATION_MS}ms loop=0",
        f"gif_real=True format=GIF dimensions={PANEL_SIZE[0]}x{PANEL_SIZE[1]} decoded_unique_frames={len({sha256_array(frame) for frame in decoded_frames})}/{FRAME_COUNT} full_canvas_frames_verified={FRAME_COUNT}/{FRAME_COUNT} disposal=2",
        f"decoded_temporal_outside_authorized_mask_pixel_differences={decoded_temporal_outside_authorized}",
        f"decoded_keyframes={KEYFRAME_INDICES} files={tuple(path.name for path in keyframe_paths)}",
        f"static_reference={reference_path.name} exact_populated_crop=True contact_sheet={contact_sheet_path.name} dimensions={contact_sheet_size[0]}x{contact_sheet_size[1]}",
        f"motion_audit={motion_audit_path.name} dimensions={motion_audit_size[0]}x{motion_audit_size[1]} mask_proof={mask_proof_path.name} dimensions={mask_proof_size[0]}x{mask_proof_size[1]}",
        "approved_png_masters_unchanged=True frozen_subsystems_01_to_04_unchanged=True frozen_working_scripts_match_archives=True",
        "generate_case_banner_unchanged=True live_repository_api_database_network_logic_added=False final_data_integration=False",
        "limitation=deterministic preview-only system health data; persistent active-case integration is intentionally deferred",
    )
    qc_path.write_text("\n".join(qc_lines) + "\n", encoding="utf-8")
    if {path.name for path in OUT_DIR.iterdir() if path.is_file()} != output_names:
        raise AssertionError("System Status output manifest changed after QC write")

    print(f"static reference: {reference_path}")
    print(f"GIF preview: {gif_path}")
    print("keyframes: " + ", ".join(str(path) for path in keyframe_paths))
    print(f"mask proof: {mask_proof_path}")
    print(f"keyframe contact sheet: {contact_sheet_path}")
    print(f"motion audit sheet: {motion_audit_path}")
    print(f"QC note: {qc_path}")
    print(f"GIF size: {gif_path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
