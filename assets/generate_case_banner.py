#!/usr/bin/env python3

"""
Generate the animated README banner for BioDefense-Intelligence-Division.

The banner uses the current repository data and refreshes whenever the
Daily Investigation GitHub Actions workflow runs.

Reads:
    data/current_case.json
    operations/active_operation.json
    reports/bioterror_threat_score_csharp.json

Writes:
    assets/biodefense-case-scan.gif

Design:
    - Wide 3:1 repository banner
    - Dark charcoal background
    - Blue intelligence accents
    - Red investigative-alert accents
    - No government seals, clearance labels, agency claims, or
      official-affiliation language
    - Continuous scan and evidence-correlation animation
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


# ============================================================
# Repository paths
# ============================================================

CURRENT_CASE_PATH = Path("data/current_case.json")
ACTIVE_OPERATION_PATH = Path(
    "operations/active_operation.json"
)
THREAT_SCORE_PATH = Path(
    "reports/bioterror_threat_score_csharp.json"
)

ASSETS_DIRECTORY = Path("assets")
OUTPUT_GIF_PATH = (
    ASSETS_DIRECTORY
    / "biodefense-case-scan.gif"
)


# ============================================================
# Banner settings
# ============================================================

WIDTH = 1800
HEIGHT = 600
FRAME_COUNT = 16
FRAME_DURATION_MS = 105

BACKGROUND = (7, 11, 18, 255)
PANEL = (13, 20, 31, 245)
PANEL_ALT = (15, 23, 36, 245)

TEXT = (229, 235, 242, 255)
TEXT_SOFT = (157, 171, 189, 255)
TEXT_DIM = (105, 121, 142, 255)

BLUE = (56, 153, 255, 255)
BLUE_SOFT = (56, 153, 255, 80)
BLUE_DARK = (23, 71, 126, 255)

RED = (230, 68, 78, 255)
RED_SOFT = (230, 68, 78, 72)
RED_DARK = (112, 33, 42, 255)

GRID = (26, 37, 54, 255)
BORDER = (55, 76, 105, 255)
WHITE = (248, 250, 252, 255)


# ============================================================
# Data helpers
# ============================================================

def load_json(
    path: Path,
    required: bool = True,
) -> dict[str, Any]:
    """Load a JSON object from disk."""

    if not path.exists():
        if required:
            raise FileNotFoundError(
                f"Required file not found: {path}"
            )

        return {}

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

    except json.JSONDecodeError as error:
        if required:
            raise ValueError(
                f"Invalid JSON in {path}: {error}"
            ) from error

        return {}

    if not isinstance(data, dict):
        if required:
            raise ValueError(
                f"Expected a JSON object in {path}"
            )

        return {}

    return data


def text_value(
    value: Any,
    default: str = "Not available",
) -> str:
    """Return a readable string."""

    if value is None:
        return default

    text = str(value).strip()

    return text if text else default


def integer_value(
    value: Any,
    default: int = 0,
) -> int:
    """Convert a value to an integer safely."""

    try:
        return int(float(str(value).strip()))

    except (TypeError, ValueError):
        return default


def deep_find(
    data: Any,
    keys: set[str],
) -> Any:
    """
    Recursively find the first value whose key matches one of the
    supplied names. Matching is case-insensitive.
    """

    normalized_keys = {
        key.lower()
        for key in keys
    }

    if isinstance(data, dict):
        for key, value in data.items():
            if str(key).lower() in normalized_keys:
                return value

        for value in data.values():
            found = deep_find(
                value,
                normalized_keys,
            )

            if found is not None:
                return found

    elif isinstance(data, list):
        for item in data:
            found = deep_find(
                item,
                normalized_keys,
            )

            if found is not None:
                return found

    return None


def utc_timestamp() -> str:
    """Return a compact UTC timestamp."""

    return datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")


def build_display_data(
    case: dict[str, Any],
    operation: dict[str, Any],
    score_data: dict[str, Any],
) -> dict[str, Any]:
    """Collect the fields shown in the animated banner."""

    overall_score = integer_value(
        deep_find(
            score_data,
            {
                "overallScore",
                "overall_score",
                "score",
            },
        ),
        integer_value(
            case.get("risk_score"),
            0,
        ),
    )

    overall_level = text_value(
        deep_find(
            score_data,
            {
                "overallLevel",
                "overall_level",
                "level",
                "rating",
            },
        ),
        text_value(
            case.get("severity"),
            "Unknown",
        ),
    ).upper()

    evidence_records = integer_value(
        deep_find(
            score_data,
            {
                "evidenceRecords",
                "evidence_records",
            },
        ),
        integer_value(
            case.get("evidence_count"),
            0,
        ),
    )

    return {
        "case_id": text_value(
            case.get("case_id"),
            "UNKNOWN-CASE",
        ),
        "classification": text_value(
            case.get("classification"),
        ),
        "threat_family": text_value(
            case.get("threat_family"),
        ),
        "severity": text_value(
            case.get("severity"),
        ).upper(),
        "priority": text_value(
            case.get("priority"),
        ).upper(),
        "platform": text_value(
            case.get("affected_platform"),
        ),
        "vendor": text_value(
            case.get("vendor"),
        ),
        "device": text_value(
            case.get("device_family"),
        ),
        "zone": text_value(
            case.get("network_zone"),
        ),
        "lead": text_value(
            case.get("lead_analyst"),
        ),
        "initial_access": text_value(
            case.get("initial_access"),
        ),
        "confidence": integer_value(
            case.get("confidence"),
            0,
        ),
        "affected_assets": integer_value(
            case.get("affected_assets"),
            0,
        ),
        "evidence_records": evidence_records,
        "indicator_records": integer_value(
            case.get(
                "ioc_count",
                operation.get(
                    "ioc_count",
                    0,
                ),
            ),
            0,
        ),
        "case_risk": integer_value(
            case.get("risk_score"),
            0,
        ),
        "overall_score": overall_score,
        "overall_level": overall_level,
        "campaign_id": text_value(
            operation.get("campaign_id"),
        ),
        "campaign_name": text_value(
            operation.get("operation"),
        ),
        "designation": text_value(
            operation.get(
                "threat_designation"
            ),
        ),
        "phase": text_value(
            operation.get("campaign_phase"),
        ),
        "containment": text_value(
            operation.get(
                "containment_level"
            ),
        ),
        "active_cases": integer_value(
            operation.get("active_cases"),
            0,
        ),
        "updated": utc_timestamp(),
    }


# ============================================================
# Font and drawing helpers
# ============================================================

def font(
    size: int,
    bold: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a readable font available on GitHub's Ubuntu runner."""

    candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/"
            + (
                "DejaVuSans-Bold.ttf"
                if bold
                else "DejaVuSans.ttf"
            )
        ),
        (
            "/usr/share/fonts/truetype/liberation2/"
            + (
                "LiberationSans-Bold.ttf"
                if bold
                else "LiberationSans-Regular.ttf"
            )
        ),
        (
            "C:/Windows/Fonts/"
            + (
                "arialbd.ttf"
                if bold
                else "arial.ttf"
            )
        ),
    ]

    for candidate in candidates:
        try:
            return ImageFont.truetype(
                candidate,
                size=size,
            )

        except OSError:
            continue

    return ImageFont.load_default()


TITLE_FONT = font(48, bold=True)
SUBTITLE_FONT = font(19)
SECTION_FONT = font(17, bold=True)
LABEL_FONT = font(14, bold=True)
VALUE_FONT = font(17)
VALUE_BOLD_FONT = font(18, bold=True)
SCORE_FONT = font(68, bold=True)
SMALL_FONT = font(12)
MICRO_FONT = font(10)


def fit_text(
    draw: ImageDraw.ImageDraw,
    value: str,
    maximum_width: int,
    preferred_size: int,
    minimum_size: int = 11,
    bold: bool = False,
):
    """Choose a font size that fits the available width."""

    size = preferred_size

    while size > minimum_size:
        candidate = font(
            size,
            bold=bold,
        )

        bounds = draw.textbbox(
            (0, 0),
            value,
            font=candidate,
        )

        if bounds[2] - bounds[0] <= maximum_width:
            return candidate

        size -= 1

    return font(
        minimum_size,
        bold=bold,
    )


def shorten(
    value: str,
    maximum_characters: int,
) -> str:
    """Shorten long labels cleanly."""

    value = text_value(value)

    if len(value) <= maximum_characters:
        return value

    return (
        value[: maximum_characters - 1].rstrip()
        + "…"
    )


def rounded_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    accent: tuple[int, int, int, int],
    fill: tuple[int, int, int, int] = PANEL,
) -> None:
    """Draw a structured interface panel."""

    draw.rounded_rectangle(
        box,
        radius=12,
        fill=fill,
        outline=BORDER,
        width=2,
    )

    x1, y1, x2, _ = box

    draw.line(
        (x1 + 18, y1 + 42, x2 - 18, y1 + 42),
        fill=accent,
        width=2,
    )

    draw.line(
        (x1 + 18, y1 + 47, x1 + 130, y1 + 47),
        fill=(
            accent[0],
            accent[1],
            accent[2],
            80,
        ),
        width=1,
    )


def label_value(
    draw: ImageDraw.ImageDraw,
    label: str,
    value: str,
    x: int,
    y: int,
    label_width: int,
    value_width: int,
) -> None:
    """Draw a compact label-and-value row."""

    draw.text(
        (x, y),
        label.upper(),
        font=LABEL_FONT,
        fill=TEXT_DIM,
    )

    rendered_value = shorten(
        value,
        47,
    )

    value_font = fit_text(
        draw,
        rendered_value,
        value_width,
        preferred_size=17,
        minimum_size=12,
    )

    draw.text(
        (x + label_width, y - 2),
        rendered_value,
        font=value_font,
        fill=TEXT,
    )


# ============================================================
# Background and animated interface
# ============================================================

def build_background() -> Image.Image:
    """Create the static red-and-blue investigative interface."""

    image = Image.new(
        "RGBA",
        (WIDTH, HEIGHT),
        BACKGROUND,
    )

    draw = ImageDraw.Draw(
        image,
        "RGBA",
    )

    # Soft vertical gradient.
    for y in range(HEIGHT):
        factor = y / HEIGHT

        color = (
            int(7 + 5 * factor),
            int(11 + 6 * factor),
            int(18 + 10 * factor),
            255,
        )

        draw.line(
            (0, y, WIDTH, y),
            fill=color,
            width=1,
        )

    # Fine technical grid.
    for x in range(0, WIDTH, 50):
        draw.line(
            (x, 0, x, HEIGHT),
            fill=GRID,
            width=1,
        )

    for y in range(0, HEIGHT, 40):
        draw.line(
            (0, y, WIDTH, y),
            fill=GRID,
            width=1,
        )

    # Upper accent rails.
    draw.rectangle(
        (0, 0, WIDTH, 8),
        fill=BLUE_DARK,
    )

    draw.rectangle(
        (0, 8, 525, 11),
        fill=BLUE,
    )

    draw.rectangle(
        (1275, 8, WIDTH, 11),
        fill=RED,
    )

    # Header.
    draw.text(
        (38, 26),
        "BioDefense-Intelligence-Division",
        font=TITLE_FONT,
        fill=WHITE,
    )

    draw.text(
        (41, 82),
        "Cyber-Biothreat Intelligence & Evidence Analysis",
        font=SUBTITLE_FONT,
        fill=BLUE,
    )

    draw.text(
        (WIDTH - 38, 31),
        "DYNAMIC CASE RECORD",
        font=SECTION_FONT,
        fill=TEXT_SOFT,
        anchor="ra",
    )

    draw.text(
        (WIDTH - 38, 61),
        "INDEPENDENT PORTFOLIO SIMULATION",
        font=SMALL_FONT,
        fill=TEXT_DIM,
        anchor="ra",
    )

    draw.line(
        (38, 110, WIDTH - 38, 110),
        fill=BORDER,
        width=2,
    )

    # Main panels.
    rounded_panel(
        draw,
        (28, 130, 920, 524),
        BLUE,
        PANEL,
    )

    rounded_panel(
        draw,
        (940, 130, 1324, 524),
        RED,
        PANEL_ALT,
    )

    rounded_panel(
        draw,
        (1344, 130, 1772, 524),
        BLUE,
        PANEL,
    )

    draw.text(
        (50, 148),
        "ACTIVE INVESTIGATION",
        font=SECTION_FONT,
        fill=BLUE,
    )

    draw.text(
        (962, 148),
        "CAMPAIGN / THREAT ASSESSMENT",
        font=SECTION_FONT,
        fill=RED,
    )

    draw.text(
        (1366, 148),
        "EVIDENCE CORRELATION",
        font=SECTION_FONT,
        fill=BLUE,
    )

    # Footer.
    draw.rectangle(
        (0, 548, WIDTH, HEIGHT),
        fill=(4, 7, 12, 235),
    )

    draw.line(
        (0, 548, WIDTH, 548),
        fill=BORDER,
        width=2,
    )

    draw.text(
        (38, 568),
        "Automated case generation • evidence reconstruction • "
        "structured threat analysis",
        font=SMALL_FONT,
        fill=TEXT_SOFT,
    )

    return image


def draw_case_panel(
    draw: ImageDraw.ImageDraw,
    data: dict[str, Any],
) -> None:
    """Draw the active investigation panel."""

    x = 52
    y = 202
    row_gap = 39

    rows = [
        ("Case ID", data["case_id"]),
        (
            "Classification",
            data["classification"],
        ),
        (
            "Threat Family",
            data["threat_family"],
        ),
        (
            "Severity / Priority",
            (
                f"{data['severity']} / "
                f"{data['priority']}"
            ),
        ),
        (
            "Target",
            (
                f"{data['platform']} • "
                f"{data['vendor']} "
                f"{data['device']}"
            ),
        ),
        ("Network Zone", data["zone"]),
        ("Lead Analyst", data["lead"]),
        (
            "Initial Access",
            data["initial_access"],
        ),
    ]

    for index, (label, value) in enumerate(rows):
        row_y = y + index * row_gap

        label_value(
            draw,
            label,
            value,
            x,
            row_y,
            label_width=176,
            value_width=640,
        )

        if index < len(rows) - 1:
            draw.line(
                (
                    x,
                    row_y + 27,
                    894,
                    row_y + 27,
                ),
                fill=(43, 57, 76, 170),
                width=1,
            )

    # Bottom metrics.
    metric_y = 480

    metrics = [
        (
            "CONFIDENCE",
            f"{data['confidence']}%",
            BLUE,
        ),
        (
            "AFFECTED ASSETS",
            str(data["affected_assets"]),
            RED,
        ),
        (
            "CASE RISK",
            str(data["case_risk"]),
            BLUE,
        ),
    ]

    metric_x = 52

    for label, value, accent in metrics:
        draw.rounded_rectangle(
            (
                metric_x,
                metric_y - 24,
                metric_x + 250,
                metric_y + 23,
            ),
            radius=8,
            fill=(15, 24, 37, 235),
            outline=(
                accent[0],
                accent[1],
                accent[2],
                180,
            ),
            width=1,
        )

        draw.text(
            (metric_x + 14, metric_y - 12),
            label,
            font=MICRO_FONT,
            fill=TEXT_DIM,
        )

        draw.text(
            (metric_x + 230, metric_y - 15),
            value,
            font=VALUE_BOLD_FONT,
            fill=accent,
            anchor="ra",
        )

        metric_x += 270


def draw_campaign_panel(
    draw: ImageDraw.ImageDraw,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    """Draw campaign and threat-score details."""

    x = 962

    campaign_font = fit_text(
        draw,
        shorten(
            data["campaign_name"],
            42,
        ),
        maximum_width=330,
        preferred_size=16,
        minimum_size=11,
        bold=True,
    )

    draw.text(
        (x, 202),
        data["campaign_id"],
        font=VALUE_BOLD_FONT,
        fill=WHITE,
    )

    draw.text(
        (x, 233),
        shorten(
            data["campaign_name"],
            42,
        ),
        font=campaign_font,
        fill=TEXT,
    )

    draw.text(
        (x, 269),
        (
            f"{data['designation']}  •  "
            f"{data['phase']}"
        ),
        font=SMALL_FONT,
        fill=TEXT_SOFT,
    )

    draw.line(
        (x, 296, 1302, 296),
        fill=(58, 70, 89, 190),
        width=1,
    )

    draw.text(
        (x, 315),
        "THREAT SCORE",
        font=LABEL_FONT,
        fill=TEXT_DIM,
    )

    draw.text(
        (x, 341),
        str(data["overall_score"]),
        font=SCORE_FONT,
        fill=RED,
    )

    draw.text(
        (1112, 351),
        data["overall_level"],
        font=VALUE_BOLD_FONT,
        fill=WHITE,
    )

    draw.text(
        (1112, 384),
        f"Containment: {data['containment']}",
        font=SMALL_FONT,
        fill=TEXT_SOFT,
    )

    draw.text(
        (1112, 406),
        f"Active cases: {data['active_cases']:,}",
        font=SMALL_FONT,
        fill=TEXT_SOFT,
    )

    # Red/blue pulse track.
    track_x1 = 963
    track_x2 = 1302
    track_y = 457

    draw.line(
        (track_x1, track_y, track_x2, track_y),
        fill=(48, 63, 83, 255),
        width=4,
    )

    pulse_position = (
        track_x1
        + int(
            (
                track_x2
                - track_x1
            )
            * frame_index
            / max(
                FRAME_COUNT - 1,
                1,
            )
        )
    )

    draw.line(
        (
            track_x1,
            track_y,
            pulse_position,
            track_y,
        ),
        fill=BLUE,
        width=4,
    )

    draw.ellipse(
        (
            pulse_position - 8,
            track_y - 8,
            pulse_position + 8,
            track_y + 8,
        ),
        fill=RED,
        outline=WHITE,
        width=1,
    )

    draw.text(
        (x, 480),
        "ANALYTICAL MODEL ACTIVE",
        font=MICRO_FONT,
        fill=TEXT_DIM,
    )


def correlation_nodes() -> list[tuple[int, int]]:
    """Return fixed node positions for the evidence graph."""

    return [
        (1388, 244),
        (1465, 205),
        (1558, 260),
        (1650, 216),
        (1722, 282),
        (1425, 350),
        (1532, 384),
        (1634, 344),
        (1715, 410),
    ]


def draw_evidence_panel(
    draw: ImageDraw.ImageDraw,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    """Draw the evidence graph and metrics."""

    nodes = correlation_nodes()

    edges = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 4),
        (0, 5),
        (1, 6),
        (2, 6),
        (2, 7),
        (3, 7),
        (4, 8),
        (5, 6),
        (6, 7),
        (7, 8),
    ]

    for first, second in edges:
        draw.line(
            (
                nodes[first][0],
                nodes[first][1],
                nodes[second][0],
                nodes[second][1],
            ),
            fill=(45, 87, 133, 165),
            width=2,
        )

    active_index = (
        frame_index
        % len(nodes)
    )

    for index, (node_x, node_y) in enumerate(nodes):
        active = index == active_index

        radius = 8 if active else 5

        node_color = (
            RED
            if active
            else BLUE
        )

        draw.ellipse(
            (
                node_x - radius,
                node_y - radius,
                node_x + radius,
                node_y + radius,
            ),
            fill=node_color,
            outline=WHITE,
            width=1,
        )

    # Metrics.
    draw.text(
        (1367, 438),
        "EVIDENCE",
        font=MICRO_FONT,
        fill=TEXT_DIM,
    )

    draw.text(
        (1367, 459),
        f"{data['evidence_records']:,}",
        font=VALUE_BOLD_FONT,
        fill=WHITE,
    )

    draw.text(
        (1493, 438),
        "INDICATORS",
        font=MICRO_FONT,
        fill=TEXT_DIM,
    )

    draw.text(
        (1493, 459),
        f"{data['indicator_records']:,}",
        font=VALUE_BOLD_FONT,
        fill=WHITE,
    )

    draw.text(
        (1628, 438),
        "UPDATED",
        font=MICRO_FONT,
        fill=TEXT_DIM,
    )

    updated_font = fit_text(
        draw,
        data["updated"],
        maximum_width=125,
        preferred_size=11,
        minimum_size=9,
    )

    draw.text(
        (1628, 459),
        data["updated"],
        font=updated_font,
        fill=TEXT_SOFT,
    )


def draw_animation(
    image: Image.Image,
    frame_index: int,
) -> None:
    """Draw the moving scan and signal effects."""

    draw = ImageDraw.Draw(
        image,
        "RGBA",
    )

    # Moving vertical scan bar.
    scan_start = 30
    scan_end = WIDTH - 30

    scan_x = (
        scan_start
        + int(
            (
                scan_end
                - scan_start
            )
            * frame_index
            / max(
                FRAME_COUNT - 1,
                1,
            )
        )
    )

    draw.rectangle(
        (
            scan_x - 12,
            118,
            scan_x + 12,
            533,
        ),
        fill=(
            BLUE[0],
            BLUE[1],
            BLUE[2],
            18,
        ),
    )

    draw.line(
        (
            scan_x,
            118,
            scan_x,
            533,
        ),
        fill=(
            BLUE[0],
            BLUE[1],
            BLUE[2],
            130,
        ),
        width=2,
    )

    # Animated footer waveform.
    waveform_points = []

    for x in range(980, 1750, 18):
        phase = (
            frame_index * 0.55
            + x * 0.035
        )

        amplitude = (
            7
            + 5 * math.sin(
                x * 0.017
            )
        )

        y = int(
            574
            + math.sin(phase)
            * amplitude
        )

        waveform_points.append(
            (x, y)
        )

    draw.line(
        waveform_points,
        fill=RED,
        width=2,
    )

    # Scan status microtext.
    draw.text(
        (WIDTH - 38, 568),
        (
            f"CASE {frame_index + 1:02d}/"
            f"{FRAME_COUNT:02d}"
        ),
        font=MICRO_FONT,
        fill=TEXT_DIM,
        anchor="ra",
    )


def render_frame(
    background: Image.Image,
    data: dict[str, Any],
    frame_index: int,
) -> Image.Image:
    """Render a single animation frame."""

    frame = background.copy()

    draw = ImageDraw.Draw(
        frame,
        "RGBA",
    )

    draw_case_panel(
        draw,
        data,
    )

    draw_campaign_panel(
        draw,
        data,
        frame_index,
    )

    draw_evidence_panel(
        draw,
        data,
        frame_index,
    )

    draw_animation(
        frame,
        frame_index,
    )

    return frame


# ============================================================
# Main
# ============================================================

def main() -> None:
    """Generate the animated case banner."""

    case = load_json(
        CURRENT_CASE_PATH,
        required=True,
    )

    operation = load_json(
        ACTIVE_OPERATION_PATH,
        required=True,
    )

    score_data = load_json(
        THREAT_SCORE_PATH,
        required=False,
    )

    display_data = build_display_data(
        case,
        operation,
        score_data,
    )

    ASSETS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    background = build_background()

    frames: list[Image.Image] = []

    for frame_index in range(FRAME_COUNT):
        frame = render_frame(
            background,
            display_data,
            frame_index,
        )

        frames.append(
            frame.convert(
                "P",
                palette=Image.Palette.ADAPTIVE,
                colors=128,
            )
        )

    frames[0].save(
        OUTPUT_GIF_PATH,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=True,
        disposal=2,
    )

    print(
        "Generated dynamic case banner: "
        f"{OUTPUT_GIF_PATH}"
    )

    print(
        "Banner details: "
        f"{WIDTH}x{HEIGHT}, "
        f"{FRAME_COUNT} frames, "
        f"case {display_data['case_id']}."
    )


if __name__ == "__main__":
    main()
