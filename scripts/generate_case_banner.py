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
RED_GLOW = (255, 76, 70, 110)

BLUE = (72, 122, 210, 255)
BLUE_DIM = (48, 88, 150, 255)

DARK = (3, 7, 9, 244)
DARK_SOFT = (3, 7, 9, 220)


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


def text_height(
    draw: ImageDraw.ImageDraw,
    rendered: str,
    font: ImageFont.ImageFont,
) -> int:
    box = draw.textbbox((0, 0), rendered, font=font)
    return box[3] - box[1]


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


def clear_text_line(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int, int] = DARK,
) -> None:
    draw.rectangle(scaled_box(box, image_width, image_height), fill=fill)


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

    if any(word in combined for word in ("contain", "recover", "recovery", "close")):
        return 4
    if any(word in combined for word in ("assess", "analysis", "monitor")):
        return 3
    if any(word in combined for word in ("valid", "forensic", "investigation")):
        return 2
    if any(
        word in combined
        for word in ("evidence", "collect", "correlation", "field coordination")
    ):
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
    regions = [
        ((1220, 8, 1650, 37), DARK),          # top-right level / node
        ((205, 315, 343, 573), DARK),         # left panel values
        ((560, 209, 712, 408), DARK),         # center-left values
        ((926, 209, 1112, 408), DARK),        # center-right values
        ((1274, 104, 1414, 229), DARK),       # evidence package values
        ((1238, 331, 1366, 548), DARK),       # case overview values
        ((458, 428, 1118, 558), DARK_SOFT),   # procedure arrows + legend
        ((70, 612, 390, 716), DARK_SOFT),     # active case feed plotting area
        ((680, 637, 772, 816), DARK),         # system status right values
        ((456, 786, 760, 816), DARK_SOFT),    # system waveform
        ((804, 638, 1188, 829), DARK_SOFT),   # threat monitor dynamic area
        ((1225, 637, 1600, 816), DARK),       # operational brief
        ((1400, 842, 1626, 883), DARK),       # single footer time
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
    rendered = f"LEVEL {data['access_level']} • CASE ACCESS  |  NODE: {data['node']}"
    right_x, y = scaled_point((1628, 14), image_width, image_height)
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
    normal_font = scaled_font(image_width, image_height, 13, True)
    compact_font = scaled_font(image_width, image_height, 12, True)

    left_x = scaled_point((565, 0), image_width, image_height)[0]
    left_max = scaled_point((708, 0), image_width, image_height)[0] - left_x

    left_rows = [
        (data["classification"], 218, WHITE),
        (data["threat"], 268, WHITE),
        (data["phase"], 318, WHITE),
        (data["status"].title(), 356, RED),
        (data["severity"].title(), 391, WHITE),
    ]

    for rendered, y_ref, color in left_rows:
        _, y = scaled_point((0, y_ref), image_width, image_height)
        lines = wrap_text(draw, rendered, compact_font, left_max, 2)
        for line_index, line in enumerate(lines):
            draw.text(
                (
                    left_x,
                    y
                    + line_index
                    * scaled_point((0, 17), image_width, image_height)[1],
                ),
                line,
                font=compact_font,
                fill=color,
            )

    right_x = scaled_point((932, 0), image_width, image_height)[0]
    right_max = scaled_point((1105, 0), image_width, image_height)[0] - right_x

    right_rows = [
        (data["priority"].title(), 218, RED),
        (data["lead"], 262, WHITE),
        (f"{data['evidence']} Records", 302, WHITE),
        (str(data["integrations"]), 342, WHITE),
        (data["updated_compact"], 380, TEXT),
    ]

    for rendered, y_ref, color in right_rows:
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
        glow_width = width + 3
        draw.line((x1, y1, x2 - glow_width * 2, y2), fill=RED_GLOW, width=glow_width)
        head = max(8, glow_width * 3)
        draw.line((x2 - head, y2 - head, x2, y2), fill=RED_GLOW, width=glow_width)
        draw.line((x2 - head, y2 + head, x2, y2), fill=RED_GLOW, width=glow_width)

    draw.line((x1, y1, x2 - width * 2, y2), fill=color, width=width)
    head = max(6, width * 3)
    draw.line((x2 - head, y2 - head, x2, y2), fill=color, width=width)
    draw.line((x2 - head, y2 + head, x2, y2), fill=color, width=width)


def draw_status_legend(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
) -> None:
    font = scaled_font(image_width, image_height, 11, True)
    items = [
        ("COMPLETED", BLUE, (585, 528)),
        ("CURRENT", RED, (746, 528)),
        ("PENDING", DIM, (904, 528)),
    ]

    line_len = max(24, scaled_point((38, 0), image_width, image_height)[0])
    line_y_offset = scaled_point((0, 7), image_width, image_height)[1]

    for label, color, point_ref in items:
        x, y = scaled_point(point_ref, image_width, image_height)
        draw.line((x - line_len, y + line_y_offset, x - 8, y + line_y_offset), fill=color, width=3 if label == "CURRENT" else 2)
        draw.text((x, y), label, font=font, fill=color)


def draw_procedure_progress(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    arrows_reference = [
        ((505, 471), (535, 471)),
        ((657, 471), (690, 471)),
        ((810, 471), (842, 471)),
        ((954, 471), (996, 471)),
    ]

    stage = stage_index(data["status"], data["phase"])
    active_arrow = 0 if stage == 0 else stage - 1
    line_width = max(2, round(image_width / 760))

    for index, (start_ref, end_ref) in enumerate(arrows_reference):
        start = scaled_point(start_ref, image_width, image_height)
        end = scaled_point(end_ref, image_width, image_height)

        if index < active_arrow:
            color = BLUE
            draw_arrow(draw, start, end, color, line_width)
        elif index == active_arrow:
            pulse = 0.55 + 0.45 * math.sin(frame_index * 0.65)
            current_width = max(line_width + 2, round(line_width * 1.5))
            current_color = (
                231,
                round(42 + 18 * pulse),
                round(42 + 18 * pulse),
                255,
            )
            draw_arrow(draw, start, end, current_color, current_width, glow=True)
        else:
            draw_arrow(draw, start, end, DIM, line_width)

    draw_status_legend(draw, image_width, image_height)


def draw_evidence_package(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    font = scaled_font(image_width, image_height, 11, True)
    x = scaled_point((1284, 0), image_width, image_height)[0]
    max_width = scaled_point((1410, 0), image_width, image_height)[0] - x

    values = [
        (data["case_id"], 115),
        (f"{data['evidence']} RECORDS", 151),
        (str(data["integrations"]), 187),
        (data["updated_compact"], 220),
    ]

    row_height = text_height(draw, "A", font) + 6

    for rendered, y_ref in values:
        clear_text_line(
            draw,
            image_width,
            image_height,
            (1278, y_ref - 3, 1416, y_ref + 15),
            DARK,
        )
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
    font = scaled_font(image_width, image_height, 10, True)
    x = scaled_point((1246, 0), image_width, image_height)[0]
    max_width = scaled_point((1360, 0), image_width, image_height)[0] - x
    line_step = scaled_point((0, 15), image_width, image_height)[1]

    rows = [
        (data["classification"], 343, WHITE, 2),
        (data["threat"], 385, WHITE, 2),
        (data["status"].title(), 424, RED, 1),
        (data["severity"].title(), 461, WHITE, 1),
        (data["date_opened"], 497, WHITE, 1),
        (data["priority"].title(), 534, RED, 1),
    ]

    for rendered, y_ref, color, max_lines in rows:
        clear_text_line(
            draw,
            image_width,
            image_height,
            (1242, y_ref - 3, 1362, y_ref + 28),
            DARK,
        )
        _, y = scaled_point((0, y_ref), image_width, image_height)
        lines = wrap_text(draw, rendered, font, max_width, max_lines)
        for index, line in enumerate(lines):
            draw.text(
                (x, y + index * line_step),
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
    x1, y1, x2, y2 = scaled_box((78, 618, 386, 713), image_width, image_height)
    seed = sum(ord(character) for character in data["case_id"])
    count = 24
    gap = max(2, scaled_point((5, 0), image_width, image_height)[0])
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

    x = scaled_point((690, 0), image_width, image_height)[0]
    for rendered, y_ref in zip(values, [646, 676, 706, 736, 766]):
        _, y = scaled_point((0, y_ref), image_width, image_height)
        draw.text((x, y), rendered, font=font, fill=BLUE if rendered != "REVIEW" else RED)

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
        offset += 13 * math.sin(
            frame_index * 0.48 + index * 0.43 + rng.uniform(0, math.tau)
        )
        offset += 7 * math.sin(
            frame_index * 0.21 + index * 0.17 + rng.uniform(0, math.tau)
        )
        y_point = max(y1 + 4, min(y2 - 4, y_center + offset))
        points.append((x_point, y_point))

    draw.line(points, fill=RED, width=max(2, round(image_width / 900)))

    summary_lines = [
        f"• {data['classification']}",
        f"• {data['threat']}",
    ]
    max_width = (
        scaled_point((1178, 0), image_width, image_height)[0]
        - scaled_point((812, 0), image_width, image_height)[0]
    )

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
        (
            f"Priority review: {data['severity'].title()} / {data['priority'].title()}",
            733,
            1,
        ),
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
    label_font = scaled_font(image_width, image_height, 13, True)
    time_font = scaled_font(image_width, image_height, 12, True)

    draw.text(
        scaled_point((1405, 852), image_width, image_height),
        "ET",
        font=label_font,
        fill=RED,
    )
    draw.text(
        scaled_point((1445, 852), image_width, image_height),
        data["updated_compact"],
        font=time_font,
        fill=TEXT,
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
