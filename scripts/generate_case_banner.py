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

REFERENCE_WIDTH = 1672
REFERENCE_HEIGHT = 941

# Keep the original quicker animation pace.
FRAME_COUNT = 18
FRAME_DURATION_MS = 120
EASTERN_TIME = ZoneInfo("America/New_York")

WHITE = (230, 233, 235, 255)
TEXT = (176, 182, 187, 255)
MUTED = (103, 110, 116, 255)
DIM = (72, 78, 84, 255)
RED = (231, 51, 47, 255)
RED_DIM = (132, 35, 34, 255)
RED_GLOW = (255, 76, 70, 90)
BLUE = (66, 124, 208, 255)
DARK = (3, 7, 9, 255)
DARK_SOFT = (3, 7, 9, 238)
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
    # Status is intentionally checked before the broad campaign phase.
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

    return 2


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
            default=value(case, "risk_score", "riskScore", default=0),
        ),
        0,
    )
    confidence = integer(value(case, "confidence", "confidence_score", default=85), 85)
    integrity = max(72.0, min(99.8, 72 + confidence * 0.28))

    case_id = text(value(case, "case_id", "caseId", default="BID-UNKNOWN"))
    campaign_id = text(
        value(operation, "campaign_id", "operation_id", default="BDC-UNKNOWN")
    )
    severity = text(value(case, "severity", default="LOW")).upper()
    priority = text(value(case, "priority", default="ROUTINE")).upper()
    status = text(value(case, "status", "case_status", default="OPEN")).upper()
    phase = text(value(operation, "campaign_phase", "phase", default="Evidence Review"))

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
            value(case, "lead_analyst", "analyst", default="Investigative Analysis Unit")
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
            value(case, "ioc_count", "indicator_count", "indicators", default=0),
            0,
        ),
        "date_opened": text(
            value(
                operation,
                "opened",
                "date_opened",
                default=value(case, "date_opened", "date", default=updated_date),
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
    # Clear only live-data interiors. Preserve the panel frames and footer box.
    regions = [
        ((1210, 4, 1650, 35), DARK),
        ((188, 306, 355, 568), DARK),
        ((542, 188, 721, 389), DARK),
        ((918, 188, 1115, 389), DARK),
        ((1268, 96, 1418, 252), DARK),
        ((1214, 318, 1355, 552), DARK),
        ((1426, 388, 1548, 414), DARK_SOFT),
        ((52, 617, 409, 744), DARK_SOFT),     # chart bars only; retain axes/labels
        ((20, 770, 424, 807), DARK),
        ((672, 625, 775, 813), DARK),
        ((450, 778, 765, 812), DARK_SOFT),    # preserve lower red detail line
        ((786, 621, 1185, 825), DARK_SOFT),   # clear all static footprint text
        ((1200, 621, 1610, 816), DARK),
        ((1334, 864, 1637, 896), DARK),       # footer box interior only
    ]
    for box, fill in regions:
        cover(draw, box, width, height, fill)


def draw_top_access(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    font = scaled_font(width, height, 13, True)
    rendered = f"LEVEL {data['access_level']} • CASE ACCESS  |  NODE: {data['node']}"
    x, y = scaled_point((1628, 14), width, height)
    draw.text((x, y), rendered, font=font, fill=RED, anchor="ra")


def draw_biohazard_glow(
    frame: Image.Image, frame_index: int, width: int, height: int
) -> Image.Image:
    """
    Stronger full-diameter glow for the biohazard area.
    Keeps it subtle/serious, smoother, and more evenly distributed
    across the circular lines without adding weird scan/crosshair behavior.
    """
    phase = frame_index * math.tau / FRAME_COUNT
    pulse = 0.55 + 0.45 * math.sin(phase * 0.85)

    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    # Slightly tightened radius so the circular structure reads more centered
    # and doesn't feel cut off at the edges.
    cx, cy = scaled_point((190, 183), width, height)
    outer_r = max(24, scaled_point((111, 0), width, height)[0])
    mid_r = max(20, scaled_point((96, 0), width, height)[0])
    inner_r = max(16, scaled_point((81, 0), width, height)[0])

    outer_w = max(2, round(width / 540))
    mid_w = max(2, round(width / 760))
    inner_w = max(1, round(width / 980))

    # Soft circular ring breathing
    draw.ellipse(
        (cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r),
        outline=(255, 56, 50, int(82 + 56 * pulse)),
        width=outer_w,
    )
    draw.ellipse(
        (cx - mid_r, cy - mid_r, cx + mid_r, cy + mid_r),
        outline=(255, 52, 47, int(62 + 42 * pulse)),
        width=mid_w,
    )
    draw.ellipse(
        (cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r),
        outline=(255, 48, 44, int(42 + 30 * pulse)),
        width=inner_w,
    )

    # Rotating hot spots around the diameter so more red ring lines glow
    for offset in (0.0, 2.1, 4.2):
        angle = phase * 0.55 + offset
        px = cx + int(math.cos(angle) * mid_r)
        py = cy + int(math.sin(angle) * mid_r)
        glow_r = max(8, round(width / 150))
        draw.ellipse(
            (px - glow_r, py - glow_r, px + glow_r, py + glow_r),
            fill=(255, 62, 56, 58),
        )
        draw.ellipse(
            (
                px - glow_r // 2,
                py - glow_r // 2,
                px + glow_r // 2,
                py + glow_r // 2,
            ),
            fill=(255, 78, 72, 84),
        )

    # Keep a softer flare in the lower-left zone, but smoother than before
    flare_angle = phase * 0.40 + 2.55
    fx = cx + int(math.cos(flare_angle) * (outer_r - 12))
    fy = cy + int(math.sin(flare_angle) * (outer_r - 12))
    flare_r = max(18, round(width / 105))
    draw.ellipse(
        (fx - flare_r, fy - flare_r, fx + flare_r, fy + flare_r),
        fill=(255, 56, 50, 54),
    )

    glow = overlay.filter(ImageFilter.GaussianBlur(radius=max(10, round(width / 118))))
    return Image.alpha_composite(frame, glow)


def draw_left_panel(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    value_font = scaled_font(width, height, 12, True)
    compact_font = scaled_font(width, height, 10, True)
    status_font = scaled_font(width, height, 9, True)

    x = scaled_point((210, 0), width, height)[0]
    max_width = scaled_point((345, 0), width, height)[0] - x

    rows = [
        (data["case_id"], 324, WHITE, value_font),
        (data["campaign_id"], 357, WHITE, value_font),
        (f"{data['severity']} / {data['priority']}", 423, WHITE, compact_font),
        (data["lead"], 456, WHITE, compact_font),
        (data["updated_date"], 489, TEXT, value_font),
        (data["unit_status"], 524, RED, value_font),
        (data["system_integrity"], 557, WHITE, value_font),
    ]
    for rendered, y_ref, color, font in rows:
        _, y = scaled_point((0, y_ref), width, height)
        draw.text(
            (x, y),
            ellipsize(draw, rendered, font, max_width),
            font=font,
            fill=color,
        )

    _, status_y = scaled_point((0, 390), width, height)
    line_step = scaled_point((0, 12), width, height)[1]
    for index, line in enumerate(
        wrap_text(draw, data["status"].title(), status_font, max_width, 2)
    ):
        draw.text((x, status_y + index * line_step), line, font=status_font, fill=RED)

    bar_x, bar_y = scaled_point((284, 548), width, height)
    bar_width = max(3, scaled_point((6, 0), width, height)[0])
    gap = max(2, scaled_point((3, 0), width, height)[0])
    for index, ref_height in enumerate((7, 10, 13, 16, 19)):
        bar_height = scaled_point((0, ref_height), width, height)[1]
        x1 = bar_x + index * (bar_width + gap)
        draw.rectangle(
            (x1, bar_y + 20 - bar_height, x1 + bar_width, bar_y + 20),
            fill=RED,
        )


def draw_center_details(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    compact = scaled_font(width, height, 11, True)
    regular = scaled_font(width, height, 12, True)
    line_step = scaled_point((0, 16), width, height)[1]

    left_x = scaled_point((565, 0), width, height)[0]
    left_max = scaled_point((709, 0), width, height)[0] - left_x
    left_rows = [
        (data["classification"], 206, WHITE, 2),
        (data["threat"], 250, WHITE, 2),
        (data["phase"], 294, WHITE, 2),
        (data["status"].title(), 334, RED, 2),
        (data["severity"].title(), 373, WHITE, 1),
    ]
    for rendered, y_ref, color, max_lines in left_rows:
        _, y = scaled_point((0, y_ref), width, height)
        for line_index, line in enumerate(
            wrap_text(draw, rendered, compact, left_max, max_lines)
        ):
            draw.text(
                (left_x, y + line_index * line_step),
                line,
                font=compact,
                fill=color,
            )

    right_x = scaled_point((932, 0), width, height)[0]
    right_max = scaled_point((1108, 0), width, height)[0] - right_x
    right_rows = [
        (data["priority"].title(), 206, RED),
        (data["lead"], 246, WHITE),
        (f"{data['evidence']} Records", 286, WHITE),
        (str(data["integrations"]), 326, WHITE),
        (data["updated_compact"], 366, TEXT),
    ]
    for rendered, y_ref, color in right_rows:
        _, y = scaled_point((0, y_ref), width, height)
        draw.text(
            (right_x, y),
            ellipsize(draw, rendered, regular, right_max),
            font=regular,
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
        glow_width = line_width + 4
        draw.line((x1, y1, x2 - 9, y2), fill=RED_GLOW, width=glow_width)
        draw.polygon(
            [(x2, y2), (x2 - 14, y2 - 11), (x2 - 14, y2 + 11)],
            fill=RED_GLOW,
        )
    draw.line((x1, y1, x2 - 9, y2), fill=color, width=line_width)
    draw.polygon(
        [(x2, y2), (x2 - 12, y2 - 8), (x2 - 12, y2 + 8)],
        fill=color,
    )


def draw_procedure_progress(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    arrow_boxes = [
        (486, 434, 548, 484),
        (634, 434, 701, 484),
        (785, 434, 852, 484),
        (935, 434, 1006, 484),
    ]
    for box in arrow_boxes:
        cover(draw, box, width, height, DARK_SOFT)

    arrows = [
        ((498, 459), (538, 459)),
        ((646, 459), (690, 459)),
        ((797, 459), (840, 459)),
        ((948, 459), (995, 459)),
    ]

    current_stage = stage_index(data["status"], data["phase"])
    current_arrow = max(0, current_stage - 1)
    normal_width = max(2, round(width / 850))
    current_width = normal_width + 3

    for index, (start_ref, end_ref) in enumerate(arrows):
        start = scaled_point(start_ref, width, height)
        end = scaled_point(end_ref, width, height)
        if index < current_arrow:
            draw_arrow(draw, start, end, BLUE, normal_width)
        elif index == current_arrow:
            pulse = 0.6 + 0.4 * math.sin(frame_index * 0.8)
            color = (round(185 + 25 * pulse), 45, 43, 255)
            draw_arrow(draw, start, end, color, current_width, glow=True)
        else:
            draw_arrow(draw, start, end, DIM, normal_width)


def draw_evidence_package(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    font = scaled_font(width, height, 10, True)
    x = scaled_point((1294, 0), width, height)[0]
    max_width = scaled_point((1414, 0), width, height)[0] - x

    rows = [
        (data["case_id"], 113),
        (f"{data['evidence']} RECORDS", 151),
        (str(data["integrations"]), 190),
    ]
    for rendered, y_ref in rows:
        _, y = scaled_point((0, y_ref), width, height)
        draw.text(
            (x, y),
            ellipsize(draw, rendered, font, max_width),
            font=font,
            fill=WHITE,
        )

    draw.text(
        scaled_point((1294, 226), width, height),
        data["updated_date"],
        font=font,
        fill=WHITE,
    )
    draw.text(
        scaled_point((1294, 242), width, height),
        data["updated_time"],
        font=font,
        fill=TEXT,
    )


def draw_magnifying_glass(
    draw: ImageDraw.ImageDraw, width: int, height: int, frame_index: int
) -> None:
    # Original quicker pacing and smooth orbit.
    center_x = 1507 + 50 * math.cos(frame_index * math.tau / FRAME_COUNT)
    center_y = 165 + 40 * math.sin(frame_index * math.tau / FRAME_COUNT * 1.4)
    x, y = scaled_point((round(center_x), round(center_y)), width, height)
    radius = max(8, scaled_point((12, 0), width, height)[0])
    line_width = max(2, round(width / 900))
    draw.ellipse(
        (x - radius, y - radius, x + radius, y + radius),
        outline=(235, 235, 235, 220),
        width=line_width,
    )
    angle = frame_index * math.tau / FRAME_COUNT
    handle = max(10, scaled_point((17, 0), width, height)[0])
    start_x = x + int(math.cos(angle) * (radius - 2))
    start_y = y + int(math.sin(angle) * (radius - 2))
    end_x = x + int(math.cos(angle) * (radius + handle))
    end_y = y + int(math.sin(angle) * (radius + handle))
    draw.line(
        (start_x, start_y, end_x, end_y), fill=RED, width=line_width + 1
    )
    draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=RED)


def draw_case_overview(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    font = scaled_font(width, height, 9, True)
    x = scaled_point((1240, 0), width, height)[0]
    max_width = scaled_point((1368, 0), width, height)[0] - x
    line_step = scaled_point((0, 14), width, height)[1]

    rows = [
        (data["classification"], 342, WHITE, 2),
        (data["threat"], 383, WHITE, 2),
        (data["status"].title(), 425, RED, 1),
        (data["severity"].title(), 462, WHITE, 1),
        (data["date_opened"], 499, WHITE, 1),
        (data["priority"].title(), 536, RED, 1),
    ]
    for rendered, y_ref, color, max_lines in rows:
        _, y = scaled_point((0, y_ref), width, height)
        for line_index, line in enumerate(
            wrap_text(draw, rendered, font, max_width, max_lines)
        ):
            draw.text(
                (x, y + line_index * line_step),
                line,
                font=font,
                fill=color,
            )


def draw_map_case_id(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    """
    Put the dynamic case ID in its own small tag above the center card,
    instead of drawing it in the middle of the CASE FILE folder/card.
    """
    font = scaled_font(width, height, 8, True)

    # Small tag placed above the center red CASE FILE block
    x1, y1, x2, y2 = scaled_box((1454, 387, 1532, 406), width, height)

    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=max(3, round(width / 1000)),
        fill=(65, 16, 16, 210),
        outline=(130, 36, 34, 220),
        width=1,
    )

    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    draw.text((cx, cy), data["case_id"], font=font, fill=WHITE, anchor="mm")


def draw_file_network_motion(
    draw: ImageDraw.ImageDraw, width: int, height: int, frame_index: int
) -> None:
    nodes = [
        (1448, 347),
        (1542, 347),
        (1406, 407),
        (1591, 407),
        (1460, 465),
        (1568, 467),
        (1508, 523),
    ]
    active_node = frame_index % len(nodes)
    for index, node_ref in enumerate(nodes):
        x, y = scaled_point(node_ref, width, height)
        if index == active_node:
            radius = 5 + round(2 * (0.5 + 0.5 * math.sin(frame_index * 0.8)))
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                outline=RED,
                width=2,
            )
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
    # Match the dense original graph: 31 red bars from -60 through NOW.
    x1, y1, x2, y2 = scaled_box((55, 624, 403, 743), width, height)

    for y_ref in (624, 683, 743):
        x_start, y = scaled_point((49, y_ref), width, height)
        x_end = scaled_point((405, y_ref), width, height)[0]
        draw.line((x_start, y, x_end, y), fill=GRID, width=1)

    seed = sum(ord(character) for character in data["case_id"])
    count = 31
    bar_width = max(4, scaled_point((6, 0), width, height)[0])
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

    sync_font = scaled_font(width, height, 9, True)
    sync_text = (
        f"FEED SYNC: {data['updated_compact']}  •  FILTER: ALL  •  STREAM: BID-LIVE"
    )
    x, y = scaled_point((29, 795), width, height)
    max_width = scaled_point((415, 0), width, height)[0] - x
    draw.text(
        (x, y),
        ellipsize(draw, sync_text, sync_font, max_width),
        font=sync_font,
        fill=TEXT,
    )


def draw_system_status(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    font = scaled_font(width, height, 11, True)
    confidence = integer(data["system_integrity"].replace("%", "").split(".")[0], 98)
    values = [
        "VERIFIED",
        "STABLE",
        "ONLINE",
        "SECURE" if confidence >= 90 else "REVIEW",
        "ACTIVE",
    ]
    x = scaled_point((690, 0), width, height)[0]
    for rendered, y_ref in zip(values, (646, 676, 706, 736, 766)):
        _, y = scaled_point((0, y_ref), width, height)
        draw.text(
            (x, y),
            rendered,
            font=font,
            fill=BLUE if rendered != "REVIEW" else RED,
        )

    x1, y1, x2, y2 = scaled_box((462, 790, 758, 812), width, height)
    seed = sum(ord(character) for character in data["case_id"]) + 444
    points = []
    for index in range(42):
        ratio = index / 41
        x_point = x1 + ratio * (x2 - x1)
        rng = random.Random(seed + index * 29)
        offset = 5 * math.sin(
            frame_index * 0.33 + index * 0.52 + rng.uniform(0, math.tau)
        )
        points.append((x_point, (y1 + y2) / 2 + offset))
    draw.line(points, fill=BLUE, width=1)


def draw_threat_monitor(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    score_font = scaled_font(width, height, 34, True)
    body_font = scaled_font(width, height, 11, True)
    bullet_font = scaled_font(width, height, 10, True)

    draw.text(
        scaled_point((808, 653), width, height),
        f"{data['score']:03d}",
        font=score_font,
        fill=RED,
    )
    draw.text(
        scaled_point((810, 706), width, height),
        data["score_level"],
        font=body_font,
        fill=WHITE,
    )
    draw.text(
        scaled_point((810, 744), width, height),
        "CURRENT FOOTPRINT",
        font=body_font,
        fill=TEXT,
    )

    # waveform
    x1, y1, x2, y2 = scaled_box((910, 648, 1182, 730), width, height)
    seed = sum(ord(character) for character in data["case_id"]) + 700
    points = []
    for index in range(48):
        rng = random.Random(seed + index * 71)
        ratio = index / 47
        x_point = x1 + ratio * (x2 - x1)
        center = (y1 + y2) / 2
        offset = 13 * math.sin(
            frame_index * 0.48 + index * 0.43 + rng.uniform(0, math.tau)
        )
        offset += 7 * math.sin(
            frame_index * 0.21 + index * 0.17 + rng.uniform(0, math.tau)
        )
        points.append((x_point, max(y1 + 4, min(y2 - 4, center + offset))))
    draw.line(points, fill=RED, width=max(2, round(width / 900)))

    # FIX: keep footprint bullet lines inside the Threat Monitor box only
    bullet_x, _ = scaled_point((808, 0), width, height)
    max_width = scaled_point((1172, 0), width, height)[0] - bullet_x

    bullets = [
        f"• {data['classification']}",
        f"• {data['threat']}",
        "• Repository correlation active",
        "• Evidence chain synchronized",
    ]
    line_positions = (778, 806, 834, 862)

    for rendered, y_ref in zip(bullets, line_positions):
        draw.text(
            scaled_point((808, y_ref), width, height),
            ellipsize(draw, rendered, bullet_font, max_width),
            font=bullet_font,
            fill=TEXT,
        )


def draw_operational_brief(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    font = scaled_font(width, height, 11, True)
    x_bullet = scaled_point((1232, 0), width, height)[0]
    x_text = scaled_point((1253, 0), width, height)[0]
    max_width = scaled_point((1594, 0), width, height)[0] - x_text

    entries = [
        (data["assessment"], 646, 2),
        (f"Phase: {data['phase']}", 697, 1),
        (f"Priority review: {data['severity'].title()} / {data['priority'].title()}", 733, 1),
        (f"Next action: {data['next_action']}", 769, 2),
    ]
    line_step = scaled_point((0, 16), width, height)[1]
    max_y = scaled_point((0, 806), width, height)[1]

    for rendered, y_ref, max_lines in entries:
        _, y = scaled_point((0, y_ref), width, height)
        draw.ellipse((x_bullet, y + 4, x_bullet + 5, y + 9), fill=RED)
        for index, line in enumerate(
            wrap_text(draw, rendered, font, max_width, max_lines)
        ):
            line_y = y + index * line_step
            if line_y <= max_y:
                draw.text((x_text, line_y), line, font=font, fill=TEXT)


def draw_lower_panel_detail_lines(
    draw: ImageDraw.ImageDraw, width: int, height: int
) -> None:
    # Restore the subtle lower red detail lines erased by the live-data clears.
    line_color = (92, 24, 24, 210)
    for x1_ref, x2_ref in ((440, 765), (781, 1185)):
        x1, y = scaled_point((x1_ref, 824), width, height)
        x2 = scaled_point((x2_ref, 0), width, height)[0]
        draw.line((x1, y, x2, y), fill=line_color, width=1)


def draw_footer_time(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    label_font = scaled_font(width, height, 11, True)
    time_font = scaled_font(width, height, 10, True)

    x1, y1, x2, y2 = scaled_box((1332, 863, 1639, 897), width, height)
    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=max(2, round(width / 900)),
        outline=(105, 29, 28, 255),
        width=1,
    )

    center_y = (y1 + y2) // 2
    label_x = scaled_point((1358, 0), width, height)[0]
    time_right_x = scaled_point((1614, 0), width, height)[0]

    draw.text(
        (label_x, center_y),
        "EASTERN TIME",
        font=label_font,
        fill=RED,
        anchor="lm",
    )
    draw.text(
        (time_right_x, center_y),
        data["updated_compact"],
        font=time_font,
        fill=TEXT,
        anchor="rm",
    )


def render_frame(
    base_image: Image.Image, data: dict[str, Any], frame_index: int
) -> Image.Image:
    frame = base_image.copy().convert("RGBA")
    width, height = frame.size
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
    draw_lower_panel_detail_lines(draw, width, height)
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
