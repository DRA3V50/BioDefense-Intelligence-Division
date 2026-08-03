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

REFERENCE_WIDTH = 1672
REFERENCE_HEIGHT = 941

FRAME_COUNT = 18
FRAME_DURATION_MS = 120

WHITE = (229, 233, 236, 255)
TEXT = (178, 183, 189, 255)
MUTED = (105, 112, 118, 255)
RED = (233, 55, 49, 255)
BLUE = (70, 125, 220, 255)
COVER = (3, 6, 9, 240)
COVER_SOFT = (3, 6, 9, 210)


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
            node = root.find(f".//{name}")
            if node is not None and node.text:
                output[key] = node.text.strip()
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


def text(v: Any, default: str = "N/A") -> str:
    if v is None:
        return default
    rendered = str(v).strip()
    return rendered or default


def integer(v: Any, default: int = 0) -> int:
    try:
        return int(float(str(v).strip()))
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
    x, y = point
    return round(x * sx), round(y * sy)


def scaled_box(
    box: tuple[int, int, int, int], image_width: int, image_height: int
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    p1 = scaled_point((x1, y1), image_width, image_height)
    p2 = scaled_point((x2, y2), image_width, image_height)
    return p1[0], p1[1], p2[0], p2[1]


def scaled_font(
    image_width: int, image_height: int, size: int, bold: bool = False
) -> ImageFont.ImageFont:
    scale = min(image_width / REFERENCE_WIDTH, image_height / REFERENCE_HEIGHT)
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
    return "LOW"


def stage_index(status: str, phase: str) -> int:
    combined = f"{status} {phase}".lower()

    if any(word in combined for word in ("scan", "open", "detection", "intake")):
        return 0
    if any(
        word in combined
        for word in ("evidence", "collect", "correlation", "field coordination")
    ):
        return 1
    if any(word in combined for word in ("valid", "review", "investigation", "forensic")):
        return 2
    if any(word in combined for word in ("assess", "analysis", "monitor")):
        return 3
    if any(word in combined for word in ("contain", "recover", "recovery", "close")):
        return 4

    return 2


def build_live_data() -> dict[str, Any]:
    case = load_json(CURRENT_CASE_PATH)
    operation = load_json(ACTIVE_OPERATION_PATH)
    score_report = load_json(CSHARP_JSON_PATH)
    if not score_report:
        score_report = load_xml(CSHARP_XML_PATH)

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
        value(case, "confidence", "confidence_score", default=85), 85
    )
    integrity = max(72.0, min(99.8, 72 + confidence * 0.28))

    return {
        "case_id": text(value(case, "case_id", "caseId", default="BID-UNKNOWN")),
        "campaign_id": text(
            value(operation, "campaign_id", "operation_id", default="BDC-UNKNOWN")
        ),
        "campaign": text(
            value(operation, "operation", "campaign", default="Active Investigation Campaign")
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
            value(case, "threat_family", "threat", default="Research-Linked Activity")
        ),
        "status": text(value(case, "status", "case_status", default="Open")).upper(),
        "severity": text(value(case, "severity", default="LOW")).upper(),
        "priority": text(value(case, "priority", default="ROUTINE")).upper(),
        "lead": text(
            value(case, "lead_analyst", "analyst", default="Investigative Analysis Unit")
        ),
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "unit_status": "ACTIVE"
        if text(value(case, "status", default="Open")).upper()
        not in {"CLOSED", "ARCHIVED"}
        else "STANDBY",
        "system_integrity": f"{integrity:.1f}%",
        "evidence": integer(
            value(
                score_report,
                "evidenceRecords",
                "evidence_records",
                default=value(case, "evidence_count", default=0),
            ),
            0,
        ),
        "integrations": integer(
            value(case, "ioc_count", "indicator_count", "indicators", default=0), 0
        ),
        "date_opened": text(
            value(
                operation,
                "opened",
                default=value(
                    case,
                    "date",
                    default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                ),
            )
        ),
        "score": score,
        "score_level": text(
            value(
                score_report,
                "overallLevel",
                "overall_level",
                default=threat_level(score),
            )
        ).upper(),
        "phase": text(
            value(operation, "campaign_phase", "phase", default="Evidence Review")
        ),
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
                default="Repository synchronized. Review current evidence package and continue investigative validation.",
            )
        ),
    }


def cover_dynamic_regions(
    draw: ImageDraw.ImageDraw, image_width: int, image_height: int
) -> None:
    regions = [
        ((162, 384, 316, 640), COVER),       # left value column only
        ((1244, 133, 1422, 266), COVER),     # evidence package values
        ((1244, 370, 1358, 592), COVER),     # case overview values
        ((380, 301, 1044, 382), COVER_SOFT), # center summary text
        ((34, 731, 398, 781), COVER_SOFT),   # case feed bars
        ((720, 692, 784, 838), COVER),       # system status values
        ((843, 720, 1193, 834), COVER_SOFT), # threat monitor values
        ((1270, 694, 1587, 837), COVER),     # operational brief body
        ((1530, 889, 1637, 920), COVER),     # footer utc
    ]

    for box, fill in regions:
        draw.rectangle(scaled_box(box, image_width, image_height), fill=fill)


def draw_left_panel(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    value_font = scaled_font(image_width, image_height, 13, True)
    small_font = scaled_font(image_width, image_height, 12, True)

    x = scaled_point((177, 0), image_width, image_height)[0]
    max_width = scaled_point((309, 0), image_width, image_height)[0] - x

    rows = [
        (data["case_id"], 392, WHITE),
        (data["campaign_id"], 425, WHITE),
        (data["status"], 457, RED),
        (
            f"{data['severity']} / {data['priority']}",
            490,
            BLUE if data["severity"] == "LOW" else WHITE,
        ),
        (data["lead"], 523, WHITE),
        ("DAILY REPOSITORY SYNC", 556, TEXT),
        (data["unit_status"], 602, RED),
    ]

    for rendered, y_ref, color in rows:
        _, y = scaled_point((0, y_ref), image_width, image_height)
        draw.text(
            (x, y),
            ellipsize(draw, rendered, value_font, max_width),
            font=value_font,
            fill=color,
        )

    draw.text(
        scaled_point((194, 634), image_width, image_height),
        data["system_integrity"],
        font=small_font,
        fill=WHITE,
    )

    bar_x, bar_y = scaled_point((247, 635), image_width, image_height)
    bar_width = max(3, scaled_point((5, 0), image_width, image_height)[0])
    gap = max(2, scaled_point((3, 0), image_width, image_height)[0])
    heights = [8, 11, 14, 16, 18]

    for index, height_ref in enumerate(heights):
        height = scaled_point((0, height_ref), image_width, image_height)[1]
        color = RED if index >= 1 else BLUE
        draw.rectangle(
            (
                bar_x + index * (bar_width + gap),
                bar_y + 18 - height,
                bar_x + index * (bar_width + gap) + bar_width,
                bar_y + 18,
            ),
            fill=color,
        )


def draw_center_summary(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    heading_font = scaled_font(image_width, image_height, 17, True)
    text_font = scaled_font(image_width, image_height, 13)
    meta_font = scaled_font(image_width, image_height, 11)

    x = scaled_point((385, 0), image_width, image_height)[0]
    max_width = scaled_point((1010, 0), image_width, image_height)[0] - x

    heading_lines = wrap_text(
        draw, data["classification"].upper(), heading_font, max_width, 1
    )
    draw.text(
        scaled_point((385, 304), image_width, image_height),
        heading_lines[0],
        font=heading_font,
        fill=RED,
    )

    threat_lines = wrap_text(
        draw, data["threat"].upper(), text_font, max_width, 2
    )
    for index, line in enumerate(threat_lines):
        y = 334 + index * 22
        draw.text(
            scaled_point((385, y), image_width, image_height),
            line,
            font=text_font,
            fill=TEXT,
        )

    meta = f"CASE {data['case_id']}  //  {data['phase']}"
    draw.text(
        scaled_point((385, 370), image_width, image_height),
        ellipsize(draw, meta, meta_font, max_width),
        font=meta_font,
        fill=MUTED,
    )


def draw_stage_indicator(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    centers = [(405, 456), (560, 456), (714, 456), (868, 456), (995, 456)]
    index = stage_index(data["status"], data["phase"])
    cx, cy = scaled_point(centers[index], image_width, image_height)

    radius = max(20, scaled_point((39, 0), image_width, image_height)[0])
    pulse = max(2, scaled_point((4, 0), image_width, image_height)[0])
    extra = round(pulse * (0.5 + 0.5 * math.sin(frame_index * 0.65)))

    draw.ellipse(
        (
            cx - radius - extra,
            cy - radius - extra,
            cx + radius + extra,
            cy + radius + extra,
        ),
        outline=RED,
        width=max(2, round(image_width / 900)),
    )
    draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=RED)


def draw_evidence_package(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    font = scaled_font(image_width, image_height, 13, True)
    x = scaled_point((1248, 0), image_width, image_height)[0]
    max_width = scaled_point((1418, 0), image_width, image_height)[0] - x

    values = [
        (data["case_id"], 149),
        (f"{data['evidence']} RECORDS", 186),
        (str(data["integrations"]), 223),
        (data["updated"], 260),
    ]

    for rendered, y_ref in values:
        _, y = scaled_point((0, y_ref), image_width, image_height)
        draw.text(
            (x, y),
            ellipsize(draw, rendered, font, max_width),
            font=font,
            fill=WHITE,
        )


def draw_case_overview(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    font = scaled_font(image_width, image_height, 12, True)
    x = scaled_point((1248, 0), image_width, image_height)[0]
    max_width = scaled_point((1355, 0), image_width, image_height)[0] - x

    values = [
        (data["classification"], 372, WHITE),
        (data["threat"], 410, TEXT),
        (data["status"].title(), 448, RED),
        (data["severity"].title(), 486, WHITE),
        (data["date_opened"], 524, TEXT),
        (data["priority"], 562, RED),
    ]

    for rendered, y_ref, color in values:
        _, y = scaled_point((0, y_ref), image_width, image_height)
        draw.text(
            (x, y),
            ellipsize(draw, rendered, font, max_width),
            font=font,
            fill=color,
        )


def draw_case_feed(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    x1, y1, x2, y2 = scaled_box((34, 731, 398, 781), image_width, image_height)
    seed = sum(ord(character) for character in data["case_id"])
    count = 28
    gap = max(2, scaled_point((4, 0), image_width, image_height)[0])
    bar_width = max(3, (x2 - x1 - gap * (count - 1)) // count)
    usable_height = y2 - y1

    for index in range(count):
        rng = random.Random(seed + index * 131)
        phase_one = rng.uniform(0, math.tau)
        phase_two = rng.uniform(0, math.tau)
        speed = rng.uniform(0.35, 0.95)

        level = (
            0.48
            + 0.26 * math.sin(frame_index * speed + phase_one)
            + 0.18 * math.sin(frame_index * 0.41 + phase_two)
        )
        level = max(0.08, min(0.98, level))
        bar_height = max(4, round(usable_height * level))
        x = x1 + index * (bar_width + gap)
        color = RED if index >= count - 2 else (WHITE if index % 3 == 0 else TEXT)

        draw.rectangle((x, y2 - bar_height, x + bar_width, y2), fill=color)


def draw_system_status(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
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

    x = scaled_point((721, 0), image_width, image_height)[0]
    for value_text, y_ref in zip(values, [700, 737, 774, 811, 848]):
        _, y = scaled_point((0, y_ref), image_width, image_height)
        draw.text((x, y), value_text, font=font, fill=WHITE)


def draw_threat_monitor(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
    frame_index: int,
) -> None:
    score_font = scaled_font(image_width, image_height, 34, True)
    body_font = scaled_font(image_width, image_height, 12)

    draw.text(
        scaled_point((842, 724), image_width, image_height),
        f"{data['score']:03d}",
        font=score_font,
        fill=RED,
    )
    draw.text(
        scaled_point((844, 785), image_width, image_height),
        data["score_level"],
        font=body_font,
        fill=WHITE,
    )
    draw.text(
        scaled_point((844, 816), image_width, image_height),
        "CURRENT",
        font=body_font,
        fill=TEXT,
    )
    draw.text(
        scaled_point((844, 846), image_width, image_height),
        "FOOTPRINT",
        font=body_font,
        fill=TEXT,
    )

    x1, y1, x2, y2 = scaled_box((965, 731, 1187, 783), image_width, image_height)
    base_seed = sum(ord(character) for character in data["case_id"]) + 700
    points = []

    for index in range(30):
        rng = random.Random(base_seed + index * 67)
        ratio = index / 29
        x = x1 + ratio * (x2 - x1)
        y_center = (y1 + y2) / 2
        offset = 0.0
        offset += 10 * math.sin(
            frame_index * 0.54 + index * 0.46 + rng.uniform(0, math.tau)
        )
        offset += 6 * math.sin(
            frame_index * 0.23 + index * 0.17 + rng.uniform(0, math.tau)
        )
        y = max(y1 + 4, min(y2 - 4, y_center + offset))
        points.append((x, y))

    draw.line(points, fill=RED, width=max(2, round(image_width / 900)))
    for px, py in points[::4]:
        draw.ellipse((px - 2, py - 2, px + 2, py + 2), fill=RED)


def draw_operational_brief(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    bullet_font = scaled_font(image_width, image_height, 11)
    body_font = scaled_font(image_width, image_height, 12)

    x_bullet = scaled_point((1272, 0), image_width, image_height)[0]
    x_text = scaled_point((1290, 0), image_width, image_height)[0]
    max_width = scaled_point((1588, 0), image_width, image_height)[0] - x_text

    bullets = [
        data["assessment"],
        f"Phase: {data['phase']}",
        f"Priority review cycle: {data['severity'].title()} ({data['threat']})",
        f"Next action: {data['next_action']}",
    ]

    for bullet, y_ref in zip(bullets, [706, 742, 778, 814]):
        _, y = scaled_point((0, y_ref), image_width, image_height)
        draw.ellipse((x_bullet, y + 5, x_bullet + 5, y + 10), fill=RED)
        lines = wrap_text(draw, bullet, body_font, max_width, 1)
        draw.text(
            (x_text, y),
            lines[0],
            font=body_font,
            fill=WHITE if y_ref == 706 else TEXT,
        )


def draw_footer_clock(
    draw: ImageDraw.ImageDraw,
    image_width: int,
    image_height: int,
    data: dict[str, Any],
) -> None:
    font = scaled_font(image_width, image_height, 11)
    clock_time = data["updated"].split()[1] if len(data["updated"].split()) > 1 else "00:00"
    draw.text(
        scaled_point((1530, 891), image_width, image_height),
        f"UTC {clock_time}",
        font=font,
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
    draw_left_panel(draw, width, height, data)
    draw_center_summary(draw, width, height, data)
    draw_stage_indicator(draw, width, height, data, frame_index)
    draw_evidence_package(draw, width, height, data)
    draw_case_overview(draw, width, height, data)
    draw_case_feed(draw, width, height, data, frame_index)
    draw_system_status(draw, width, height, data)
    draw_threat_monitor(draw, width, height, data, frame_index)
    draw_operational_brief(draw, width, height, data)
    draw_footer_clock(draw, width, height, data)

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
