#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import random
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

BASE_IMAGE_PATH = Path("assets/biodefense-dashboard-base.png")
OUTPUT_GIF_PATH = Path("assets/biodefense-case-scan.gif")

CURRENT_CASE_PATH = Path("data/current_case.json")
ACTIVE_OPERATION_PATH = Path("operations/active_operation.json")
CSHARP_JSON_PATH = Path("reports/bioterror_threat_score_csharp.json")
CSHARP_XML_PATH = Path("reports/bioterror_threat_score_csharp.xml")

REFERENCE_WIDTH = 1672
REFERENCE_HEIGHT = 941

FRAME_COUNT = 18
FRAME_DURATION_MS = 120
EASTERN_TIME = ZoneInfo("America/New_York")

WHITE = (230, 233, 235, 255)
TEXT = (176, 182, 187, 255)
MUTED = (103, 110, 116, 255)
DIM = (70, 76, 81, 255)
RED = (231, 51, 47, 255)
RED_DIM = (132, 35, 34, 255)
RED_GLOW = (255, 76, 70, 120)
BLUE = (68, 125, 205, 255)
DARK = (3, 7, 9, 244)
DARK_SOFT = (3, 7, 9, 218)


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
    except (OSError, ET.ParseError):
        return {}

    output: dict[str, Any] = {}
    aliases = {
        "overall_score": ("OverallScore", "Score"),
        "overall_level": ("OverallLevel", "Level", "Rating"),
        "evidence_records": ("EvidenceRecords", "EvidenceCount"),
    }

    for key, names in aliases.items():
        for name in names:
            element = root.find(f".//{name}")
            if element is not None and element.text:
                output[key] = element.text.strip()
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


def text(raw: Any, default: str = "N/A") -> str:
    if raw is None:
        return default
    rendered = str(raw).strip()
    return rendered or default


def integer(raw: Any, default: int = 0) -> int:
    try:
        return int(float(str(raw).strip()))
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


def scaled_point(
    point: tuple[int, int], image_width: int, image_height: int
) -> tuple[int, int]:
    sx = image_width / REFERENCE_WIDTH
    sy = image_height / REFERENCE_HEIGHT
    return round(point[0] * sx), round(point[1] * sy)


def scaled_box(
    box: tuple[int, int, int, int], image_width: int, image_height: int
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    p1 = scaled_point((x1, y1), image_width, image_height)
    p2 = scaled_point((x2, y2), image_width, image_height)
    return p1[0], p1[1], p2[0], p2[1]


def scaled_font(
    image_width: int,
    image_height: int,
    size: int,
    bold: bool = False,
) -> ImageFont.ImageFont:
    scale = min(image_width / REFERENCE_WIDTH, image_height / REFERENCE_HEIGHT)
    return load_font(max(8, round(size * scale)), bold)


def text_width(
    draw: ImageDraw.ImageDraw,
    rendered: str,
    font: ImageFont.ImageFont,
) -> int:
    box = draw.textbbox((0, 0), rendered, font=font)
    return box[2] - box[0]


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
        shortened = candidate.rstrip() + "..."
        if text_width(draw, shortened, font) <= maximum_width:
            return shortened
        candidate = candidate[:-1]

    return "..."


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
    return "LOW"


def access_level(score: int, severity: str, priority: str) -> int:
    combined = f"{severity} {priority}".lower()
    if score >= 85 or "critical" in combined:
        return 7
    if score >= 65 or "high" in combined:
        return 6
    if score >= 40 or "moderate" in combined or "elevated" in combined:
        return 5
    return 4


def stage_index(status: str, phase: str) -> int:
    combined = f"{status} {phase}".lower()

    # Check late-stage terms first so "operational recovery" does not get
    # mistaken for the word "review".
    if any(word in combined for word in ("contain", "recover", "recovery", "close")):
        return 4
    if any(word in combined for word in ("assess", "analysis", "monitor")):
        return 3
    if any(word in combined for word in ("valid", "forensic", "investigation")):
        return 2
    if any(word in combined for word in ("evidence", "collect", "correlation", "field coordination")):
        return 1
    if any(word in combined for word in ("scan", "open", "detection", "intake")):
        return 0

    return 2


def build_live_data() -> dict[str, Any]:
    case = load_json(CURRENT_CASE_PATH)
    operation = load_json(ACTIVE_OPERATION_PATH)
    score_report = load_json(CSHARP_JSON_PATH)
    if not score_report:
        score_report = load_xml(CSHARP_XML_PATH)

    now_eastern = datetime.now(EASTERN_TIME)
    updated_date = now_eastern.strftime("%Y-%m-%d")
    updated_time = now_eastern.strftime("%I:%M %p %Z").lstrip("0")
    updated_compact = f"{updated_date} {updated_time}"

    score = integer(
        value(
            score_report,
            "overallScore",
            "overall_score",
            "score",
            default=value(case, "risk_score", "riskScore", default=0),
        ),
        0,
    )

    confidence = integer(
        value(case, "confidence", "confidence_score", default=85),
        85,
    )
    integrity = max(72.0, min(99.8, 72 + confidence * 0.28))

    case_id = text(value(case, "case_id", "caseId", default="BID-UNKNOWN"))
    campaign_id = text(
        value(operation, "campaign_id", "operation_id", default="BDC-UNKNOWN")
    )
    severity = text(value(case, "severity", default="LOW")).upper()
    priority = text(value(case, "priority", default="ROUTINE")).upper()
    status = text(value(case, "status", "case_status", default="OPEN")).upper()
    phase = text(
        value(operation, "campaign_phase", "phase", default="Evidence Review")
    )

    case_suffix = "".join(character for character in case_id if character.isdigit())[-4:]
    campaign_suffix = "".join(
        character for character in campaign_id if character.isdigit()
    )[-3:]
    node = f"BID-{case_suffix or '0000'}-{campaign_suffix or '000'}"

    return {
        "case_id": case_id,
        "campaign_id": campaign_id,
        "campaign": text(
            value(
                operation,
                "operation",
                "campaign",
                "campaign_name",
                default="Active Investigation Campaign",
            )
        ),
        "classification": text(
            value(
                case,
                "classification",
                "case_type",
                "investigation_type",
                default="Protected Systems Investigation",
            )
        ),
        "threat": text(
            value(
                case,
                "threat_family",
                "threat",
                "threat_name",
                default="Research-Linked Activity",
            )
        ),
        "status": status,
        "severity": severity,
        "priority": priority,
        "lead": text(
            value(
                case,
                "lead_analyst",
                "analyst",
                default="Investigative Analysis Unit",
            )
        ),
        "updated_date": updated_date,
        "updated_time": updated_time,
        "updated_compact": updated_compact,
        "unit_status": "ACTIVE" if status not in {"CLOSED", "ARCHIVED"} else "STANDBY",
        "system_integrity": f"{integrity:.1f}%",
        "evidence": integer(
            value(
                score_report,
                "evidenceRecords",
                "evidence_records",
                default=value(case, "evidence_count", "evidenceCount", default=0),
            ),
            0,
        ),
        "integrations": integer(
            value(
                case,
                "ioc_count",
                "indicator_count",
                "indicators",
                default=0,
            ),
            0,
        ),
        "date_opened": text(
            value(
                operation,
                "opened",
                "date_opened",
                default=value(
                    case,
                    "date_opened",
                    "date",
                    default=updated_date,
                ),
            )
        ),
        "score": score,
        "score_level": text(
            value(
                score_report,
                "overallLevel",
                "overall_level",
                "level",
                default=threat_level(score),
            )
        ).upper(),
        "phase": phase,
        "next_action": text(
            value(
                operation,
                "next_objective",
                "next_action",
                default=value(
                    case,
                    "recommended_action",
                    default="Continue synchronized evidence review and case validation.",
                ),
            )
        ),
        "assessment": text(
            value(
                case,
                "assessment",
                "summary",
                default="Available evidence supports expanded investigative review.",
            )
        ),
        "access_level": access_level(score, severity, priority),
        "node": node,
    }


def cover_dynamic_regions(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
) -> None:
    """Clear only the areas that contain live values.

    The procedure icons, stage labels, legend, chart labels, and panel headings
    are deliberately preserved from the base artwork.
    """
    regions = [
        ((1220, 8, 1650, 38), DARK),       # top access / node
        ((202, 313, 347, 575), DARK),      # left-side live values
        ((558, 205, 744, 410), DARK),      # center-left live values
        ((925, 205, 1120, 410), DARK),     # center-right live values
        ((682, 636, 778, 785), DARK),      # system-status values
        ((456, 785, 765, 817), DARK_SOFT), # system-status waveform
        ((804, 637, 1188, 828), DARK_SOFT),# threat monitor
        ((1224, 637, 1602, 817), DARK),    # operational brief
        ((1000, 866, 1608, 908), DARK),    # remove both static footer clocks
    ]

    for box, fill in regions:
        draw.rectangle(scaled_box(box, image_width, image_height), fill=fill)


def draw_top_access(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    font = scaled_font(image_width, image_height, 13, True)
    rendered = (
        f"LEVEL {data['access_level']} • CASE ACCESS  |  NODE: {data['node']}"
    )
    right_x, y = scaled_point((1625, 14), image_width, image_height)
    draw.text((right_x, y), rendered, font=font, fill=RED, anchor="ra")


def draw_left_panel(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    value_font = scaled_font(image_width, image_height, 13, True)
    compact_font = scaled_font(image_width, image_height, 10, True)
    small_font = scaled_font(image_width, image_height, 12, True)

    x = scaled_point((210, 0), image_width, image_height)[0]
    max_width = scaled_point((340, 0), image_width, image_height)[0] - x

    rows = [
        (data["case_id"], 324, WHITE, value_font),
        (data["campaign_id"], 357, WHITE, value_font),
        (data["status"], 390, RED, value_font),
        (
            f"{data['severity']} / {data['priority']}",
            423,
            RED if data["priority"] in {"HIGH", "ELEVATED", "CRITICAL"} else WHITE,
            compact_font,
        ),
        (data["lead"], 456, WHITE, compact_font),
        (data["updated_date"], 489, TEXT, value_font),
        (data["unit_status"], 524, RED, value_font),
    ]

    for rendered, y_ref, color, row_font in rows:
        _, y = scaled_point((0, y_ref), image_width, image_height)
        draw.text(
            (x, y),
            ellipsize(draw, rendered, row_font, max_width),
            font=row_font,
            fill=color,
        )

    draw.text(
        scaled_point((210, 557), image_width, image_height),
        data["system_integrity"],
        font=small_font,
        fill=WHITE,
    )

    bar_x, bar_y = scaled_point((279, 551), image_width, image_height)
    bar_width = max(3, scaled_point((6, 0), image_width, image_height)[0])
    gap = max(2, scaled_point((3, 0), image_width, image_height)[0])
    heights = [7, 10, 13, 16, 19]

    for index, height_ref in enumerate(heights):
        height = scaled_point((0, height_ref), image_width, image_height)[1]
        draw.rectangle(
            (
                bar_x + index * (bar_width + gap),
                bar_y + 20 - height,
                bar_x + index * (bar_width + gap) + bar_width,
                bar_y + 20,
            ),
            fill=RED,
        )


def draw_center_details(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    normal_font = scaled_font(image_width, image_height, 12, True)
    compact_font = scaled_font(image_width, image_height, 11, True)
    line_step = scaled_point((0, 16), image_width, image_height)[1]

    left_x = scaled_point((566, 0), image_width, image_height)[0]
    left_max = scaled_point((738, 0), image_width, image_height)[0] - left_x

    left_rows = [
        (data["classification"], 210, WHITE, 2, (558, 205, 744, 247)),
        (data["threat"], 253, WHITE, 2, (558, 248, 744, 291)),
        (data["phase"], 298, WHITE, 2, (558, 293, 744, 334)),
        (data["status"].title(), 340, RED, 1, (558, 336, 744, 368)),
        (data["severity"].title(), 378, WHITE, 1, (558, 373, 744, 405)),
    ]

    for rendered, y_ref, color, max_lines, clear_box in left_rows:
        draw.rectangle(scaled_box(clear_box, image_width, image_height), fill=DARK)
        _, y = scaled_point((0, y_ref), image_width, image_height)
        lines = wrap_text(draw, rendered, compact_font, left_max, max_lines)
        for line_index, line in enumerate(lines):
            draw.text(
                (left_x, y + line_index * line_step),
                line,
                font=compact_font,
                fill=color,
            )

    right_x = scaled_point((934, 0), image_width, image_height)[0]
    right_max = scaled_point((1114, 0), image_width, image_height)[0] - right_x

    right_rows = [
        (data["priority"].title(), 210, RED, (925, 205, 1120, 238)),
        (data["lead"], 252, WHITE, (925, 245, 1120, 278)),
        (f"{data['evidence']} Records", 292, WHITE, (925, 285, 1120, 318)),
        (str(data["integrations"]), 332, WHITE, (925, 325, 1120, 358)),
        (data["updated_date"], 372, TEXT, (925, 365, 1120, 400)),
    ]

    for rendered, y_ref, color, clear_box in right_rows:
        draw.rectangle(scaled_box(clear_box, image_width, image_height), fill=DARK)
        _, y = scaled_point((0, y_ref), image_width, image_height)
        draw.text(
            (right_x, y),
            ellipsize(draw, rendered, normal_font, right_max),
            font=normal_font,
            fill=color,
        )


def draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: tuple[int, int, int, int],
    width: int,
    glow: bool = False,
) -> None:
    x1, y1 = start
    x2, y2 = end

    if glow:
        glow_width = width + 4
        glow_color = (180, 45, 43, 95)
        draw.line((x1, y1, x2 - glow_width * 2, y2), fill=glow_color, width=glow_width)
        glow_head = max(8, glow_width * 3)
        draw.line((x2 - glow_head, y2 - glow_head, x2, y2), fill=glow_color, width=glow_width)
        draw.line((x2 - glow_head, y2 + glow_head, x2, y2), fill=glow_color, width=glow_width)

    draw.line((x1, y1, x2 - width * 2, y2), fill=color, width=width)
    head = max(6, width * 3)
    draw.line((x2 - head, y2 - head, x2, y2), fill=color, width=width)
    draw.line((x2 - head, y2 + head, x2, y2), fill=color, width=width)


def draw_procedure_progress(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    """Update stage borders and arrows without erasing icons or the legend.

    Completed stages/arrows are blue, the current stage and incoming arrow are
    bold dark red, and pending stages/arrows are dim gray. The legend in the
    base image is a key, so it stays static while the actual stages update.
    """
    icon_boxes = [
        (408, 419, 496, 503),
        (554, 419, 642, 503),
        (708, 419, 792, 503),
        (855, 419, 944, 503),
        (1006, 419, 1095, 503),
    ]
    arrows_reference = [
        ((505, 461), (535, 461)),
        ((657, 461), (690, 461)),
        ((810, 461), (842, 461)),
        ((954, 461), (996, 461)),
    ]
    arrow_clear_boxes = [
        (497, 444, 544, 480),
        (648, 444, 699, 480),
        (801, 444, 852, 480),
        (946, 444, 1003, 480),
    ]

    stage = stage_index(data["status"], data["phase"])
    current_arrow = stage - 1 if stage > 0 else -1
    line_width = max(2, round(image_width / 760))

    # Remove only the old arrow artwork.
    for clear_box in arrow_clear_boxes:
        draw.rectangle(scaled_box(clear_box, image_width, image_height), fill=DARK_SOFT)

    # Remove only the thin icon borders, preserving each icon and label.
    border_thickness = max(7, round(image_width / 240))
    for index, icon_box in enumerate(icon_boxes):
        x1, y1, x2, y2 = scaled_box(icon_box, image_width, image_height)
        draw.rectangle((x1, y1, x2, y1 + border_thickness), fill=DARK_SOFT)
        draw.rectangle((x1, y2 - border_thickness, x2, y2), fill=DARK_SOFT)
        draw.rectangle((x1, y1, x1 + border_thickness, y2), fill=DARK_SOFT)
        draw.rectangle((x2 - border_thickness, y1, x2, y2), fill=DARK_SOFT)

        if index < stage:
            border_color = BLUE
            border_width = 2
        elif index == stage:
            pulse = 0.55 + 0.45 * math.sin(frame_index * 0.65)
            border_color = (round(150 + 45 * pulse), 36, 34, 255)
            border_width = 4
        else:
            border_color = DIM
            border_width = 2

        draw.rounded_rectangle(
            (x1, y1, x2, y2),
            radius=max(4, round(image_width / 420)),
            outline=border_color,
            width=border_width,
        )

    # Draw arrows using the same completed/current/pending state.
    for index, (start_ref, end_ref) in enumerate(arrows_reference):
        start = scaled_point(start_ref, image_width, image_height)
        end = scaled_point(end_ref, image_width, image_height)

        if index < current_arrow:
            draw_arrow(draw, start, end, BLUE, line_width)
        elif index == current_arrow:
            pulse = 0.55 + 0.45 * math.sin(frame_index * 0.65)
            current_color = (round(145 + 40 * pulse), 38, 36, 255)
            draw_arrow(
                draw,
                start,
                end,
                current_color,
                max(line_width + 2, 4),
                glow=True,
            )
        else:
            draw_arrow(draw, start, end, DIM, line_width)


def draw_evidence_package(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    font = scaled_font(image_width, image_height, 11, True)
    x = scaled_point((1298, 0), image_width, image_height)[0]
    max_width = scaled_point((1398, 0), image_width, image_height)[0] - x

    rows = [
        (data["case_id"], 114, (1286, 101, 1400, 136)),
        (f"{data['evidence']} RECORDS", 155, (1286, 140, 1400, 176)),
        (str(data["integrations"]), 195, (1286, 180, 1400, 216)),
        (data["updated_date"], 235, (1286, 218, 1400, 252)),
    ]

    for rendered, y_ref, clear_box in rows:
        draw.rectangle(scaled_box(clear_box, image_width, image_height), fill=DARK)
        _, y = scaled_point((0, y_ref), image_width, image_height)
        draw.text(
            (x, y),
            ellipsize(draw, rendered, font, max_width),
            font=font,
            fill=WHITE,
        )


def draw_evidence_folder_scan(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    frame_index: int,
) -> None:
    x1, y1, x2, y2 = scaled_box((1418, 73, 1612, 255), image_width, image_height)
    scan_y = y1 + round(((frame_index + 1) / FRAME_COUNT) * (y2 - y1))
    draw.rectangle((x1, scan_y - 2, x2, scan_y + 2), fill=(231, 51, 47, 42))
    draw.line((x1, scan_y, x2, scan_y), fill=RED_DIM, width=1)


def draw_case_overview(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    font = scaled_font(image_width, image_height, 9, True)
    x = scaled_point((1238, 0), image_width, image_height)[0]
    max_width = scaled_point((1364, 0), image_width, image_height)[0] - x
    line_step = scaled_point((0, 14), image_width, image_height)[1]

    rows = [
        (data["classification"], 343, WHITE, 2, (1232, 331, 1368, 373)),
        (data["threat"], 385, WHITE, 2, (1232, 374, 1368, 414)),
        (data["status"].title(), 424, RED, 1, (1232, 415, 1368, 448)),
        (data["severity"].title(), 462, WHITE, 1, (1232, 449, 1368, 486)),
        (data["date_opened"], 500, WHITE, 1, (1232, 487, 1368, 523)),
        (data["priority"].title(), 538, RED, 1, (1232, 524, 1368, 558)),
    ]

    for rendered, y_ref, color, max_lines, clear_box in rows:
        draw.rectangle(scaled_box(clear_box, image_width, image_height), fill=DARK)
        _, y = scaled_point((0, y_ref), image_width, image_height)
        lines = wrap_text(draw, rendered, font, max_width, max_lines)
        for line_index, line in enumerate(lines):
            draw.text(
                (x, y + line_index * line_step),
                line,
                font=font,
                fill=color,
            )


def draw_file_network_motion(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    frame_index: int,
) -> None:
    nodes = [
        (1448, 347),
        (1542, 347),
        (1406, 407),
        (1591, 407),
        (1460, 465),
        (1568, 467),
        (1508, 410),
        (1508, 523),
    ]

    active_node = frame_index % len(nodes)
    for index, node_ref in enumerate(nodes):
        x, y = scaled_point(node_ref, image_width, image_height)
        if index == active_node:
            radius = 5 + round(2 * (0.5 + 0.5 * math.sin(frame_index * 0.8)))
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=RED, width=2)
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=RED)
        else:
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=RED_DIM)

    x1, y1, x2, y2 = scaled_box((1380, 304, 1612, 567), image_width, image_height)
    scan_y = y1 + round(((frame_index + 0.5) / FRAME_COUNT) * (y2 - y1))
    draw.line((x1, scan_y, x2, scan_y), fill=(231, 51, 47, 62), width=1)


def draw_case_feed(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    # Clear and redraw only the plot interior. The y-axis labels and x-axis
    # coordinates remain untouched on the left and below the plot.
    plot_box = (62, 638, 405, 754)
    draw.rectangle(scaled_box(plot_box, image_width, image_height), fill=DARK_SOFT)

    x1, y1, x2, y2 = scaled_box((70, 644, 398, 750), image_width, image_height)
    axis_x, axis_y = scaled_point((61, 752), image_width, image_height)
    axis_right = scaled_point((405, 0), image_width, image_height)[0]
    axis_top = scaled_point((0, 638), image_width, image_height)[1]
    draw.line((axis_x, axis_top, axis_x, axis_y), fill=MUTED, width=1)
    draw.line((axis_x, axis_y, axis_right, axis_y), fill=MUTED, width=1)

    seed = sum(ord(character) for character in data["case_id"])
    count = 24
    gap = max(2, scaled_point((4, 0), image_width, image_height)[0])
    bar_width = max(3, (x2 - x1 - gap * (count - 1)) // count)
    usable_height = y2 - y1

    for index in range(count):
        rng = random.Random(seed + index * 137)
        phase_one = rng.uniform(0, math.tau)
        phase_two = rng.uniform(0, math.tau)
        speed = rng.uniform(0.28, 0.92)

        level = (
            0.48
            + 0.29 * math.sin(frame_index * speed + phase_one)
            + 0.16 * math.sin(frame_index * 0.39 + phase_two)
        )
        level = max(0.08, min(0.98, level))
        bar_height = max(4, round(usable_height * level))
        x = x1 + index * (bar_width + gap)
        color = RED if index >= count - 2 else (WHITE if index % 4 == 0 else TEXT)
        draw.rectangle((x, y2 - bar_height, x + bar_width, y2), fill=color)


def draw_system_status(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    font = scaled_font(image_width, image_height, 12, True)
    confidence = integer(data["system_integrity"].replace("%", "").split(".")[0], 98)

    values = [
        "VERIFIED",
        "STABLE",
        "ONLINE",
        "SECURE" if confidence >= 90 else "REVIEW",
        "ACTIVE",
    ]

    # Cover all five static values, including the final ACTIVE row.
    draw.rectangle(
        scaled_box((682, 636, 778, 786), image_width, image_height),
        fill=DARK,
    )

    x = scaled_point((690, 0), image_width, image_height)[0]
    for rendered, y_ref in zip(values, [646, 676, 706, 736, 766]):
        _, y = scaled_point((0, y_ref), image_width, image_height)
        draw.text(
            (x, y),
            rendered,
            font=font,
            fill=BLUE if rendered != "REVIEW" else RED,
        )

    x1, y1, x2, y2 = scaled_box((462, 790, 758, 812), image_width, image_height)
    seed = sum(ord(character) for character in data["case_id"]) + 444
    points = []

    for index in range(42):
        ratio = index / 41
        x_point = x1 + ratio * (x2 - x1)
        rng = random.Random(seed + index * 29)
        offset = 5 * math.sin(
            frame_index * 0.33 + index * 0.52 + rng.uniform(0, math.tau)
        )
        y_point = (y1 + y2) / 2 + offset
        points.append((x_point, y_point))

    draw.line(points, fill=BLUE, width=1)


def draw_threat_monitor(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    score_font = scaled_font(image_width, image_height, 34, True)
    body_font = scaled_font(image_width, image_height, 12, True)
    small_font = scaled_font(image_width, image_height, 10)

    draw.text(
        scaled_point((808, 653), image_width, image_height),
        f"{data['score']:03d}",
        font=score_font,
        fill=RED,
    )
    draw.text(
        scaled_point((810, 706), image_width, image_height),
        data["score_level"],
        font=body_font,
        fill=WHITE,
    )
    draw.text(
        scaled_point((810, 744), image_width, image_height),
        "CURRENT FOOTPRINT",
        font=body_font,
        fill=TEXT,
    )

    x1, y1, x2, y2 = scaled_box((910, 648, 1182, 730), image_width, image_height)
    seed = sum(ord(character) for character in data["case_id"]) + 700
    points = []

    for index in range(48):
        rng = random.Random(seed + index * 71)
        ratio = index / 47
        x_point = x1 + ratio * (x2 - x1)
        y_center = (y1 + y2) / 2
        offset = 0.0
        offset += 13 * math.sin(frame_index * 0.48 + index * 0.43 + rng.uniform(0, math.tau))
        offset += 7 * math.sin(frame_index * 0.21 + index * 0.17 + rng.uniform(0, math.tau))
        y_point = max(y1 + 4, min(y2 - 4, y_center + offset))
        points.append((x_point, y_point))

    draw.line(points, fill=RED, width=max(2, round(image_width / 900)))

    summary_lines = [
        f"• {data['classification']}",
        f"• {data['threat']}",
    ]
    max_width = scaled_point((1178, 0), image_width, image_height)[0] - scaled_point((812, 0), image_width, image_height)[0]

    for rendered, y_ref in zip(summary_lines, [776, 803]):
        draw.text(
            scaled_point((812, y_ref), image_width, image_height),
            ellipsize(draw, rendered, small_font, max_width),
            font=small_font,
            fill=TEXT,
        )


def draw_operational_brief(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    font = scaled_font(image_width, image_height, 11)
    x_bullet = scaled_point((1232, 0), image_width, image_height)[0]
    x_text = scaled_point((1253, 0), image_width, image_height)[0]
    max_width = scaled_point((1594, 0), image_width, image_height)[0] - x_text

    entries = [
        (data["assessment"], 646, 2),
        (f"Phase: {data['phase']}", 697, 1),
        (f"Priority review: {data['severity'].title()} / {data['priority'].title()}", 733, 1),
        (f"Next action: {data['next_action']}", 769, 2),
    ]

    for rendered, y_ref, maximum_lines in entries:
        _, y = scaled_point((0, y_ref), image_width, image_height)
        draw.ellipse((x_bullet, y + 5, x_bullet + 5, y + 10), fill=RED)
        lines = wrap_text(draw, rendered, font, max_width, maximum_lines)
        for line_index, line in enumerate(lines):
            line_y = y + line_index * scaled_point((0, 17), image_width, image_height)[1]
            if line_y > scaled_point((0, 808), image_width, image_height)[1]:
                break
            draw.text((x_text, line_y), line, font=font, fill=TEXT)


def draw_footer_time(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    label_font = scaled_font(image_width, image_height, 12, True)
    time_font = scaled_font(image_width, image_height, 11, True)

    # One Eastern timestamp only. ZoneInfo automatically supplies EST or EDT.
    right_x, y = scaled_point((1594, 882), image_width, image_height)
    rendered = f"ET  |  {data['updated_compact']}"
    draw.text(
        (right_x, y),
        rendered,
        font=time_font,
        fill=TEXT,
        anchor="ra",
    )
    label_x = right_x - text_width(draw, rendered, time_font) - scaled_point((12, 0), image_width, image_height)[0]
    draw.text((label_x, y), "LIVE", font=label_font, fill=RED, anchor="ra")


def render_frame(
    base_image: Image.Image,
    data: dict[str, Any],
    frame_index: int,
) -> Image.Image:
    frame = base_image.copy().convert("RGBA")
    draw = ImageDraw.Draw(frame, "RGBA")
    width, height = frame.size

    cover_dynamic_regions(draw, width, height)
    draw_top_access(draw, width, height, data)
    draw_left_panel(draw, width, height, data)
    draw_center_details(draw, width, height, data)
    draw_procedure_progress(draw, width, height, data, frame_index)
    draw_evidence_package(draw, width, height, data)
    draw_evidence_folder_scan(draw, width, height, frame_index)
    draw_case_overview(draw, width, height, data)
    draw_file_network_motion(draw, width, height, frame_index)
    draw_case_feed(draw, width, height, data, frame_index)
    draw_system_status(draw, width, height, data, frame_index)
    draw_threat_monitor(draw, width, height, data, frame_index)
    draw_operational_brief(draw, width, height, data)
    draw_footer_time(draw, width, height, data)

    return frame


def main() -> None:
    if not BASE_IMAGE_PATH.exists():
        raise FileNotFoundError(f"Missing dashboard base image: {BASE_IMAGE_PATH}")

    base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
    data = build_live_data()
    frames: list[Image.Image] = []

    for frame_index in range(FRAME_COUNT):
        frame = render_frame(base_image, data, frame_index)
        frames.append(frame.convert("P", palette=Image.ADAPTIVE, colors=224))

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

    print(f"Generated dynamic BioDefense banner: {OUTPUT_GIF_PATH}")
    print(
        f"Banner details: {base_image.width}x{base_image.height}, "
        f"{FRAME_COUNT} frames, case {data['case_id']}."
    )


if __name__ == "__main__":
    main()
