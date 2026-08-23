#!/usr/bin/env python3
"""Render only the center workflow/procedure strip as a controlled preview."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
POPULATED_PATH = ROOT / "APPROVED_POPULATED_LAYOUT.png"
CLEAR_PATH = ROOT / "APPROVED_CLEAR_BASE_LAYOUT.png"
OUT_DIR = ROOT / "workflow_strip_test_output"
SCRIPT_NAME = Path(__file__).name

EXPECTED_MASTER_SHA256 = {
    POPULATED_PATH: "90a223d08555853fd58c7bc7c0c30eadecfa7df3b5320db23e373462735312c4",
    CLEAR_PATH: "168d5b6ba745de5431f8fbaa9c5d5e4a95464b9e150f6aa23b862e4800d68f38",
}
PROTECTED_ARCHIVES = (
    ROOT / "approved_subsystems" / "subsystem_01_biohazard_APPROVED",
    ROOT / "approved_subsystems" / "subsystem_02_evidence_magnifier_APPROVED",
)

# Full populated-master procedure strip, including its dividers, legend, and
# panel border. The clear master is intentionally not a donor: its cards are
# smaller and roughly 49 px higher.
VIEW_BOUNDS = (423, 372, 1259, 546)
VIEW_SIZE = (VIEW_BOUNDS[2] - VIEW_BOUNDS[0], VIEW_BOUNDS[3] - VIEW_BOUNDS[1])
EXPECTED_VIEW_SHA256 = "174c770a4eee2ed6b17f43fcf5aeeab1bd59f1f753f576fe7bb62c7c3a013dd5"

STAGES = (
    "CASE_SCAN",
    "EVIDENCE_REVIEW",
    "VALIDATION",
    "ASSESSMENT",
    "PROBLEM_REVIEW",
)
STAGE_LABELS = {
    "CASE_SCAN": "CASE SCAN",
    "EVIDENCE_REVIEW": "EVIDENCE REVIEW",
    "VALIDATION": "VALIDATION",
    "ASSESSMENT": "ASSESSMENT",
    "PROBLEM_REVIEW": "PROBLEM REVIEW",
}

# Fixed populated-master geometry. All tuples use exclusive x2/y2.
STAGE_ROIS_GLOBAL = (
    (454, 387, 545, 492),
    (605, 387, 712, 492),
    (770, 387, 861, 492),
    (936, 387, 1031, 492),
    (1102, 387, 1206, 492),
)
EXPECTED_STAGE_MASK_COUNTS = (1859, 2435, 1996, 2351, 2249)
EXPECTED_STAGE_MASK_BBOXES = (
    (454, 387, 544, 492),
    (605, 387, 712, 492),
    (770, 387, 861, 492),
    (937, 387, 1031, 492),
    (1102, 387, 1206, 492),
)
ARROW_ROIS_GLOBAL = (
    (553, 409, 603, 426),
    (709, 410, 760, 426),
    (872, 410, 928, 426),
    (1041, 409, 1099, 426),
)
EXPECTED_ARROW_MASK_COUNTS = (382, 387, 413, 478)
EXPECTED_ARROW_MASK_BBOXES = ARROW_ROIS_GLOBAL
ANIMATION_SAFE_BOUNDS_GLOBAL = (450, 383, 1210, 495)
LEGEND_BOUNDS_GLOBAL = (543, 520, 1095, 539)

STATUS_COLORS = {
    "completed": np.array((48.0, 122.0, 207.0), dtype=np.float64),
    "current": np.array((226.0, 31.0, 27.0), dtype=np.float64),
    "pending": np.array((92.0, 92.0, 92.0), dtype=np.float64),
}
STATUS_GAINS = {"completed": 0.94, "pending": 0.76}

FRAME_COUNT = 120
FRAME_DURATION_MS = 50
FRAMES_PER_STAGE = FRAME_COUNT // len(STAGES)
TRANSITION_FRAME_COUNT = 6
TRANSITION_START = FRAMES_PER_STAGE - TRANSITION_FRAME_COUNT
PROOF_FRAME_INDICES = (9, 33, 57, 81, 105)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_array(array: np.ndarray) -> str:
    return sha256_bytes(np.ascontiguousarray(array).tobytes())


def snapshot_files(paths: tuple[Path, ...]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for directory in paths:
        if not directory.is_dir():
            raise AssertionError(f"Missing frozen subsystem archive: {directory}")
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                snapshot[str(path.relative_to(ROOT))] = sha256_bytes(path.read_bytes())
    return snapshot


def local_bounds(global_bounds: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return (
        global_bounds[0] - VIEW_BOUNDS[0],
        global_bounds[1] - VIEW_BOUNDS[1],
        global_bounds[2] - VIEW_BOUNDS[0],
        global_bounds[3] - VIEW_BOUNDS[1],
    )


def mask_bbox_global(mask: np.ndarray) -> tuple[int, int, int, int]:
    yy, xx = np.where(mask)
    if not len(xx):
        raise AssertionError("Workflow element mask is empty")
    return (
        int(np.min(xx)) + VIEW_BOUNDS[0],
        int(np.min(yy)) + VIEW_BOUNDS[1],
        int(np.max(xx)) + 1 + VIEW_BOUNDS[0],
        int(np.max(yy)) + 1 + VIEW_BOUNDS[1],
    )


def build_element_masks(
    source_view: np.ndarray,
) -> tuple[list[np.ndarray], list[np.ndarray], np.ndarray, list[float], list[float]]:
    """Extract the approved silhouettes once; never redraw or transform them."""
    stage_masks: list[np.ndarray] = []
    stage_norms: list[float] = []
    for index, bounds in enumerate(STAGE_ROIS_GLOBAL):
        x1, y1, x2, y2 = local_bounds(bounds)
        roi = source_view[y1:y2, x1:x2]
        maximum = np.max(roi, axis=2).astype(np.int16)
        minimum = np.min(roi, axis=2).astype(np.int16)
        chroma = maximum - minimum
        luminance = (
            0.2126 * roi[:, :, 0]
            + 0.7152 * roi[:, :, 1]
            + 0.0722 * roi[:, :, 2]
        )
        seed = (luminance >= 38.0) & (chroma <= 42)
        neighborhood = cv2.dilate(seed.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        local_mask = neighborhood & (luminance >= 10.0) & (chroma <= 55)
        mask = np.zeros(source_view.shape[:2], dtype=bool)
        mask[y1:y2, x1:x2] = local_mask
        if int(np.count_nonzero(mask)) != EXPECTED_STAGE_MASK_COUNTS[index]:
            raise AssertionError(f"Stage {STAGES[index]} silhouette changed")
        if mask_bbox_global(mask) != EXPECTED_STAGE_MASK_BBOXES[index]:
            raise AssertionError(f"Stage {STAGES[index]} geometry changed")
        stage_masks.append(mask)
        stage_norms.append(float(np.percentile(luminance[local_mask], 95.0)))

    arrow_masks: list[np.ndarray] = []
    arrow_norms: list[float] = []
    for index, bounds in enumerate(ARROW_ROIS_GLOBAL):
        x1, y1, x2, y2 = local_bounds(bounds)
        roi = source_view[y1:y2, x1:x2].astype(np.int16)
        red, green, blue = roi[:, :, 0], roi[:, :, 1], roi[:, :, 2]
        maximum = np.max(roi, axis=2)
        minimum = np.min(roi, axis=2)
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        if index < 3:
            seed = (blue >= 15) & (blue - red >= 5) & (blue - green >= 3)
        else:
            seed = (red >= 15) & (red - green >= 5) & (red - blue >= 5)
        neighborhood = cv2.dilate(seed.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        local_mask = neighborhood & ((maximum - minimum) >= 3) & (luminance >= 3.0)
        mask = np.zeros(source_view.shape[:2], dtype=bool)
        mask[y1:y2, x1:x2] = local_mask
        if int(np.count_nonzero(mask)) != EXPECTED_ARROW_MASK_COUNTS[index]:
            raise AssertionError(f"Workflow connector {index + 1} silhouette changed")
        if mask_bbox_global(mask) != EXPECTED_ARROW_MASK_BBOXES[index]:
            raise AssertionError(f"Workflow connector {index + 1} geometry changed")
        arrow_masks.append(mask)
        arrow_norms.append(float(np.percentile(luminance[local_mask], 95.0)))

    animation_union = np.any(
        np.stack((*stage_masks, *arrow_masks), axis=0),
        axis=0,
    )
    safe_x1, safe_y1, safe_x2, safe_y2 = local_bounds(ANIMATION_SAFE_BOUNDS_GLOBAL)
    safe_mask = np.zeros(source_view.shape[:2], dtype=bool)
    safe_mask[safe_y1:safe_y2, safe_x1:safe_x2] = True
    if np.any(animation_union & ~safe_mask):
        raise AssertionError("Workflow silhouette escaped its declared safe region")
    legend_x1, legend_y1, legend_x2, legend_y2 = local_bounds(LEGEND_BOUNDS_GLOBAL)
    if np.any(animation_union[legend_y1:legend_y2, legend_x1:legend_x2]):
        raise AssertionError("Workflow animation mask overlaps the fixed legend")
    return stage_masks, arrow_masks, animation_union, stage_norms, arrow_norms


def statuses_for_stage(current_stage: str) -> tuple[list[str], list[str]]:
    """Return state-correct card and incoming-flow connector statuses."""
    if current_stage not in STAGES:
        raise ValueError(f"Unknown current_stage={current_stage!r}; expected one of {STAGES}")
    current_index = STAGES.index(current_stage)
    card_statuses = [
        "completed" if index < current_index else "current" if index == current_index else "pending"
        for index in range(len(STAGES))
    ]
    arrow_statuses: list[str] = []
    for arrow_index in range(len(ARROW_ROIS_GLOBAL)):
        if arrow_index < current_index - 1:
            arrow_statuses.append("completed")
        elif arrow_index == current_index - 1:
            arrow_statuses.append("current")
        else:
            arrow_statuses.append("pending")
    return card_statuses, arrow_statuses


def recolor_mask(
    frame: np.ndarray,
    source_view: np.ndarray,
    mask: np.ndarray,
    normalization: float,
    status: str,
    gain: float,
) -> None:
    source = source_view[mask].astype(np.float64)
    luminance = 0.2126 * source[:, 0] + 0.7152 * source[:, 1] + 0.0722 * source[:, 2]
    strength = np.clip(luminance / max(normalization, 1.0), 0.0, 1.0)
    colored = STATUS_COLORS[status][None, :] * strength[:, None] * gain
    frame[mask] = np.rint(np.clip(colored, 0.0, 255.0)).astype(np.uint8)


def render_workflow_state(
    source_view: np.ndarray,
    stage_masks: list[np.ndarray],
    arrow_masks: list[np.ndarray],
    stage_norms: list[float],
    arrow_norms: list[float],
    current_stage: str,
    emphasis_phase: float,
) -> np.ndarray:
    """Render one fixed-geometry state from the explicit current_stage argument."""
    card_statuses, arrow_statuses = statuses_for_stage(current_stage)
    frame = source_view.copy()
    breathing = 0.5 - 0.5 * math.cos(math.tau * (emphasis_phase % 1.0))
    for mask, normalization, status in zip(stage_masks, stage_norms, card_statuses):
        gain = 0.98 + 0.10 * breathing if status == "current" else STATUS_GAINS[status]
        recolor_mask(frame, source_view, mask, normalization, status, gain)

    for index, (mask, normalization, status) in enumerate(
        zip(arrow_masks, arrow_norms, arrow_statuses)
    ):
        gain = 1.0 if status == "current" else STATUS_GAINS[status]
        recolor_mask(frame, source_view, mask, normalization, status, gain)
        if status == "current":
            yy, xx = np.where(mask)
            minimum_x = float(np.min(xx))
            maximum_x = float(np.max(xx))
            glint_center = minimum_x + (maximum_x - minimum_x) * (emphasis_phase % 1.0)
            sigma = max(2.5, (maximum_x - minimum_x) * 0.11)
            glint = np.exp(-0.5 * ((xx.astype(np.float64) - glint_center) / sigma) ** 2)
            lifted = frame[yy, xx].astype(np.float64) + 12.0 * glint[:, None]
            frame[yy, xx] = np.rint(np.clip(lifted, 0.0, 255.0)).astype(np.uint8)
    return frame


def smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def render_preview_frame(
    source_view: np.ndarray,
    stage_masks: list[np.ndarray],
    arrow_masks: list[np.ndarray],
    animation_union: np.ndarray,
    stage_norms: list[float],
    arrow_norms: list[float],
    frame_index: int,
) -> np.ndarray:
    if not 0 <= frame_index <= FRAME_COUNT:
        raise ValueError(f"Preview frame outside closed range: {frame_index}")
    if frame_index == FRAME_COUNT:
        return render_workflow_state(
            source_view,
            stage_masks,
            arrow_masks,
            stage_norms,
            arrow_norms,
            STAGES[0],
            0.0,
        )
    stage_index = frame_index // FRAMES_PER_STAGE
    local_frame = frame_index % FRAMES_PER_STAGE
    phase = local_frame / FRAMES_PER_STAGE
    first = render_workflow_state(
        source_view,
        stage_masks,
        arrow_masks,
        stage_norms,
        arrow_norms,
        STAGES[stage_index],
        phase,
    )
    if local_frame < TRANSITION_START:
        return first
    next_index = (stage_index + 1) % len(STAGES)
    transition_sample = local_frame - TRANSITION_START + 1
    linear_progress = transition_sample / (TRANSITION_FRAME_COUNT + 1)
    progress = smoothstep(linear_progress)
    second = render_workflow_state(
        source_view,
        stage_masks,
        arrow_masks,
        stage_norms,
        arrow_norms,
        STAGES[next_index],
        linear_progress / FRAMES_PER_STAGE,
    )
    blended = source_view.copy()
    blended_values = (
        (1.0 - progress) * first[animation_union].astype(np.float64)
        + progress * second[animation_union].astype(np.float64)
    )
    blended[animation_union] = np.rint(np.clip(blended_values, 0.0, 255.0)).astype(np.uint8)
    return blended


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


def array_bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    yy, xx = np.where(mask)
    return int(np.min(xx)), int(np.min(yy)), int(np.max(xx)) + 1, int(np.max(yy)) + 1


def make_proof_sheet(
    decoded_frames: list[np.ndarray],
    proof_path: Path,
) -> list[tuple[int, int, int, int]]:
    margin = 12
    gap = 12
    header = 32
    cell_width, cell_height = VIEW_SIZE[0], VIEW_SIZE[1] + header
    sheet_width = margin * 2 + cell_width * 2 + gap
    sheet_height = margin * 2 + cell_height * 3 + gap * 2
    sheet = Image.new("RGB", (sheet_width, sheet_height), (12, 12, 12))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    panel_origins = (
        (margin, margin),
        (margin + cell_width + gap, margin),
        (margin, margin + cell_height + gap),
        (margin + cell_width + gap, margin + cell_height + gap),
        ((sheet_width - cell_width) // 2, margin + 2 * (cell_height + gap)),
    )
    pasted_bounds: list[tuple[int, int, int, int]] = []
    for stage, frame_index, (x, y) in zip(STAGES, PROOF_FRAME_INDICES, panel_origins):
        draw.rectangle((x, y, x + cell_width - 1, y + header - 1), fill=(22, 22, 22))
        draw.text(
            (x + 10, y + 9),
            f"current_stage = {stage}   |   {STAGE_LABELS[stage]}",
            fill=(235, 235, 235),
            font=font,
        )
        sheet.paste(Image.fromarray(decoded_frames[frame_index], "RGB"), (x, y + header))
        pasted_bounds.append((x, y + header, x + cell_width, y + header + VIEW_SIZE[1]))
    sheet.save(proof_path)
    reopened = np.array(Image.open(proof_path).convert("RGB"))
    for frame_index, (x1, y1, x2, y2) in zip(PROOF_FRAME_INDICES, pasted_bounds):
        if not np.array_equal(reopened[y1:y2, x1:x2], decoded_frames[frame_index]):
            raise AssertionError(f"Proof panel differs from decoded GIF frame {frame_index}")
    return pasted_bounds


def assert_state_colors(
    decoded_frames: list[np.ndarray],
    stage_masks: list[np.ndarray],
    arrow_masks: list[np.ndarray],
) -> None:
    for current_index, frame_index in enumerate(PROOF_FRAME_INDICES):
        card_statuses, arrow_statuses = statuses_for_stage(STAGES[current_index])
        for mask, status in zip(stage_masks, card_statuses):
            mean = np.mean(decoded_frames[frame_index][mask].astype(np.float64), axis=0)
            if status == "completed" and mean[2] - mean[0] < 25.0:
                raise AssertionError("Completed workflow card is not blue in decoded proof")
            if status == "current" and mean[0] - max(mean[1], mean[2]) < 35.0:
                raise AssertionError("Current workflow card is not red in decoded proof")
            if status == "pending" and float(np.max(mean) - np.min(mean)) > 5.0:
                raise AssertionError("Pending workflow card is not gray in decoded proof")
        for mask, status in zip(arrow_masks, arrow_statuses):
            mean = np.mean(decoded_frames[frame_index][mask].astype(np.float64), axis=0)
            if status == "completed" and mean[2] - mean[0] < 25.0:
                raise AssertionError("Completed connector is not blue in decoded proof")
            if status == "current" and mean[0] - max(mean[1], mean[2]) < 35.0:
                raise AssertionError("Current connector is not red in decoded proof")
            if status == "pending" and float(np.max(mean) - np.min(mean)) > 5.0:
                raise AssertionError("Pending connector is not gray in decoded proof")


def main() -> None:
    protected_before_by_archive = tuple(
        snapshot_files((archive,)) for archive in PROTECTED_ARCHIVES
    )
    protected_before = snapshot_files(PROTECTED_ARCHIVES)
    master_hashes = {path: sha256_bytes(path.read_bytes()) for path in EXPECTED_MASTER_SHA256}
    for path, expected in EXPECTED_MASTER_SHA256.items():
        if master_hashes[path] != expected:
            raise AssertionError(f"Approved master changed: {path.name}")

    populated = Image.open(POPULATED_PATH).convert("RGB")
    clear = Image.open(CLEAR_PATH).convert("RGB")
    if populated.size != (1727, 911) or clear.size != (1727, 911):
        raise AssertionError("Approved master dimensions changed")
    populated_rgb = np.array(populated)
    x1, y1, x2, y2 = VIEW_BOUNDS
    source_view = populated_rgb[y1:y2, x1:x2].copy()
    if source_view.shape[:2] != (VIEW_SIZE[1], VIEW_SIZE[0]):
        raise AssertionError(f"Workflow viewport changed size: {source_view.shape}")
    if sha256_array(source_view) != EXPECTED_VIEW_SHA256:
        raise AssertionError("Approved populated workflow pixels changed")

    stage_masks, arrow_masks, animation_union, stage_norms, arrow_norms = build_element_masks(
        source_view
    )
    raw_frames = [
        render_preview_frame(
            source_view,
            stage_masks,
            arrow_masks,
            animation_union,
            stage_norms,
            arrow_norms,
            frame_index,
        )
        for frame_index in range(FRAME_COUNT)
    ]
    closure = render_preview_frame(
        source_view,
        stage_masks,
        arrow_masks,
        animation_union,
        stage_norms,
        arrow_norms,
        FRAME_COUNT,
    )
    if not np.array_equal(closure, raw_frames[0]):
        raise AssertionError("Workflow preview does not close exactly at frame 120")
    if not all(
        np.array_equal(frame[~animation_union], source_view[~animation_union])
        for frame in raw_frames
    ):
        raise AssertionError("Raw source-frame pixels changed outside workflow silhouettes")
    master_animation_mask = np.zeros(populated_rgb.shape[:2], dtype=bool)
    master_animation_mask[y1:y2, x1:x2] = animation_union
    for frame in raw_frames:
        full_control = populated_rgb.copy()
        full_control[y1:y2, x1:x2] = frame
        if not np.array_equal(full_control[~master_animation_mask], populated_rgb[~master_animation_mask]):
            raise AssertionError("A source frame changed pixels outside the intended workflow region")

    representative_indices = tuple(
        sorted(set((*PROOF_FRAME_INDICES, 18, 23, 42, 47, 66, 71, 90, 95, 114, 119)))
    )
    palette_source = Image.new(
        "RGB",
        (VIEW_SIZE[0], VIEW_SIZE[1] * len(representative_indices)),
    )
    for row, frame_index in enumerate(representative_indices):
        palette_source.paste(
            Image.fromarray(raw_frames[frame_index], "RGB"),
            (0, row * VIEW_SIZE[1]),
        )
    palette = palette_source.quantize(
        colors=256,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    palette_bytes = bytes(palette.getpalette() or [])
    if len(palette_bytes) != 768:
        raise AssertionError("Workflow GIF palette is not 256 colors")
    encoded_frames = [
        Image.fromarray(frame, "RGB").quantize(palette=palette, dither=Image.Dither.NONE)
        for frame in raw_frames
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gif_path = OUT_DIR / "workflow_strip_preview_6s.gif"
    staging_path = OUT_DIR / ".workflow_strip_preview_6s.staging.gif"
    encoded_frames[0].save(
        staging_path,
        format="GIF",
        save_all=True,
        append_images=encoded_frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=False,
        disposal=1,
        palette=palette_bytes,
    )

    decoded_frames: list[np.ndarray] = []
    durations: list[int] = []
    disposals: list[int] = []
    with Image.open(staging_path) as gif:
        gif_format = gif.format
        gif_size = gif.size
        gif_frame_count = gif.n_frames
        gif_loop = gif.info.get("loop")
        for frame_index in range(gif.n_frames):
            gif.seek(frame_index)
            durations.append(int(gif.info.get("duration", 0)))
            disposals.append(int(getattr(gif, "disposal_method", 0)))
            decoded_frames.append(np.array(gif.convert("RGB")))

    logical_size, descriptors, encoded_palette = parse_gif(staging_path)
    if (
        gif_format != "GIF"
        or gif_size != VIEW_SIZE
        or logical_size != VIEW_SIZE
        or gif_frame_count != FRAME_COUNT
        or len(descriptors) != FRAME_COUNT
        or gif_loop != 0
        or set(durations) != {FRAME_DURATION_MS}
        or sum(durations) != FRAME_COUNT * FRAME_DURATION_MS
        or set(disposals) != {1}
    ):
        raise AssertionError("Workflow GIF format/canvas/count/timing/loop/disposal failed")
    if any(
        descriptor[4]
        or descriptor[5]
        or descriptor[6] != 1
        or descriptor[7] != FRAME_DURATION_MS // 10
        or descriptor[8]
        for descriptor in descriptors
    ):
        raise AssertionError("Workflow GIF palette/interlace/disposal/delay/transparency failed")
    if encoded_palette != palette_bytes:
        raise AssertionError("Workflow GIF global palette changed")
    expected_decoded = [np.array(frame.convert("RGB")) for frame in encoded_frames]
    if not all(
        np.array_equal(actual, expected)
        for actual, expected in zip(decoded_frames, expected_decoded)
    ):
        raise AssertionError("Decoded workflow GIF differs from intended frames")
    decoded_unique_count = len({sha256_array(frame) for frame in decoded_frames})
    # The stage-1 card breath is deliberately symmetric, so a few non-adjacent
    # poses repeat on opposite sides of its cycle. Adjacent dwell is forbidden.
    if decoded_unique_count < 100:
        raise AssertionError(
            f"Workflow GIF contains too few distinct emphasis poses: {decoded_unique_count}"
        )
    if not all(
        not np.array_equal(decoded_frames[index], decoded_frames[index - 1])
        for index in range(1, FRAME_COUNT)
    ):
        raise AssertionError("Workflow GIF contains an adjacent motion dwell")
    if not all(
        np.array_equal(frame[~animation_union], decoded_frames[0][~animation_union])
        for frame in decoded_frames[1:]
    ):
        raise AssertionError("Decoded pixels outside workflow silhouettes shimmered")

    descriptor_rectangles: list[tuple[int, int, int, int]] = []
    for frame_index, descriptor in enumerate(descriptors):
        left, top, width, height = descriptor[:4]
        rectangle = (left, top, left + width, top + height)
        descriptor_rectangles.append(rectangle)
        if frame_index == 0:
            if rectangle != (0, 0, VIEW_SIZE[0], VIEW_SIZE[1]):
                raise AssertionError("Workflow GIF first frame is not full canvas")
            continue
        difference = np.any(
            expected_decoded[frame_index] != expected_decoded[frame_index - 1],
            axis=2,
        )
        expected_rectangle = array_bbox(difference)
        if rectangle != expected_rectangle:
            raise AssertionError(
                f"Workflow GIF delta rectangle mismatch at frame {frame_index}: "
                f"{rectangle} vs {expected_rectangle}"
            )
    staging_path.replace(gif_path)
    if gif_path.stat().st_size > 3 * 1024 * 1024:
        raise AssertionError(f"Workflow GIF is not lightweight: {gif_path.stat().st_size} bytes")

    assert_state_colors(decoded_frames, stage_masks, arrow_masks)
    proof_path = OUT_DIR / "workflow_strip_all_five_states_proof.png"
    make_proof_sheet(decoded_frames, proof_path)

    legend_x1, legend_y1, legend_x2, legend_y2 = local_bounds(LEGEND_BOUNDS_GLOBAL)
    if not all(
        np.array_equal(
            frame[legend_y1:legend_y2, legend_x1:legend_x2],
            decoded_frames[0][legend_y1:legend_y2, legend_x1:legend_x2],
        )
        for frame in decoded_frames[1:]
    ):
        raise AssertionError("Completed/current/pending legend changed between states")

    qc_path = OUT_DIR / "workflow_strip_qc.txt"
    qc_lines = (
        "Subsystem #3 workflow/procedure strip isolated QC",
        f"script_used={SCRIPT_NAME}",
        f"approved_populated_master={POPULATED_PATH.name} role=sole pixel and geometry source sha256={master_hashes[POPULATED_PATH]}",
        f"approved_clear_master={CLEAR_PATH.name} role=hash-verified alignment reference only; not composited sha256={master_hashes[CLEAR_PATH]}",
        "preview_variable_name=current_stage",
        "preview_values=" + ",".join(STAGES),
        "state_logic=completed blue; current red; pending gray; incoming current flow red",
        f"dimensions={VIEW_SIZE[0]}x{VIEW_SIZE[1]}",
        f"frame_count={FRAME_COUNT} duration_per_frame={FRAME_DURATION_MS}ms total_duration={FRAME_COUNT * FRAME_DURATION_MS}ms loop=0",
        f"proof_frames={PROOF_FRAME_INDICES} one decoded frame per controlled state",
        f"animation_region_global={ANIMATION_SAFE_BOUNDS_GLOBAL} changed_support_pixels={int(np.count_nonzero(animation_union))}",
        "source_frames_outside_intended_workflow_animation_region_changed_pixels=0",
        "cards_icons_labels_arrows_fixed=True transforms=0 resizing=False drifting=False",
        "legend_completed_blue_current_red_pending_gray=True legend_geometry_fixed=True",
        f"gif_real=True delta_frames_verified={FRAME_COUNT - 1}/{FRAME_COUNT - 1} shared_palette=True size_bytes={gif_path.stat().st_size}",
        f"decoded_unique_frames={decoded_unique_count}/{FRAME_COUNT} adjacent_duplicate_frames=0",
        f"frozen_subsystem_01_unchanged={snapshot_files((PROTECTED_ARCHIVES[0],)) == protected_before_by_archive[0]}",
        f"frozen_subsystem_02_unchanged={snapshot_files((PROTECTED_ARCHIVES[1],)) == protected_before_by_archive[1]}",
        "approved_masters_modified=False final_dashboard_integration=False other_subsystems_animated=False",
    )
    qc_path.write_text("\n".join(qc_lines) + "\n", encoding="utf-8")

    expected_outputs = {gif_path.name, proof_path.name, qc_path.name}
    actual_outputs = {path.name for path in OUT_DIR.iterdir() if path.is_file()}
    if actual_outputs != expected_outputs:
        raise AssertionError(f"Unexpected workflow output manifest: {sorted(actual_outputs)}")
    if snapshot_files(PROTECTED_ARCHIVES) != protected_before:
        raise AssertionError("A frozen approved subsystem changed during workflow rendering")
    for path, expected in EXPECTED_MASTER_SHA256.items():
        if sha256_bytes(path.read_bytes()) != expected:
            raise AssertionError(f"Approved master changed during render: {path.name}")

    print(f"workflow GIF: {gif_path}")
    print(f"five-state proof: {proof_path}")
    print(f"QC note: {qc_path}")
    print(f"GIF size: {gif_path.stat().st_size} bytes")
    print(f"changed support: {int(np.count_nonzero(animation_union))} pixels")


if __name__ == "__main__":
    main()
