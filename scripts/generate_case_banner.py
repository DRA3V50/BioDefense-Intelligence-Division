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

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE_IMAGE_PATH = Path("assets/biodefense-dashboard-base.png")
OUTPUT_GIF_PATH = Path("assets/biodefense-case-scan.gif")
CURRENT_CASE_PATH = Path("data/current_case.json")
ACTIVE_OPERATION_PATH = Path("operations/active_operation.json")
CSHARP_JSON_PATH = Path("reports/bioterror_threat_score_csharp.json")
CSHARP_XML_PATH = Path("reports/bioterror_threat_score_csharp.xml")

# This script is mapped specifically to the new 1727 x 911 base PNG.
REFERENCE_WIDTH = 1727
REFERENCE_HEIGHT = 911

# Keep the quicker, smooth animation pace from the older working script.
FRAME_COUNT = 18
FRAME_DURATION_MS = 120
EASTERN_TIME = ZoneInfo("America/New_York")

WHITE = (230, 233, 235, 255)
TEXT = (176, 182, 187, 255)
MUTED = (103, 110, 116, 255)
DIM = (72, 78, 84, 255)
RED = (231, 51, 47, 255)
RED_DIM = (132, 35, 34, 255)
RED_GLOW = (255, 76, 70, 78)
BLUE = (66, 124, 208, 255)
DARK = (2, 7, 9, 255)
DARK_SOFT = (2, 7, 9, 238)
GRID = (36, 43, 47, 180)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
        return loaded if isinstance(loaded, dict) else {}
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
    mapping = {
        "overall_score": ("OverallScore", "Score"),
        "overall_level": ("OverallLevel", "Level", "Rating"),
        "evidence_records": ("EvidenceRecords", "EvidenceCount"),
    }
    for destination, aliases in mapping.items():
        for alias in aliases:
            element = root.find(f".//{alias}")
            if element is not None and element.text:
                output[destination] = element.text.strip()
                break
    return output


def deep_find(data: Any, aliases: tuple[str, ...]) -> Any:
    expected = {alias.lower() for alias in aliases}
    if isinstance(data, dict):
        for key, item in data.items():
            if str(key).lower() in expected:
                return item
        for item in data.values():
            found = deep_find(item, aliases)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = deep_find(item, aliases)
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


def scaled_point(point: tuple[int, int], width: int, height: int) -> tuple[int, int]:
    return (
        round(point[0] * width / REFERENCE_WIDTH),
        round(point[1] * height / REFERENCE_HEIGHT),
    )


def scaled_box(
    box: tuple[int, int, int, int], width: int, height: int
) -> tuple[int, int, int, int]:
    x1, y1 = scaled_point((box[0], box[1]), width, height)
    x2, y2 = scaled_point((box[2], box[3]), width, height)
    return x1, y1, x2, y2


def scaled_font(
    width: int, height: int, size: int, bold: bool = False
) -> ImageFont.ImageFont:
    scale = min(width / REFERENCE_WIDTH, height / REFERENCE_HEIGHT)
    return load_font(max(8, round(size * scale)), bold)


def text_width(
    draw: ImageDraw.ImageDraw, rendered: str, font: ImageFont.ImageFont
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
    return "GUARDED"


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
    status_text = status.lower()
    phase_text = phase.lower()

    stage_terms = [
        (0, ("case scan", "scan", "open", "detection", "intake")),
        (1, ("evidence review", "evidence collection", "collect", "correlation", "field coordination")),
        (2, ("validation", "validate", "forensic", "investigation")),
        (3, ("assessment", "assess", "analysis", "intelligence analysis", "monitor")),
        (4, ("problem review", "containment", "contain", "recovery", "recover", "closed", "close")),
    ]

    for index, terms in stage_terms:
        if any(term in status_text for term in terms):
            return index
    for index, terms in stage_terms:
        if any(term in phase_text for term in terms):
            return index
    return 0


def eastern_timestamp(now: datetime) -> tuple[str, str, str]:
    date = now.strftime("%Y-%m-%d")
    hour = now.strftime("%I").lstrip("0") or "12"
    time_label = f"{hour}:{now.strftime('%M %p %Z')}"
    return date, time_label, f"{date} {time_label}"


def build_live_data() -> dict[str, Any]:
    case = load_json(CURRENT_CASE_PATH)
    operation = load_json(ACTIVE_OPERATION_PATH)
    score_report = load_json(CSHARP_JSON_PATH) or load_xml(CSHARP_XML_PATH)

    now = datetime.now(EASTERN_TIME)
    updated_date, updated_time, updated_compact = eastern_timestamp(now)

    score = integer(
        value(
            score_report,
            "overallScore",
            "overall_score",
            "score",
            default=value(case, "risk_score", "riskScore", default=46),
        ),
        46,
    )
    confidence = integer(value(case, "confidence", "confidence_score", default=82), 82)
    integrity = max(72.0, min(99.8, 72 + confidence * 0.28))

    case_id = text(value(case, "case_id", "caseId", default="BID-2026-8932"))
    campaign_id = text(
        value(operation, "campaign_id", "operation_id", default="BDC-2026-001")
    )
    severity = text(value(case, "severity", default="MODERATE")).upper()
    priority = text(value(case, "priority", default="ELEVATED")).upper()
    status = text(value(case, "status", "case_status", default="MONITORING")).upper()
    phase = text(value(operation, "campaign_phase", "phase", default="Operational Recovery"))

    case_suffix = "".join(character for character in case_id if character.isdigit())[-4:]
    campaign_suffix = "".join(
        character for character in campaign_id if character.isdigit()
    )[-3:]

    return {
        "case_id": case_id,
        "campaign_id": campaign_id,
        "classification": text(
            value(
                case,
                "classification",
                "case_type",
                "investigation_type",
                default="Specimen Management Security Review",
            )
        ),
        "threat": text(
            value(
                case,
                "threat_family",
                "threat",
                "threat_name",
                default="Biomedical Supply Chain Compromise",
            )
        ),
        "status": status,
        "severity": severity,
        "priority": priority,
        "lead": text(value(case, "lead_analyst", "analyst", default="Analyst Team Alpha")),
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
                default=value(case, "evidence_count", "evidenceCount", default=35),
            ),
            35,
        ),
        "integrations": integer(
            value(case, "ioc_count", "indicator_count", "indicators", default=16),
            16,
        ),
        "date_opened": text(
            value(
                operation,
                "opened",
                "date_opened",
                default=value(case, "date_opened", "date", default="2026-07-01"),
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
                    default="Verify recovery controls and prepare the final operational assessment.",
                ),
            )
        ),
        "assessment": text(
            value(
                case,
                "assessment",
                "summary",
                default="Correlated records suggest a multi-stage intrusion affecting research, evidence, or laboratory support systems.",
            )
        ),
        "access_level": access_level(score, severity, priority),
        "node": f"BID-{case_suffix or '0000'}-{campaign_suffix or '000'}",
    }


def cover(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    width: int,
    height: int,
    fill=DARK,
) -> None:
    draw.rectangle(scaled_box(box, width, height), fill=fill)


def cover_dynamic_regions(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    # Remove only sample/live values. All panel borders, icons, stage boxes,
    # labels, navigation, and artwork remain untouched.
    regions = [
        ((1325, 3, 1710, 36), DARK),          # top access line
        ((211, 322, 394, 561), DARK),         # left-panel values
        ((312, 518, 394, 562), DARK),         # left integrity bars
        ((592, 187, 780, 366), DARK),         # center-left values
        ((978, 187, 1212, 366), DARK),        # center-right values
        ((1378, 90, 1502, 258), DARK),        # evidence-package values
        ((1330, 312, 1476, 542), DARK),       # case-overview values
        ((1458, 300, 1622, 344), DARK),       # case-ID tag above map
        ((524, 402, 598, 464), DARK),         # procedure arrow 1
        ((675, 402, 750, 464), DARK),         # procedure arrow 2
        ((826, 402, 914, 464), DARK),         # procedure arrow 3
        ((993, 402, 1082, 464), DARK),        # procedure arrow 4
        ((54, 616, 446, 770), DARK),          # active-feed chart interior
        ((17, 767, 466, 811), DARK),          # active-feed sync line
        ((728, 614, 814, 753), DARK),         # system-status values
        ((484, 760, 816, 797), DARK),         # system-status waveform
        ((837, 612, 1254, 824), DARK),        # threat-monitor interior
        ((1266, 612, 1691, 824), DARK),       # operational-brief interior
        ((1338, 827, 1691, 878), DARK),       # footer-time interior
    ]
    for box, fill in regions:
        cover(draw, box, width, height, fill)


def draw_top_access(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    font = scaled_font(width, height, 12, True)
    rendered = f"LEVEL {data['access_level']}  •  CASE ACCESS   |   NODE: {data['node']}"
    x, y = scaled_point((1707, 15), width, height)
    draw.text((x, y), rendered, font=font, fill=RED, anchor="ra")


def draw_biohazard_glow(
    frame: Image.Image, frame_index: int, width: int, height: int
) -> Image.Image:
    """Apply a restrained pulse to existing red artwork; do not draw new rings."""
    phase = frame_index * math.tau / FRAME_COUNT
    pulse = 0.5 + 0.5 * math.sin(phase)

    x1, y1, x2, y2 = scaled_box((18, 44, 398, 320), width, height)
    crop = frame.crop((x1, y1, x2, y2)).convert("RGBA")

    mask = Image.new("L", crop.size, 0)
    values: list[int] = []
    for red, green, blue, alpha in crop.getdata():
        dominance = red - max(green, blue)
        if alpha > 0 and red >= 72 and dominance >= 22:
            base = min(255, max(0, int(dominance * 1.45)))
            values.append(base)
        else:
            values.append(0)
    mask.putdata(values)

    # Very low-alpha breathing glow. This is deliberately subtle.
    tight = mask.filter(ImageFilter.GaussianBlur(radius=max(1, round(width / 900))))
    soft = mask.filter(ImageFilter.GaussianBlur(radius=max(4, round(width / 340))))

    tight_layer = Image.new("RGBA", crop.size, (255, 58, 52, 0))
    tight_layer.putalpha(tight.point(lambda v: int(v * (0.10 + 0.07 * pulse))))

    soft_layer = Image.new("RGBA", crop.size, (255, 36, 32, 0))
    soft_layer.putalpha(soft.point(lambda v: int(v * (0.035 + 0.035 * pulse))))

    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    overlay.alpha_composite(soft_layer, (x1, y1))
    overlay.alpha_composite(tight_layer, (x1, y1))
    return Image.alpha_composite(frame, overlay)


def draw_left_panel(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    value_font = scaled_font(width, height, 11, True)
    compact_font = scaled_font(width, height, 9, True)
    x = scaled_point((225, 0), width, height)[0]
    max_width = scaled_point((390, 0), width, height)[0] - x

    rows = [
        (data["case_id"], 334, WHITE, value_font),
        (data["campaign_id"], 365, WHITE, value_font),
        (data["status"].title(), 396, RED, compact_font),
        (f"{data['severity'].title()} / {data['priority'].title()}", 427, WHITE, compact_font),
        (data["lead"], 458, WHITE, compact_font),
        (data["updated_date"], 488, TEXT, compact_font),
        (data["unit_status"], 519, RED, value_font),
        (data["system_integrity"], 549, WHITE, compact_font),
    ]
    for rendered, y_ref, color, font in rows:
        _, y = scaled_point((0, y_ref), width, height)
        draw.text(
            (x, y),
            ellipsize(draw, rendered, font, max_width),
            font=font,
            fill=color,
        )

    bar_x, bar_y = scaled_point((326, 553), width, height)
    bar_width = max(4, scaled_point((7, 0), width, height)[0])
    gap = max(3, scaled_point((4, 0), width, height)[0])
    for index, ref_height in enumerate((8, 13, 19, 25, 32)):
        bar_height = scaled_point((0, ref_height), width, height)[1]
        x1 = bar_x + index * (bar_width + gap)
        draw.rectangle((x1, bar_y - bar_height, x1 + bar_width, bar_y), fill=RED)


def draw_center_details(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    font = scaled_font(width, height, 10, True)
    line_step = scaled_point((0, 14), width, height)[1]

    left_x = scaled_point((598, 0), width, height)[0]
    left_max = scaled_point((776, 0), width, height)[0] - left_x
    left_rows = [
        (data["classification"], 195, WHITE, 2),
        (data["threat"], 237, WHITE, 2),
        (data["phase"], 279, WHITE, 1),
        (data["status"].title(), 318, RED, 1),
        (data["severity"].title(), 352, WHITE, 1),
    ]
    for rendered, y_ref, color, max_lines in left_rows:
        _, y = scaled_point((0, y_ref), width, height)
        for index, line in enumerate(wrap_text(draw, rendered, font, left_max, max_lines)):
            draw.text((left_x, y + index * line_step), line, font=font, fill=color)

    right_x = scaled_point((991, 0), width, height)[0]
    right_max = scaled_point((1208, 0), width, height)[0] - right_x
    right_rows = [
        (data["priority"].title(), 196, RED),
        (data["lead"], 235, WHITE),
        (f"{data['evidence']} Records", 278, WHITE),
        (str(data["integrations"]), 316, WHITE),
        (data["updated_compact"], 352, TEXT),
    ]
    for rendered, y_ref, color in right_rows:
        _, y = scaled_point((0, y_ref), width, height)
        draw.text(
            (right_x, y),
            ellipsize(draw, rendered, font, right_max),
            font=font,
            fill=color,
        )


def draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: tuple[int, int, int, int],
    line_width: int,
    glow: bool = False,
) -> None:
    x1, y1 = start
    x2, y2 = end
    if glow:
        draw.line((x1, y1, x2 - 10, y2), fill=RED_GLOW, width=line_width + 4)
        draw.polygon(
            [(x2, y2), (x2 - 15, y2 - 11), (x2 - 15, y2 + 11)],
            fill=RED_GLOW,
        )
    draw.line((x1, y1, x2 - 9, y2), fill=color, width=line_width)
    draw.polygon(
        [(x2, y2), (x2 - 13, y2 - 9), (x2 - 13, y2 + 9)],
        fill=color,
    )


def draw_procedure_progress(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    arrows = [
        ((539, 434), (584, 434)),
        ((691, 434), (736, 434)),
        ((844, 434), (901, 434)),
        ((1014, 434), (1067, 434)),
    ]

    current_stage = stage_index(data["status"], data["phase"])
    current_arrow = min(max(current_stage, 0), 3)
    normal_width = max(2, round(width / 900))
    current_width = normal_width + 3

    for index, (start_ref, end_ref) in enumerate(arrows):
        start = scaled_point(start_ref, width, height)
        end = scaled_point(end_ref, width, height)
        if index < current_arrow:
            draw_arrow(draw, start, end, BLUE, normal_width)
        elif index == current_arrow:
            pulse = 0.55 + 0.45 * math.sin(frame_index * 0.85)
            color = (round(190 + 25 * pulse), 45, 43, 255)
            draw_arrow(draw, start, end, color, current_width, glow=True)
        else:
            draw_arrow(draw, start, end, DIM, normal_width)


def draw_evidence_package(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    font = scaled_font(width, height, 9, True)
    x = scaled_point((1384, 0), width, height)[0]
    max_width = scaled_point((1494, 0), width, height)[0] - x

    rows = [
        (data["case_id"], 108),
        (f"{data['evidence']} RECORDS", 149),
        (str(data["integrations"]), 190),
    ]
    for rendered, y_ref in rows:
        _, y = scaled_point((0, y_ref), width, height)
        draw.text((x, y), ellipsize(draw, rendered, font, max_width), font=font, fill=WHITE)

    draw.text(scaled_point((1364, 224), width, height), data["updated_date"], font=font, fill=WHITE)
    draw.text(scaled_point((1364, 241), width, height), data["updated_time"], font=font, fill=TEXT)


def draw_magnifying_glass(
    draw: ImageDraw.ImageDraw, width: int, height: int, frame_index: int
) -> None:
    phase = frame_index * math.tau / FRAME_COUNT
    center_x = 1532 + 45 * math.cos(phase)
    center_y = 166 + 34 * math.sin(phase * 1.25)
    x, y = scaled_point((round(center_x), round(center_y)), width, height)
    radius = max(8, scaled_point((11, 0), width, height)[0])
    line_width = max(2, round(width / 1000))
    draw.ellipse(
        (x - radius, y - radius, x + radius, y + radius),
        outline=(235, 235, 235, 210),
        width=line_width,
    )
    angle = phase + 0.4
    handle = max(10, scaled_point((16, 0), width, height)[0])
    start_x = x + int(math.cos(angle) * (radius - 2))
    start_y = y + int(math.sin(angle) * (radius - 2))
    end_x = x + int(math.cos(angle) * (radius + handle))
    end_y = y + int(math.sin(angle) * (radius + handle))
    draw.line((start_x, start_y, end_x, end_y), fill=RED, width=line_width + 1)
    draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=RED)


def draw_case_overview(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    font = scaled_font(width, height, 8, True)
    x = scaled_point((1334, 0), width, height)[0]
    max_width = scaled_point((1468, 0), width, height)[0] - x
    line_step = scaled_point((0, 13), width, height)[1]

    rows = [
        (data["classification"], 326, WHITE, 2),
        (data["threat"], 371, WHITE, 2),
        (data["status"].title(), 417, RED, 1),
        (data["severity"].title(), 451, WHITE, 1),
        (data["date_opened"], 486, WHITE, 1),
        (data["priority"].title(), 520, RED, 1),
    ]
    for rendered, y_ref, color, max_lines in rows:
        _, y = scaled_point((0, y_ref), width, height)
        for index, line in enumerate(wrap_text(draw, rendered, font, max_width, max_lines)):
            draw.text((x, y + index * line_step), line, font=font, fill=color)


def draw_map_case_id(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    # Use the existing dedicated tag above the map; never draw on the CASE FILE folder.
    font = scaled_font(width, height, 8, True)
    x1, y1, x2, y2 = scaled_box((1464, 306, 1616, 338), width, height)
    draw.rectangle((x1, y1, x2, y2), fill=(4, 9, 11, 245))
    draw.rectangle((x1, y1, x2, y2), outline=(75, 76, 72, 230), width=1)
    draw.text(
        ((x1 + x2) // 2, (y1 + y2) // 2),
        f"CASE ID: {data['case_id']}",
        font=font,
        fill=WHITE,
        anchor="mm",
    )


def draw_file_network_motion(
    draw: ImageDraw.ImageDraw, width: int, height: int, frame_index: int
) -> None:
    nodes = [
        (1510, 367),
        (1630, 384),
        (1468, 419),
        (1660, 421),
        (1510, 476),
        (1606, 488),
        (1558, 536),
    ]
    active_node = frame_index % len(nodes)
    for index, node_ref in enumerate(nodes):
        x, y = scaled_point(node_ref, width, height)
        if index == active_node:
            radius = 5 + round(2 * (0.5 + 0.5 * math.sin(frame_index * 0.8)))
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=RED, width=2)
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=RED)
        else:
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=RED_DIM)


def draw_case_feed(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    x1, y1, x2, y2 = scaled_box((62, 622, 439, 749), width, height)

    for y_ref in (622, 685, 749):
        x_start, y = scaled_point((52, y_ref), width, height)
        x_end = scaled_point((440, y_ref), width, height)[0]
        draw.line((x_start, y, x_end, y), fill=GRID, width=1)

    seed = sum(ord(character) for character in data["case_id"])
    count = 31
    bar_width = max(4, scaled_point((7, 0), width, height)[0])
    usable_height = max(12, y2 - y1)
    final_start = x2 - bar_width

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
        x = round(x1 + index * (final_start - x1) / (count - 1))
        draw.rectangle((x, y2 - bar_height, x + bar_width, y2), fill=RED)

    axis_font = scaled_font(width, height, 9, True)
    for label, x_ref in (("-60", 62), ("-50", 122), ("-40", 183), ("-30", 245), ("-20", 307), ("-10", 369), ("NOW", 431)):
        x_label, y_label = scaled_point((x_ref, 756), width, height)
        draw.text((x_label, y_label), label, font=axis_font, fill=TEXT, anchor="ma")

    sync_font = scaled_font(width, height, 8, True)
    sync_text = f"FEED SYNC: {data['updated_compact']}  •  FILTER: ALL  •  STREAM: BID-LIVE"
    x, y = scaled_point((27, 784), width, height)
    max_width = scaled_point((452, 0), width, height)[0] - x
    draw.text((x, y), ellipsize(draw, sync_text, sync_font, max_width), font=sync_font, fill=TEXT)


def draw_system_status(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    font = scaled_font(width, height, 9, True)
    confidence = integer(data["system_integrity"].replace("%", "").split(".")[0], 98)
    values = [
        "VERIFIED",
        "STABLE",
        "ONLINE",
        "SECURE" if confidence >= 90 else "REVIEW",
        "ACTIVE",
    ]
    x = scaled_point((735, 0), width, height)[0]
    for rendered, y_ref in zip(values, (631, 657, 684, 710, 736)):
        _, y = scaled_point((0, y_ref), width, height)
        draw.text((x, y), rendered, font=font, fill=BLUE if rendered != "REVIEW" else RED)

    x1, y1, x2, y2 = scaled_box((490, 772, 807, 789), width, height)
    seed = sum(ord(character) for character in data["case_id"]) + 444
    points = []
    for index in range(50):
        ratio = index / 49
        x_point = x1 + ratio * (x2 - x1)
        rng = random.Random(seed + index * 29)
        offset = 4 * math.sin(frame_index * 0.33 + index * 0.52 + rng.uniform(0, math.tau))
        points.append((x_point, (y1 + y2) / 2 + offset))
    draw.line(points, fill=BLUE, width=1)


def draw_threat_monitor(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    score_font = scaled_font(width, height, 32, True)
    body_font = scaled_font(width, height, 9, True)
    bullet_font = scaled_font(width, height, 9, True)

    draw.text(scaled_point((853, 625), width, height), f"{data['score']:03d}", font=score_font, fill=RED)
    draw.text(scaled_point((854, 670), width, height), data["score_level"], font=body_font, fill=WHITE)
    draw.text(scaled_point((854, 700), width, height), "CURRENT FOOTPRINT", font=body_font, fill=TEXT)

    x1, y1, x2, y2 = scaled_box((957, 629, 1225, 690), width, height)
    seed = sum(ord(character) for character in data["case_id"]) + 700
    points = []
    for index in range(48):
        rng = random.Random(seed + index * 71)
        ratio = index / 47
        x_point = x1 + ratio * (x2 - x1)
        center = (y1 + y2) / 2
        offset = 10 * math.sin(frame_index * 0.48 + index * 0.43 + rng.uniform(0, math.tau))
        offset += 5 * math.sin(frame_index * 0.21 + index * 0.17 + rng.uniform(0, math.tau))
        points.append((x_point, max(y1 + 3, min(y2 - 3, center + offset))))
    draw.line(points, fill=RED, width=max(2, round(width / 950)))

    bullet_x, _ = scaled_point((854, 0), width, height)
    max_width = scaled_point((1236, 0), width, height)[0] - bullet_x
    bullets = [
        f"• {data['classification']}",
        f"• {data['threat']}",
        "• Repository correlation active",
        "• Evidence chain synchronized",
    ]
    for rendered, y_ref in zip(bullets, (725, 746, 767, 788)):
        draw.text(
            scaled_point((854, y_ref), width, height),
            ellipsize(draw, rendered, bullet_font, max_width),
            font=bullet_font,
            fill=TEXT,
        )


def draw_operational_brief(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    font = scaled_font(width, height, 9, True)
    x_bullet = scaled_point((1290, 0), width, height)[0]
    x_text = scaled_point((1310, 0), width, height)[0]
    max_width = scaled_point((1682, 0), width, height)[0] - x_text
    line_step = scaled_point((0, 15), width, height)[1]

    entries = [
        (data["assessment"], 625, 2),
        (f"Phase: {data['phase']}", 681, 1),
        (f"Priority review: {data['severity'].title()} / {data['priority'].title()}", 721, 1),
        (f"Next action: {data['next_action']}", 761, 2),
    ]

    for rendered, y_ref, max_lines in entries:
        _, y = scaled_point((0, y_ref), width, height)
        draw.ellipse((x_bullet, y + 3, x_bullet + 5, y + 8), fill=RED)
        for index, line in enumerate(wrap_text(draw, rendered, font, max_width, max_lines)):
            line_y = y + index * line_step
            if line_y < scaled_point((0, 803), width, height)[1]:
                draw.text((x_text, line_y), line, font=font, fill=TEXT)


def draw_lower_panel_borders(
    draw: ImageDraw.ImageDraw, width: int, height: int
) -> None:
    border = (135, 28, 26, 255)
    y = scaled_point((0, 812), width, height)[1]
    for x1_ref, x2_ref in ((10, 465), (474, 826), (834, 1254), (1262, 1690)):
        x1 = scaled_point((x1_ref, 0), width, height)[0]
        x2 = scaled_point((x2_ref, 0), width, height)[0]
        draw.line((x1, y, x2, y), fill=border, width=1)


def draw_footer_time(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    label_font = scaled_font(width, height, 10, True)
    time_font = scaled_font(width, height, 9, True)
    x1, y1, x2, y2 = scaled_box((1348, 834, 1684, 872), width, height)
    center_y = (y1 + y2) // 2
    label_x = scaled_point((1382, 0), width, height)[0]
    time_right_x = scaled_point((1670, 0), width, height)[0]

    draw.text((label_x, center_y), "EASTERN TIME", font=label_font, fill=RED, anchor="lm")
    draw.text((time_right_x, center_y), data["updated_compact"], font=time_font, fill=TEXT, anchor="rm")


def render_frame(
    base_image: Image.Image, data: dict[str, Any], frame_index: int
) -> Image.Image:
    frame = base_image.copy().convert("RGBA")
    width, height = frame.size

    # Glow first so the subsequent live text remains crisp.
    frame = draw_biohazard_glow(frame, frame_index, width, height)
    draw = ImageDraw.Draw(frame, "RGBA")

    cover_dynamic_regions(draw, width, height)
    draw_top_access(draw, width, height, data)
    draw_left_panel(draw, width, height, data)
    draw_center_details(draw, width, height, data)
    draw_procedure_progress(draw, width, height, data, frame_index)
    draw_evidence_package(draw, width, height, data)
    draw_magnifying_glass(draw, width, height, frame_index)
    draw_case_overview(draw, width, height, data)
    draw_map_case_id(draw, width, height, data)
    draw_file_network_motion(draw, width, height, frame_index)
    draw_case_feed(draw, width, height, data, frame_index)
    draw_system_status(draw, width, height, data, frame_index)
    draw_threat_monitor(draw, width, height, data, frame_index)
    draw_operational_brief(draw, width, height, data)
    draw_lower_panel_borders(draw, width, height)
    draw_footer_time(draw, width, height, data)
    return frame


def main() -> None:
    if not BASE_IMAGE_PATH.exists():
        raise FileNotFoundError(f"Missing dashboard base image: {BASE_IMAGE_PATH}")

    base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
    if base_image.size != (REFERENCE_WIDTH, REFERENCE_HEIGHT):
        raise ValueError(
            f"Expected base image {REFERENCE_WIDTH}x{REFERENCE_HEIGHT}, "
            f"received {base_image.width}x{base_image.height}."
        )

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
