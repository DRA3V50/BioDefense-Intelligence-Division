#!/usr/bin/env python3
"""Render the isolated BioDefense biohazard fixed-pivot proof.

This intentionally does not import or execute any of the legacy renderers.  The
approved source files are read-only inputs; every generated artifact is written
under ``biohazard_test_output`` beside this script.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parent
POPULATED_PATH = ROOT / "APPROVED_POPULATED_LAYOUT.png"
CLEAR_PATH = ROOT / "APPROVED_CLEAR_BASE_LAYOUT.png"
REFERENCE_PATH = ROOT / "BIOHAZARD_REFERENCE.png"
OUT_DIR = ROOT / "biohazard_test_output"
RUN_PREFIX = "biohazard_test_fullcanvas_circumference"
BEFORE_CENTERING_PATH = OUT_DIR / "biohazard_test_before_up4_000deg.png"

# The populated emblem's 120-degree rotational symmetry and the independently
# registered reference both resolve to source pixel (205, 191).  Pillow's image
# coordinates describe pixel edges, so that pixel's center -- and the exact
# mathematical center of the fixed odd-sized square -- is (205.5, 191.5).
SOURCE_HUB_PIXEL = (205, 191)
SOURCE_HUB = (205.5, 191.5)
PREVIOUS_CENTERING_DELTA = (0, -4)
ADDITIONAL_CENTERING_DELTA = (0, -10)
CENTERING_DELTA = (
    PREVIOUS_CENTERING_DELTA[0] + ADDITIONAL_CENTERING_DELTA[0],
    PREVIOUS_CENTERING_DELTA[1] + ADDITIONAL_CENTERING_DELTA[1],
)
HUB_PIXEL = (
    SOURCE_HUB_PIXEL[0] + CENTERING_DELTA[0],
    SOURCE_HUB_PIXEL[1] + CENTERING_DELTA[1],
)
HUB = (
    SOURCE_HUB[0] + CENTERING_DELTA[0],
    SOURCE_HUB[1] + CENTERING_DELTA[1],
)
SPRITE_SIZE = 181
LOCAL_PIVOT = (90.5, 90.5)
SOURCE_ORIGIN = (115, 101)
PASTE_ORIGIN = (
    SOURCE_ORIGIN[0] + CENTERING_DELTA[0],
    SOURCE_ORIGIN[1] + CENTERING_DELTA[1],
)
SOURCE_BOUNDS = (
    SOURCE_ORIGIN[0],
    SOURCE_ORIGIN[1],
    SOURCE_ORIGIN[0] + SPRITE_SIZE,
    SOURCE_ORIGIN[1] + SPRITE_SIZE,
)
SCALE = 1.0

# Isolated scanner viewport from the authoritative populated master.
VIEW_BOUNDS = (14, 44, 384, 294)
VIEW_SIZE = (VIEW_BOUNDS[2] - VIEW_BOUNDS[0], VIEW_BOUNDS[3] - VIEW_BOUNDS[1])
VIEW_HUB = (HUB[0] - VIEW_BOUNDS[0], HUB[1] - VIEW_BOUNDS[1])
VIEW_SOURCE_PASTE = (
    SOURCE_ORIGIN[0] - VIEW_BOUNDS[0],
    SOURCE_ORIGIN[1] - VIEW_BOUNDS[1],
)
VIEW_PASTE = (PASTE_ORIGIN[0] - VIEW_BOUNDS[0], PASTE_ORIGIN[1] - VIEW_BOUNDS[1])
PREVIOUS_HUB = (
    SOURCE_HUB[0] + PREVIOUS_CENTERING_DELTA[0],
    SOURCE_HUB[1] + PREVIOUS_CENTERING_DELTA[1],
)
PREVIOUS_PASTE_ORIGIN = (
    SOURCE_ORIGIN[0] + PREVIOUS_CENTERING_DELTA[0],
    SOURCE_ORIGIN[1] + PREVIOUS_CENTERING_DELTA[1],
)
VIEW_PREVIOUS_PASTE = (
    PREVIOUS_PASTE_ORIGIN[0] - VIEW_BOUNDS[0],
    PREVIOUS_PASTE_ORIGIN[1] - VIEW_BOUNDS[1],
)

FRAME_COUNT = 120
FRAME_DURATION_MS = 50
KEYFRAME_DEGREES = (0, 90, 180, 270)
EXPORT_PROOF_FRAMES = (0, 15, 30, 45)

# The clear master uses different panel geometry.  These stationary-ring fits
# define a local similarity registration into populated-master coordinates.
CLEAR_RING_CENTER = (214.5, 163.5)
CLEAR_RING_RADIUS = 106.7
POPULATED_RING_CENTER = (204.5, 174.5)
POPULATED_RING_RADIUS = 112.4
SCANNER_FLARE_RADIUS = 110.0
ATMOSPHERE_RADIUS = 121.0
ATMOSPHERE_SIGMA = 5.5
ATMOSPHERE_SHADOW_RADIUS = 113.0
ATMOSPHERE_SHADOW_SIGMA = 7.0
ATMOSPHERE_RADIAL_BOUNDS = (108.0, 133.0)
ATMOSPHERE_RED = (66, 6, 5)
ATMOSPHERE_RED_ALPHA_MAX = 88
ATMOSPHERE_BLACK_ALPHA_MAX = 42
ATMOSPHERE_NOISE_SEED = 9147

# Frozen extraction/background hashes from the approved pre-adjustment test.
EXPECTED_SPRITE_RGBA_SHA256 = "a049a0b946dbbd479ff5116b5ed9f4936088ba2e6c630f4081eb958e1dd511e7"
EXPECTED_SPRITE_ALPHA_SHA256 = "49a1084350989d3feee7973cfa0c77fceea0fc60262f84eec7ff1c1864a0d6ee"
EXPECTED_STATIONARY_BACKGROUND_SHA256 = "cffc3cae38848effc6d7c473d0365ac02c4759340d9c7b5d60e2b4a129e966dc"
EXPECTED_BEFORE_CENTERING_SHA256 = "6ed24c15c14e5f210e0a8a48099e1ccabb14ae26c913f5f90fc8b9b1310d0dcb"
EXPECTED_PRE_ATMOSPHERE_RGB_SEQUENCE_SHA256 = "66f4612545bac052e7ba9ae1c84a32a42123ff37db3d9957341dd4c2a3ec7271"
EXPECTED_EMBLEM_ALPHA_SEQUENCE_SHA256 = "919a16851789331f1e1ec09cd017fdfab4218c8421afb1ada45b509efa0544b8"
EXPECTED_SCANNER_ILLUMINATION_ALPHA_SEQUENCE_SHA256 = "4c7b052e0c853e6f713ec8cb19ba7b3aeeef70971d07744008bee4e98b024d81"
EXPECTED_EMBLEM_GLOW_ALPHA_SEQUENCE_SHA256 = "9085e171aff6b2d2e12a44de54ab1202b48034a092c83d91f96b68cac72511cb"
EXPECTED_INPUT_SHA256 = {
    POPULATED_PATH: "90a223d08555853fd58c7bc7c0c30eadecfa7df3b5320db23e373462735312c4",
    CLEAR_PATH: "168d5b6ba745de5431f8fbaa9c5d5e4a95464b9e150f6aa23b862e4800d68f38",
    REFERENCE_PATH: "ec0eb4cd38db13d34c0259f8ba920e4d9a1d2783feeb2f0d25e4ea2b0bf52ba5",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_array(array: np.ndarray) -> str:
    return sha256_bytes(np.ascontiguousarray(array).tobytes())


def sha256_array_sequence(arrays: list[np.ndarray]) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        digest.update(np.ascontiguousarray(array).tobytes())
    return digest.hexdigest()


def parse_gif_frame_descriptors(
    path: Path,
) -> tuple[
    tuple[int, int],
    list[tuple[int, int, int, int, bool, int, int, bool, bool]],
    bytes,
]:
    """Read GIF image-descriptor rectangles directly from the encoded bytes."""
    data = path.read_bytes()
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise AssertionError(f"Not a GIF stream: {path}")
    position = 6
    logical_width = int.from_bytes(data[position:position + 2], "little")
    logical_height = int.from_bytes(data[position + 2:position + 4], "little")
    packed = data[position + 4]
    position += 7
    global_palette = b""
    if packed & 0x80:
        global_palette_length = 3 * (2 ** ((packed & 0x07) + 1))
        global_palette = data[position:position + global_palette_length]
        position += global_palette_length

    pending_disposal = 0
    pending_delay_cs = 0
    pending_transparency = False
    descriptors: list[tuple[int, int, int, int, bool, int, int, bool, bool]] = []
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
                if block_size != 4:
                    raise AssertionError(f"Unexpected GIF graphics-control size: {block_size}")
                control = data[position:position + block_size]
                position += block_size
                pending_disposal = (control[0] >> 2) & 0x07
                pending_delay_cs = int.from_bytes(control[1:3], "little")
                pending_transparency = bool(control[0] & 0x01)
                if data[position] != 0:
                    raise AssertionError("Malformed GIF graphics-control terminator")
                position += 1
            else:
                while True:
                    block_size = data[position]
                    position += 1
                    if block_size == 0:
                        break
                    position += block_size
            continue
        if marker != 0x2C:
            raise AssertionError(
                f"Unexpected GIF block marker 0x{marker:02x} at byte {position - 1}"
            )

        left = int.from_bytes(data[position:position + 2], "little")
        top = int.from_bytes(data[position + 2:position + 4], "little")
        width = int.from_bytes(data[position + 4:position + 6], "little")
        height = int.from_bytes(data[position + 6:position + 8], "little")
        image_packed = data[position + 8]
        position += 9
        has_local_color_table = bool(image_packed & 0x80)
        if has_local_color_table:
            position += 3 * (2 ** ((image_packed & 0x07) + 1))
        position += 1  # LZW minimum code size
        while True:
            block_size = data[position]
            position += 1
            if block_size == 0:
                break
            position += block_size
        descriptors.append(
            (
                left,
                top,
                width,
                height,
                has_local_color_table,
                pending_disposal,
                pending_delay_cs,
                bool(image_packed & 0x40),
                pending_transparency,
            )
        )
        pending_disposal = 0
        pending_delay_cs = 0
        pending_transparency = False

    return (logical_width, logical_height), descriptors, global_palette


def screen_blend_rgb(base_rgb: np.ndarray, overlay_rgba: np.ndarray) -> np.ndarray:
    """Apply a transparent illumination layer without darkening any channel."""
    if overlay_rgba.shape != (*base_rgb.shape[:2], 4):
        raise AssertionError(
            f"Overlay/base shape mismatch: overlay={overlay_rgba.shape}, base={base_rgb.shape}"
        )
    base = base_rgb.astype(np.float32)
    alpha = overlay_rgba[:, :, 3:4].astype(np.float32) / 255.0
    effective_light = overlay_rgba[:, :, :3].astype(np.float32) * alpha
    screened = 255.0 - (255.0 - base) * (255.0 - effective_light) / 255.0
    result = np.clip(np.rint(screened), 0, 255).astype(np.uint8)
    if np.any(result < base_rgb):
        raise AssertionError("Transparent illumination darkened a source channel")
    return result


def solid_alpha_blend_rgb(
    base_rgb: np.ndarray,
    color: tuple[int, int, int],
    alpha: np.ndarray,
) -> np.ndarray:
    """Pointwise normal-alpha blend used only for atmosphere color/shadow."""
    if alpha.shape != base_rgb.shape[:2]:
        raise AssertionError(
            f"Atmosphere alpha/base shape mismatch: alpha={alpha.shape}, base={base_rgb.shape}"
        )
    blend = alpha.astype(np.float32)[:, :, None] / 255.0
    solid = np.array(color, dtype=np.float32)[None, None, :]
    result = np.rint(base_rgb.astype(np.float32) * (1.0 - blend) + solid * blend)
    return np.clip(result, 0, 255).astype(np.uint8)


def smoothstep01(value: np.ndarray) -> np.ndarray:
    clipped = np.clip(value, 0.0, 1.0)
    return clipped * clipped * (3.0 - 2.0 * clipped)


def wrapped_angle_delta(angle: np.ndarray, center: float) -> np.ndarray:
    return np.arctan2(np.sin(angle - center), np.cos(angle - center))


def require_inputs() -> None:
    missing = [p.name for p in (POPULATED_PATH, CLEAR_PATH, REFERENCE_PATH) if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing required workspace input(s): {', '.join(missing)}")


def register_clear_to_populated(clear_rgb: np.ndarray, output_size: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Register the current clear scanner locally without modifying either master."""
    scale = POPULATED_RING_RADIUS / CLEAR_RING_RADIUS
    tx = POPULATED_RING_CENTER[0] - scale * CLEAR_RING_CENTER[0]
    ty = POPULATED_RING_CENTER[1] - scale * CLEAR_RING_CENTER[1]
    matrix = np.array(((scale, 0.0, tx), (0.0, scale, ty)), dtype=np.float32)
    registered = cv2.warpAffine(
        clear_rgb,
        matrix,
        output_size,
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    return registered, matrix


def fill_small_holes(mask: np.ndarray, maximum_area: int = 96) -> np.ndarray:
    """Keep small opaque grunge islands without filling the emblem's real cutouts."""
    result = mask.astype(np.uint8).copy()
    inverse = (result == 0).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(inverse, connectivity=8)
    border_labels = set(np.unique(np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1]))))
    for label in range(1, count):
        if label in border_labels:
            continue
        if int(stats[label, cv2.CC_STAT_AREA]) <= maximum_area:
            result[labels == label] = 1
    return result


def extract_fixed_sprite(
    populated_rgb: np.ndarray,
    registered_clear_rgb: np.ndarray,
) -> tuple[Image.Image, np.ndarray, list[dict[str, object]], dict[str, object]]:
    """Isolate original populated pixels in one fixed, never-recropped square."""
    x1, y1, x2, y2 = SOURCE_BOUNDS
    source = populated_rgb[y1:y2, x1:x2].copy()
    clean = registered_clear_rgb[y1:y2, x1:x2]
    if source.shape[:2] != (SPRITE_SIZE, SPRITE_SIZE):
        raise AssertionError(f"Unexpected fixed source shape: {source.shape}")

    red, green, blue = (source[:, :, channel].astype(np.int16) for channel in range(3))
    dominance = red - np.maximum(green, blue)
    difference = np.max(np.abs(source.astype(np.int16) - clean.astype(np.int16)), axis=2)
    yy, xx = np.mgrid[0:SPRITE_SIZE, 0:SPRITE_SIZE]
    radius = np.hypot(
        xx + 0.5 - LOCAL_PIVOT[0],
        yy + 0.5 - LOCAL_PIVOT[1],
    )

    # The clean comparison rejects unchanged stationary artwork.  Thickness,
    # component area, and the fixed radial limit then reject grid/ring/flare noise.
    strong = (red > 40) & (dominance > 60) & (difference > 30) & (radius < 82.5)
    opened = cv2.morphologyEx(
        strong.astype(np.uint8),
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(opened, connectivity=8)

    clean_red, clean_green, clean_blue = (clean[:, :, channel].astype(np.int16) for channel in range(3))
    clean_dominance = clean_red - np.maximum(clean_green, clean_blue)
    clean_stationary = cv2.dilate(
        ((clean_red > 30) & (clean_dominance > 12)).astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )

    retained = np.zeros_like(opened)
    components: list[dict[str, object]] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < 300:
            continue
        component = labels == label
        stationary_overlap = float(np.mean(clean_stationary[component]))
        if stationary_overlap >= 0.35:
            continue
        retained[component] = 1
        components.append(
            {
                "area": area,
                "bbox_local": tuple(int(value) for value in stats[label, :4]),
                "centroid_local_qc_only": tuple(float(value) for value in centroids[label]),
                "registered_clear_overlap": stationary_overlap,
                "median_populated_clear_difference": float(np.median(difference[component])),
            }
        )

    components.sort(key=lambda item: int(item["area"]), reverse=True)
    if len(components) != 6:
        raise AssertionError(f"Expected six emblem components, retained {len(components)}: {components}")

    grown_support = cv2.dilate(
        retained,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
    )
    permissive = (red > 24) & (dominance > 8) & (difference > 15) & (radius < 83.0)
    silhouette = (permissive & (grown_support > 0)) | (retained > 0)
    silhouette = cv2.morphologyEx(
        silhouette.astype(np.uint8),
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )
    silhouette = fill_small_holes(silhouette, maximum_area=96)

    # Keep only shapes grown from the six qualified source components.
    final_count, final_labels, _, _ = cv2.connectedComponentsWithStats(silhouette, connectivity=8)
    final_mask = np.zeros_like(silhouette)
    for label in range(1, final_count):
        component = final_labels == label
        if np.any(retained[component]):
            final_mask[component] = 1

    alpha = cv2.GaussianBlur(final_mask.astype(np.float32) * 255.0, (0, 0), 0.55)
    alpha[alpha < 4.0] = 0.0
    alpha = np.clip(np.rint(alpha), 0, 255).astype(np.uint8)
    nonzero_y, nonzero_x = np.where(alpha > 0)
    if not len(nonzero_x):
        raise AssertionError("Extracted biohazard alpha is empty")
    maximum_radius = float(
        np.max(
            np.hypot(
                nonzero_x + 0.5 - LOCAL_PIVOT[0],
                nonzero_y + 0.5 - LOCAL_PIVOT[1],
            )
        )
    )
    if maximum_radius >= 86.0:
        raise AssertionError(f"Extracted alpha approaches protected scanner rings: radius={maximum_radius:.3f}")
    if np.any(alpha[[0, -1], :]) or np.any(alpha[:, [0, -1]]):
        raise AssertionError("Extracted alpha touches the fixed-square boundary")

    rgba = np.dstack((source, alpha))
    sprite = Image.fromarray(rgba, "RGBA")
    identity_ok = bool(np.array_equal(rgba[:, :, :3][alpha > 0], source[alpha > 0]))
    if not identity_ok:
        raise AssertionError("Sprite RGB no longer maps identically to populated source pixels")

    mask_120 = np.array(
        Image.fromarray((final_mask * 255).astype(np.uint8), "L").rotate(
            120,
            resample=Image.Resampling.NEAREST,
            expand=False,
            center=LOCAL_PIVOT,
        )
    ) > 0
    binary = final_mask > 0
    symmetry_dice = float(2 * np.count_nonzero(binary & mask_120) / (np.count_nonzero(binary) + np.count_nonzero(mask_120)))

    diagnostics: dict[str, object] = {
        "strong_candidate_pixels": int(np.count_nonzero(strong)),
        "final_binary_pixels": int(np.count_nonzero(final_mask)),
        "alpha_nonzero_pixels": int(np.count_nonzero(alpha)),
        "alpha_maximum_radius": maximum_radius,
        "rotation_symmetry_dice_120deg": symmetry_dice,
        "source_rgb_identity": identity_ok,
        "difference_minimum_on_strong_candidates": int(np.min(difference[strong])),
    }
    return sprite, alpha, components, diagnostics


def build_stationary_background(
    populated_rgb: np.ndarray,
    registered_clear_rgb: np.ndarray,
    sprite_alpha: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, tuple[int, int, int]]:
    """Restore only the hidden emblem footprint; outer scanner art stays original."""
    vx1, vy1, vx2, vy2 = VIEW_BOUNDS
    populated_view = populated_rgb[vy1:vy2, vx1:vx2].copy()
    clean_view = registered_clear_rgb[vy1:vy2, vx1:vx2].copy()

    yy_global, xx_global = np.mgrid[vy1:vy2, vx1:vx2]
    radial = np.hypot(
        xx_global + 0.5 - SOURCE_HUB[0],
        yy_global + 0.5 - SOURCE_HUB[1],
    )
    dark_annulus = (
        (radial >= 84.0)
        & (radial <= 89.0)
        & (np.max(populated_view, axis=2) < 80)
        & (np.max(clean_view, axis=2) < 80)
    )
    tone_offset = np.rint(
        np.median(populated_view[dark_annulus], axis=0)
        - np.median(clean_view[dark_annulus], axis=0)
    ).astype(np.int16)
    clean_view = np.clip(clean_view.astype(np.int16) + tone_offset, 0, 255).astype(np.uint8)

    restoration = np.zeros((VIEW_SIZE[1], VIEW_SIZE[0]), dtype=np.uint8)
    px, py = VIEW_SOURCE_PASTE
    restoration[py:py + SPRITE_SIZE, px:px + SPRITE_SIZE] = (sprite_alpha > 0).astype(np.uint8)
    restoration = cv2.dilate(
        restoration,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    )
    restoration[radial >= 85.0] = 0
    restoration_soft = cv2.GaussianBlur(restoration.astype(np.float32), (0, 0), 0.65)
    restoration_soft[radial >= 85.0] = 0.0
    blend = restoration_soft[:, :, None]
    stationary = np.rint(populated_view * (1.0 - blend) + clean_view * blend).clip(0, 255).astype(np.uint8)

    protected = radial >= 85.0
    if not np.array_equal(stationary[protected], populated_view[protected]):
        raise AssertionError("Protected outer scanner/ring pixels changed while clearing the emblem")
    return stationary, restoration_soft, tuple(int(value) for value in tone_offset)


def build_ring_detail_mask(populated_rgb: np.ndarray) -> np.ndarray:
    """Select fixed approved ring pixels whose brightness may be illuminated."""
    vx1, vy1, vx2, vy2 = VIEW_BOUNDS
    view = populated_rgb[vy1:vy2, vx1:vx2]
    red, green, blue = (view[:, :, channel].astype(np.int16) for channel in range(3))
    yy, xx = np.mgrid[0:VIEW_SIZE[1], 0:VIEW_SIZE[0]]
    radius = np.hypot(
        xx + vx1 + 0.5 - POPULATED_RING_CENTER[0],
        yy + vy1 + 0.5 - POPULATED_RING_CENTER[1],
    )
    ring_bands = ((radius >= 96.0) & (radius <= 114.0)) | ((radius >= 120.0) & (radius <= 124.0))
    return (
        ring_bands
        & (red > 25)
        & ((red - np.maximum(green, blue)) > 10)
    )


def build_scanner_atmosphere_base(populated_rgb: np.ndarray) -> dict[str, np.ndarray]:
    """Build one fixed scanner-coordinate smoke texture; frames vary opacity only."""
    vx1, vy1, vx2, vy2 = VIEW_BOUNDS
    view = populated_rgb[vy1:vy2, vx1:vx2]
    red, green, blue = (view[:, :, channel].astype(np.int16) for channel in range(3))
    yy, xx = np.mgrid[0:VIEW_SIZE[1], 0:VIEW_SIZE[0]]
    px = xx + 0.5
    py = yy + 0.5
    scanner_center = (
        POPULATED_RING_CENTER[0] - VIEW_BOUNDS[0],
        POPULATED_RING_CENTER[1] - VIEW_BOUNDS[1],
    )
    radius = np.hypot(px - scanner_center[0], py - scanner_center[1])
    angle = np.arctan2(py - scanner_center[1], px - scanner_center[0])
    radial_support = (
        (radius >= ATMOSPHERE_RADIAL_BOUNDS[0])
        & (radius <= ATMOSPHERE_RADIAL_BOUNDS[1])
    )
    radial_envelope = np.exp(-0.5 * ((radius - ATMOSPHERE_RADIUS) / ATMOSPHERE_SIGMA) ** 2)
    radial_envelope[~radial_support] = 0.0

    # Fixed multiscale noise breaks the annulus into soft contaminated wisps.
    # The RNG is instantiated exactly once and is never sampled in the frame loop.
    rng = np.random.default_rng(ATMOSPHERE_NOISE_SEED)
    noise = rng.standard_normal((VIEW_SIZE[1], VIEW_SIZE[0])).astype(np.float32)
    coarse = cv2.GaussianBlur(noise, (0, 0), 8.0)
    fine = cv2.GaussianBlur(noise, (0, 0), 3.0)

    def fixed_percentile_normalize(field: np.ndarray) -> np.ndarray:
        low, high = np.percentile(field[radial_support], (6.0, 94.0))
        if high <= low:
            raise AssertionError("Degenerate fixed atmosphere noise normalization")
        return smoothstep01((field - low) / (high - low))

    coarse_normalized = fixed_percentile_normalize(coarse)
    fine_normalized = fixed_percentile_normalize(fine)
    multiscale = 0.72 * coarse_normalized + 0.28 * fine_normalized
    wisps = smoothstep01((multiscale - 0.15) / 0.74)

    lower_left = np.exp(-0.5 * (wrapped_angle_delta(angle, 3.0 * math.pi / 4.0) / 0.60) ** 2)
    lower_side = np.exp(-0.5 * (wrapped_angle_delta(angle, 0.62 * math.pi) / 0.78) ** 2)
    asymmetric_envelope = np.clip(0.74 + 0.22 * lower_left + 0.08 * lower_side, 0.0, 1.0)

    border_distance = np.minimum.reduce((px, VIEW_SIZE[0] - px, py, VIEW_SIZE[1] - py))
    viewport_edge_fade = smoothstep01(border_distance / 5.0)

    # Red scanner strokes and the main crosshair remain readable.  The smoke
    # occupies their negative space and reaches red detail only shallowly.
    fixed_red_detail = (
        (red > 22)
        & ((red - np.maximum(green, blue)) > 8)
        & radial_support
    )
    fixed_red_detail = cv2.dilate(
        fixed_red_detail.astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    ) > 0
    fixed_crosshair = (
        (np.abs(px - scanner_center[0]) <= 1.25)
        | (np.abs(py - scanner_center[1]) <= 1.25)
    ) & radial_support
    protected_detail = fixed_red_detail | fixed_crosshair
    red_detail_attenuation = np.ones_like(radius, dtype=np.float32)
    red_detail_attenuation[fixed_red_detail] = 0.13
    red_detail_attenuation[fixed_crosshair] = 0.04
    shadow_detail_attenuation = np.ones_like(radius, dtype=np.float32)
    shadow_detail_attenuation[fixed_red_detail] = 0.18
    shadow_detail_attenuation[fixed_crosshair] = 0.04

    foundation_base = (
        radial_envelope
        * asymmetric_envelope
        * (0.76 + 0.24 * coarse_normalized)
        * viewport_edge_fade
        * red_detail_attenuation
    ).astype(np.float32)
    red_base = (
        radial_envelope
        * asymmetric_envelope
        * (0.58 + 0.42 * wisps)
        * viewport_edge_fade
        * red_detail_attenuation
    ).astype(np.float32)
    shadow_radial = (
        0.58 * np.exp(-0.5 * ((radius - ATMOSPHERE_SHADOW_RADIUS) / ATMOSPHERE_SHADOW_SIGMA) ** 2)
        + 0.42 * np.exp(-0.5 * ((radius - 130.0) / 4.8) ** 2)
    )
    shadow_base = (
        shadow_radial
        * radial_support
        * asymmetric_envelope
        * (0.52 + 0.48 * (1.0 - 0.50 * coarse_normalized))
        * viewport_edge_fade
        * shadow_detail_attenuation
    ).astype(np.float32)
    phase_map = (
        0.46 * (coarse_normalized - 0.5)
        + 0.18 * np.sin(3.0 * angle + math.pi * fine_normalized)
    ).astype(np.float32)
    return {
        "radius": radius.astype(np.float32),
        "angle": angle.astype(np.float32),
        "foundation_base": foundation_base,
        "red_base": red_base,
        "shadow_base": shadow_base,
        "phase_map": phase_map,
        "radial_support": radial_support,
        "protected_detail": protected_detail,
    }


def atmosphere_fade_value(frame_index: int) -> float:
    return 0.5 - 0.5 * math.cos(math.tau * frame_index / FRAME_COUNT)


def scanner_atmosphere(
    stationary_rgb: np.ndarray,
    frame_index: int,
    base: dict[str, np.ndarray],
    enabled: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, float | int | bool]]:
    """Apply bounded dark-red haze and black shaping without spatial resampling."""
    if not enabled:
        zeros = np.zeros(stationary_rgb.shape[:2], dtype=np.uint8)
        return stationary_rgb.copy(), zeros, zeros, zeros.astype(bool), {
            "enabled": False,
            "fade": atmosphere_fade_value(frame_index),
            "changed_pixels": 0,
            "maximum_channel_drop": 0,
            "maximum_channel_gain": 0,
            "new_zero_channels": 0,
            "new_saturated_channels": 0,
        }

    t = frame_index / FRAME_COUNT
    phase = -math.pi / 2.0 - math.tau * t
    angle = base["angle"]
    phase_map = base["phase_map"]
    main_arc = np.exp(
        -0.5 * (wrapped_angle_delta(angle, phase + 0.55) / 0.48) ** 2
    )
    trailing_arc = np.exp(
        -0.5 * (wrapped_angle_delta(angle, phase + 0.95) / 0.75) ** 2
    )
    secondary_arc = np.exp(
        -0.5 * (wrapped_angle_delta(angle, phase + 2.30) / 0.34) ** 2
    )
    counter_arc = np.exp(
        -0.5 * (wrapped_angle_delta(angle, phase - 1.90) / 0.34) ** 2
    )
    dark_arc = np.exp(
        -0.5 * (wrapped_angle_delta(angle, phase - 0.40) / 0.50) ** 2
    )
    local_fade = 0.5 + 0.5 * np.sin(math.tau * t - angle + phase_map)
    fade = atmosphere_fade_value(frame_index)
    foundation_temporal = 0.92 + 0.08 * local_fade
    red_segments = np.clip(
        0.68 * main_arc
        + 0.24 * trailing_arc
        + 0.34 * (fade * secondary_arc + (1.0 - fade) * counter_arc),
        0.0,
        1.0,
    )
    shadow_temporal = np.clip(
        0.18 + 0.72 * dark_arc + 0.10 * (1.0 - local_fade),
        0.0,
        1.0,
    )

    red_alpha = np.clip(
        np.rint(
            42.0 * base["foundation_base"] * foundation_temporal
            + 80.0 * base["red_base"] * red_segments
        ),
        0,
        ATMOSPHERE_RED_ALPHA_MAX,
    ).astype(np.uint8)
    shadow_alpha = np.clip(
        np.rint(ATMOSPHERE_BLACK_ALPHA_MAX * base["shadow_base"] * shadow_temporal),
        0,
        ATMOSPHERE_BLACK_ALPHA_MAX,
    ).astype(np.uint8)
    red_alpha[red_alpha < 3] = 0
    shadow_alpha[shadow_alpha < 2] = 0
    support = (red_alpha > 0) | (shadow_alpha > 0)
    if np.any(support & ~base["radial_support"]):
        raise AssertionError("Atmosphere escaped its fixed radial support")

    red_haze = solid_alpha_blend_rgb(stationary_rgb, ATMOSPHERE_RED, red_alpha)
    atmospheric_rgb = solid_alpha_blend_rgb(red_haze, (0, 0, 0), shadow_alpha)
    # Recompute the documented pointwise blend; equality proves no scanner
    # sample was translated, rotated, blurred, or otherwise spatially sampled.
    reproduced = solid_alpha_blend_rgb(
        solid_alpha_blend_rgb(stationary_rgb, ATMOSPHERE_RED, red_alpha),
        (0, 0, 0),
        shadow_alpha,
    )
    if not np.array_equal(atmospheric_rgb, reproduced):
        raise AssertionError("Atmosphere is not a purely pointwise radiometric blend")
    if not np.array_equal(atmospheric_rgb[~support], stationary_rgb[~support]):
        raise AssertionError("Atmosphere changed pixels outside its declared support")

    delta = atmospheric_rgb.astype(np.int16) - stationary_rgb.astype(np.int16)
    negative = -delta[delta < 0]
    positive = delta[delta > 0]
    new_zero_channels = int(np.count_nonzero((atmospheric_rgb == 0) & (stationary_rgb > 0)))
    new_saturated_channels = int(
        np.count_nonzero((atmospheric_rgb == 255) & (stationary_rgb < 255))
    )
    maximum_drop = int(np.max(negative)) if negative.size else 0
    maximum_gain = int(np.max(positive)) if positive.size else 0
    if maximum_drop > 48:
        raise AssertionError(f"Atmosphere shadow is too strong: channel drop={maximum_drop}")
    if maximum_gain > 24:
        raise AssertionError(f"Atmosphere red emission is too strong: channel gain={maximum_gain}")
    if new_zero_channels or new_saturated_channels:
        raise AssertionError(
            "Atmosphere introduced clipped channels: "
            f"zeros={new_zero_channels}, saturation={new_saturated_channels}"
        )
    stats: dict[str, float | int | bool] = {
        "enabled": True,
        "fade": fade,
        "changed_pixels": int(np.count_nonzero(np.any(delta != 0, axis=2))),
        "maximum_channel_drop": maximum_drop,
        "mean_channel_drop": float(np.mean(negative)) if negative.size else 0.0,
        "p99_channel_drop": float(np.percentile(negative, 99.0)) if negative.size else 0.0,
        "maximum_channel_gain": maximum_gain,
        "mean_channel_gain": float(np.mean(positive)) if positive.size else 0.0,
        "p99_channel_gain": float(np.percentile(positive, 99.0)) if positive.size else 0.0,
        "new_zero_channels": new_zero_channels,
        "new_saturated_channels": new_saturated_channels,
    }
    return atmospheric_rgb, red_alpha, shadow_alpha, support, stats


def scanner_illumination(
    frame_index: int,
    ring_detail_mask: np.ndarray,
) -> tuple[Image.Image, np.ndarray, tuple[float, float]]:
    """Create only transparent light; the approved scanner pixels never move."""
    t = frame_index / FRAME_COUNT
    angle = -math.pi / 2.0 - math.tau * t
    scanner_center = (
        POPULATED_RING_CENTER[0] - VIEW_BOUNDS[0],
        POPULATED_RING_CENTER[1] - VIEW_BOUNDS[1],
    )
    flare = (
        scanner_center[0] + math.cos(angle) * SCANNER_FLARE_RADIUS,
        scanner_center[1] + math.sin(angle) * SCANNER_FLARE_RADIUS,
    )

    yy, xx = np.mgrid[0:VIEW_SIZE[1], 0:VIEW_SIZE[0]]
    px = xx + 0.5
    py = yy + 0.5
    pixel_angle = np.arctan2(py - scanner_center[1], px - scanner_center[0])
    angle_delta = np.arctan2(np.sin(pixel_angle - angle), np.cos(pixel_angle - angle))
    radial_distance = np.hypot(px - scanner_center[0], py - scanner_center[1])
    radial_delta = radial_distance - SCANNER_FLARE_RADIUS

    # Brighten only existing approved ring-detail pixels near the passing flare.
    ring_weight = np.exp(-0.5 * (angle_delta / 0.13) ** 2)
    ring_weight[np.abs(angle_delta) > 0.39] = 0.0
    ring_alpha = ring_detail_mask.astype(np.float32) * ring_weight * 20.0

    # Tight polar-coordinate flare, truncated at three sigma to prevent bloom.
    body = 18.0 * np.exp(
        -0.5 * (radial_delta / 5.0) ** 2
        -0.5 * (angle_delta / 0.075) ** 2
    )
    body[(np.abs(radial_delta) > 15.0) | (np.abs(angle_delta) > 0.225)] = 0.0
    core = 36.0 * np.exp(
        -0.5 * (radial_delta / 2.0) ** 2
        -0.5 * (angle_delta / 0.028) ** 2
    )
    core[(np.abs(radial_delta) > 6.0) | (np.abs(angle_delta) > 0.084)] = 0.0
    alpha = np.clip(np.rint(ring_alpha + body + core), 0, 74).astype(np.uint8)
    rgba = np.zeros((VIEW_SIZE[1], VIEW_SIZE[0], 4), dtype=np.uint8)
    rgba[:, :, :3] = (255, 48, 38)
    rgba[:, :, 3] = alpha
    return Image.fromarray(rgba, "RGBA"), alpha, flare


def render_frame(
    stationary_rgb: np.ndarray,
    sprite: Image.Image,
    frame_index: int,
    ring_detail_mask: np.ndarray,
    atmosphere_base: dict[str, np.ndarray],
    atmosphere_enabled: bool = True,
    emblem_view_paste: tuple[int, int] = VIEW_PASTE,
) -> tuple[
    Image.Image,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    tuple[float, float],
    dict[str, float | int | bool],
    dict[str, float | int | bool],
]:
    """Use one invariant fixed-square transform path for every frame, including zero."""
    degrees = 360.0 * frame_index / FRAME_COUNT
    rotated = sprite.rotate(
        -degrees,
        resample=Image.Resampling.BICUBIC,
        expand=False,
        center=LOCAL_PIVOT,
    )
    (
        atmospheric_rgb,
        atmosphere_red_alpha,
        atmosphere_shadow_alpha,
        atmosphere_support,
        atmosphere_stats,
    ) = scanner_atmosphere(
        stationary_rgb,
        frame_index,
        atmosphere_base,
        enabled=atmosphere_enabled,
    )
    illumination, illumination_alpha, flare = scanner_illumination(frame_index, ring_detail_mask)
    illuminated_rgb = screen_blend_rgb(atmospheric_rgb, np.array(illumination))

    # The breathing light sits behind the original sprite so its blood/grunge
    # RGB pixels are never brightened or washed out.
    rotated_alpha_image = rotated.getchannel("A")
    rotated_alpha = np.array(rotated_alpha_image)
    binary_alpha = Image.fromarray(((rotated_alpha > 0) * 255).astype(np.uint8), "L")
    edge_profile = np.array(binary_alpha.filter(ImageFilter.GaussianBlur(1.35))).astype(np.float32)
    bounded_edge = cv2.dilate(
        (rotated_alpha > 0).astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)),
    ) > 0
    edge_profile[(rotated_alpha > 0) | ~bounded_edge] = 0.0
    profile_peak = float(np.max(edge_profile))
    breath = 0.5 - 0.5 * math.cos(math.tau * frame_index / FRAME_COUNT)
    glow_peak_alpha = 10.0 + 9.0 * breath
    if profile_peak > 0.0:
        glow_alpha = np.clip(
            np.rint(edge_profile / profile_peak * glow_peak_alpha),
            0,
            19,
        ).astype(np.uint8)
    else:
        glow_alpha = np.zeros_like(rotated_alpha)

    emblem_alpha_view = np.zeros((VIEW_SIZE[1], VIEW_SIZE[0]), dtype=np.uint8)
    glow_alpha_view = np.zeros((VIEW_SIZE[1], VIEW_SIZE[0]), dtype=np.uint8)
    px, py = emblem_view_paste
    emblem_alpha_view[py:py + SPRITE_SIZE, px:px + SPRITE_SIZE] = rotated_alpha
    glow_alpha_view[py:py + SPRITE_SIZE, px:px + SPRITE_SIZE] = glow_alpha

    # Keep the emblem-edge glow off the approved scanner strokes.  This mask is
    # fixed in scanner coordinates and never follows the moved emblem.
    protected_ring_detail = cv2.dilate(
        ring_detail_mask.astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    ) > 0
    glow_alpha_view[protected_ring_detail] = 0
    glow_overlay = np.zeros((VIEW_SIZE[1], VIEW_SIZE[0], 4), dtype=np.uint8)
    glow_overlay[:, :, :3] = (235, 32, 27)
    glow_overlay[:, :, 3] = glow_alpha_view
    lit_rgb = screen_blend_rgb(illuminated_rgb, glow_overlay)

    declared_light_support = (illumination_alpha > 0) | (glow_alpha_view > 0)
    total_radiometric_support = atmosphere_support | declared_light_support
    if not np.array_equal(lit_rgb[~total_radiometric_support], stationary_rgb[~total_radiometric_support]):
        raise AssertionError("Radiometric layers changed pixels outside declared support")
    lighting_delta = lit_rgb.astype(np.int16) - atmospheric_rgb.astype(np.int16)
    if np.any(lighting_delta < 0):
        raise AssertionError("Flare/glow darkened the atmosphere-adjusted scanner")

    frame = Image.fromarray(lit_rgb, "RGB").convert("RGBA")
    frame.alpha_composite(rotated, emblem_view_paste)
    frame_rgb = np.array(frame.convert("RGB"))
    rotated_rgba = np.array(rotated)
    output_region = frame_rgb[py:py + SPRITE_SIZE, px:px + SPRITE_SIZE]
    opaque = rotated_alpha == 255
    if not np.array_equal(output_region[opaque], rotated_rgba[:, :, :3][opaque]):
        raise AssertionError("Lighting altered opaque emblem/grunge RGB pixels")

    changed_channels = lighting_delta[lighting_delta > 0]
    lighting_stats: dict[str, float | int | bool] = {
        "no_channel_darkening": True,
        "changed_pixels": int(np.count_nonzero(np.any(lighting_delta > 0, axis=2))),
        "maximum_channel_delta": int(np.max(lighting_delta)),
        "mean_positive_channel_delta": (
            float(np.mean(changed_channels)) if changed_channels.size else 0.0
        ),
        "p99_positive_channel_delta": (
            float(np.percentile(changed_channels, 99.0)) if changed_channels.size else 0.0
        ),
        "new_saturated_channels": int(
            np.count_nonzero((lit_rgb == 255) & (stationary_rgb < 255))
        ),
    }
    return (
        Image.fromarray(frame_rgb, "RGB"),
        emblem_alpha_view,
        illumination_alpha,
        glow_alpha_view,
        atmosphere_red_alpha,
        atmosphere_shadow_alpha,
        atmosphere_support,
        flare,
        lighting_stats,
        atmosphere_stats,
    )


def render_unlit_control(
    stationary_rgb: np.ndarray,
    sprite: Image.Image,
    view_paste: tuple[int, int],
) -> Image.Image:
    """Render a zero-degree centering control with every illumination layer off."""
    rotated = sprite.rotate(
        0.0,
        resample=Image.Resampling.BICUBIC,
        expand=False,
        center=LOCAL_PIVOT,
    )
    frame = Image.fromarray(stationary_rgb, "RGB").convert("RGBA")
    frame.alpha_composite(rotated, view_paste)
    return frame.convert("RGB")


def checkerboard(size: tuple[int, int], tile: int = 12) -> Image.Image:
    board = Image.new("RGBA", size, (28, 28, 28, 255))
    draw = ImageDraw.Draw(board)
    for y in range(0, size[1], tile):
        for x in range(0, size[0], tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle((x, y, min(x + tile - 1, size[0] - 1), min(y + tile - 1, size[1] - 1)), fill=(55, 55, 55, 255))
    return board


def labeled_panel(image: Image.Image, label: str, panel_size: tuple[int, int] = (201, 225)) -> Image.Image:
    font = ImageFont.load_default()
    panel = Image.new("RGB", panel_size, (3, 6, 7))
    draw = ImageDraw.Draw(panel)
    draw.text((8, 7), label, font=font, fill=(235, 235, 235))
    available = (panel_size[0] - 20, panel_size[1] - 34)
    shown = image.convert("RGBA").copy()
    shown.thumbnail(available, Image.Resampling.LANCZOS)
    if shown.mode == "RGBA":
        backing = checkerboard(shown.size)
        backing.alpha_composite(shown)
        shown_rgb = backing.convert("RGB")
    else:
        shown_rgb = shown.convert("RGB")
    x = (panel_size[0] - shown_rgb.width) // 2
    y = 28 + (available[1] - shown_rgb.height) // 2
    panel.paste(shown_rgb, (x, y))
    return panel


def make_source_reference_sheet(
    populated_rgb: np.ndarray,
    registered_clear_rgb: np.ndarray,
    sprite: Image.Image,
    reference: Image.Image,
) -> Image.Image:
    x1, y1, x2, y2 = SOURCE_BOUNDS
    panels = (
        labeled_panel(Image.fromarray(populated_rgb[y1:y2, x1:x2], "RGB"), "POPULATED FIXED SOURCE"),
        labeled_panel(Image.fromarray(registered_clear_rgb[y1:y2, x1:x2], "RGB"), "REGISTERED CLEAR COMPARISON"),
        labeled_panel(sprite, f"ISOLATED {SPRITE_SIZE}x{SPRITE_SIZE} SPRITE"),
        labeled_panel(reference, "SUPPLIED APPEARANCE REFERENCE"),
    )
    sheet = Image.new("RGB", (sum(panel.width for panel in panels), max(panel.height for panel in panels)), (3, 6, 7))
    x = 0
    for panel in panels:
        sheet.paste(panel, (x, 0))
        x += panel.width
    return sheet


def make_keyframe_sheet(decoded_frames: dict[int, Image.Image]) -> Image.Image:
    columns = 2
    header = 34
    rows = 2
    sheet = Image.new("RGB", (VIEW_SIZE[0] * columns, (VIEW_SIZE[1] + header) * rows), (3, 6, 7))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, degrees in enumerate(KEYFRAME_DEGREES):
        frame_index = int(round(degrees * FRAME_COUNT / 360.0)) % FRAME_COUNT
        column = index % columns
        row = index // columns
        x = column * VIEW_SIZE[0]
        y = row * (VIEW_SIZE[1] + header)
        phase = frame_index / FRAME_COUNT
        fade = atmosphere_fade_value(frame_index)
        draw.text(
            (x + 8, y + 7),
            f"FRAME {frame_index} | PHASE {phase:.2f} | FADE {fade:.2f} | EMBLEM {degrees} DEG",
            font=font,
            fill=(235, 235, 235),
        )
        sheet.paste(decoded_frames[frame_index].convert("RGB"), (x, y + header))

        # Proof-only crosshair: its intersection is the mathematical local hub.
        hx = x + VIEW_HUB[0]
        hy = y + header + VIEW_HUB[1]
        draw.line((hx - 8, hy, hx + 8, hy), fill=(255, 240, 80), width=1)
        draw.line((hx, hy - 8, hx, hy + 8), fill=(255, 240, 80), width=1)
        draw.ellipse((hx - 2, hy - 2, hx + 2, hy + 2), outline=(255, 255, 255), width=1)
    return sheet


def make_centering_comparison(before: Image.Image, after: Image.Image) -> Image.Image:
    """Show the exact four-pixel translation using illumination-free controls."""
    header = 28
    sheet = Image.new("RGB", (VIEW_SIZE[0] * 2, VIEW_SIZE[1] + header), (3, 6, 7))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    panels = (
        (before.convert("RGB"), "BEFORE (UNLIT) | HUB Y 191.5", SOURCE_HUB),
        (after.convert("RGB"), "AFTER (UNLIT) | HUB Y 187.5 | DY -4", HUB),
    )
    for index, (frame, label, hub) in enumerate(panels):
        x = index * VIEW_SIZE[0]
        sheet.paste(frame, (x, header))
        draw.text((x + 8, 8), label, font=font, fill=(235, 235, 235))
        hx = x + hub[0] - VIEW_BOUNDS[0]
        hy = header + hub[1] - VIEW_BOUNDS[1]
        draw.line((hx - 8, hy, hx + 8, hy), fill=(255, 240, 80), width=1)
        draw.line((hx, hy - 8, hx, hy + 8), fill=(255, 240, 80), width=1)
        draw.ellipse((hx - 2, hy - 2, hx + 2, hy + 2), outline=(255, 255, 255), width=1)
        scanner_x = x + POPULATED_RING_CENTER[0] - VIEW_BOUNDS[0]
        scanner_y = header + POPULATED_RING_CENTER[1] - VIEW_BOUNDS[1]
        draw.line((scanner_x - 5, scanner_y, scanner_x + 5, scanner_y), fill=(80, 220, 255), width=1)
        draw.line((scanner_x, scanner_y - 5, scanner_x, scanner_y + 5), fill=(80, 220, 255), width=1)
    return sheet


def make_geometry_proof(unlit_final: Image.Image) -> Image.Image:
    """Label the exact fixed scanner and final emblem geometry without lighting bias."""
    header = 30
    legend_width = 455
    sheet = Image.new(
        "RGB",
        (VIEW_SIZE[0] + legend_width, max(VIEW_SIZE[1] + header, 330)),
        (3, 6, 7),
    )
    sheet.paste(unlit_final.convert("RGB"), (0, header))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text(
        (8, 9),
        "BIOHAZARD GEOMETRY PROOF - UNLIT / NO ATMOSPHERE / MARKERS NOT IN GIF",
        font=font,
        fill=(238, 238, 238),
    )

    # Destination fixed-square bounds and paste-origin marker.
    paste_x, paste_y = VIEW_PASTE
    draw.rectangle(
        (
            paste_x,
            header + paste_y,
            paste_x + SPRITE_SIZE,
            header + paste_y + SPRITE_SIZE,
        ),
        outline=(255, 90, 220),
        width=1,
    )
    draw.line(
        (paste_x - 8, header + paste_y, paste_x + 8, header + paste_y),
        fill=(255, 90, 220),
        width=2,
    )
    draw.line(
        (paste_x, header + paste_y - 8, paste_x, header + paste_y + 8),
        fill=(255, 90, 220),
        width=2,
    )

    scanner_x = POPULATED_RING_CENTER[0] - VIEW_BOUNDS[0]
    scanner_y = POPULATED_RING_CENTER[1] - VIEW_BOUNDS[1]
    draw.line(
        (scanner_x - 12, header + scanner_y, scanner_x + 12, header + scanner_y),
        fill=(70, 225, 255),
        width=2,
    )
    draw.line(
        (scanner_x, header + scanner_y - 12, scanner_x, header + scanner_y + 12),
        fill=(70, 225, 255),
        width=2,
    )
    draw.ellipse(
        (
            scanner_x - 5,
            header + scanner_y - 5,
            scanner_x + 5,
            header + scanner_y + 5,
        ),
        outline=(70, 225, 255),
        width=1,
    )

    pivot_x, pivot_y = VIEW_HUB
    draw.line(
        (pivot_x - 7, header + pivot_y - 7, pivot_x + 7, header + pivot_y + 7),
        fill=(255, 235, 70),
        width=2,
    )
    draw.line(
        (pivot_x - 7, header + pivot_y + 7, pivot_x + 7, header + pivot_y - 7),
        fill=(255, 235, 70),
        width=2,
    )
    draw.ellipse(
        (
            pivot_x - 3,
            header + pivot_y - 3,
            pivot_x + 3,
            header + pivot_y + 3,
        ),
        outline=(255, 255, 255),
        width=1,
    )

    legend_x = VIEW_SIZE[0] + 18
    lines = (
        ("CYAN  scanner-circle center", (70, 225, 255)),
        (f"  global={POPULATED_RING_CENTER}", (205, 215, 220)),
        (f"  view={(scanner_x, scanner_y)}", (205, 215, 220)),
        ("", (205, 215, 220)),
        ("YELLOW  final emblem center / pivot", (255, 235, 70)),
        (f"  global={HUB}", (205, 215, 220)),
        (f"  view={VIEW_HUB}", (205, 215, 220)),
        (f"  local fixed pivot={LOCAL_PIVOT}", (205, 215, 220)),
        ("", (205, 215, 220)),
        ("MAGENTA  exact destination paste origin", (255, 90, 220)),
        (f"  global={PASTE_ORIGIN}", (205, 215, 220)),
        (f"  view={VIEW_PASTE}", (205, 215, 220)),
        (f"  destination square={SPRITE_SIZE}x{SPRITE_SIZE}", (205, 215, 220)),
        ("", (205, 215, 220)),
        (f"source hub={SOURCE_HUB}  prior hub={PREVIOUS_HUB}", (205, 215, 220)),
        (f"prior -> final delta={ADDITIONAL_CENTERING_DELTA}", (205, 215, 220)),
        (f"source -> final delta={CENTERING_DELTA}", (205, 215, 220)),
        (f"source crop unchanged={SOURCE_BOUNDS}", (205, 215, 220)),
        (f"scale={SCALE:.1f}  bbox recenter=False  autoscale=False", (205, 215, 220)),
    )
    y = 44
    for label, color in lines:
        draw.text((legend_x, y), label, font=font, fill=color)
        y += 14
    return sheet


def make_gif_assembly_proof(
    decoded_frames: dict[int, Image.Image],
    emblem_bboxes: list[tuple[int, int, int, int]],
    gif_descriptors: list[tuple[int, int, int, int, bool, int, int, bool, bool]],
) -> Image.Image:
    """Show decoded frames alongside the exact invariant GIF assembly records."""
    columns = 2
    rows = 2
    panel_header = 54
    footer = 50
    panel_height = panel_header + VIEW_SIZE[1]
    sheet = Image.new(
        "RGB",
        (VIEW_SIZE[0] * columns, panel_height * rows + footer),
        (3, 6, 7),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    bbox_color = (80, 255, 130)
    pivot_color = (255, 235, 70)
    fixed_square_color = (255, 90, 220)

    for panel_index, frame_index in enumerate(EXPORT_PROOF_FRAMES):
        column = panel_index % columns
        row = panel_index // columns
        x = column * VIEW_SIZE[0]
        y = row * panel_height
        descriptor = gif_descriptors[frame_index]
        bbox = emblem_bboxes[frame_index]
        lines = (
            f"FRAME {frame_index:03d} | CANVAS={VIEW_SIZE[0]}x{VIEW_SIZE[1]} | GIF RECT={descriptor[:4]}",
            f"PASTE V={VIEW_PASTE} G={PASTE_ORIGIN}",
            f"PIVOT V={VIEW_HUB} G={HUB} L={LOCAL_PIVOT}",
            f"COMPOSITED EMBLEM ALPHA BBOX={bbox}",
        )
        for line_index, line in enumerate(lines):
            draw.text((x + 6, y + 4 + 12 * line_index), line, font=font, fill=(232, 235, 236))
        image_y = y + panel_header
        sheet.paste(decoded_frames[frame_index].convert("RGB"), (x, image_y))
        paste_x, paste_y = VIEW_PASTE
        draw.rectangle(
            (
                x + paste_x,
                image_y + paste_y,
                x + paste_x + SPRITE_SIZE - 1,
                image_y + paste_y + SPRITE_SIZE - 1,
            ),
            outline=fixed_square_color,
            width=1,
        )
        draw.line(
            (x + paste_x - 5, image_y + paste_y, x + paste_x + 5, image_y + paste_y),
            fill=fixed_square_color,
            width=1,
        )
        draw.line(
            (x + paste_x, image_y + paste_y - 5, x + paste_x, image_y + paste_y + 5),
            fill=fixed_square_color,
            width=1,
        )
        x1, y1, x2, y2 = bbox
        draw.rectangle(
            (x + x1, image_y + y1, x + x2 - 1, image_y + y2 - 1),
            outline=bbox_color,
            width=1,
        )
        pivot_x = x + VIEW_HUB[0]
        pivot_y = image_y + VIEW_HUB[1]
        draw.line((pivot_x - 6, pivot_y, pivot_x + 6, pivot_y), fill=pivot_color, width=1)
        draw.line((pivot_x, pivot_y - 6, pivot_x, pivot_y + 6), fill=pivot_color, width=1)

    footer_y = panel_height * rows + 7
    draw.text(
        (8, footer_y),
        "ALL 120 GIF IMAGE DESCRIPTORS=(0,0,370,250) | OPTIMIZE=FALSE | DISPOSAL=2",
        font=font,
        fill=(225, 225, 225),
    )
    draw.text(
        (8, footer_y + 15),
        "FIXED 181x181 SOURCE SQUARE | NO PRE-SAVE CROP | NO AUTOSCALE | NO PER-FRAME RECENTER",
        font=font,
        fill=(225, 225, 225),
    )
    draw.text(
        (8, footer_y + 30),
        "MAGENTA=FIXED PASTE SQUARE | GREEN=EMBLEM ALPHA BBOX | YELLOW=FIXED PIVOT (PROOF ONLY)",
        font=font,
        fill=(225, 225, 225),
    )
    return sheet


def main() -> None:
    require_inputs()
    input_hashes = {path: sha256_bytes(path.read_bytes()) for path in EXPECTED_INPUT_SHA256}
    for path, expected in EXPECTED_INPUT_SHA256.items():
        if input_hashes[path] != expected:
            raise AssertionError(
                f"Approved input changed: {path.name}={input_hashes[path]}, expected={expected}"
            )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not BEFORE_CENTERING_PATH.is_file():
        raise FileNotFoundError(
            f"Missing preserved before-centering proof: {BEFORE_CENTERING_PATH}"
        )
    before_centering_hash = sha256_bytes(BEFORE_CENTERING_PATH.read_bytes())
    if before_centering_hash != EXPECTED_BEFORE_CENTERING_SHA256:
        raise AssertionError(
            f"Preserved before-centering proof changed: {before_centering_hash}"
        )
    before_centering = Image.open(BEFORE_CENTERING_PATH).convert("RGB")
    if before_centering.size != VIEW_SIZE:
        raise AssertionError(f"Unexpected before-centering size: {before_centering.size}")

    if SOURCE_BOUNDS != (115, 101, 296, 282):
        raise AssertionError(f"Frozen source bounds changed: {SOURCE_BOUNDS}")
    if (HUB[0] - PASTE_ORIGIN[0], HUB[1] - PASTE_ORIGIN[1]) != LOCAL_PIVOT:
        raise AssertionError("Global destination hub and paste origin are no longer coupled")
    if (VIEW_HUB[0] - VIEW_PASTE[0], VIEW_HUB[1] - VIEW_PASTE[1]) != LOCAL_PIVOT:
        raise AssertionError("Viewport hub and paste origin are no longer coupled")

    populated_image = Image.open(POPULATED_PATH).convert("RGB")
    clear_image = Image.open(CLEAR_PATH).convert("RGB")
    if populated_image.size != (1727, 911) or clear_image.size != populated_image.size:
        raise AssertionError(
            f"Unexpected approved-master sizes: populated={populated_image.size}, clear={clear_image.size}"
        )
    populated_rgb = np.array(populated_image)
    clear_rgb = np.array(clear_image)
    registered_clear_rgb, registration_matrix = register_clear_to_populated(clear_rgb, populated_image.size)

    sprite, sprite_alpha, components, extraction = extract_fixed_sprite(populated_rgb, registered_clear_rgb)
    sprite_rgba_hash = sha256_array(np.array(sprite))
    sprite_alpha_hash = sha256_array(sprite_alpha)
    if sprite_rgba_hash != EXPECTED_SPRITE_RGBA_SHA256:
        raise AssertionError(f"Fixed sprite changed during centering work: {sprite_rgba_hash}")
    if sprite_alpha_hash != EXPECTED_SPRITE_ALPHA_SHA256:
        raise AssertionError(f"Fixed sprite alpha changed during centering work: {sprite_alpha_hash}")
    stationary_rgb, restoration_mask, tone_offset = build_stationary_background(
        populated_rgb,
        registered_clear_rgb,
        sprite_alpha,
    )
    stationary_hash = sha256_array(stationary_rgb)
    if stationary_hash != EXPECTED_STATIONARY_BACKGROUND_SHA256:
        raise AssertionError(f"Stationary scanner background changed unexpectedly: {stationary_hash}")
    ring_detail_mask = build_ring_detail_mask(populated_rgb)
    ring_detail_hash = sha256_array(ring_detail_mask.astype(np.uint8))
    atmosphere_base = build_scanner_atmosphere_base(populated_rgb)
    atmosphere_base_hash = sha256_array_sequence(
        [
            atmosphere_base["foundation_base"],
            atmosphere_base["red_base"],
            atmosphere_base["shadow_base"],
            atmosphere_base["phase_map"],
            atmosphere_base["radial_support"].astype(np.uint8),
            atmosphere_base["protected_detail"].astype(np.uint8),
        ]
    )

    source_control = render_unlit_control(stationary_rgb, sprite, VIEW_SOURCE_PASTE)
    previous_control = render_unlit_control(stationary_rgb, sprite, VIEW_PREVIOUS_PASTE)
    final_control = render_unlit_control(stationary_rgb, sprite, VIEW_PASTE)
    source_alpha_view = np.zeros((VIEW_SIZE[1], VIEW_SIZE[0]), dtype=np.uint8)
    previous_alpha_view = np.zeros((VIEW_SIZE[1], VIEW_SIZE[0]), dtype=np.uint8)
    destination_alpha_view = np.zeros((VIEW_SIZE[1], VIEW_SIZE[0]), dtype=np.uint8)
    source_px, source_py = VIEW_SOURCE_PASTE
    previous_px, previous_py = VIEW_PREVIOUS_PASTE
    destination_px, destination_py = VIEW_PASTE
    source_alpha_view[
        source_py:source_py + SPRITE_SIZE,
        source_px:source_px + SPRITE_SIZE,
    ] = sprite_alpha
    previous_alpha_view[
        previous_py:previous_py + SPRITE_SIZE,
        previous_px:previous_px + SPRITE_SIZE,
    ] = sprite_alpha
    destination_alpha_view[
        destination_py:destination_py + SPRITE_SIZE,
        destination_px:destination_px + SPRITE_SIZE,
    ] = sprite_alpha
    source_to_final_support = (source_alpha_view > 0) | (destination_alpha_view > 0)
    previous_to_final_support = (previous_alpha_view > 0) | (destination_alpha_view > 0)
    source_to_final_outside_unchanged = np.array_equal(
        np.array(source_control)[~source_to_final_support],
        np.array(final_control)[~source_to_final_support],
    )
    previous_to_final_outside_unchanged = np.array_equal(
        np.array(previous_control)[~previous_to_final_support],
        np.array(final_control)[~previous_to_final_support],
    )
    if not source_to_final_outside_unchanged or not previous_to_final_outside_unchanged:
        raise AssertionError("Centering controls changed pixels outside translated emblem support")
    expected_previous_from_final = np.zeros_like(destination_alpha_view)
    expected_previous_from_final[10:, :] = destination_alpha_view[:-10, :]
    if not np.array_equal(expected_previous_from_final, previous_alpha_view):
        raise AssertionError("Final zero-degree emblem alpha is not an exact -10 px translation")

    frames: list[Image.Image] = []
    emblem_alpha_union = np.zeros((VIEW_SIZE[1], VIEW_SIZE[0]), dtype=bool)
    illumination_alpha_union = np.zeros((VIEW_SIZE[1], VIEW_SIZE[0]), dtype=bool)
    glow_alpha_union = np.zeros((VIEW_SIZE[1], VIEW_SIZE[0]), dtype=bool)
    atmosphere_support_union = np.zeros((VIEW_SIZE[1], VIEW_SIZE[0]), dtype=bool)
    geometry_records: list[tuple[object, ...]] = []
    scanner_geometry_records: list[tuple[object, ...]] = []
    alpha_masses: list[float] = []
    radial_second_moments: list[float] = []
    illumination_alpha_maxima: list[int] = []
    glow_alpha_maxima: list[int] = []
    flare_positions: list[tuple[float, float]] = []
    emblem_alpha_frames: list[np.ndarray] = []
    illumination_alpha_frames: list[np.ndarray] = []
    glow_alpha_frames: list[np.ndarray] = []
    atmosphere_red_alpha_frames: list[np.ndarray] = []
    atmosphere_shadow_alpha_frames: list[np.ndarray] = []
    atmosphere_support_frames: list[np.ndarray] = []
    pre_atmosphere_control_arrays: list[np.ndarray] = []
    previous_control_arrays: list[np.ndarray] = []
    previous_emblem_alpha_frames: list[np.ndarray] = []
    previous_glow_alpha_frames: list[np.ndarray] = []
    lighting_stats_by_frame: list[dict[str, float | int | bool]] = []
    atmosphere_stats_by_frame: list[dict[str, float | int | bool]] = []
    view_yy, view_xx = np.mgrid[0:VIEW_SIZE[1], 0:VIEW_SIZE[0]]
    protected_glow_ring_detail = cv2.dilate(
        ring_detail_mask.astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    ) > 0
    view_radius_squared = (
        (view_xx + 0.5 - VIEW_HUB[0]) ** 2
        + (view_yy + 0.5 - VIEW_HUB[1]) ** 2
    )
    for frame_index in range(FRAME_COUNT):
        (
            frame,
            emblem_alpha,
            illumination_alpha,
            glow_alpha,
            atmosphere_red_alpha,
            atmosphere_shadow_alpha,
            atmosphere_support,
            flare,
            lighting_stats,
            atmosphere_stats,
        ) = render_frame(
            stationary_rgb,
            sprite,
            frame_index,
            ring_detail_mask,
            atmosphere_base,
            atmosphere_enabled=True,
        )
        (
            control_frame,
            control_emblem_alpha,
            control_illumination_alpha,
            control_glow_alpha,
            _,
            _,
            control_atmosphere_support,
            control_flare,
            _,
            _,
        ) = render_frame(
            stationary_rgb,
            sprite,
            frame_index,
            ring_detail_mask,
            atmosphere_base,
            atmosphere_enabled=False,
        )
        (
            previous_frame,
            previous_emblem_alpha,
            previous_illumination_alpha,
            previous_glow_alpha,
            _,
            _,
            previous_atmosphere_support,
            previous_flare,
            _,
            _,
        ) = render_frame(
            stationary_rgb,
            sprite,
            frame_index,
            ring_detail_mask,
            atmosphere_base,
            atmosphere_enabled=False,
            emblem_view_paste=VIEW_PREVIOUS_PASTE,
        )
        if (
            not np.array_equal(emblem_alpha, control_emblem_alpha)
            or not np.array_equal(illumination_alpha, control_illumination_alpha)
            or not np.array_equal(glow_alpha, control_glow_alpha)
            or np.any(control_atmosphere_support)
            or flare != control_flare
            or not np.array_equal(illumination_alpha, previous_illumination_alpha)
            or np.any(previous_atmosphere_support)
            or flare != previous_flare
        ):
            raise AssertionError(f"Atmosphere changed preserved subsystem state at frame {frame_index}")
        expected_previous_emblem = np.zeros_like(emblem_alpha)
        expected_previous_emblem[10:, :] = emblem_alpha[:-10, :]
        expected_previous_glow = np.zeros_like(glow_alpha)
        expected_previous_glow[10:, :] = glow_alpha[:-10, :]
        if not np.array_equal(previous_emblem_alpha, expected_previous_emblem):
            raise AssertionError(
                f"Rotating emblem alpha is not an exact -10 px translation at frame {frame_index}"
            )
        glow_translation_mismatch = previous_glow_alpha != expected_previous_glow
        if np.any(glow_translation_mismatch & ~protected_glow_ring_detail):
            raise AssertionError(
                "Breathing glow failed to follow the exact -10 px translation outside "
                f"the fixed scanner-ring protection mask at frame {frame_index}"
            )
        frames.append(frame)
        pre_atmosphere_control_arrays.append(np.array(control_frame))
        previous_control_arrays.append(np.array(previous_frame))
        emblem_alpha_union |= emblem_alpha > 0
        illumination_alpha_union |= illumination_alpha > 0
        glow_alpha_union |= glow_alpha > 0
        atmosphere_support_union |= atmosphere_support
        illumination_alpha_maxima.append(int(np.max(illumination_alpha)))
        glow_alpha_maxima.append(int(np.max(glow_alpha)))
        flare_positions.append(flare)
        emblem_alpha_frames.append(emblem_alpha)
        illumination_alpha_frames.append(illumination_alpha)
        glow_alpha_frames.append(glow_alpha)
        previous_emblem_alpha_frames.append(previous_emblem_alpha)
        previous_glow_alpha_frames.append(previous_glow_alpha)
        atmosphere_red_alpha_frames.append(atmosphere_red_alpha)
        atmosphere_shadow_alpha_frames.append(atmosphere_shadow_alpha)
        atmosphere_support_frames.append(atmosphere_support)
        lighting_stats_by_frame.append(lighting_stats)
        atmosphere_stats_by_frame.append(atmosphere_stats)
        weights = emblem_alpha.astype(np.float64) / 255.0
        mass = float(np.sum(weights))
        alpha_masses.append(mass)
        radial_second_moments.append(float(np.sum(weights * view_radius_squared) / mass))
        geometry_records.append((HUB, sprite.size, PASTE_ORIGIN, LOCAL_PIVOT, SCALE, VIEW_PASTE))
        scanner_geometry_records.append(
            (
                stationary_hash,
                ring_detail_hash,
                POPULATED_RING_CENTER,
                POPULATED_RING_RADIUS,
                (0, 0),
                0.0,
                1.0,
                False,
            )
        )
        if sha256_array(stationary_rgb) != stationary_hash:
            raise AssertionError(f"Stationary scanner background mutated before frame {frame_index}")

    emblem_bboxes: list[tuple[int, int, int, int]] = []
    for frame_index, alpha in enumerate(emblem_alpha_frames):
        nonzero_y, nonzero_x = np.where(alpha > 0)
        if not len(nonzero_x):
            raise AssertionError(f"Composited emblem alpha is empty at frame {frame_index}")
        emblem_bboxes.append(
            (
                int(np.min(nonzero_x)),
                int(np.min(nonzero_y)),
                int(np.max(nonzero_x)) + 1,
                int(np.max(nonzero_y)) + 1,
            )
        )
    expected_proof_bboxes = {
        0: (112, 52, 274, 200),
        15: (110, 58, 267, 215),
        30: (125, 54, 273, 216),
        45: (110, 52, 267, 209),
    }
    actual_proof_bboxes = {
        frame_index: emblem_bboxes[frame_index] for frame_index in EXPORT_PROOF_FRAMES
    }
    if actual_proof_bboxes != expected_proof_bboxes:
        raise AssertionError(
            "Placed emblem alpha bboxes changed before GIF assembly: "
            f"actual={actual_proof_bboxes}, expected={expected_proof_bboxes}"
        )

    pre_atmosphere_rgb_sequence_hash = sha256_array_sequence(pre_atmosphere_control_arrays)
    previous_pre_atmosphere_rgb_sequence_hash = sha256_array_sequence(previous_control_arrays)
    emblem_alpha_sequence_hash = sha256_array_sequence(emblem_alpha_frames)
    previous_emblem_alpha_sequence_hash = sha256_array_sequence(previous_emblem_alpha_frames)
    illumination_alpha_sequence_hash = sha256_array_sequence(illumination_alpha_frames)
    glow_alpha_sequence_hash = sha256_array_sequence(glow_alpha_frames)
    previous_glow_alpha_sequence_hash = sha256_array_sequence(previous_glow_alpha_frames)
    expected_sequence_hashes = {
        "previous-position pre-atmosphere RGB": (
            previous_pre_atmosphere_rgb_sequence_hash,
            EXPECTED_PRE_ATMOSPHERE_RGB_SEQUENCE_SHA256,
        ),
        "previous-position emblem alpha": (
            previous_emblem_alpha_sequence_hash,
            EXPECTED_EMBLEM_ALPHA_SEQUENCE_SHA256,
        ),
        "scanner illumination alpha": (
            illumination_alpha_sequence_hash,
            EXPECTED_SCANNER_ILLUMINATION_ALPHA_SEQUENCE_SHA256,
        ),
        "previous-position emblem glow alpha": (
            previous_glow_alpha_sequence_hash,
            EXPECTED_EMBLEM_GLOW_ALPHA_SEQUENCE_SHA256,
        ),
    }
    for sequence_name, (actual_hash, expected_hash) in expected_sequence_hashes.items():
        if actual_hash != expected_hash:
            raise AssertionError(
                f"Preserved {sequence_name} sequence changed: {actual_hash}, expected={expected_hash}"
            )

    atmosphere_state_hashes = [
        sha256_array_sequence(
            [
                atmosphere_red_alpha_frames[index],
                atmosphere_shadow_alpha_frames[index],
            ]
        )
        for index in range(FRAME_COUNT)
    ]
    unique_atmosphere_states = len(set(atmosphere_state_hashes))
    if unique_atmosphere_states != FRAME_COUNT:
        raise AssertionError(
            f"Atmosphere does not contain 120 unique fade states: {unique_atmosphere_states}"
        )
    raw_atmosphere_outside_support_unchanged = all(
        np.array_equal(
            np.array(frames[frame_index])[~atmosphere_support_frames[frame_index]],
            pre_atmosphere_control_arrays[frame_index][~atmosphere_support_frames[frame_index]],
        )
        for frame_index in range(FRAME_COUNT)
    )
    if not raw_atmosphere_outside_support_unchanged:
        raise AssertionError("Raw atmosphere output escaped its declared frame support")

    atmosphere_red_sequence_hash = sha256_array_sequence(atmosphere_red_alpha_frames)
    atmosphere_shadow_sequence_hash = sha256_array_sequence(atmosphere_shadow_alpha_frames)
    atmosphere_red_alpha_maxima = [int(np.max(alpha)) for alpha in atmosphere_red_alpha_frames]
    atmosphere_shadow_alpha_maxima = [
        int(np.max(alpha)) for alpha in atmosphere_shadow_alpha_frames
    ]
    atmosphere_support_counts = [
        int(np.count_nonzero(support)) for support in atmosphere_support_frames
    ]
    atmosphere_red_coverage_over_five = [
        int(np.count_nonzero(alpha > 5)) for alpha in atmosphere_red_alpha_frames
    ]
    atmosphere_fade_values = [atmosphere_fade_value(index) for index in range(FRAME_COUNT)]
    atmosphere_state_step_differences = [
        float(
            np.mean(
                np.abs(
                    atmosphere_red_alpha_frames[(index + 1) % FRAME_COUNT].astype(np.int16)
                    - atmosphere_red_alpha_frames[index].astype(np.int16)
                )
            )
            + np.mean(
                np.abs(
                    atmosphere_shadow_alpha_frames[(index + 1) % FRAME_COUNT].astype(np.int16)
                    - atmosphere_shadow_alpha_frames[index].astype(np.int16)
                )
            )
        )
        for index in range(FRAME_COUNT)
    ]
    if atmosphere_state_step_differences[-1] > max(atmosphere_state_step_differences[:-1]) * 1.10:
        raise AssertionError("Atmosphere loop seam exceeds ordinary adjacent fade motion")

    _, red_alpha_frame_120, shadow_alpha_frame_120, support_frame_120, _ = scanner_atmosphere(
        stationary_rgb,
        FRAME_COUNT,
        atmosphere_base,
        enabled=True,
    )
    atmosphere_state_closes_exactly = (
        np.array_equal(red_alpha_frame_120, atmosphere_red_alpha_frames[0])
        and np.array_equal(shadow_alpha_frame_120, atmosphere_shadow_alpha_frames[0])
        and np.array_equal(support_frame_120, atmosphere_support_frames[0])
    )
    if not atmosphere_state_closes_exactly:
        raise AssertionError("Atmosphere state does not close exactly at the 6-second boundary")

    atmosphere_radii = atmosphere_base["radius"][atmosphere_support_union]
    atmosphere_support_radius_range = (
        float(np.min(atmosphere_radii)),
        float(np.max(atmosphere_radii)),
    )
    if (
        atmosphere_support_radius_range[0] < ATMOSPHERE_RADIAL_BOUNDS[0]
        or atmosphere_support_radius_range[1] > ATMOSPHERE_RADIAL_BOUNDS[1]
    ):
        raise AssertionError(
            f"Atmosphere support radius escaped bounds: {atmosphere_support_radius_range}"
        )
    protected_detail_red_alpha_max = max(
        int(np.max(alpha[atmosphere_base["protected_detail"]]))
        for alpha in atmosphere_red_alpha_frames
    )
    protected_detail_shadow_alpha_max = max(
        int(np.max(alpha[atmosphere_base["protected_detail"]]))
        for alpha in atmosphere_shadow_alpha_frames
    )
    if len(set(geometry_records)) != 1:
        raise AssertionError("Frame geometry is not invariant")
    if len(set(scanner_geometry_records)) != 1:
        raise AssertionError("Scanner/ring geometry changed between frames")

    hub_delta = (
        HUB_PIXEL[0] - SOURCE_HUB_PIXEL[0],
        HUB_PIXEL[1] - SOURCE_HUB_PIXEL[1],
    )
    paste_delta = (
        PASTE_ORIGIN[0] - SOURCE_ORIGIN[0],
        PASTE_ORIGIN[1] - SOURCE_ORIGIN[1],
    )
    if hub_delta != CENTERING_DELTA or paste_delta != CENTERING_DELTA:
        raise AssertionError(
            f"Centering translation mismatch: hub={hub_delta}, paste={paste_delta}, requested={CENTERING_DELTA}"
        )
    incremental_hub_delta = (
        HUB[0] - PREVIOUS_HUB[0],
        HUB[1] - PREVIOUS_HUB[1],
    )
    incremental_paste_delta = (
        PASTE_ORIGIN[0] - PREVIOUS_PASTE_ORIGIN[0],
        PASTE_ORIGIN[1] - PREVIOUS_PASTE_ORIGIN[1],
    )
    if (
        incremental_hub_delta != ADDITIONAL_CENTERING_DELTA
        or incremental_paste_delta != ADDITIONAL_CENTERING_DELTA
    ):
        raise AssertionError(
            "The emblem hub and destination paste were not moved together by the exact "
            f"additional delta: hub={incremental_hub_delta}, paste={incremental_paste_delta}"
        )

    # Rotate a one-pixel marker centered exactly on the hub through every GIF
    # angle.  This is a transform probe only and is never composited into output.
    pivot_probe = np.zeros((SPRITE_SIZE, SPRITE_SIZE), dtype=np.uint8)
    pivot_probe[HUB_PIXEL[1] - PASTE_ORIGIN[1], HUB_PIXEL[0] - PASTE_ORIGIN[0]] = 255
    pivot_probe_image = Image.fromarray(pivot_probe, "L")
    pivot_probe_positions: set[tuple[int, int]] = set()
    for frame_index in range(FRAME_COUNT):
        probe_rotated = np.array(
            pivot_probe_image.rotate(
                -360.0 * frame_index / FRAME_COUNT,
                resample=Image.Resampling.NEAREST,
                expand=False,
                center=LOCAL_PIVOT,
            )
        )
        py, px = np.unravel_index(int(np.argmax(probe_rotated)), probe_rotated.shape)
        pivot_probe_positions.add((int(px), int(py)))
    expected_probe = (HUB_PIXEL[0] - PASTE_ORIGIN[0], HUB_PIXEL[1] - PASTE_ORIGIN[1])
    if pivot_probe_positions != {expected_probe}:
        raise AssertionError(f"Rotation transform moved the hub probe: {pivot_probe_positions}")

    # Build one global palette from representative phase states, then use it
    # unchanged for every GIF frame so stationary pixels cannot shimmer.
    palette_indices = (0, 30, 60, 90)
    palette_source = Image.new("RGB", (VIEW_SIZE[0], VIEW_SIZE[1] * len(palette_indices)))
    for palette_row, frame_index in enumerate(palette_indices):
        palette_source.paste(frames[frame_index], (0, palette_row * VIEW_SIZE[1]))
    palette = palette_source.quantize(
        colors=256,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    palette_bytes = bytes(palette.getpalette() or [])
    if len(palette_bytes) != 768:
        raise AssertionError(f"Unexpected global GIF palette length: {len(palette_bytes)}")
    palette_hash = sha256_bytes(palette_bytes)
    if any(frame.size != VIEW_SIZE or frame.mode != "RGB" for frame in frames):
        raise AssertionError("A raw animation frame is not a full-size RGB canvas before GIF encoding")
    encoded_frames = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    if any(frame.size != VIEW_SIZE or frame.mode != "P" for frame in encoded_frames):
        raise AssertionError("A quantized GIF frame changed canvas size before save")
    if any("transparency" in frame.info for frame in encoded_frames):
        raise AssertionError("Unexpected transparency metadata would permit delta-frame disposal")
    gif_path = OUT_DIR / f"{RUN_PREFIX}_6s.gif"
    gif_staging_path = OUT_DIR / f".{RUN_PREFIX}_6s.staging.gif"
    encoded_frames[0].save(
        gif_staging_path,
        format="GIF",
        save_all=True,
        append_images=encoded_frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=False,
        disposal=2,
        palette=palette_bytes,
    )

    decoded: dict[int, Image.Image] = {}
    decoded_arrays: list[np.ndarray] = []
    durations: list[int] = []
    disposals: list[int] = []
    pillow_tile_extents: list[tuple[int, int, int, int]] = []
    pillow_dispose_extents: list[tuple[int, int, int, int]] = []
    with Image.open(gif_staging_path) as gif:
        gif_format = gif.format
        gif_size = gif.size
        gif_frames = gif.n_frames
        gif_loop = gif.info.get("loop")
        for frame_index in range(gif.n_frames):
            gif.seek(frame_index)
            durations.append(int(gif.info.get("duration", 0)))
            disposals.append(int(getattr(gif, "disposal_method", 0)))
            if not gif.tile:
                raise AssertionError(f"GIF frame {frame_index} has no image tile")
            tile = gif.tile[0]
            tile_extents = tuple(getattr(tile, "extents", tile[1]))
            pillow_tile_extents.append(tile_extents)
            pillow_dispose_extents.append(tuple(gif.dispose_extent))
            actual = gif.convert("RGB").copy()
            decoded_arrays.append(np.array(actual))
            if frame_index in EXPORT_PROOF_FRAMES:
                decoded[frame_index] = actual

    if gif_format != "GIF" or gif_size != VIEW_SIZE or gif_frames != FRAME_COUNT:
        raise AssertionError(f"GIF validation failed: format={gif_format}, size={gif_size}, frames={gif_frames}")
    if gif_loop != 0 or set(durations) != {FRAME_DURATION_MS}:
        raise AssertionError(f"GIF timing validation failed: loop={gif_loop}, durations={set(durations)}")
    logical_screen_size, gif_descriptors, encoded_global_palette = parse_gif_frame_descriptors(
        gif_staging_path
    )
    full_canvas_descriptor = (0, 0, VIEW_SIZE[0], VIEW_SIZE[1])
    if logical_screen_size != VIEW_SIZE or len(gif_descriptors) != FRAME_COUNT:
        raise AssertionError(
            "GIF binary structure mismatch: "
            f"logical_screen={logical_screen_size}, descriptors={len(gif_descriptors)}"
        )
    if any(descriptor[:4] != full_canvas_descriptor for descriptor in gif_descriptors):
        bad = [
            (index, descriptor[:4])
            for index, descriptor in enumerate(gif_descriptors)
            if descriptor[:4] != full_canvas_descriptor
        ]
        raise AssertionError(f"GIF contains cropped/local frame rectangles: {bad[:8]}")
    if any(descriptor[4] for descriptor in gif_descriptors):
        raise AssertionError("GIF unexpectedly contains per-frame local color tables")
    if any(descriptor[5] != 2 for descriptor in gif_descriptors):
        raise AssertionError("GIF image descriptors do not all use disposal method 2")
    if any(descriptor[6] != FRAME_DURATION_MS // 10 for descriptor in gif_descriptors):
        raise AssertionError("GIF image descriptors do not all use the 50 ms delay")
    if any(descriptor[7] for descriptor in gif_descriptors):
        raise AssertionError("GIF unexpectedly interlaced one or more frames")
    if any(descriptor[8] for descriptor in gif_descriptors):
        raise AssertionError("GIF unexpectedly enabled frame transparency")
    if len(encoded_global_palette) != 768 or sha256_bytes(encoded_global_palette) != palette_hash:
        raise AssertionError("Encoded GIF global palette differs from the intended shared palette")
    if set(pillow_tile_extents) != {full_canvas_descriptor}:
        raise AssertionError(f"Pillow exposed local GIF tile extents: {set(pillow_tile_extents)}")
    if set(pillow_dispose_extents) != {full_canvas_descriptor}:
        raise AssertionError(
            f"Pillow exposed non-full disposal extents: {set(pillow_dispose_extents)}"
        )
    expected_encoded_rgb = [np.array(frame.convert("RGB")) for frame in encoded_frames]
    if not all(
        np.array_equal(decoded, expected)
        for decoded, expected in zip(decoded_arrays, expected_encoded_rgb)
    ):
        raise AssertionError("Decoded GIF frames differ from pre-save full-canvas quantized frames")

    # Publish only after the staged stream has passed binary rectangle, palette,
    # disposal, tile-extent, and decoded-pixel checks.
    gif_staging_path.replace(gif_path)

    animation_union = (
        emblem_alpha_union
        | illumination_alpha_union
        | glow_alpha_union
        | atmosphere_support_union
    )
    outside_union = ~animation_union
    stationary_outside_union = all(
        np.array_equal(frame[outside_union], decoded_arrays[0][outside_union])
        for frame in decoded_arrays[1:]
    )
    if not stationary_outside_union:
        raise AssertionError("Encoded GIF changed pixels outside all declared animation layers")

    pre_atmosphere_control_decoded_arrays = [
        np.array(
            Image.fromarray(control, "RGB")
            .quantize(palette=palette, dither=Image.Dither.NONE)
            .convert("RGB")
        )
        for control in pre_atmosphere_control_arrays
    ]
    decoded_atmosphere_outside_support_unchanged = all(
        np.array_equal(
            decoded_arrays[frame_index][~atmosphere_support_frames[frame_index]],
            pre_atmosphere_control_decoded_arrays[frame_index][
                ~atmosphere_support_frames[frame_index]
            ],
        )
        for frame_index in range(FRAME_COUNT)
    )
    if not decoded_atmosphere_outside_support_unchanged:
        raise AssertionError("Decoded atmosphere escaped its per-frame declared support")

    protected_ring = ring_detail_mask
    scanner_radius_view = np.hypot(
        view_xx + 0.5 - (POPULATED_RING_CENTER[0] - VIEW_BOUNDS[0]),
        view_yy + 0.5 - (POPULATED_RING_CENTER[1] - VIEW_BOUNDS[1]),
    )
    protected_outer_circumference = protected_ring & (scanner_radius_view >= 104.0)
    emblem_ring_overlap_pixels = int(np.count_nonzero(emblem_alpha_union & protected_ring))
    emblem_outer_circumference_overlap_pixels = int(
        np.count_nonzero(emblem_alpha_union & protected_outer_circumference)
    )
    illuminated_ring_pixels = int(np.count_nonzero(illumination_alpha_union & protected_ring))
    glow_ring_overlap_pixels = int(np.count_nonzero(glow_alpha_union & protected_ring))
    if emblem_outer_circumference_overlap_pixels != 0:
        raise AssertionError(
            "Rotating emblem overlaps the protected scanner circumference: "
            f"{emblem_outer_circumference_overlap_pixels} pixels"
        )
    if glow_ring_overlap_pixels != 0:
        raise AssertionError(
            f"Emblem-edge glow overlaps protected scanner-ring detail: {glow_ring_overlap_pixels} pixels"
        )

    stable_ring_counts: list[int] = []
    stable_ring_matches_control: list[bool] = []
    for frame_index, decoded_frame in enumerate(decoded_arrays):
        stable_ring = (
            protected_ring
            & ~atmosphere_support_frames[frame_index]
            & ~(illumination_alpha_frames[frame_index] > 0)
            & ~(emblem_alpha_frames[frame_index] > 0)
            & ~(glow_alpha_frames[frame_index] > 0)
        )
        stable_ring_counts.append(int(np.count_nonzero(stable_ring)))
        stable_ring_matches_control.append(
            np.array_equal(
                decoded_frame[stable_ring],
                pre_atmosphere_control_decoded_arrays[frame_index][stable_ring],
            )
        )
    scanner_ring_stable_pixels_match_control = all(stable_ring_matches_control)
    if min(stable_ring_counts) <= 0 or not scanner_ring_stable_pixels_match_control:
        raise AssertionError(
            "Stationary scanner-ring landmarks do not match the fixed control outside current light support"
        )

    stable_detail_counts: list[int] = []
    stable_detail_matches_control: list[bool] = []
    for frame_index, decoded_frame in enumerate(decoded_arrays):
        stable_detail = (
            atmosphere_base["protected_detail"]
            & ~atmosphere_support_frames[frame_index]
            & ~(illumination_alpha_frames[frame_index] > 0)
            & ~(emblem_alpha_frames[frame_index] > 0)
            & ~(glow_alpha_frames[frame_index] > 0)
        )
        stable_detail_counts.append(int(np.count_nonzero(stable_detail)))
        stable_detail_matches_control.append(
            np.array_equal(
                decoded_frame[stable_detail],
                pre_atmosphere_control_decoded_arrays[frame_index][stable_detail],
            )
        )
    fixed_detail_stable_pixels_match_control = all(stable_detail_matches_control)
    if min(stable_detail_counts) <= 0 or not fixed_detail_stable_pixels_match_control:
        raise AssertionError("Fixed ring/grid/crosshair landmarks changed outside radiometric support")
    flare_radii = [
        math.hypot(
            position[0] - (POPULATED_RING_CENTER[0] - VIEW_BOUNDS[0]),
            position[1] - (POPULATED_RING_CENTER[1] - VIEW_BOUNDS[1]),
        )
        for position in flare_positions
    ]
    if max(abs(radius - SCANNER_FLARE_RADIUS) for radius in flare_radii) > 1e-9:
        raise AssertionError("Scanner flare path radius changed during the loop")
    flare_phase_degrees = [
        math.degrees(math.atan2(
            position[1] - (POPULATED_RING_CENTER[1] - VIEW_BOUNDS[1]),
            position[0] - (POPULATED_RING_CENTER[0] - VIEW_BOUNDS[0]),
        ))
        for position in flare_positions
    ]
    flare_phase_steps = [
        (
            (flare_phase_degrees[(index + 1) % FRAME_COUNT] - flare_phase_degrees[index] + 180.0)
            % 360.0
        )
        - 180.0
        for index in range(FRAME_COUNT)
    ]
    if max(abs(step + 3.0) for step in flare_phase_steps) > 1e-9:
        raise AssertionError(f"Flare phase step is not a cyclic -3 degrees: {flare_phase_steps}")
    adjacent_unique = all(
        sha256_array(decoded_arrays[index]) != sha256_array(decoded_arrays[index - 1])
        for index in range(1, len(decoded_arrays))
    )
    if not adjacent_unique:
        raise AssertionError("Encoded GIF contains adjacent duplicate frames")
    decoded_frame_hashes = [sha256_array(frame) for frame in decoded_arrays]
    unique_decoded_frames = len(set(decoded_frame_hashes))
    if unique_decoded_frames != FRAME_COUNT:
        raise AssertionError(
            f"Encoded GIF does not contain 120 distinct frames: {unique_decoded_frames}"
        )
    cyclic_adjacent_mean_differences = [
        float(
            np.mean(
                np.abs(
                    decoded_arrays[(index + 1) % FRAME_COUNT].astype(np.int16)
                    - decoded_arrays[index].astype(np.int16)
                )
            )
        )
        for index in range(FRAME_COUNT)
    ]

    decoded_atmosphere_changed_pixels: list[int] = []
    decoded_atmosphere_mean_absolute_deltas: list[float] = []
    decoded_atmosphere_maximum_darkening: list[int] = []
    decoded_atmosphere_maximum_red_gain: list[int] = []
    for frame_index in range(FRAME_COUNT):
        delta = (
            decoded_arrays[frame_index].astype(np.int16)
            - pre_atmosphere_control_decoded_arrays[frame_index].astype(np.int16)
        )
        changed = np.any(delta != 0, axis=2)
        if np.any(changed & ~atmosphere_support_frames[frame_index]):
            raise AssertionError(
                f"Decoded atmosphere escaped support at frame {frame_index}"
            )
        decoded_atmosphere_changed_pixels.append(int(np.count_nonzero(changed)))
        decoded_atmosphere_mean_absolute_deltas.append(
            float(np.mean(np.abs(delta[changed]))) if np.any(changed) else 0.0
        )
        decoded_atmosphere_maximum_darkening.append(
            int(np.max(-delta[delta < 0])) if np.any(delta < 0) else 0
        )
        decoded_atmosphere_maximum_red_gain.append(
            int(np.max(delta[:, :, 0]))
        )
    if min(decoded_atmosphere_changed_pixels) <= 0:
        raise AssertionError("Atmosphere disappeared after GIF quantization")

    # A point flare can be bright yet fail to read as a circumference effect.
    # Measure the actual decoded GIF against a same-palette, atmosphere-disabled
    # control and require a visible, nearly complete annular band at its strongest
    # phase.  Seventy-two five-degree bins make this explicitly a circle test.
    scanner_angle_view = np.mod(
        np.arctan2(
            view_yy + 0.5 - (POPULATED_RING_CENTER[1] - VIEW_BOUNDS[1]),
            view_xx + 0.5 - (POPULATED_RING_CENTER[0] - VIEW_BOUNDS[0]),
        ),
        math.tau,
    )
    band_annulus = (
        (scanner_radius_view >= ATMOSPHERE_RADIAL_BOUNDS[0])
        & (scanner_radius_view <= ATMOSPHERE_RADIAL_BOUNDS[1])
    )
    visible_band_masks: list[np.ndarray] = []
    visible_band_pixel_counts: list[int] = []
    visible_band_angular_bin_counts: list[int] = []
    visible_band_scores: list[int] = []
    visible_band_bin_pixel_counts: list[list[int]] = []
    for frame_index in range(FRAME_COUNT):
        decoded_delta = np.abs(
            decoded_arrays[frame_index].astype(np.int16)
            - pre_atmosphere_control_decoded_arrays[frame_index].astype(np.int16)
        )
        visible_strength = np.max(decoded_delta, axis=2)
        visible_band = band_annulus & (visible_strength >= 6)
        angular_bins = np.floor(scanner_angle_view / math.tau * 72.0).astype(np.int16) % 72
        bin_counts = [
            int(np.count_nonzero(visible_band & (angular_bins == bin_index)))
            for bin_index in range(72)
        ]
        visible_band_masks.append(visible_band)
        visible_band_pixel_counts.append(int(np.count_nonzero(visible_band)))
        visible_band_angular_bin_counts.append(int(sum(count > 0 for count in bin_counts)))
        visible_band_scores.append(int(np.sum(visible_strength[visible_band], dtype=np.int64)))
        visible_band_bin_pixel_counts.append(bin_counts)

    strongest_band_frame = max(
        range(FRAME_COUNT),
        key=lambda index: (visible_band_scores[index], -index),
    )
    strongest_visible_band = visible_band_masks[strongest_band_frame]
    strongest_band_visible_pixels = visible_band_pixel_counts[strongest_band_frame]
    strongest_band_covered_bins = visible_band_angular_bin_counts[strongest_band_frame]
    if strongest_band_visible_pixels < 2500 or strongest_band_covered_bins < 65:
        raise AssertionError(
            "Decoded circumference band is not visibly annular: "
            f"frame={strongest_band_frame}, pixels={strongest_band_visible_pixels}, "
            f"covered_5deg_bins={strongest_band_covered_bins}/72"
        )
    strongest_visible_radii = scanner_radius_view[strongest_visible_band]
    strongest_band_radius_range = (
        float(np.min(strongest_visible_radii)),
        float(np.max(strongest_visible_radii)),
    )
    radial_bins = np.floor(scanner_radius_view).astype(np.int16)
    strongest_delta = np.max(
        np.abs(
            decoded_arrays[strongest_band_frame].astype(np.int16)
            - pre_atmosphere_control_decoded_arrays[strongest_band_frame].astype(np.int16)
        ),
        axis=2,
    )
    radial_scores = {
        radius_bin: int(
            np.sum(
                strongest_delta[
                    strongest_visible_band & (radial_bins == radius_bin)
                ],
                dtype=np.int64,
            )
        )
        for radius_bin in range(
            int(math.floor(ATMOSPHERE_RADIAL_BOUNDS[0])),
            int(math.ceil(ATMOSPHERE_RADIAL_BOUNDS[1])) + 1,
        )
    }
    strongest_band_peak_radius = max(radial_scores, key=radial_scores.get)
    if not 116 <= strongest_band_peak_radius <= 126:
        raise AssertionError(
            f"Visible circumference band no longer hugs the outer scanner ring: peak radius={strongest_band_peak_radius}"
        )

    # Isolate only the circumference atmosphere: the comparison controls carry
    # the identical emblem rotation, point flare, ring brightening, and edge glow.
    atmosphere_effects = [
        decoded_arrays[index].astype(np.int16)
        - pre_atmosphere_control_decoded_arrays[index].astype(np.int16)
        for index in range(FRAME_COUNT)
    ]
    phase_pairs = tuple(zip(EXPORT_PROOF_FRAMES[:-1], EXPORT_PROOF_FRAMES[1:]))
    band_phase_motion_p90: list[float] = []
    band_phase_motion_pixels_ge4: list[int] = []
    band_phase_motion_pixels_ge6: list[int] = []
    for first, second in phase_pairs:
        phase_motion = np.max(
            np.abs(atmosphere_effects[second] - atmosphere_effects[first]),
            axis=2,
        )
        annular_motion = phase_motion[band_annulus]
        band_phase_motion_p90.append(float(np.percentile(annular_motion, 90.0)))
        band_phase_motion_pixels_ge4.append(int(np.count_nonzero(annular_motion >= 4)))
        band_phase_motion_pixels_ge6.append(int(np.count_nonzero(annular_motion >= 6)))
    if (
        min(band_phase_motion_p90) < 5.0
        or min(band_phase_motion_pixels_ge4) < 2000
        or min(band_phase_motion_pixels_ge6) < 500
    ):
        raise AssertionError(
            "Decoded circumference atmosphere does not animate visibly between proof phases: "
            f"p90={band_phase_motion_p90}, >=4={band_phase_motion_pixels_ge4}, "
            f">=6={band_phase_motion_pixels_ge6}"
        )

    # Verify the illumination survives GIF quantization at the configured path,
    # rather than merely trusting the pre-encode phase coordinates.
    decoded_flare_centroid_errors: list[float] = []
    decoded_flare_window_changed_pixels: list[int] = []
    decoded_flare_window_peak_channel_deltas: list[int] = []
    decoded_glow_changed_pixels: list[int] = []
    for frame_index, decoded_frame in enumerate(decoded_arrays):
        degrees = 360.0 * frame_index / FRAME_COUNT
        rotated = sprite.rotate(
            -degrees,
            resample=Image.Resampling.BICUBIC,
            expand=False,
            center=LOCAL_PIVOT,
        )
        atmospheric_rgb, _, _, _, _ = scanner_atmosphere(
            stationary_rgb,
            frame_index,
            atmosphere_base,
            enabled=True,
        )
        unlit = Image.fromarray(atmospheric_rgb, "RGB").convert("RGBA")
        unlit.alpha_composite(rotated, VIEW_PASTE)
        unlit_decoded = np.array(
            unlit.convert("RGB")
            .quantize(palette=palette, dither=Image.Dither.NONE)
            .convert("RGB")
        )
        decoded_light_delta = decoded_frame.astype(np.int16) - unlit_decoded.astype(np.int16)
        expected_flare = flare_positions[frame_index]
        flare_window = (
            (view_xx + 0.5 - expected_flare[0]) ** 2
            + (view_yy + 0.5 - expected_flare[1]) ** 2
            <= 14.0 ** 2
        )
        positive_luminance = np.maximum(np.mean(decoded_light_delta, axis=2), 0.0)
        flare_weights = positive_luminance * flare_window
        flare_mass = float(np.sum(flare_weights))
        if flare_mass <= 0.0:
            raise AssertionError(f"Decoded flare disappeared at frame {frame_index}")
        decoded_flare_centroid = (
            float(np.sum((view_xx + 0.5) * flare_weights) / flare_mass),
            float(np.sum((view_yy + 0.5) * flare_weights) / flare_mass),
        )
        decoded_flare_centroid_errors.append(
            math.hypot(
                decoded_flare_centroid[0] - expected_flare[0],
                decoded_flare_centroid[1] - expected_flare[1],
            )
        )
        decoded_flare_window_changed_pixels.append(
            int(np.count_nonzero(np.any(decoded_light_delta[flare_window] != 0, axis=1)))
        )
        decoded_flare_window_peak_channel_deltas.append(
            int(np.max(decoded_light_delta[flare_window]))
        )

        scanner_layer, _, _ = scanner_illumination(frame_index, ring_detail_mask)
        scanner_only_rgb = screen_blend_rgb(atmospheric_rgb, np.array(scanner_layer))
        scanner_only = Image.fromarray(scanner_only_rgb, "RGB").convert("RGBA")
        scanner_only.alpha_composite(rotated, VIEW_PASTE)
        scanner_only_decoded = np.array(
            scanner_only.convert("RGB")
            .quantize(palette=palette, dither=Image.Dither.NONE)
            .convert("RGB")
        )
        decoded_glow_change = np.any(decoded_frame != scanner_only_decoded, axis=2)
        if np.any(decoded_glow_change & ~(glow_alpha_frames[frame_index] > 0)):
            raise AssertionError(
                f"Decoded emblem glow escaped its declared support at frame {frame_index}"
            )
        decoded_glow_changed_pixels.append(int(np.count_nonzero(decoded_glow_change)))

    if max(decoded_flare_centroid_errors) > 3.0:
        raise AssertionError(
            "Decoded traveling flare no longer follows its fixed-radius path: "
            f"maximum centroid error={max(decoded_flare_centroid_errors):.3f}"
        )
    if min(decoded_flare_window_changed_pixels) <= 0:
        raise AssertionError("Decoded traveling flare is invisible in at least one frame")
    if min(decoded_glow_changed_pixels) <= 0:
        raise AssertionError("Decoded breathing emblem-edge glow is invisible in at least one frame")

    individual_paths: list[Path] = []
    for frame_index in EXPORT_PROOF_FRAMES:
        path = OUT_DIR / f"{RUN_PREFIX}_keyframe_frame_{frame_index:03d}.png"
        decoded[frame_index].save(path)
        individual_paths.append(path)

    keyframes_match_decoded_gif = all(
        np.array_equal(
            np.array(Image.open(path).convert("RGB")),
            decoded_arrays[frame_index],
        )
        for frame_index, path in zip(EXPORT_PROOF_FRAMES, individual_paths)
    )
    if not keyframes_match_decoded_gif:
        raise AssertionError("A saved PNG keyframe differs from its decoded GIF frame")

    assembly_proof = make_gif_assembly_proof(decoded, emblem_bboxes, gif_descriptors)
    assembly_proof_path = OUT_DIR / (
        f"{RUN_PREFIX}_assembly_proof_frames_000_015_030_045.png"
    )
    assembly_proof.save(assembly_proof_path)

    visible_band_still_path = OUT_DIR / (
        f"{RUN_PREFIX}_visible_band_still_frame_{strongest_band_frame:03d}.png"
    )
    Image.fromarray(decoded_arrays[strongest_band_frame], "RGB").save(visible_band_still_path)
    if not np.array_equal(
        np.array(Image.open(visible_band_still_path).convert("RGB")),
        decoded_arrays[strongest_band_frame],
    ):
        raise AssertionError("Visible-band still is not an exact decoded GIF frame")

    # Proof-only yellow, cyan, and magenta geometry markers must never leak into
    # the animation or any exact decoded keyframe.
    proof_yellow_pixels_in_animation = sum(
        int(
            np.count_nonzero(
                (frame[:, :, 0] >= 240)
                & (frame[:, :, 1] >= 205)
                & (frame[:, :, 2] <= 135)
            )
        )
        for frame in decoded_arrays
    )
    proof_crosshair_absent_from_animation = proof_yellow_pixels_in_animation == 0
    if not proof_crosshair_absent_from_animation:
        raise AssertionError("Proof crosshair leaked into animation frames")
    proof_cyan_pixels_in_animation = sum(
        int(np.count_nonzero(np.all(frame == (70, 225, 255), axis=2)))
        for frame in decoded_arrays
    )
    proof_magenta_pixels_in_animation = sum(
        int(np.count_nonzero(np.all(frame == (255, 90, 220), axis=2)))
        for frame in decoded_arrays
    )
    if proof_cyan_pixels_in_animation or proof_magenta_pixels_in_animation:
        raise AssertionError(
            "Geometry-proof markers leaked into animation frames: "
            f"cyan={proof_cyan_pixels_in_animation}, magenta={proof_magenta_pixels_in_animation}"
        )
    proof_green_pixels_in_animation = sum(
        int(np.count_nonzero(np.all(frame == (80, 255, 130), axis=2)))
        for frame in decoded_arrays
    )
    if proof_green_pixels_in_animation:
        raise AssertionError("Assembly-proof bbox color leaked into animation frames")

    total_duration = sum(durations)
    if total_duration != FRAME_COUNT * FRAME_DURATION_MS:
        raise AssertionError(f"Unexpected GIF duration: {total_duration} ms")
    if set(disposals) != {2}:
        raise AssertionError(f"Unexpected GIF disposal methods: {sorted(set(disposals))}")

    paste_origin_records = {record[2] for record in geometry_records}
    pivot_records = {(record[0], record[3]) for record in geometry_records}
    if paste_origin_records != {PASTE_ORIGIN} or pivot_records != {(HUB, LOCAL_PIVOT)}:
        raise AssertionError(
            f"Frame assembly geometry is not invariant: paste={paste_origin_records}, pivot={pivot_records}"
        )
    if len(set(emblem_bboxes)) <= 1:
        raise AssertionError("Rotating emblem bboxes did not change with the artwork orientation")

    qc_note_path = OUT_DIR / f"{RUN_PREFIX}_export_qc.txt"
    qc_note_lines = (
        "Biohazard isolated GIF assembly QC",
        f"paste_origin_identical_all_frames=True global={PASTE_ORIGIN} view={VIEW_PASTE}",
        f"pivot_identical_all_frames=True global={HUB} view={VIEW_HUB} local={LOCAL_PIVOT}",
        f"full_canvas_before_save=True size={VIEW_SIZE[0]}x{VIEW_SIZE[1]} frames={FRAME_COUNT}",
        "no_frame_cropping_before_gif_save=True",
        "gif_optimization_enabled=False",
        f"gif_full_canvas_descriptors=True rectangle={full_canvas_descriptor} count={len(gif_descriptors)}",
        "gif_local_color_tables=False",
        "gif_local_frame_placement_changed=False offsets=(0,0) on all frames",
        "gif_disposal_method=2 on all frames",
        f"circumference_band_animated=True unique_states={unique_atmosphere_states} strongest_frame={strongest_band_frame}",
        f"circumference_band_visible_bins={strongest_band_covered_bins}/72 visible_pixels={strongest_band_visible_pixels}",
        f"circumference_band_phase_motion_p90={band_phase_motion_p90}",
        f"circumference_band_phase_motion_pixels_ge6={band_phase_motion_pixels_ge6}",
    )
    qc_note_path.write_text("\n".join(qc_note_lines) + "\n", encoding="utf-8")

    requested_png_paths = [*individual_paths, assembly_proof_path, visible_band_still_path]
    for path in requested_png_paths:
        with Image.open(path) as image:
            if image.format != "PNG":
                raise AssertionError(f"Requested still is not PNG: {path.name}={image.format}")
            if path in individual_paths or path == visible_band_still_path:
                if image.size != VIEW_SIZE or image.mode != "RGB":
                    raise AssertionError(
                        f"Unexpected decoded-still properties: {path.name}, size={image.size}, mode={image.mode}"
                    )
    with Image.open(assembly_proof_path) as proof:
        if proof.size != (VIEW_SIZE[0] * 2, (54 + VIEW_SIZE[1]) * 2 + 50) or proof.mode != "RGB":
            raise AssertionError(
                f"Unexpected assembly-proof properties: size={proof.size}, mode={proof.mode}"
            )

    expected_run_outputs = {
        gif_path.name,
        assembly_proof_path.name,
        qc_note_path.name,
        visible_band_still_path.name,
        *(path.name for path in individual_paths),
    }
    actual_run_outputs = {
        path.name
        for path in OUT_DIR.glob(f"{RUN_PREFIX}*")
        if path.is_file()
    }
    if actual_run_outputs != expected_run_outputs or len(actual_run_outputs) != 8:
        raise AssertionError(
            "Corrective pass did not produce exactly the eight requested files: "
            f"actual={sorted(actual_run_outputs)}, expected={sorted(expected_run_outputs)}"
        )

    print(f"sprite dimensions: {sprite.width}x{sprite.height}")
    print(
        "centering: "
        f"prior_hub={PREVIOUS_HUB}, final_hub={HUB}, incremental_delta={incremental_hub_delta}; "
        f"prior_paste={PREVIOUS_PASTE_ORIGIN}, final_paste={PASTE_ORIGIN}, "
        f"incremental_delta={incremental_paste_delta}"
    )
    print(f"fixed local pivot: {LOCAL_PIVOT}; scale: {SCALE:.1f}")
    print(
        "visible circumference band: "
        f"strongest_frame={strongest_band_frame}, visible_pixels={strongest_band_visible_pixels}, "
        f"angular_bins={strongest_band_covered_bins}/72, peak_radius={strongest_band_peak_radius}, "
        f"visible_radius_range=({strongest_band_radius_range[0]:.3f}, {strongest_band_radius_range[1]:.3f})"
    )
    print(
        f"GIF: {gif_format}, {gif_size[0]}x{gif_size[1]}, {gif_frames} frames, "
        f"{durations[0]} ms/frame, {total_duration} ms total, loop={gif_loop}, disposal=2"
    )
    print(f"unique decoded frames: {unique_decoded_frames}")
    print(f"animated GIF: {gif_path}")
    print("four keyframes: " + ", ".join(str(path) for path in individual_paths))
    print(f"assembly proof: {assembly_proof_path}")
    print(f"export QC note: {qc_note_path}")
    print(f"visible-band still: {visible_band_still_path}")
    return

    lighting_no_channel_darkening = all(
        bool(stats["no_channel_darkening"]) for stats in lighting_stats_by_frame
    )
    lighting_maximum_channel_delta = max(
        int(stats["maximum_channel_delta"]) for stats in lighting_stats_by_frame
    )
    lighting_mean_positive_channel_delta_range = (
        min(float(stats["mean_positive_channel_delta"]) for stats in lighting_stats_by_frame),
        max(float(stats["mean_positive_channel_delta"]) for stats in lighting_stats_by_frame),
    )
    lighting_p99_positive_channel_delta_max = max(
        float(stats["p99_positive_channel_delta"]) for stats in lighting_stats_by_frame
    )
    lighting_new_saturated_channels_max = max(
        int(stats["new_saturated_channels"]) for stats in lighting_stats_by_frame
    )
    atmosphere_maximum_channel_drop = max(
        int(stats["maximum_channel_drop"]) for stats in atmosphere_stats_by_frame
    )
    atmosphere_mean_channel_drop_range = (
        min(float(stats["mean_channel_drop"]) for stats in atmosphere_stats_by_frame),
        max(float(stats["mean_channel_drop"]) for stats in atmosphere_stats_by_frame),
    )
    atmosphere_p99_channel_drop_max = max(
        float(stats["p99_channel_drop"]) for stats in atmosphere_stats_by_frame
    )
    atmosphere_maximum_channel_gain = max(
        int(stats["maximum_channel_gain"]) for stats in atmosphere_stats_by_frame
    )
    atmosphere_mean_channel_gain_range = (
        min(float(stats["mean_channel_gain"]) for stats in atmosphere_stats_by_frame),
        max(float(stats["mean_channel_gain"]) for stats in atmosphere_stats_by_frame),
    )
    atmosphere_p99_channel_gain_max = max(
        float(stats["p99_channel_gain"]) for stats in atmosphere_stats_by_frame
    )
    atmosphere_new_zero_channels_max = max(
        int(stats["new_zero_channels"]) for stats in atmosphere_stats_by_frame
    )
    atmosphere_new_saturated_channels_max = max(
        int(stats["new_saturated_channels"]) for stats in atmosphere_stats_by_frame
    )
    report_lines = [
        "BioDefense isolated biohazard QC - centered rotation + scanner atmosphere",
        "",
        f"populated_input={POPULATED_PATH}",
        f"populated_input_sha256={input_hashes[POPULATED_PATH]}",
        f"clear_input={CLEAR_PATH}",
        f"clear_input_sha256={input_hashes[CLEAR_PATH]}",
        f"reference_input={REFERENCE_PATH}",
        f"reference_input_sha256={input_hashes[REFERENCE_PATH]}",
        "approved_inputs_hash_match=True",
        f"preserved_before_centering_frame={BEFORE_CENTERING_PATH}",
        f"preserved_before_centering_sha256={before_centering_hash}",
        f"source_reference_crop={source_reference_path}",
        f"centering_comparison={centering_comparison_path}",
        f"keyframe_proof_sheet={keyframe_sheet_path}",
        f"gif_output={gif_path}",
        f"preserved_pre_atmosphere_archive={OUT_DIR / 'baseline_up4_glow_before_atmosphere'}",
        "",
        f"sprite_dimensions={sprite.width}x{sprite.height}",
        f"source_hub_pixel={SOURCE_HUB_PIXEL}",
        f"source_hub_mathematical={SOURCE_HUB}",
        f"destination_hub_pixel={HUB_PIXEL}",
        f"destination_hub_mathematical={HUB}",
        f"pivot_local={LOCAL_PIVOT}",
        f"source_bounds={SOURCE_BOUNDS}",
        f"source_origin_global={SOURCE_ORIGIN}",
        f"paste_origin_global={PASTE_ORIGIN}",
        f"source_origin_view={VIEW_SOURCE_PASTE}",
        f"paste_origin_view={VIEW_PASTE}",
        f"centering_requested_delta={CENTERING_DELTA}",
        f"centering_hub_delta={hub_delta}",
        f"centering_paste_delta={paste_delta}",
        f"centering_x_unchanged={hub_delta[0] == 0 and paste_delta[0] == 0}",
        f"centering_controls_unlit=True",
        f"centering_controls_outside_translation_unchanged={controls_outside_translation_unchanged}",
        f"scale={SCALE:.1f}",
        f"geometry_unique_records={len(set(geometry_records))}",
        f"pivot_probe_unique_positions={len(pivot_probe_positions)}",
        f"pivot_probe_local_position={next(iter(pivot_probe_positions))}",
        f"rotated_alpha_mass_range=({min(alpha_masses):.6f}, {max(alpha_masses):.6f})",
        f"rotated_radial_second_moment_range=({min(radial_second_moments):.6f}, {max(radial_second_moments):.6f})",
        "frame_dependent_xy_correction=False",
        "sprite_crop_after_isolation=False",
        "sprite_resize_or_autoscale=False",
        "unicode_glyph_generation=False",
        f"sprite_rgba_sha256={sprite_rgba_hash}",
        f"sprite_rgba_matches_frozen_baseline={sprite_rgba_hash == EXPECTED_SPRITE_RGBA_SHA256}",
        f"sprite_alpha_sha256={sprite_alpha_hash}",
        f"sprite_alpha_matches_frozen_baseline={sprite_alpha_hash == EXPECTED_SPRITE_ALPHA_SHA256}",
        "",
        f"registration_matrix_clean_to_populated={registration_matrix.tolist()}",
        f"registered_clean_tone_offset={tone_offset}",
        f"retained_component_count={len(components)}",
        f"retained_component_areas={[component['area'] for component in components]}",
        f"strong_candidate_pixels={extraction['strong_candidate_pixels']}",
        f"final_binary_pixels={extraction['final_binary_pixels']}",
        f"alpha_nonzero_pixels={extraction['alpha_nonzero_pixels']}",
        f"alpha_maximum_radius={extraction['alpha_maximum_radius']:.4f}",
        f"rotation_symmetry_dice_120deg={extraction['rotation_symmetry_dice_120deg']:.6f}",
        f"source_rgb_identity={extraction['source_rgb_identity']}",
        f"stationary_background_sha256={stationary_hash}",
        f"stationary_background_matches_frozen_baseline={stationary_hash == EXPECTED_STATIONARY_BACKGROUND_SHA256}",
        f"pre_atmosphere_rgb_sequence_sha256={pre_atmosphere_rgb_sequence_hash}",
        f"pre_atmosphere_rgb_sequence_matches_frozen_baseline={pre_atmosphere_rgb_sequence_hash == EXPECTED_PRE_ATMOSPHERE_RGB_SEQUENCE_SHA256}",
        f"emblem_alpha_sequence_sha256={emblem_alpha_sequence_hash}",
        f"emblem_alpha_sequence_matches_frozen_baseline={emblem_alpha_sequence_hash == EXPECTED_EMBLEM_ALPHA_SEQUENCE_SHA256}",
        f"scanner_illumination_alpha_sequence_sha256={illumination_alpha_sequence_hash}",
        f"scanner_illumination_alpha_sequence_matches_frozen_baseline={illumination_alpha_sequence_hash == EXPECTED_SCANNER_ILLUMINATION_ALPHA_SEQUENCE_SHA256}",
        f"emblem_glow_alpha_sequence_sha256={glow_alpha_sequence_hash}",
        f"emblem_glow_alpha_sequence_matches_frozen_baseline={glow_alpha_sequence_hash == EXPECTED_EMBLEM_GLOW_ALPHA_SEQUENCE_SHA256}",
        f"restoration_mask_pixels={int(np.count_nonzero(restoration_mask))}",
        "protected_outer_scanner_matches_populated=True",
        "",
        "radiometric_overlay_only=True",
        "scanner_geometry_animation=False",
        "scanner_geometry_resampled=False",
        "scanner_transform_translation=(0, 0)",
        "scanner_transform_rotation_degrees=0.0",
        "scanner_transform_scale=1.0",
        f"scanner_geometry_unique_records={len(set(scanner_geometry_records))}",
        f"scanner_center_global={POPULATED_RING_CENTER}",
        f"scanner_center_view={(POPULATED_RING_CENTER[0] - VIEW_BOUNDS[0], POPULATED_RING_CENTER[1] - VIEW_BOUNDS[1])}",
        f"scanner_fitted_ring_radius={POPULATED_RING_RADIUS}",
        "",
        "scanner_atmosphere_enabled=True",
        "scanner_atmosphere_spatial_resampling=False",
        "scanner_atmosphere_pointwise_blend_verified=True",
        "scanner_atmosphere_fixed_texture_opacity_animation=True",
        f"scanner_atmosphere_center_global={POPULATED_RING_CENTER}",
        f"scanner_atmosphere_center_view={(POPULATED_RING_CENTER[0] - VIEW_BOUNDS[0], POPULATED_RING_CENTER[1] - VIEW_BOUNDS[1])}",
        f"scanner_atmosphere_radial_center={ATMOSPHERE_RADIUS}",
        f"scanner_atmosphere_radial_sigma={ATMOSPHERE_SIGMA}",
        f"scanner_atmosphere_declared_radial_bounds={ATMOSPHERE_RADIAL_BOUNDS}",
        f"scanner_atmosphere_actual_support_radius_range=({atmosphere_support_radius_range[0]:.6f}, {atmosphere_support_radius_range[1]:.6f})",
        f"scanner_atmosphere_red={ATMOSPHERE_RED}",
        f"scanner_atmosphere_red_alpha_cap={ATMOSPHERE_RED_ALPHA_MAX}",
        f"scanner_atmosphere_black_alpha_cap={ATMOSPHERE_BLACK_ALPHA_MAX}",
        f"scanner_atmosphere_noise_seed={ATMOSPHERE_NOISE_SEED}",
        f"scanner_atmosphere_base_sha256={atmosphere_base_hash}",
        f"scanner_atmosphere_red_alpha_sequence_sha256={atmosphere_red_sequence_hash}",
        f"scanner_atmosphere_shadow_alpha_sequence_sha256={atmosphere_shadow_sequence_hash}",
        f"scanner_atmosphere_unique_states={unique_atmosphere_states}",
        f"scanner_atmosphere_state_closes_exactly_at_frame_120={atmosphere_state_closes_exactly}",
        f"scanner_atmosphere_state_step_difference_range=({min(atmosphere_state_step_differences):.6f}, {max(atmosphere_state_step_differences):.6f})",
        f"scanner_atmosphere_seam_step_difference={atmosphere_state_step_differences[-1]:.6f}",
        f"scanner_atmosphere_fade_range=({min(atmosphere_fade_values):.6f}, {max(atmosphere_fade_values):.6f})",
        f"scanner_atmosphere_keyframe_fades={{0: {atmosphere_fade_values[0]:.2f}, 30: {atmosphere_fade_values[30]:.2f}, 60: {atmosphere_fade_values[60]:.2f}, 90: {atmosphere_fade_values[90]:.2f}}}",
        f"scanner_atmosphere_support_pixel_range=({min(atmosphere_support_counts)}, {max(atmosphere_support_counts)})",
        f"scanner_atmosphere_red_coverage_alpha_gt_5_range=({min(atmosphere_red_coverage_over_five)}, {max(atmosphere_red_coverage_over_five)})",
        f"scanner_atmosphere_red_alpha_max_range=({min(atmosphere_red_alpha_maxima)}, {max(atmosphere_red_alpha_maxima)})",
        f"scanner_atmosphere_shadow_alpha_max_range=({min(atmosphere_shadow_alpha_maxima)}, {max(atmosphere_shadow_alpha_maxima)})",
        f"scanner_atmosphere_protected_detail_red_alpha_max={protected_detail_red_alpha_max}",
        f"scanner_atmosphere_protected_detail_shadow_alpha_max={protected_detail_shadow_alpha_max}",
        f"scanner_atmosphere_maximum_channel_drop={atmosphere_maximum_channel_drop}",
        f"scanner_atmosphere_mean_channel_drop_range=({atmosphere_mean_channel_drop_range[0]:.6f}, {atmosphere_mean_channel_drop_range[1]:.6f})",
        f"scanner_atmosphere_p99_channel_drop_max={atmosphere_p99_channel_drop_max:.6f}",
        f"scanner_atmosphere_maximum_channel_gain={atmosphere_maximum_channel_gain}",
        f"scanner_atmosphere_mean_channel_gain_range=({atmosphere_mean_channel_gain_range[0]:.6f}, {atmosphere_mean_channel_gain_range[1]:.6f})",
        f"scanner_atmosphere_p99_channel_gain_max={atmosphere_p99_channel_gain_max:.6f}",
        f"scanner_atmosphere_new_zero_channels_max={atmosphere_new_zero_channels_max}",
        f"scanner_atmosphere_new_saturated_channels_max={atmosphere_new_saturated_channels_max}",
        f"scanner_atmosphere_raw_changes_outside_support=0",
        f"scanner_atmosphere_decoded_changes_outside_support=0",
        f"scanner_atmosphere_decoded_changed_pixel_range=({min(decoded_atmosphere_changed_pixels)}, {max(decoded_atmosphere_changed_pixels)})",
        f"scanner_atmosphere_decoded_mean_absolute_delta_range=({min(decoded_atmosphere_mean_absolute_deltas):.6f}, {max(decoded_atmosphere_mean_absolute_deltas):.6f})",
        f"scanner_atmosphere_decoded_maximum_darkening_range=({min(decoded_atmosphere_maximum_darkening)}, {max(decoded_atmosphere_maximum_darkening)})",
        f"scanner_atmosphere_decoded_maximum_red_gain_range=({min(decoded_atmosphere_maximum_red_gain)}, {max(decoded_atmosphere_maximum_red_gain)})",
        f"fixed_ring_grid_crosshair_stable_pixel_count_range=({min(stable_detail_counts)}, {max(stable_detail_counts)})",
        f"fixed_ring_grid_crosshair_stable_pixels_match_control={fixed_detail_stable_pixels_match_control}",
        "",
        f"scanner_flare_path_radius={SCANNER_FLARE_RADIUS}",
        f"scanner_flare_phase_step_degrees={flare_phase_steps[0]:.6f}",
        f"scanner_flare_seam_phase_step_degrees={flare_phase_steps[-1]:.6f}",
        f"scanner_flare_radius_range=({min(flare_radii):.6f}, {max(flare_radii):.6f})",
        f"decoded_flare_centroid_error_range=({min(decoded_flare_centroid_errors):.6f}, {max(decoded_flare_centroid_errors):.6f})",
        f"decoded_flare_window_changed_pixel_range=({min(decoded_flare_window_changed_pixels)}, {max(decoded_flare_window_changed_pixels)})",
        f"decoded_flare_window_peak_channel_delta_range=({min(decoded_flare_window_peak_channel_deltas)}, {max(decoded_flare_window_peak_channel_deltas)})",
        f"ring_detail_mask_sha256={ring_detail_hash}",
        f"ring_detail_mask_pixels={int(np.count_nonzero(ring_detail_mask))}",
        f"scanner_ring_stable_pixel_count_range=({min(stable_ring_counts)}, {max(stable_ring_counts)})",
        f"scanner_ring_stable_pixels_match_fixed_control={scanner_ring_stable_pixels_match_control}",
        f"rotated_alpha_inner_ring_detail_occlusion_pixels={emblem_ring_overlap_pixels}",
        f"rotated_alpha_protected_outer_circumference_overlap_pixels={emblem_outer_circumference_overlap_pixels}",
        f"emblem_glow_protected_ring_overlap_pixels={glow_ring_overlap_pixels}",
        f"illuminated_existing_ring_pixels={illuminated_ring_pixels}",
        f"scanner_illumination_alpha_max_range=({min(illumination_alpha_maxima)}, {max(illumination_alpha_maxima)})",
        f"emblem_breathing_glow_alpha_max_range=({min(glow_alpha_maxima)}, {max(glow_alpha_maxima)})",
        f"decoded_emblem_glow_changed_pixel_range=({min(decoded_glow_changed_pixels)}, {max(decoded_glow_changed_pixels)})",
        f"flare_glow_no_channel_darkening={lighting_no_channel_darkening}",
        "lighting_changes_outside_declared_support=0",
        "opaque_rotated_sprite_rgb_identity=True",
        f"lighting_maximum_channel_delta={lighting_maximum_channel_delta}",
        f"lighting_mean_positive_channel_delta_range=({lighting_mean_positive_channel_delta_range[0]:.6f}, {lighting_mean_positive_channel_delta_range[1]:.6f})",
        f"lighting_p99_positive_channel_delta_max={lighting_p99_positive_channel_delta_max:.6f}",
        f"lighting_new_saturated_channels_max={lighting_new_saturated_channels_max}",
        "",
        f"gif_format={gif_format}",
        f"gif_dimensions={gif_size[0]}x{gif_size[1]}",
        f"gif_frame_count={gif_frames}",
        f"gif_frame_duration_ms={durations[0]}",
        f"gif_total_duration_ms={total_duration}",
        f"gif_loop={gif_loop}",
        f"gif_disposal_methods={sorted(set(disposals))}",
        f"gif_fixed_palette_sha256={palette_hash}",
        f"gif_adjacent_frames_unique={adjacent_unique}",
        f"gif_unique_decoded_frames={unique_decoded_frames}",
        f"gif_cyclic_adjacent_mean_difference_range=({min(cyclic_adjacent_mean_differences):.6f}, {max(cyclic_adjacent_mean_differences):.6f})",
        f"gif_loop_seam_mean_difference={cyclic_adjacent_mean_differences[-1]:.6f}",
        f"gif_stationary_pixels_outside_animation_union={stationary_outside_union}",
        f"atmosphere_keyframe_count={len(individual_paths)}",
        "atmosphere_keyframe_frames=(0, 30, 60, 90)",
        f"keyframe_pngs_match_decoded_gif={keyframes_match_decoded_gif}",
        f"proof_yellow_pixels_in_animation={proof_yellow_pixels_in_animation}",
        f"proof_crosshair_absent_from_animation={proof_crosshair_absent_from_animation}",
        "",
        "individual_keyframes=" + ", ".join(str(path) for path in individual_paths),
    ]
    for index, component in enumerate(components, start=1):
        report_lines.append(f"component_{index}={component}")
    qc_path = OUT_DIR / f"{RUN_PREFIX}_qc.txt"
    qc_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"sprite dimensions: {sprite.width}x{sprite.height}")
    print(
        "centering: "
        f"source_hub={SOURCE_HUB}, destination_hub={HUB}, delta={hub_delta}; "
        f"source_origin={SOURCE_ORIGIN}, destination_origin={PASTE_ORIGIN}, delta={paste_delta}"
    )
    print(f"fixed local pivot: {LOCAL_PIVOT}")
    print(f"scale: {SCALE:.1f}")
    print(f"GIF format: {gif_format}")
    print(f"GIF dimensions: {gif_size[0]}x{gif_size[1]}")
    print(f"GIF frame count: {gif_frames}")
    print(f"frame duration: {durations[0]} ms (total {total_duration} ms)")
    print(f"source/reference crop: {source_reference_path}")
    print(f"unlit centering comparison: {centering_comparison_path}")
    print(f"keyframe proof sheet: {keyframe_sheet_path}")
    print(f"animated GIF: {gif_path}")
    print(f"QC report: {qc_path}")


if __name__ == "__main__":
    main()
