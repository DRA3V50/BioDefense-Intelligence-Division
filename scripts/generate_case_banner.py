#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import random
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


BASE_IMAGE_PATH = Path("assets/biodefense-dashboard-base.png")
OUTPUT_GIF_PATH = Path("assets/biodefense-case-scan.gif")

CURRENT_CASE_PATH = Path("data/current_case.json")
ACTIVE_OPERATION_PATH = Path("operations/active_operation.json")
CSHARP_JSON_PATH = Path("reports/bioterror_threat_score_csharp.json")
CSHARP_XML_PATH = Path("reports/bioterror_threat_score_csharp.xml")

REFERENCE_WIDTH = 1788
REFERENCE_HEIGHT = 880

FRAME_COUNT = 16
FRAME_DURATION_MS = 125

WHITE = (230, 239, 246, 255)
TEXT = (175, 195, 211, 255)
MUTED = (95, 124, 145, 255)
BLUE = (59, 155, 238, 255)
BLUE_BRIGHT = (84, 190, 255, 255)
RED = (223, 54, 63, 255)
RED_BRIGHT = (255, 75, 82, 255)
PANEL_COVER = (3, 11, 16, 244)
PANEL_COVER_SOFT = (3, 11, 16, 222)
GRID = (17, 47, 61, 125)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            value = json.load(file)
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_xml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return {}

    output: dict[str, Any] = {}

    for aliases, destination in (
        (("OverallScore", "Score"), "overall_score"),
        (("OverallLevel", "Level", "Rating"), "overall_level"),
        (("EvidenceRecords", "EvidenceCount"), "evidence_records"),
    ):
        for alias in aliases:
            element = root.find(f".//{alias}")
            if element is not None and element.text:
                output[destination] = element.text.strip()
                break

    return output


def deep_find(data: Any, aliases: tuple[str, ...]) -> Any:
    expected = {alias.lower() for alias in aliases}

    if isinstance(data, dict):
        for key, value in data.items():
            if str(key).lower() in expected:
                return value

        for value in data.values():
            found = deep_find(value, aliases)
            if found is not None:
                return found

    elif isinstance(data, list):
        for value in data:
            found = deep_find(value, aliases)
            if found is not None:
                return found

    return None


def value(data: dict[str, Any], *aliases: str, default: Any = "N/A") -> Any:
    found = deep_find(data, aliases)

    if found is None:
        return default

    if isinstance(found, str) and not found.strip():
        return default

    return found


def text(value_to_render: Any, default: str = "N/A") -> str:
    if value_to_render is None:
        return default

    rendered = str(value_to_render).strip()
    return rendered or default


def integer(value_to_render: Any, default: int = 0) -> int:
    try:
        return int(float(str(value_to_render).strip()))
    except (TypeError, ValueError):
        return default


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
        "C:/Windows/Fonts/consolab.ttf" if bold else "C:/Windows/Fonts/consola.ttf",
    ]

    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue

    return ImageFont.load_default()


def text_width(draw: ImageDraw.ImageDraw, rendered: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), rendered, font=font)
    return box[2] - box[0]


def fit_font(
    draw: ImageDraw.ImageDraw,
    rendered: str,
    maximum_width: int,
    preferred_size: int,
    minimum_size: int,
    bold: bool = False,
) -> ImageFont.ImageFont:
    for size in range(preferred_size, minimum_size - 1, -1):
        candidate = load_font(size, bold)
        if text_width(draw, rendered, candidate) <= maximum_width:
            return candidate

    return load_font(minimum_size, bold)


def ellipsize(
    draw: ImageDraw.ImageDraw,
    rendered: str,
    font: ImageFont.ImageFont,
    maximum_width: int,
) -> str:
    candidate = text(rendered)

    if text_width(draw, candidate, font) <= maximum_width:
        return candidate

    while candidate:
        shortened = candidate.rstrip() + "…"
        if text_width(draw, shortened, font) <= maximum_width:
            return shortened
        candidate = candidate[:-1]

    return "…"


def wrap_text(
    draw: ImageDraw.ImageDraw,
    rendered: str,
    font: ImageFont.ImageFont,
    maximum_width: int,
    maximum_lines: int,
) -> list[str]:
    words = text(rendered).split()

    if not words:
        return ["N/A"]

    lines: list[str] = []
    current = words[0]

    for word in words[1:]:
        candidate = f"{current} {word}"

        if text_width(draw, candidate, font) <= maximum_width:
            current = candidate
        else:
            lines.append(current)
            current = word

    lines.append(current)

    if len(lines) > maximum_lines:
        lines = lines[:maximum_lines]
        lines[-1] = ellipsize(draw, lines[-1], font, maximum_width)

    return lines


def threat_level(score: int) -> str:
    if score >= 85:
        return "CRITICAL"
    if score >= 65:
        return "HIGH"
    if score >= 40:
        return "ELEVATED"
    return "GUARDED"


def active_stage(case_status: str, campaign_phase: str) -> int:
    combined = f"{case_status} {campaign_phase}".lower()

    if "recover" in combined or "close" in combined or "monitor" in combined:
        return 4
    if "assess" in combined or "contain" in combined:
        return 3
    if "valid" in combined or "analy" in combined:
        return 2
    if "correl" in combined or "evidence review" in combined:
        return 1

    return 0


def scaled_font(
    image_width: int,
    image_height: int,
    reference_size: int,
    bold: bool = False,
) -> ImageFont.ImageFont:
    scale = min(
        image_width / REFERENCE_WIDTH,
        image_height / REFERENCE_HEIGHT,
    )
    return load_font(max(8, round(reference_size * scale)), bold)


def scaled_box(
    image_width: int,
    image_height: int,
    box: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    sx = image_width / REFERENCE_WIDTH
    sy = image_height / REFERENCE_HEIGHT
    x1, y1, x2, y2 = box
    return (
        round(x1 * sx),
        round(y1 * sy),
        round(x2 * sx),
        round(y2 * sy),
    )


def scaled_point(
    image_width: int,
    image_height: int,
    point: tuple[int, int],
) -> tuple[int, int]:
    sx = image_width / REFERENCE_WIDTH
    sy = image_height / REFERENCE_HEIGHT
    x, y = point
    return round(x * sx), round(y * sy)


def build_live_data() -> dict[str, Any]:
    case = load_json(CURRENT_CASE_PATH)
    operation = load_json(ACTIVE_OPERATION_PATH)
    score_report = load_json(CSHARP_JSON_PATH)

    if not score_report:
        score_report = load_xml(CSHARP_XML_PATH)

    case_score = integer(
        value(
            score_report,
            "overallScore",
            "overall_score",
            "score",
            default=value(case, "risk_score", "riskScore", default=0),
        ),
        0,
    )

    score_label = text(
        value(
            score_report,
            "overallLevel",
            "overall_level",
            "level",
            "rating",
            default=threat_level(case_score),
        )
    ).upper()

    return {
        "case_id": text(
            value(case, "case_id", "caseId", default="BID-UNKNOWN")
        ),
        "evidence": integer(
            value(
                score_report,
                "evidenceRecords",
                "evidence_records",
                default=value(case, "evidence_count", "evidenceCount", default=0),
            ),
            0,
        ),
        "indicators": integer(
            value(case, "ioc_count", "indicator_count", "indicators", default=0),
            0,
        ),
        "case_type": text(
            value(
                case,
                "classification",
                "investigation_type",
                "case_type",
                default="Cyber-Biothreat Investigation",
            )
        ),
        "threat": text(
            value(
                case,
                "threat_family",
                "threat",
                "threat_name",
                default="Unresolved Biological Systems Activity",
            )
        ),
        "status": text(
            value(case, "status", "case_status", default="Active Review")
        ),
        "analyst": text(
            value(
                case,
                "lead_analyst",
                "analyst",
                default="Investigative Analysis Unit",
            )
        ),
        "confidence": integer(
            value(case, "confidence", "confidence_score", default=0),
            0,
        ),
        "priority": text(
            value(case, "priority", "case_priority", default="Routine")
        ).upper(),
        "score": case_score,
        "score_level": score_label,
        "campaign": text(
            value(
                operation,
                "operation",
                "campaign",
                "campaign_name",
                default="Active Investigation Campaign",
            )
        ),
        "campaign_id": text(
            value(
                operation,
                "campaign_id",
                "operation_id",
                default="BDC-UNKNOWN",
            )
        ),
        "phase": text(
            value(
                operation,
                "campaign_phase",
                "phase",
                default="Evidence Review",
            )
        ),
        "next_action": text(
            value(
                operation,
                "next_objective",
                "next_action",
                default=value(
                    case,
                    "recommended_action",
                    default="Continue evidence review and validation.",
                ),
            )
        ),
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def cover_dynamic_regions(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
) -> None:
    regions = [
        # Evidence values
        (1342, 137, 1592, 263, PANEL_COVER),
        # Case overview values
        (1353, 345, 1438, 555, PANEL_COVER),
        # Active case bars
        (52, 671, 449, 764, PANEL_COVER_SOFT),
        # System status values
        (741, 657, 817, 778, PANEL_COVER),
        # Threat score and waveform
        (872, 664, 1267, 767, PANEL_COVER_SOFT),
        # Operational brief content
        (1334, 659, 1724, 779, PANEL_COVER),
        # UTC clock
        (1586, 829, 1758, 859, PANEL_COVER),
    ]

    for x1, y1, x2, y2, fill in regions:
        draw.rectangle(
            scaled_box(
                image_width,
                image_height,
                (x1, y1, x2, y2),
            ),
            fill=fill,
        )


def draw_evidence_package(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    value_font = scaled_font(image_width, image_height, 14)
    rows = [
        ("case_id", 153),
        ("evidence", 185),
        ("indicators", 218),
        ("updated", 250),
    ]

    rendered = {
        "case_id": data["case_id"],
        "evidence": f"{data['evidence']} RECORDS",
        "indicators": str(data["indicators"]),
        "updated": data["updated"],
    }

    x, _ = scaled_point(image_width, image_height, (1355, 0))
    maximum_width = scaled_point(image_width, image_height, (1578, 0))[0] - x

    for key, reference_y in rows:
        _, y = scaled_point(image_width, image_height, (0, reference_y))
        value_text = ellipsize(
            draw,
            rendered[key],
            value_font,
            maximum_width,
        )
        draw.text(
            (x, y),
            value_text,
            font=value_font,
            fill=WHITE,
        )


def draw_case_overview(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    preferred = scaled_font(image_width, image_height, 12)
    bold = scaled_font(image_width, image_height, 12, True)

    rows = [
        ("case_type", 365, preferred, BLUE_BRIGHT),
        ("threat", 399, preferred, TEXT),
        ("status", 433, bold, RED_BRIGHT),
        ("analyst", 468, preferred, TEXT),
        ("confidence", 502, bold, BLUE_BRIGHT),
        ("priority", 537, bold, RED_BRIGHT),
    ]

    values = {
        "case_type": data["case_type"],
        "threat": data["threat"],
        "status": data["status"],
        "analyst": data["analyst"],
        "confidence": f"{data['confidence']}%",
        "priority": data["priority"],
    }

    x, _ = scaled_point(image_width, image_height, (1355, 0))
    maximum_width = scaled_point(image_width, image_height, (1430, 0))[0] - x

    for key, reference_y, row_font, color in rows:
        _, y = scaled_point(image_width, image_height, (0, reference_y))
        final_font = fit_font(
            draw,
            values[key],
            maximum_width,
            getattr(row_font, "size", 12),
            8,
            key in {"status", "confidence", "priority"},
        )
        draw.text(
            (x, y),
            ellipsize(draw, values[key], final_font, maximum_width),
            font=final_font,
            fill=color,
        )


def draw_case_feed(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    seed = sum(ord(character) for character in data["case_id"])
    x1, y1, x2, y2 = scaled_box(
        image_width,
        image_height,
        (59, 678, 443, 759),
    )

    count = 28
    gap = max(2, round(4 * image_width / REFERENCE_WIDTH))
    usable_width = x2 - x1
    bar_width = max(3, (usable_width - gap * (count - 1)) // count)

    for index in range(count):
        rng = random.Random(seed + index * 911)
        primary_phase = rng.uniform(0, math.tau)
        secondary_phase = rng.uniform(0, math.tau)
        speed = rng.uniform(0.25, 0.75)

        level = (
            0.5
            + 0.31 * math.sin(frame_index * speed + primary_phase)
            + 0.18 * math.sin(frame_index * 0.41 + secondary_phase)
        )
        level = max(0.08, min(1.0, level))
        height = max(4, round((y2 - y1) * level))
        x = x1 + index * (bar_width + gap)

        color = RED if index in {count - 2, count - 1} else BLUE

        draw.rectangle(
            (x, y2 - height, x + bar_width, y2),
            fill=color,
        )


def draw_system_status(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
) -> None:
    status_font = scaled_font(image_width, image_height, 12, True)
    rows = [
        ("VERIFIED", 675),
        ("STABLE", 708),
        ("CURRENT", 741),
        ("SECURE", 774),
        ("ACTIVE", 807),
    ]

    x, _ = scaled_point(image_width, image_height, (743, 0))

    for status, reference_y in rows:
        _, y = scaled_point(image_width, image_height, (0, reference_y))
        draw.text((x, y), status, font=status_font, fill=BLUE_BRIGHT)


def draw_threat_monitor(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    score_font = scaled_font(image_width, image_height, 34, True)
    body_font = scaled_font(image_width, image_height, 12, True)

    score_x, score_y = scaled_point(
        image_width,
        image_height,
        (876, 693),
    )

    draw.text(
        (score_x, score_y),
        f"{data['score']:03d}",
        font=score_font,
        fill=RED_BRIGHT,
    )

    posture_x, posture_y = scaled_point(
        image_width,
        image_height,
        (876, 775),
    )

    draw.text(
        (posture_x, posture_y),
        data["score_level"],
        font=body_font,
        fill=WHITE,
    )

    x1, y1, x2, y2 = scaled_box(
        image_width,
        image_height,
        (1002, 684, 1264, 755),
    )

    seed = sum(ord(character) for character in data["case_id"]) + 713
    rng = random.Random(seed)
    phases = [rng.uniform(0, math.tau) for _ in range(4)]
    points = []

    for index in range(58):
        ratio = index / 57
        x = x1 + ratio * (x2 - x1)
        offset = 0.0

        for harmonic in range(4):
            offset += (
                (6 + harmonic * 1.8)
                * math.sin(
                    index * (0.22 + harmonic * 0.047)
                    + frame_index * (0.26 + harmonic * 0.073)
                    + phases[harmonic]
                )
            )

        noise = random.Random(
            seed + frame_index * 101 + index * 59
        ).uniform(-3.0, 3.0)

        y = (y1 + y2) / 2 + offset * 0.55 + noise
        y = max(y1 + 2, min(y2 - 2, y))
        points.append((x, y))

    draw.line(points, fill=RED_BRIGHT, width=max(2, round(image_width / 900)))


def draw_operational_brief(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    bullet_font = scaled_font(image_width, image_height, 12)
    strong_font = scaled_font(image_width, image_height, 12, True)

    x, y = scaled_point(image_width, image_height, (1348, 665))
    maximum_width = scaled_point(image_width, image_height, (1717, 0))[0] - x

    campaign = ellipsize(
        draw,
        data["campaign"],
        strong_font,
        maximum_width - scaled_point(image_width, image_height, (24, 0))[0],
    )

    lines = [
        campaign,
        f"{data['campaign_id']} • {data['phase']}",
    ]

    action_lines = wrap_text(
        draw,
        data["next_action"],
        bullet_font,
        maximum_width - scaled_point(image_width, image_height, (24, 0))[0],
        2,
    )
    lines.extend(action_lines)

    spacing = scaled_point(image_width, image_height, (0, 29))[1]

    for index, line in enumerate(lines[:4]):
        line_y = y + index * spacing
        draw.ellipse(
            (
                x,
                line_y + 4,
                x + max(5, round(7 * image_width / REFERENCE_WIDTH)),
                line_y + max(9, round(11 * image_height / REFERENCE_HEIGHT)),
            ),
            outline=BLUE_BRIGHT if index < 2 else RED,
            width=max(1, round(image_width / 1100)),
        )
        draw.text(
            (
                x + scaled_point(image_width, image_height, (20, 0))[0],
                line_y,
            ),
            line,
            font=strong_font if index == 0 else bullet_font,
            fill=WHITE if index == 0 else TEXT,
        )


def draw_active_stage(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    centers = [
        (409, 426),
        (568, 426),
        (727, 426),
        (889, 426),
        (1047, 426),
    ]

    stage = active_stage(data["status"], data["phase"])
    cx, cy = scaled_point(image_width, image_height, centers[stage])
    base_radius = scaled_point(
        image_width,
        image_height,
        (35, 0),
    )[0]
    pulse = max(
        1,
        round(
            scaled_point(image_width, image_height, (4, 0))[0]
            * (0.5 + 0.5 * math.sin(frame_index * 0.75))
        ),
    )
    color = RED_BRIGHT if stage == 4 else BLUE_BRIGHT

    draw.ellipse(
        (
            cx - base_radius - pulse,
            cy - base_radius - pulse,
            cx + base_radius + pulse,
            cy + base_radius + pulse,
        ),
        outline=color,
        width=max(2, round(image_width / 900)),
    )


def draw_biohazard_scan(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    frame_index: int,
) -> None:
    x1, y1, x2, y2 = scaled_box(
        image_width,
        image_height,
        (1467, 319, 1735, 570),
    )

    scan_y = y1 + round(
        ((frame_index + 0.5) / FRAME_COUNT)
        * (y2 - y1)
    )

    draw.rectangle(
        (x1, scan_y - 2, x2, scan_y + 2),
        fill=(223, 54, 63, 55),
    )

    draw.line(
        (x1, scan_y, x2, scan_y),
        fill=RED,
        width=max(1, round(image_width / 1300)),
    )


def draw_utc_clock(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    updated: str,
) -> None:
    clock_font = scaled_font(image_width, image_height, 11)
    x, y = scaled_point(
        image_width,
        image_height,
        (1586, 839),
    )
    draw.text(
        (x, y),
        f"UTC {updated[11:16]}",
        font=clock_font,
        fill=MUTED,
    )


def render_frame(
    base_image: Image.Image,
    data: dict[str, Any],
    frame_index: int,
) -> Image.Image:
    frame = base_image.copy().convert("RGBA")
    draw = ImageDraw.Draw(frame, "RGBA")
    width, height = frame.size

    cover_dynamic_regions(draw, width, height)
    draw_evidence_package(draw, width, height, data)
    draw_case_overview(draw, width, height, data)
    draw_case_feed(draw, width, height, data, frame_index)
    draw_system_status(draw, width, height)
    draw_threat_monitor(draw, width, height, data, frame_index)
    draw_operational_brief(draw, width, height, data)
    draw_active_stage(draw, width, height, data, frame_index)
    draw_biohazard_scan(draw, width, height, frame_index)
    draw_utc_clock(draw, width, height, data["updated"])

    return frame


def main() -> None:
    if not BASE_IMAGE_PATH.exists():
        raise FileNotFoundError(
            f"Missing dashboard base image: {BASE_IMAGE_PATH}"
        )

    data = build_live_data()
    base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
    frames: list[Image.Image] = []

    for frame_index in range(FRAME_COUNT):
        frame = render_frame(base_image, data, frame_index)
        frames.append(
            frame.convert(
                "P",
                palette=Image.ADAPTIVE,
                colors=192,
            )
        )

    OUTPUT_GIF_PATH.parent.mkdir(parents=True, exist_ok=True)

    frames[0].save(
        OUTPUT_GIF_PATH,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=False,
        disposal=2,
    )

    with Image.open(OUTPUT_GIF_PATH) as output:
        assert output.size == base_image.size
        assert output.n_frames == FRAME_COUNT

    print(
        "Generated approved-style dynamic banner: "
        f"{OUTPUT_GIF_PATH}"
    )
    print(
        f"Banner details: {base_image.width}x{base_image.height}, "
        f"{FRAME_COUNT} frames, case {data['case_id']}."
    )


if __name__ == "__main__":
    main()
