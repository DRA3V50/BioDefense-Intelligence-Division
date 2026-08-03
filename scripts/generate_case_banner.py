#!/usr/bin/env python3

"""
Generate the animated README banner for BioDefense-Intelligence-Division.

This script keeps the approved Resident Evil-inspired investigative
interface as the permanent visual base and updates its case information
whenever the Daily Investigation workflow runs.

Reads:
    data/current_case.json
    operations/active_operation.json
    reports/bioterror_threat_score_csharp.json
    assets/biodefense-dashboard-base.png

Writes:
    assets/biodefense-case-scan.gif
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


CURRENT_CASE_PATH = Path("data/current_case.json")
ACTIVE_OPERATION_PATH = Path("operations/active_operation.json")
THREAT_SCORE_PATH = Path(
    "reports/bioterror_threat_score_csharp.json"
)

ASSETS_DIRECTORY = Path("assets")
BASE_IMAGE_PATH = (
    ASSETS_DIRECTORY
    / "biodefense-dashboard-base.png"
)
OUTPUT_GIF_PATH = (
    ASSETS_DIRECTORY
    / "biodefense-case-scan.gif"
)

FRAME_COUNT = 16
FRAME_DURATION_MS = 115

TEXT = (201, 219, 220, 255)
TEXT_BRIGHT = (232, 240, 241, 255)
TEXT_DIM = (86, 121, 123, 255)

CYAN = (28, 164, 158, 255)
CYAN_DARK = (15, 83, 82, 255)
CYAN_FAINT = (28, 164, 158, 42)

RED = (220, 53, 59, 255)

PANEL = (3, 14, 18, 244)
PANEL_ALT = (5, 13, 17, 246)
DIVIDER = (17, 59, 60, 220)


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

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

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

    rendered = str(value).strip()
    return rendered if rendered else default


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
    """Recursively find the first matching key."""

    normalized = {key.lower() for key in keys}

    if isinstance(data, dict):
        for key, value in data.items():
            if str(key).lower() in normalized:
                return value

        for value in data.values():
            found = deep_find(value, normalized)

            if found is not None:
                return found

    elif isinstance(data, list):
        for item in data:
            found = deep_find(item, normalized)

            if found is not None:
                return found

    return None


def now_utc() -> str:
    """Return a compact UTC timestamp."""

    return datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")


def build_data(
    case: dict[str, Any],
    operation: dict[str, Any],
    score_data: dict[str, Any],
) -> dict[str, Any]:
    """Collect the current values displayed by the banner."""

    overall_score = integer_value(
        deep_find(
            score_data,
            {
                "overallScore",
                "overall_score",
                "score",
            },
        ),
        integer_value(case.get("risk_score"), 0),
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
        text_value(case.get("severity"), "Unknown"),
    ).upper()

    evidence_records = integer_value(
        deep_find(
            score_data,
            {
                "evidenceRecords",
                "evidence_records",
            },
        ),
        integer_value(case.get("evidence_count"), 0),
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
        "lead": text_value(
            case.get("lead_analyst"),
        ),
        "confidence": integer_value(
            case.get("confidence"),
            0,
        ),
        "evidence": evidence_records,
        "indicators": integer_value(
            case.get("ioc_count"),
            0,
        ),
        "risk": integer_value(
            case.get("risk_score"),
            0,
        ),
        "score": overall_score,
        "score_level": overall_level,
        "campaign_id": text_value(
            operation.get("campaign_id"),
        ),
        "campaign": text_value(
            operation.get("operation"),
        ),
        "phase": text_value(
            operation.get("campaign_phase"),
        ),
        "containment": text_value(
            operation.get("containment_level"),
        ),
        "next_action": text_value(
            operation.get(
                "next_objective",
                case.get(
                    "recommended_action",
                    "Continue evidence review.",
                ),
            ),
        ),
        "updated": now_utc(),
    }


def font(
    size: int,
    bold: bool = False,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a monospaced interface font."""

    candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/"
            + (
                "DejaVuSansMono-Bold.ttf"
                if bold
                else "DejaVuSansMono.ttf"
            )
        ),
        (
            "/usr/share/fonts/truetype/liberation2/"
            + (
                "LiberationMono-Bold.ttf"
                if bold
                else "LiberationMono-Regular.ttf"
            )
        ),
        (
            "C:/Windows/Fonts/"
            + (
                "consolab.ttf"
                if bold
                else "consola.ttf"
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


HEADER_FONT = font(16, bold=True)
LABEL_FONT = font(11)
VALUE_FONT = font(12)
VALUE_BOLD_FONT = font(13, bold=True)
SMALL_FONT = font(10)
MICRO_FONT = font(8)


def fit_font(
    draw: ImageDraw.ImageDraw,
    value: str,
    maximum_width: int,
    preferred_size: int,
    minimum_size: int = 8,
    bold: bool = False,
):
    """Return the largest font that fits the width."""

    size = preferred_size

    while size >= minimum_size:
        candidate = font(size, bold=bold)
        box = draw.textbbox(
            (0, 0),
            value,
            font=candidate,
        )

        if box[2] - box[0] <= maximum_width:
            return candidate

        size -= 1

    return font(minimum_size, bold=bold)


def shorten(
    value: str,
    maximum_characters: int,
) -> str:
    """Shorten long values cleanly."""

    rendered = text_value(value)

    if len(rendered) <= maximum_characters:
        return rendered

    return (
        rendered[: maximum_characters - 1].rstrip()
        + "…"
    )


def load_base() -> Image.Image:
    """Load the approved visual base."""

    if not BASE_IMAGE_PATH.exists():
        raise FileNotFoundError(
            "Missing approved banner base: "
            f"{BASE_IMAGE_PATH}"
        )

    image = Image.open(
        BASE_IMAGE_PATH
    ).convert("RGBA")

    if image.size != (2043, 629):
        image = image.resize(
            (2043, 629),
            Image.Resampling.LANCZOS,
        )

    return image


def cover_sample_content(
    image: Image.Image,
) -> None:
    """
    Hide only the sample government-style and lower-panel content while
    preserving the approved title, textures, biohazard panel, grid, and
    overall Resident Evil-inspired interface.
    """

    draw = ImageDraw.Draw(image, "RGBA")

    regions = [
        (17, 100, 239, 521, PANEL_ALT),
        (1582, 24, 2039, 224, PANEL_ALT),
        (1537, 239, 1790, 480, PANEL_ALT),
        (270, 474, 655, 628, PANEL),
        (657, 474, 1082, 628, PANEL),
        (1087, 474, 1538, 628, PANEL_ALT),
        (1543, 474, 2042, 628, PANEL),
    ]

    for x1, y1, x2, y2, fill in regions:
        draw.rectangle(
            (x1, y1, x2, y2),
            fill=fill,
        )


def draw_portfolio_badge(
    draw: ImageDraw.ImageDraw,
) -> None:
    """Replace the seal with an original portfolio emblem."""

    center_x = 124
    center_y = 238

    for radius, color, width in [
        (73, CYAN_DARK, 2),
        (58, CYAN, 2),
        (44, CYAN_DARK, 1),
    ]:
        draw.ellipse(
            (
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
            ),
            outline=color,
            width=width,
        )

    shield = [
        (124, 184),
        (157, 198),
        (151, 246),
        (124, 274),
        (97, 246),
        (91, 198),
    ]

    draw.polygon(
        shield,
        fill=(4, 23, 27, 220),
        outline=CYAN,
    )

    for offset in range(-22, 23, 8):
        y = center_y + offset
        wave = int(
            15 * math.sin(offset / 9)
        )

        draw.line(
            (
                center_x - wave,
                y,
                center_x + wave,
                y,
            ),
            fill=CYAN,
            width=1,
        )

    draw.text(
        (center_x, 126),
        "BIODEFENSE ANALYSIS",
        font=SMALL_FONT,
        fill=CYAN,
        anchor="ma",
    )

    draw.text(
        (center_x, 382),
        "PORTFOLIO SIMULATION",
        font=VALUE_BOLD_FONT,
        fill=RED,
        anchor="ma",
    )

    draw.text(
        (center_x, 411),
        "SYNTHETIC CASE DATA",
        font=SMALL_FONT,
        fill=TEXT_DIM,
        anchor="ma",
    )


def draw_key_value(
    draw: ImageDraw.ImageDraw,
    label: str,
    value: str,
    x: int,
    y: int,
    label_width: int,
    value_width: int,
    color=TEXT,
) -> None:
    """Draw one compact key-value row."""

    draw.text(
        (x, y),
        label.upper(),
        font=LABEL_FONT,
        fill=TEXT_DIM,
    )

    rendered = shorten(value, 64)

    value_font = fit_font(
        draw,
        rendered,
        value_width,
        preferred_size=12,
        minimum_size=8,
    )

    draw.text(
        (x + label_width, y),
        rendered,
        font=value_font,
        fill=color,
    )


def draw_evidence_package(
    draw: ImageDraw.ImageDraw,
    data: dict[str, Any],
) -> None:
    """Draw the live evidence package."""

    draw.text(
        (1606, 40),
        "EVIDENCE PACKAGE",
        font=HEADER_FONT,
        fill=TEXT,
    )

    draw.line(
        (1606, 69, 2015, 69),
        fill=CYAN_DARK,
        width=1,
    )

    rows = [
        ("CASE ID", data["case_id"]),
        (
            "EVIDENCE",
            f"{data['evidence']:,} RECORDS",
        ),
        (
            "INDICATORS",
            f"{data['indicators']:,}",
        ),
        ("UPDATED", data["updated"]),
        ("SOURCE", "SYNTHETIC REPOSITORY"),
    ]

    y = 91

    for label, value in rows:
        draw_key_value(
            draw,
            label,
            value,
            1606,
            y,
            label_width=116,
            value_width=270,
        )
        y += 25

    draw.text(
        (1606, 197),
        "RECORD: PORTFOLIO SIMULATION",
        font=SMALL_FONT,
        fill=RED,
    )


def draw_case_overview(
    draw: ImageDraw.ImageDraw,
    data: dict[str, Any],
) -> None:
    """Draw current case details."""

    draw.text(
        (1558, 252),
        "CASE OVERVIEW",
        font=HEADER_FONT,
        fill=CYAN,
    )

    rows = [
        ("TYPE", data["classification"]),
        ("THREAT", data["threat_family"]),
        (
            "STATUS",
            (
                f"{data['severity']} / "
                f"{data['priority']}"
            ),
        ),
        ("ANALYST", data["lead"]),
        (
            "CONFIDENCE",
            f"{data['confidence']}%",
        ),
    ]

    y = 288

    for label, value in rows:
        draw.text(
            (1558, y),
            f"{label}:",
            font=SMALL_FONT,
            fill=TEXT_DIM,
        )

        rendered = shorten(value, 35)

        value_font = fit_font(
            draw,
            rendered,
            maximum_width=210,
            preferred_size=11,
            minimum_size=8,
        )

        draw.text(
            (1558, y + 16),
            rendered,
            font=value_font,
            fill=TEXT,
        )

        y += 37


def draw_case_scan(
    draw: ImageDraw.ImageDraw,
    frame_index: int,
) -> None:
    """Animate the existing case-scan rail."""

    left = 315
    right = 746
    y = 145

    draw.rectangle(
        (left, y, right, y + 4),
        fill=(8, 36, 39, 220),
    )

    segment = 88

    x = (
        left
        + int(
            (
                right
                - left
                - segment
            )
            * frame_index
            / max(
                FRAME_COUNT - 1,
                1,
            )
        )
    )

    draw.rectangle(
        (x, y, x + segment, y + 4),
        fill=CYAN,
    )


def draw_active_case_feed(
    draw: ImageDraw.ImageDraw,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    """Draw the live active-case feed."""

    draw.text(
        (289, 494),
        "ACTIVE CASE FEED",
        font=HEADER_FONT,
        fill=CYAN,
    )

    baseline = 574

    for index in range(28):
        x = 291 + index * 12

        height = (
            7
            + (
                index * 7
                + frame_index * 5
                + data["evidence"]
            )
            % 42
        )

        draw.rectangle(
            (
                x,
                baseline - height,
                x + 6,
                baseline,
            ),
            fill=CYAN,
        )

    draw.text(
        (289, 585),
        shorten(
            f"case-feed://{data['case_id'].lower()}",
            48,
        ),
        font=SMALL_FONT,
        fill=TEXT_DIM,
    )

    draw.text(
        (289, 604),
        (
            f"{data['evidence']:,} evidence records • "
            f"{data['indicators']:,} indicators"
        ),
        font=MICRO_FONT,
        fill=TEXT_DIM,
    )


def draw_system_status(
    draw: ImageDraw.ImageDraw,
    data: dict[str, Any],
) -> None:
    """Draw the current system status panel."""

    draw.text(
        (681, 494),
        "SYSTEM STATUS",
        font=HEADER_FONT,
        fill=CYAN,
    )

    rows = [
        ("Evidence Integrity", "VERIFIED"),
        ("Data Pipeline", "STABLE"),
        ("Case Record", "CURRENT"),
        (
            "Threat Score",
            (
                f"{data['score']} / "
                f"{data['score_level']}"
            ),
        ),
    ]

    y = 529

    for label, value in rows:
        draw.text(
            (681, y),
            f"• {label}:",
            font=VALUE_FONT,
            fill=TEXT_DIM,
        )

        draw.text(
            (862, y),
            value,
            font=VALUE_BOLD_FONT,
            fill=CYAN,
        )

        y += 25

    center_x = 1004
    center_y = 551

    for radius in range(16, 60, 8):
        draw.arc(
            (
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
            ),
            start=195,
            end=520,
            fill=CYAN_DARK,
            width=2,
        )


def draw_threat_monitor(
    draw: ImageDraw.ImageDraw,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    """Draw the animated threat-monitor panel."""

    draw.text(
        (1112, 494),
        "THREAT MONITOR",
        font=HEADER_FONT,
        fill=RED,
    )

    draw.text(
        (1112, 528),
        (
            f"• Threat score: "
            f"{data['score']} "
            f"({data['score_level']})"
        ),
        font=VALUE_FONT,
        fill=RED,
    )

    draw.text(
        (1112, 550),
        (
            f"• Containment posture: "
            f"{data['containment']}"
        ),
        font=VALUE_FONT,
        fill=TEXT_DIM,
    )

    points = []

    for x in range(1112, 1505, 8):
        phase = (
            frame_index * 0.5
            + x * 0.045
        )

        amplitude = (
            6
            + 3 * math.sin(
                x * 0.02
            )
        )

        y = int(
            592
            + math.sin(phase)
            * amplitude
        )

        points.append((x, y))

    draw.line(
        points,
        fill=RED,
        width=2,
    )

    draw.text(
        (1112, 608),
        "ANALYTICAL MODEL ACTIVE",
        font=MICRO_FONT,
        fill=TEXT_DIM,
    )


def draw_operational_brief(
    draw: ImageDraw.ImageDraw,
    data: dict[str, Any],
) -> None:
    """Draw current campaign and next action."""

    draw.text(
        (1569, 494),
        "OPERATIONAL BRIEF",
        font=HEADER_FONT,
        fill=CYAN,
    )

    campaign = shorten(
        data["campaign"],
        54,
    )

    campaign_font = fit_font(
        draw,
        campaign,
        maximum_width=430,
        preferred_size=11,
        minimum_size=8,
        bold=True,
    )

    draw.text(
        (1569, 526),
        campaign,
        font=campaign_font,
        fill=TEXT,
    )

    draw.text(
        (1569, 549),
        (
            f"{data['campaign_id']} • "
            f"{data['phase']}"
        ),
        font=SMALL_FONT,
        fill=TEXT_DIM,
    )

    words = shorten(
        data["next_action"],
        95,
    ).split()

    lines = []
    current = ""

    for word in words:
        candidate = (
            f"{current} {word}".strip()
        )

        if len(candidate) > 49:
            lines.append(current)
            current = word
        else:
            current = candidate

    if current:
        lines.append(current)

    draw.multiline_text(
        (1569, 576),
        "\n".join(lines[:2]),
        font=SMALL_FONT,
        fill=TEXT_DIM,
        spacing=3,
    )


def draw_biohazard_scan(
    draw: ImageDraw.ImageDraw,
    frame_index: int,
) -> None:
    """Animate a subtle scan inside the biohazard panel."""

    left = 1816
    right = 2019

    x = (
        left
        + int(
            (
                right - left
            )
            * frame_index
            / max(
                FRAME_COUNT - 1,
                1,
            )
        )
    )

    draw.rectangle(
        (x - 6, 253, x + 6, 470),
        fill=CYAN_FAINT,
    )

    draw.line(
        (x, 253, x, 470),
        fill=CYAN_DARK,
        width=1,
    )


def render_frame(
    base: Image.Image,
    data: dict[str, Any],
    frame_index: int,
) -> Image.Image:
    """Render one frame."""

    frame = base.copy()
    cover_sample_content(frame)

    draw = ImageDraw.Draw(
        frame,
        "RGBA",
    )

    draw_portfolio_badge(draw)
    draw_evidence_package(draw, data)
    draw_case_overview(draw, data)
    draw_case_scan(draw, frame_index)
    draw_active_case_feed(
        draw,
        data,
        frame_index,
    )
    draw_system_status(draw, data)
    draw_threat_monitor(
        draw,
        data,
        frame_index,
    )
    draw_operational_brief(draw, data)
    draw_biohazard_scan(
        draw,
        frame_index,
    )

    return frame


def main() -> None:
    """Generate the approved-style dynamic GIF."""

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

    data = build_data(
        case,
        operation,
        score_data,
    )

    ASSETS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    base = load_base()
    frames: list[Image.Image] = []

    for frame_index in range(FRAME_COUNT):
        frame = render_frame(
            base,
            data,
            frame_index,
        )

        frames.append(
            frame.convert(
                "P",
                palette=Image.ADAPTIVE,
                colors=192,
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
        "Generated approved-style dynamic banner: "
        f"{OUTPUT_GIF_PATH}"
    )

    print(
        "Banner details: "
        f"{base.width}x{base.height}, "
        f"{FRAME_COUNT} frames, "
        f"case {data['case_id']}."
    )


if __name__ == "__main__":
    main()
