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
    # Coordinates are mapped to the current 1672 x 941 base PNG.
    regions = [
        ((1238, 2, 1642, 31), DARK),          # top-right access line
        ((188, 310, 353, 557), DARK),         # left-side live values
        ((552, 184, 741, 376), DARK),         # center-left live values
        ((925, 184, 1110, 376), DARK),        # center-right live values
        ((1282, 91, 1376, 247), DARK),         # Evidence Package values
        ((1224, 316, 1365, 548), DARK),        # Case Overview values
        ((52, 621, 407, 741), DARK_SOFT),      # Active Case Feed plot
        ((17, 767, 422, 808), DARK),           # Active Case Feed sync line
        ((667, 620, 759, 768), DARK),          # System Status values
        ((450, 774, 758, 802), DARK_SOFT),     # System Status waveform
        ((786, 624, 1173, 823), DARK),         # Threat Monitor content
        ((1217, 624, 1601, 815), DARK),        # Operational Brief content
        ((1310, 847, 1627, 896), DARK),        # footer time box interior
    ]
    for box, fill in regions:
        cover(draw, box, width, height, fill)


def draw_top_access(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    font = scaled_font(width, height, 12, True)
    rendered = f"LEVEL {data['access_level']} • CASE ACCESS  |  NODE: {data['node']}"
    x, y = scaled_point((1617, 10), width, height)
    draw.text((x, y), rendered, font=font, fill=RED, anchor="ra")


def draw_biohazard_glow(
    frame: Image.Image, frame_index: int, width: int, height: int
) -> Image.Image:
    """
    Subtle red pulse / sweep for the biohazard logo.
    - no crosshair lines
    - smoother motion
    - slightly smaller / more centered glow region
    - stronger glow across more of the circular diameter
    """
    phase = frame_index * math.tau / FRAME_COUNT

    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    # Slightly adjusted center so the glow reads more centered visually.
    cx, cy = scaled_point((191, 182), width, height)

    # Slightly smaller radii so the full circular feel is more visible.
    outer_r = max(24, scaled_point((112, 0), width, height)[0])
    mid_r = max(20, scaled_point((96, 0), width, height)[0])
    inner_r = max(16, scaled_point((78, 0), width, height)[0])

    ring_width_outer = max(2, round(width / 720))
    ring_width_mid = max(2, round(width / 840))
    ring_width_inner = max(1, round(width / 1100))

    pulse = 0.5 + 0.5 * math.sin(phase * 0.9)

    # Base breathing glow on the ring structure
    draw.ellipse(
        (cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r),
        outline=(255, 56, 52, int(70 + 40 * pulse)),
        width=ring_width_outer,
    )
    draw.ellipse(
        (cx - mid_r, cy - mid_r, cx + mid_r, cy + mid_r),
        outline=(255, 48, 44, int(60 + 34 * pulse)),
        width=ring_width_mid,
    )
    draw.ellipse(
        (cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r),
        outline=(255, 42, 38, int(42 + 28 * pulse)),
        width=ring_width_inner,
    )

    # Soft orbiting highlights so more of the red circular lines glow
    glow_points = []
    for offset in (0.0, 2.10, 4.20):
        angle = phase * 0.60 + offset
        px = cx + int(math.cos(angle) * mid_r)
        py = cy + int(math.sin(angle) * mid_r)
        glow_points.append((px, py))

    for px, py in glow_points:
        spot_r = max(8, round(width / 145))
        draw.ellipse(
            (px - spot_r, py - spot_r, px + spot_r, py + spot_r),
            fill=(255, 62, 58, 52),
        )
        draw.ellipse(
            (px - spot_r // 2, py - spot_r // 2, px + spot_r // 2, py + spot_r // 2),
            fill=(255, 75, 70, 72),
        )

    # One slower diagonal sweep flare
    sweep_angle = phase * 0.45 + 0.6
    sx = cx + int(math.cos(sweep_angle) * (outer_r - 6))
    sy = cy + int(math.sin(sweep_angle) * (outer_r - 6))
    flare_r = max(14, round(width / 100))
    draw.ellipse(
        (sx - flare_r, sy - flare_r, sx + flare_r, sy + flare_r),
        fill=(255, 52, 48, 58),
    )

    glow = overlay.filter(ImageFilter.GaussianBlur(radius=max(10, round(width / 120))))
    return Image.alpha_composite(frame, glow)


def draw_left_panel(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    value_font = scaled_font(width, height, 11, True)
    compact_font = scaled_font(width, height, 9, True)
    status_font = scaled_font(width, height, 9, True)

    x = scaled_point((199, 0), width, height)[0]
    max_width = scaled_point((347, 0), width, height)[0] - x

    rows = [
        (data["case_id"], 320, WHITE, value_font),
        (data["campaign_id"], 351, WHITE, value_font),
        (f"{data['severity']} / {data['priority']}", 413, WHITE, compact_font),
        (data["lead"], 444, WHITE, compact_font),
        (data["updated_date"], 475, TEXT, value_font),
        (data["unit_status"], 506, RED, value_font),
        (data["system_integrity"], 537, WHITE, value_font),
    ]
    for rendered, y_ref, color, font in rows:
        _, y = scaled_point((0, y_ref), width, height)
        draw.text(
            (x, y),
            ellipsize(draw, rendered, font, max_width),
            font=font,
            fill=color,
        )

    _, status_y = scaled_point((0, 382), width, height)
    line_step = scaled_point((0, 12), width, height)[1]
    for index, line in enumerate(
        wrap_text(draw, data["status"].title(), status_font, max_width, 2)
    ):
        draw.text((x, status_y + index * line_step), line, font=status_font, fill=RED)

    bar_x, bar_y = scaled_point((280, 529), width, height)
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
    compact = scaled_font(width, height, 10, True)
    regular = scaled_font(width, height, 11, True)
    line_step = scaled_point((0, 14), width, height)[1]

    left_x = scaled_point((558, 0), width, height)[0]
    left_max = scaled_point((735, 0), width, height)[0] - left_x
    left_rows = [
        (data["classification"], 191, WHITE, 2),
        (data["threat"], 232, WHITE, 2),
        (data["phase"], 274, WHITE, 2),
        (data["status"].title(), 315, RED, 2),
        (data["severity"].title(), 352, WHITE, 1),
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

    right_x = scaled_point((930, 0), width, height)[0]
    right_max = scaled_point((1104, 0), width, height)[0] - right_x
    right_rows = [
        (data["priority"].title(), 191, RED),
        (data["lead"], 232, WHITE),
        (f"{data['evidence']} Records", 274, WHITE),
        (str(data["integrations"]), 315, WHITE),
        (data["updated_compact"], 352, TEXT),
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
    # Remove the four baked-in arrows only, then redraw them from live stage data.
    arrow_boxes = [
        (488, 417, 548, 458),
        (638, 417, 698, 458),
        (788, 417, 848, 458),
        (938, 417, 998, 458),
    ]
    for box in arrow_boxes:
        cover(draw, box, width, height, DARK_SOFT)

    arrows = [
        ((499, 439), (538, 439)),
        ((649, 439), (688, 439)),
        ((799, 439), (838, 439)),
        ((949, 439), (988, 439)),
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
    font = scaled_font(width, height, 9, True)
    x = scaled_point((1290, 0), width, height)[0]
    max_width = scaled_point((1370, 0), width, height)[0] - x

    rows = [
        (data["case_id"], 103),
        (f"{data['evidence']} RECORDS", 143),
        (str(data["integrations"]), 181),
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
        scaled_point((1290, 218), width, height),
        data["updated_date"],
        font=font,
        fill=WHITE,
    )
    draw.text(
        scaled_point((1290, 234), width, height),
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
    x = scaled_point((1230, 0), width, height)[0]
    max_width = scaled_point((1360, 0), width, height)[0] - x
    line_step = scaled_point((0, 13), width, height)[1]

    rows = [
        (data["classification"], 326, WHITE, 2),
        (data["threat"], 368, WHITE, 2),
        (data["status"].title(), 408, RED, 1),
        (data["severity"].title(), 446, WHITE, 1),
        (data["date_opened"], 478, WHITE, 1),
        (data["priority"].title(), 514, RED, 1),
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
    Rebuild the center CASE FILE card in the Case Overview map area
    so it stays red, readable, and centered.
    """
    cx, cy = scaled_point((1492, 427), width, height)

    card_w = max(90, scaled_point((126, 0), width, height)[0])
    card_h = max(82, scaled_point((108, 0), width, height)[1])

    x1 = cx - card_w // 2
    y1 = cy - card_h // 2
    x2 = cx + card_w // 2
    y2 = cy + card_h // 2

    radius = max(6, round(width / 320))

    # Main red card
    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=radius,
        fill=(96, 22, 20, 215),
        outline=RED,
        width=max(2, round(width / 900)),
    )

    # Inner frame
    inset = max(7, round(width / 220))
    draw.rounded_rectangle(
        (x1 + inset, y1 + inset, x2 - inset, y2 - inset),
        radius=max(4, radius - 2),
        outline=(155, 42, 40, 200),
        width=1,
    )

    # Divider lines
    draw.line(
        (x1 + 10, y1 + 26, x2 - 10, y1 + 26),
        fill=(130, 40, 38, 170),
        width=1,
    )
    draw.line(
        (x1 + 10, y2 - 22, x2 - 10, y2 - 22),
        fill=(130, 40, 38, 170),
        width=1,
    )

    id_font = scaled_font(width, height, 8, True)
    title_font = scaled_font(width, height, 13, True)
    sub_font = scaled_font(width, height, 8, True)

    draw.text(
        (cx, y1 + 15),
        data["case_id"],
        font=id_font,
        fill=WHITE,
        anchor="ma",
    )
    draw.text(
        (cx, cy - 2),
        "CASE FILE",
        font=title_font,
        fill=(255, 138, 130, 255),
        anchor="ma",
    )
    draw.text(
        (cx, y2 - 12),
        data["priority"].title(),
        font=sub_font,
        fill=TEXT,
        anchor="ma",
    )


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
    # Exact plot coordinates for the new base PNG.
    x1, y1, x2, y2 = scaled_box((56, 625, 405, 738), width, height)

    for y_ref in (625, 682, 738):
        grid_x1, grid_y = scaled_point((50, y_ref), width, height)
        grid_x2 = scaled_point((407, y_ref), width, height)[0]
        draw.line((grid_x1, grid_y, grid_x2, grid_y), fill=GRID, width=1)

    seed = sum(ord(character) for character in data["case_id"])
    count = 20
    gap = max(3, scaled_point((5, 0), width, height)[0])
    bar_width = max(4, (x2 - x1 - gap * (count - 1)) // count)
    usable_height = max(12, y2 - y1)

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
        draw.rectangle((x, y2 - bar_height, x + bar_width, y2), fill=RED)

    sync_font = scaled_font(width, height, 8, True)
    sync_text = (
        f"FEED SYNC: {data['updated_compact']}  •  FILTER: ALL  •  STREAM: BID-LIVE"
    )
    sync_x, sync_y = scaled_point((22, 775), width, height)
    max_width = scaled_point((414, 0), width, height)[0] - sync_x
    draw.text(
        (sync_x, sync_y),
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
    font = scaled_font(width, height, 10, True)
    confidence = integer(data["system_integrity"].replace("%", "").split(".")[0], 98)
    values = [
        "VERIFIED",
        "STABLE",
        "ONLINE",
        "SECURE" if confidence >= 90 else "REVIEW",
        "ACTIVE",
    ]
    x = scaled_point((680, 0), width, height)[0]
    for rendered, y_ref in zip(values, (628, 659, 690, 721, 752)):
        _, y = scaled_point((0, y_ref), width, height)
        draw.text(
            (x, y),
            rendered,
            font=font,
            fill=BLUE if rendered != "REVIEW" else RED,
        )

    x1, y1, x2, y2 = scaled_box((455, 779, 750, 791), width, height)
    seed = sum(ord(character) for character in data["case_id"]) + 444
    points = []
    for index in range(42):
        ratio = index / 41
        x_point = x1 + ratio * (x2 - x1)
        rng = random.Random(seed + index * 29)
        offset = 4 * math.sin(
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
    body_font = scaled_font(width, height, 12, True)
    bullet_font = scaled_font(width, height, 11, True)

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

    # Bigger / clearer bullet lines
    bullet_x, _ = scaled_point((812, 0), width, height)
    max_width = scaled_point((1178, 0), width, height)[0] - bullet_x

    bullets = [
        f"• {data['classification']}",
        f"• {data['threat']}",
        "• Repository correlation active",
    ]
    line_positions = (776, 806, 836)

    for rendered, y_ref in zip(bullets, line_positions):
        draw.text(
            scaled_point((812, y_ref), width, height),
            ellipsize(draw, rendered, bullet_font, max_width),
            font=bullet_font,
            fill=TEXT,
        )

    # Restore the panel's lower border after clearing the baked-in text.
    border_y = scaled_point((0, 823), width, height)[1]
    border_x1 = scaled_point((779, 0), width, height)[0]
    border_x2 = scaled_point((1178, 0), width, height)[0]
    draw.line((border_x1, border_y, border_x2, border_y), fill=RED_DIM, width=1)


def draw_operational_brief(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    font = scaled_font(width, height, 10, True)
    x_bullet = scaled_point((1216, 0), width, height)[0]
    x_text = scaled_point((1237, 0), width, height)[0]
    max_width = scaled_point((1594, 0), width, height)[0] - x_text

    entries = [
        (data["assessment"], 629, 2),
        (f"Phase: {data['phase']}", 683, 1),
        (f"Priority review: {data['severity'].title()} / {data['priority'].title()}", 721, 1),
        (f"Next action: {data['next_action']}", 757, 2),
    ]
    line_step = scaled_point((0, 16), width, height)[1]
    max_y = scaled_point((0, 804), width, height)[1]

    for rendered, y_ref, max_lines in entries:
        _, y = scaled_point((0, y_ref), width, height)
        draw.ellipse((x_bullet, y + 4, x_bullet + 5, y + 9), fill=RED)
        for index, line in enumerate(
            wrap_text(draw, rendered, font, max_width, max_lines)
        ):
            line_y = y + index * line_step
            if line_y <= max_y:
                draw.text((x_text, line_y), line, font=font, fill=TEXT)


def draw_footer_time(
    draw: ImageDraw.ImageDraw, width: int, height: int, data: dict[str, Any]
) -> None:
    label = "EASTERN TIME"
    timestamp = data["updated_compact"]
    label_font = scaled_font(width, height, 10, True)
    time_font = scaled_font(width, height, 9, True)

    inner_x1 = scaled_point((1328, 0), width, height)[0]
    inner_x2 = scaled_point((1602, 0), width, height)[0]
    y = scaled_point((0, 861), width, height)[1]
    gap = scaled_point((17, 0), width, height)[0]

    label_width = text_width(draw, label, label_font)
    time_width = text_width(draw, timestamp, time_font)
    total_width = label_width + gap + time_width
    available_width = inner_x2 - inner_x1

    if total_width > available_width:
        timestamp = ellipsize(
            draw,
            timestamp,
            time_font,
            max(80, available_width - label_width - gap),
        )
        time_width = text_width(draw, timestamp, time_font)
        total_width = label_width + gap + time_width

    start_x = inner_x1 + max(0, (available_width - total_width) // 2)
    draw.text((start_x, y), label, font=label_font, fill=RED)
    draw.text(
        (start_x + label_width + gap, y),
        timestamp,
        font=time_font,
        fill=TEXT,
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
