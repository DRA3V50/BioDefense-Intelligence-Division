#!/usr/bin/env python3
"""Render only the Evidence Package magnifying-glass subsystem."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
POPULATED_PATH = ROOT / "APPROVED_POPULATED_LAYOUT.png"
CLEAR_PATH = ROOT / "APPROVED_CLEAR_BASE_LAYOUT.png"
OUT_DIR = ROOT / "evidence_magnifier_test_output"
RUN_PREFIX = "evidence_magnifier_isolated"

EXPECTED_INPUT_SHA256 = {
    POPULATED_PATH: "90a223d08555853fd58c7bc7c0c30eadecfa7df3b5320db23e373462735312c4",
    CLEAR_PATH: "168d5b6ba745de5431f8fbaa9c5d5e4a95464b9e150f6aa23b862e4800d68f38",
}

# Tight populated-master Evidence Package panel. The legacy donor crop started
# 50 px too far left and clipped the approved panel's right/top/bottom borders.
VIEW_BOUNDS = (1268, 40, 1720, 267)
VIEW_SIZE = (VIEW_BOUNDS[2] - VIEW_BOUNDS[0], VIEW_BOUNDS[3] - VIEW_BOUNDS[1])

# One immutable source square containing the approved baked-in lens and handle.
SPRITE_BOUNDS = (1638, 145, 1680, 187)
SPRITE_SIZE = (42, 42)
SOURCE_ORIGIN_GLOBAL = (SPRITE_BOUNDS[0], SPRITE_BOUNDS[1])
SOURCE_ORIGIN_VIEW = (
    SOURCE_ORIGIN_GLOBAL[0] - VIEW_BOUNDS[0],
    SOURCE_ORIGIN_GLOBAL[1] - VIEW_BOUNDS[1],
)
SOURCE_LENS_PIVOT_GLOBAL = (1653.5, 160.5)
SOURCE_LENS_PIVOT_VIEW = (
    SOURCE_LENS_PIVOT_GLOBAL[0] - VIEW_BOUNDS[0],
    SOURCE_LENS_PIVOT_GLOBAL[1] - VIEW_BOUNDS[1],
)
LOCAL_LENS_PIVOT = (
    SOURCE_LENS_PIVOT_GLOBAL[0] - SOURCE_ORIGIN_GLOBAL[0],
    SOURCE_LENS_PIVOT_GLOBAL[1] - SOURCE_ORIGIN_GLOBAL[1],
)
# Master coordinates above are pixel-edge coordinates. OpenCV treats integer
# coordinates as pixel centers, so the same physical pivot is half a pixel lower
# in each numeric axis when constructing an affine matrix.
SOURCE_LENS_PIVOT_CV = (
    SOURCE_LENS_PIVOT_VIEW[0] - 0.5,
    SOURCE_LENS_PIVOT_VIEW[1] - 0.5,
)

EXPECTED_VIEW_RGB_SHA256 = "70fcad3566e778505c6a48edc58b3dee9869b48605aa72b0102f90496fef1cbe"
EXPECTED_SPRITE_RGB_SHA256 = "b0b20b58f06c2b2ff112e0218e781e669ae721c78c93ff370cdb3e98e1349337"
EXPECTED_SPRITE_MASK_SHA256 = "92fc51cb03aab1841be59b1b792a95b162a80d2d7d1bd08ece762bae18124388"
EXPECTED_STATIONARY_PLATE_SHA256 = "2c5063a445b1efc2531ac7e15054bc98bfc7b4a80b7bff01eb1ede887ffa8c16"

FRAME_COUNT = 120
FRAME_DURATION_MS = 50
PROOF_FRAMES = (0, 30, 60, 90)

# A deterministic irregular inspection route through the visible label,
# archive, and seal areas. A periodic centripetal Catmull-Rom curve is densely
# sampled and reparameterized by arc length so unequal control-point spacing
# cannot create speed jumps. Frame 0 remains at the approved baked-in pose.
SCAN_CONTROL_POINTS_GLOBAL = (
    (1653.5, 160.5),
    (1625.0, 142.0),
    (1580.0, 148.0),
    (1552.0, 176.0),
    (1564.0, 208.0),
    (1608.0, 204.0),
    (1644.0, 188.0),
)
SCAN_DENSE_SAMPLES_PER_SEGMENT = 1024
SCAN_CENTER_BOUNDS_GLOBAL = (1545.0, 135.0, 1660.0, 215.0)
EVIDENCE_ART_SAFE_BOUNDS_GLOBAL = (1518, 108, 1690, 240)
HANDLE_TURN_DEGREES = 360.0
HANDLE_SPEED_MODULATION_DEGREES = 6.0


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_array(array: np.ndarray) -> str:
    return sha256_bytes(np.ascontiguousarray(array).tobytes())


def centripetal_catmull_rom_point(
    points: np.ndarray,
    segment_index: int,
    local_t: float,
) -> np.ndarray:
    """Evaluate one segment of a closed centripetal Catmull-Rom spline."""
    count = len(points)
    p0 = points[(segment_index - 1) % count]
    p1 = points[segment_index % count]
    p2 = points[(segment_index + 1) % count]
    p3 = points[(segment_index + 2) % count]

    def next_knot(knot: float, first: np.ndarray, second: np.ndarray) -> float:
        return knot + float(np.linalg.norm(second - first)) ** 0.5

    t0 = 0.0
    t1 = next_knot(t0, p0, p1)
    t2 = next_knot(t1, p1, p2)
    t3 = next_knot(t2, p2, p3)
    knot = t1 + local_t * (t2 - t1)
    a1 = ((t1 - knot) * p0 + (knot - t0) * p1) / (t1 - t0)
    a2 = ((t2 - knot) * p1 + (knot - t1) * p2) / (t2 - t1)
    a3 = ((t3 - knot) * p2 + (knot - t2) * p3) / (t3 - t2)
    b1 = ((t2 - knot) * a1 + (knot - t0) * a2) / (t2 - t0)
    b2 = ((t3 - knot) * a2 + (knot - t1) * a3) / (t3 - t1)
    return ((t2 - knot) * b1 + (knot - t1) * b2) / (t2 - t1)


def build_scan_centers() -> tuple[tuple[float, float], ...]:
    """Return frames 0..120 at nearly constant distance along the closed route."""
    control_points = np.asarray(SCAN_CONTROL_POINTS_GLOBAL, dtype=np.float64)
    dense_points: list[np.ndarray] = []
    for segment_index in range(len(control_points)):
        for sample_index in range(SCAN_DENSE_SAMPLES_PER_SEGMENT):
            dense_points.append(
                centripetal_catmull_rom_point(
                    control_points,
                    segment_index,
                    sample_index / SCAN_DENSE_SAMPLES_PER_SEGMENT,
                )
            )
    dense_points.append(control_points[0].copy())
    dense = np.asarray(dense_points, dtype=np.float64)
    distances = np.linalg.norm(np.diff(dense, axis=0), axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(distances)))
    targets = np.linspace(0.0, float(cumulative[-1]), FRAME_COUNT + 1)
    sampled = np.column_stack(
        tuple(np.interp(targets, cumulative, dense[:, axis]) for axis in (0, 1))
    )
    sampled[0] = control_points[0]
    sampled[-1] = control_points[0]
    return tuple((float(point[0]), float(point[1])) for point in sampled)


SCAN_CENTERS_GLOBAL = build_scan_centers()


def motion_state(
    frame_index: int,
) -> tuple[tuple[float, float], tuple[float, float], float]:
    """Return center, translation, and continuous clockwise handle rotation."""
    if not 0 <= frame_index <= FRAME_COUNT:
        raise ValueError(f"Frame index outside closed motion range: {frame_index}")
    center = SCAN_CENTERS_GLOBAL[frame_index]
    translation = (
        center[0] - SOURCE_LENS_PIVOT_GLOBAL[0],
        center[1] - SOURCE_LENS_PIVOT_GLOBAL[1],
    )
    phase = math.tau * frame_index / FRAME_COUNT
    rotation = (
        HANDLE_TURN_DEGREES * frame_index / FRAME_COUNT
        + HANDLE_SPEED_MODULATION_DEGREES * math.sin(phase)
    )
    if frame_index == 0:
        rotation = 0.0
    elif frame_index == FRAME_COUNT:
        rotation = HANDLE_TURN_DEGREES
    return center, translation, rotation


def extract_magnifier(
    populated_rgb: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Extract the approved lens once and reconstruct only its vacated pixels."""
    vx1, vy1, vx2, vy2 = VIEW_BOUNDS
    sx1, sy1, sx2, sy2 = SPRITE_BOUNDS
    view = populated_rgb[vy1:vy2, vx1:vx2].copy()
    sprite_rgb = populated_rgb[sy1:sy2, sx1:sx2].copy()
    if view.shape[:2] != (VIEW_SIZE[1], VIEW_SIZE[0]):
        raise AssertionError(f"Unexpected Evidence viewport shape: {view.shape}")
    if sprite_rgb.shape[:2] != (SPRITE_SIZE[1], SPRITE_SIZE[0]):
        raise AssertionError(f"Unexpected magnifier source shape: {sprite_rgb.shape}")
    if sha256_array(view) != EXPECTED_VIEW_RGB_SHA256:
        raise AssertionError("Approved Evidence Package pixels changed")
    if sha256_array(sprite_rgb) != EXPECTED_SPRITE_RGB_SHA256:
        raise AssertionError("Approved magnifier source square changed")

    maximum = np.max(sprite_rgb, axis=2).astype(np.int16)
    minimum = np.min(sprite_rgb, axis=2).astype(np.int16)
    mean = np.mean(sprite_rgb, axis=2)
    neutral_seed = (mean >= 52.0) & ((maximum - minimum) <= 36)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        neutral_seed.astype(np.uint8),
        connectivity=8,
    )
    if count <= 1:
        raise AssertionError("Approved magnifier neutral-stroke component is missing")
    component_index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    component = labels == component_index
    component_stats = tuple(int(value) for value in stats[component_index])
    if component_stats != (4, 4, 30, 31, 218):
        raise AssertionError(f"Unexpected magnifier component geometry: {component_stats}")

    # Two pixels of the approved dark edge/shadow travel with the neutral stroke.
    # The same exact mask is used once for restoration and for sprite alpha, so
    # recompositing at the source position reproduces the master pixel-for-pixel.
    sprite_mask = cv2.dilate(
        component.astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    ) > 0
    if sha256_array(sprite_mask.astype(np.uint8)) != EXPECTED_SPRITE_MASK_SHA256:
        raise AssertionError("Magnifier extraction mask changed")

    restoration_mask = np.zeros(view.shape[:2], dtype=np.uint8)
    ox, oy = SOURCE_ORIGIN_VIEW
    restoration_mask[oy:oy + SPRITE_SIZE[1], ox:ox + SPRITE_SIZE[0]] = (
        sprite_mask.astype(np.uint8) * 255
    )
    stationary_plate = cv2.inpaint(
        view[:, :, ::-1],
        restoration_mask,
        3,
        cv2.INPAINT_TELEA,
    )[:, :, ::-1]
    if sha256_array(stationary_plate) != EXPECTED_STATIONARY_PLATE_SHA256:
        raise AssertionError("Fixed magnifier clean plate changed")

    sprite_rgba = np.dstack(
        (sprite_rgb, sprite_mask.astype(np.uint8) * 255)
    )
    source_layer = np.zeros((VIEW_SIZE[1], VIEW_SIZE[0], 4), dtype=np.uint8)
    source_layer[oy:oy + SPRITE_SIZE[1], ox:ox + SPRITE_SIZE[0]] = sprite_rgba
    return view, stationary_plate, sprite_rgba, source_layer


def transform_rgba_subpixel(
    source_layer: np.ndarray,
    dx: float,
    dy: float,
    rotation_degrees: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Rigidly rotate/translate one fixed full-canvas premultiplied layer."""
    wrapped_rotation = rotation_degrees % 360.0
    if (
        abs(dx) < 1e-12
        and abs(dy) < 1e-12
        and min(wrapped_rotation, 360.0 - wrapped_rotation) < 1e-12
    ):
        return source_layer.copy(), np.array(
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            dtype=np.float64,
        )
    alpha = source_layer[:, :, 3].astype(np.float32) / 255.0
    premultiplied = np.empty(source_layer.shape, dtype=np.float32)
    premultiplied[:, :, :3] = source_layer[:, :, :3].astype(np.float32) * alpha[:, :, None]
    premultiplied[:, :, 3] = source_layer[:, :, 3].astype(np.float32)
    # OpenCV's positive angle is counter-clockwise in image space. Negating the
    # requested visual angle gives the intended continuous clockwise handle turn.
    matrix = cv2.getRotationMatrix2D(
        SOURCE_LENS_PIVOT_CV,
        -wrapped_rotation,
        1.0,
    )
    matrix[0, 2] += dx
    matrix[1, 2] += dy
    warped = cv2.warpAffine(
        premultiplied,
        matrix.astype(np.float32),
        VIEW_SIZE,
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )
    warped_alpha = np.clip(warped[:, :, 3], 0.0, 255.0)
    output = np.zeros(source_layer.shape, dtype=np.uint8)
    valid = warped_alpha > 1e-5
    output[:, :, 3] = np.rint(warped_alpha).astype(np.uint8)
    output_rgb = np.zeros(warped[:, :, :3].shape, dtype=np.float32)
    output_rgb[valid] = (
        warped[:, :, :3][valid] * 255.0 / warped_alpha[valid, None]
    )
    output[:, :, :3] = np.rint(np.clip(output_rgb, 0.0, 255.0)).astype(np.uint8)
    return output, matrix.astype(np.float64)


def render_frame(
    stationary_plate: np.ndarray,
    source_layer: np.ndarray,
    frame_index: int,
) -> tuple[
    Image.Image,
    np.ndarray,
    tuple[float, float],
    float,
    np.ndarray,
]:
    center, (dx, dy), rotation_degrees = motion_state(frame_index)
    overlay, matrix = transform_rgba_subpixel(
        source_layer,
        dx,
        dy,
        rotation_degrees,
    )
    frame = Image.fromarray(stationary_plate, "RGB").convert("RGBA")
    frame = Image.alpha_composite(frame, Image.fromarray(overlay, "RGBA"))
    return frame.convert("RGB"), overlay[:, :, 3], center, rotation_degrees, matrix


def parse_gif(
    path: Path,
) -> tuple[tuple[int, int], list[tuple[int, int, int, int, bool, bool, int, int, bool]], bytes]:
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
                block_length = data[position]
                position += 1
                control = data[position:position + block_length]
                position += block_length + 1
                pending = (
                    (control[0] >> 2) & 0x07,
                    int.from_bytes(control[1:3], "little"),
                    bool(control[0] & 0x01),
                )
            else:
                while True:
                    block_length = data[position]
                    position += 1
                    if block_length == 0:
                        break
                    position += block_length
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
            block_length = data[position]
            position += 1
            if block_length == 0:
                break
            position += block_length
        descriptors.append(
            (
                left,
                top,
                frame_width,
                frame_height,
                local_palette,
                interlaced,
                pending[0],
                pending[1],
                pending[2],
            )
        )
        pending = (0, 0, False)
    return (width, height), descriptors, global_palette


def main() -> None:
    input_hashes = {
        path: sha256_bytes(path.read_bytes()) for path in EXPECTED_INPUT_SHA256
    }
    for path, expected in EXPECTED_INPUT_SHA256.items():
        if input_hashes[path] != expected:
            raise AssertionError(
                f"Approved input changed: {path.name}={input_hashes[path]}, expected={expected}"
            )
    populated = Image.open(POPULATED_PATH).convert("RGB")
    if populated.size != (1727, 911):
        raise AssertionError(f"Unexpected populated master size: {populated.size}")
    populated_rgb = np.array(populated)
    source_view, stationary_plate, sprite_rgba, source_layer = extract_magnifier(
        populated_rgb
    )

    frames: list[Image.Image] = []
    alpha_frames: list[np.ndarray] = []
    centers: list[tuple[float, float]] = []
    rotations: list[float] = []
    affine_matrices: list[np.ndarray] = []
    bboxes_global: list[tuple[int, int, int, int]] = []
    alpha_centroid_residuals: list[float] = []
    alpha_masses: list[float] = []
    source_alpha = source_layer[:, :, 3].astype(np.float64) / 255.0
    source_mass = float(np.sum(source_alpha))
    source_centroid_cv = np.array(
        (
            float(
                np.sum(np.arange(VIEW_SIZE[0], dtype=np.float64)[None, :] * source_alpha)
                / source_mass
            ),
            float(
                np.sum(np.arange(VIEW_SIZE[1], dtype=np.float64)[:, None] * source_alpha)
                / source_mass
            ),
        ),
        dtype=np.float64,
    )
    for frame_index in range(FRAME_COUNT):
        frame, alpha, center, rotation, matrix = render_frame(
            stationary_plate,
            source_layer,
            frame_index,
        )
        if frame.size != VIEW_SIZE:
            raise AssertionError(f"Frame {frame_index} changed canvas size: {frame.size}")
        nonzero_y, nonzero_x = np.where(alpha > 0)
        if not len(nonzero_x):
            raise AssertionError(f"Magnifier disappeared at frame {frame_index}")
        bbox_global = (
            int(np.min(nonzero_x)) + VIEW_BOUNDS[0],
            int(np.min(nonzero_y)) + VIEW_BOUNDS[1],
            int(np.max(nonzero_x)) + 1 + VIEW_BOUNDS[0],
            int(np.max(nonzero_y)) + 1 + VIEW_BOUNDS[1],
        )
        safe_x1, safe_y1, safe_x2, safe_y2 = EVIDENCE_ART_SAFE_BOUNDS_GLOBAL
        if not (
            safe_x1 <= bbox_global[0]
            and safe_y1 <= bbox_global[1]
            and bbox_global[2] <= safe_x2
            and bbox_global[3] <= safe_y2
        ):
            raise AssertionError(
                f"Magnifier escaped its folder-safe bounds at frame {frame_index}: {bbox_global}"
            )
        center_x1, center_y1, center_x2, center_y2 = SCAN_CENTER_BOUNDS_GLOBAL
        if not (
            center_x1 <= center[0] <= center_x2
            and center_y1 <= center[1] <= center_y2
        ):
            raise AssertionError(
                f"Magnifier center escaped its scan route bounds at frame {frame_index}: {center}"
            )
        linear = matrix[:, :2]
        singular_values = np.linalg.svd(linear, compute_uv=False)
        if (
            abs(float(np.linalg.det(linear)) - 1.0) > 1e-6
            or float(np.max(np.abs(singular_values - 1.0))) > 1e-6
        ):
            raise AssertionError(
                f"Magnifier affine changed scale/shear at frame {frame_index}: {matrix}"
            )
        mapped_pivot_cv = matrix @ np.array(
            (SOURCE_LENS_PIVOT_CV[0], SOURCE_LENS_PIVOT_CV[1], 1.0),
            dtype=np.float64,
        )
        expected_pivot_cv = np.array(
            (
                center[0] - VIEW_BOUNDS[0] - 0.5,
                center[1] - VIEW_BOUNDS[1] - 0.5,
            ),
            dtype=np.float64,
        )
        if float(np.linalg.norm(mapped_pivot_cv - expected_pivot_cv)) > 1e-6:
            raise AssertionError(
                f"Magnifier pivot mapping drifted at frame {frame_index}: "
                f"{mapped_pivot_cv} vs {expected_pivot_cv}"
            )
        weights = alpha.astype(np.float64) / 255.0
        mass = float(np.sum(weights))
        centroid_cv = np.array(
            (
                float(
                    np.sum(np.arange(VIEW_SIZE[0], dtype=np.float64)[None, :] * weights)
                    / mass
                ),
                float(
                    np.sum(np.arange(VIEW_SIZE[1], dtype=np.float64)[:, None] * weights)
                    / mass
                ),
            ),
            dtype=np.float64,
        )
        predicted_centroid_cv = matrix @ np.array(
            (source_centroid_cv[0], source_centroid_cv[1], 1.0),
            dtype=np.float64,
        )
        alpha_centroid_residuals.append(
            float(np.linalg.norm(centroid_cv - predicted_centroid_cv))
        )
        alpha_masses.append(mass)
        frames.append(frame)
        alpha_frames.append(alpha)
        centers.append(center)
        rotations.append(rotation)
        affine_matrices.append(matrix)
        bboxes_global.append(bbox_global)

    if not np.array_equal(np.array(frames[0]), source_view):
        raise AssertionError("Frame 0 does not exactly recompose the approved populated panel")
    closure_frame, closure_alpha, closure_center, closure_rotation, closure_matrix = render_frame(
        stationary_plate,
        source_layer,
        FRAME_COUNT,
    )
    if (
        not np.array_equal(np.array(closure_frame), np.array(frames[0]))
        or not np.array_equal(closure_alpha, alpha_frames[0])
        or closure_center != centers[0]
        or closure_rotation != HANDLE_TURN_DEGREES
        or not np.array_equal(
            closure_matrix,
            np.array(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)), dtype=np.float64),
        )
    ):
        raise AssertionError("Magnifier motion does not close exactly at frame 120")

    cyclic_steps = [
        math.dist(centers[index], centers[(index + 1) % FRAME_COUNT])
        for index in range(FRAME_COUNT)
    ]
    if (
        max(cyclic_steps) / min(cyclic_steps) > 1.01
        or cyclic_steps[-1] > max(cyclic_steps[:-1]) * 1.01
    ):
        raise AssertionError("Arc-length roaming path changed speed or loop seam")
    center_array = np.asarray(centers, dtype=np.float64)
    centered_positions = center_array - np.mean(center_array, axis=0)
    path_rank = int(np.linalg.matrix_rank(centered_positions, tol=1e-6))
    path_area = 0.5 * abs(
        float(
            np.dot(center_array[:, 0], np.roll(center_array[:, 1], -1))
            - np.dot(center_array[:, 1], np.roll(center_array[:, 0], -1))
        )
    )
    if path_rank != 2 or path_area < 4000.0:
        raise AssertionError(
            f"Magnifier path regressed from roaming motion: rank={path_rank}, area={path_area}"
        )
    rotation_steps = np.diff(
        np.asarray((*rotations, closure_rotation), dtype=np.float64)
    )
    if (
        not np.all(rotation_steps > 0.0)
        or abs(float(np.sum(rotation_steps)) - HANDLE_TURN_DEGREES) > 1e-9
        or float(np.min(rotation_steps)) < 2.5
        or float(np.max(rotation_steps)) > 3.5
    ):
        raise AssertionError(
            f"Handle rotation did not make one smooth full turn: {rotation_steps}"
        )
    centroid_residual = max(alpha_centroid_residuals)
    if centroid_residual > 0.15:
        raise AssertionError(
            f"Rigid affine introduced centroid jitter: residual={centroid_residual:.6f}"
        )
    alpha_mass_span_fraction = (
        max(alpha_masses) - min(alpha_masses)
    ) / source_mass
    if alpha_mass_span_fraction > 0.01:
        raise AssertionError(
            f"Rigid affine changed magnifier alpha mass: {alpha_mass_span_fraction:.6%}"
        )
    fractional_position_frames = sum(
        abs(center[0] - round(center[0])) > 1e-6
        or abs(center[1] - round(center[1])) > 1e-6
        for center in centers
    )
    if fractional_position_frames < 110:
        raise AssertionError("Motion path was rounded to too many integer positions")

    palette_indices = (0, 30, 60, 90)
    palette_source = Image.new(
        "RGB",
        (VIEW_SIZE[0], VIEW_SIZE[1] * len(palette_indices)),
    )
    for row, frame_index in enumerate(palette_indices):
        palette_source.paste(frames[frame_index], (0, row * VIEW_SIZE[1]))
    palette = palette_source.quantize(
        colors=256,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    palette_bytes = bytes(palette.getpalette() or [])
    if len(palette_bytes) != 768:
        raise AssertionError("GIF palette is not 256 colors")
    encoded_frames = [
        frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gif_path = OUT_DIR / f"{RUN_PREFIX}_6s.gif"
    staging_path = OUT_DIR / f".{RUN_PREFIX}_6s.staging.gif"
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

    decoded_arrays: list[np.ndarray] = []
    durations: list[int] = []
    disposals: list[int] = []
    tile_extents: list[tuple[int, int, int, int]] = []
    dispose_extents: list[tuple[int, int, int, int]] = []
    decoded_proofs: dict[int, Image.Image] = {}
    with Image.open(staging_path) as gif:
        gif_format = gif.format
        gif_size = gif.size
        gif_frames = gif.n_frames
        gif_loop = gif.info.get("loop")
        for frame_index in range(gif.n_frames):
            gif.seek(frame_index)
            durations.append(int(gif.info.get("duration", 0)))
            disposals.append(int(getattr(gif, "disposal_method", 0)))
            tile = gif.tile[0]
            tile_extents.append(tuple(getattr(tile, "extents", tile[1])))
            dispose_extents.append(tuple(gif.dispose_extent))
            decoded = gif.convert("RGB").copy()
            decoded_arrays.append(np.array(decoded))
            if frame_index in PROOF_FRAMES:
                decoded_proofs[frame_index] = decoded

    logical_size, descriptors, encoded_palette = parse_gif(staging_path)
    full_descriptor = (0, 0, VIEW_SIZE[0], VIEW_SIZE[1])
    if (
        gif_format != "GIF"
        or gif_size != VIEW_SIZE
        or logical_size != VIEW_SIZE
        or gif_frames != FRAME_COUNT
        or len(descriptors) != FRAME_COUNT
        or gif_loop != 0
        or set(durations) != {FRAME_DURATION_MS}
        or sum(durations) != FRAME_COUNT * FRAME_DURATION_MS
        or set(disposals) != {2}
    ):
        raise AssertionError("GIF format, canvas, count, timing, loop, or disposal failed")
    if any(descriptor[:4] != full_descriptor for descriptor in descriptors):
        raise AssertionError("GIF encoder cropped one or more local frame rectangles")
    if any(
        descriptor[4]
        or descriptor[5]
        or descriptor[6] != 2
        or descriptor[7] != FRAME_DURATION_MS // 10
        or descriptor[8]
        for descriptor in descriptors
    ):
        raise AssertionError("GIF local palette/interlace/disposal/delay/transparency failed")
    if encoded_palette != palette_bytes:
        raise AssertionError("Encoded GIF global palette changed")
    if set(tile_extents) != {full_descriptor} or set(dispose_extents) != {full_descriptor}:
        raise AssertionError("Decoder exposed non-full frame/disposal extents")
    expected_decoded = [np.array(frame.convert("RGB")) for frame in encoded_frames]
    if not all(
        np.array_equal(actual, expected)
        for actual, expected in zip(decoded_arrays, expected_decoded)
    ):
        raise AssertionError("Decoded GIF differs from pre-save full-canvas frames")
    if not all(
        not np.array_equal(decoded_arrays[index], decoded_arrays[index - 1])
        for index in range(1, FRAME_COUNT)
    ):
        raise AssertionError("Adjacent encoded frames contain a visible motion dwell")
    decoded_hashes = {sha256_array(frame) for frame in decoded_arrays}
    if len(decoded_hashes) != FRAME_COUNT:
        raise AssertionError(
            f"Roaming scan did not encode 120 distinct poses: {len(decoded_hashes)}"
        )
    staging_path.replace(gif_path)

    proof_paths: list[Path] = []
    proof_labels = {
        0: "start",
        30: "quarter",
        60: "half",
        90: "three_quarter",
    }
    for frame_index in PROOF_FRAMES:
        path = OUT_DIR / (
            f"{RUN_PREFIX}_frame_{frame_index:03d}_{proof_labels[frame_index]}.png"
        )
        decoded_proofs[frame_index].save(path)
        if not np.array_equal(
            np.array(Image.open(path).convert("RGB")),
            decoded_arrays[frame_index],
        ):
            raise AssertionError(f"Proof PNG differs from decoded frame {frame_index}")
        proof_paths.append(path)

    motion_union = np.any(np.stack(alpha_frames, axis=0) > 0, axis=0)
    stationary_outside_union = all(
        np.array_equal(frame[~motion_union], decoded_arrays[0][~motion_union])
        for frame in decoded_arrays[1:]
    )
    if not stationary_outside_union:
        raise AssertionError("Pixels outside magnifier motion changed in the GIF")

    qc_path = OUT_DIR / f"{RUN_PREFIX}_qc.txt"
    bbox_union = (
        min(box[0] for box in bboxes_global),
        min(box[1] for box in bboxes_global),
        max(box[2] for box in bboxes_global),
        max(box[3] for box in bboxes_global),
    )
    qc_lines = (
        "Evidence Package magnifying glass isolated QC",
        f"viewport={VIEW_BOUNDS} size={VIEW_SIZE[0]}x{VIEW_SIZE[1]}",
        f"source_lens_pivot_global={SOURCE_LENS_PIVOT_GLOBAL} local={LOCAL_LENS_PIVOT}",
        "path_type=closed centripetal Catmull-Rom roaming scan; arc_length_reparameterized=True",
        f"path_targets=label/archive/seal control_points={len(SCAN_CONTROL_POINTS_GLOBAL)} path_area={path_area:.3f}px2 rank={path_rank}",
        f"center_bounds_used={SCAN_CENTER_BOUNDS_GLOBAL} actual_x=({min(p[0] for p in centers):.4f},{max(p[0] for p in centers):.4f}) actual_y=({min(p[1] for p in centers):.4f},{max(p[1] for p in centers):.4f})",
        f"art_bounds_used={EVIDENCE_ART_SAFE_BOUNDS_GLOBAL} magnifier_bbox_union_global={bbox_union} contained=True",
        f"handle_rotation=clockwise continuous 0..360 degrees turns=1 speed_modulation=+/-{HANDLE_SPEED_MODULATION_DEGREES:.1f}deg",
        f"rotation_step_range=({float(np.min(rotation_steps)):.6f},{float(np.max(rotation_steps)):.6f})deg seam_step={float(rotation_steps[-1]):.6f}deg",
        f"rigid_full_canvas_affine=True scale=1 no_crop=True no_recenter=True fractional_positions={fractional_position_frames}/{FRAME_COUNT}",
        f"path_step_range=({min(cyclic_steps):.6f},{max(cyclic_steps):.6f}) seam_step={cyclic_steps[-1]:.6f}",
        f"pivot_orbit_residual_max={centroid_residual:.6f}px alpha_mass_span={alpha_mass_span_fraction:.6%}",
        "frame0_recomposes_approved_panel_pre_encoding=True frame120_closes_exactly=True",
        f"gif=GIF/{VIEW_SIZE[0]}x{VIEW_SIZE[1]}/{FRAME_COUNT}frames/{FRAME_DURATION_MS}ms total={FRAME_COUNT * FRAME_DURATION_MS}ms loop0 disposal2",
        f"gif_full_canvas_descriptors={len(descriptors)}/{FRAME_COUNT} optimize=False local_palettes=False",
        f"decoded_unique_frames={len(decoded_hashes)}/{FRAME_COUNT} decoded_proofs_exact=True frames={PROOF_FRAMES}",
        f"stationary_pixels_outside_motion_union={int(np.count_nonzero(~motion_union))} exact=True",
        "approved_masters_modified=False approved_biohazard_modified=False other_subsystem_animation=False",
    )
    qc_path.write_text("\n".join(qc_lines) + "\n", encoding="utf-8")

    expected_outputs = {
        gif_path.name,
        qc_path.name,
        *(path.name for path in proof_paths),
    }
    for superseded_name in (
        f"{RUN_PREFIX}_frame_060_mid.png",
        f"{RUN_PREFIX}_frame_119_end.png",
    ):
        superseded_path = OUT_DIR / superseded_name
        if superseded_path.exists() and superseded_path.name not in expected_outputs:
            superseded_path.unlink()
    actual_outputs = {
        path.name
        for path in OUT_DIR.glob(f"{RUN_PREFIX}*")
        if path.is_file()
    }
    if actual_outputs != expected_outputs or len(actual_outputs) != 6:
        raise AssertionError(
            f"Expected exactly six Subsystem #2 outputs: {sorted(actual_outputs)}"
        )

    for path, expected in EXPECTED_INPUT_SHA256.items():
        if sha256_bytes(path.read_bytes()) != expected:
            raise AssertionError(f"Approved input changed during render: {path.name}")

    print(f"isolated GIF: {gif_path}")
    print("proof frames: " + ", ".join(str(path) for path in proof_paths))
    print(f"QC note: {qc_path}")
    print(f"motion center range: x={min(p[0] for p in centers):.3f}..{max(p[0] for p in centers):.3f}, y={min(p[1] for p in centers):.3f}..{max(p[1] for p in centers):.3f}")
    print(f"magnifier support union: {bbox_union}")


if __name__ == "__main__":
    main()
