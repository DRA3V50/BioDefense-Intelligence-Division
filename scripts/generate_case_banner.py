#!/usr/bin/env python3

import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter


CURRENT_CASE_FILE = Path("data/current_case.json")
OPERATION_FILE = Path("operations/active_operation.json")
OUTPUT_GIF = Path("assets/biodefense-case-scan.gif")

WIDTH = 1800
HEIGHT = 600
FRAMES = 16
FRAME_DURATION_MS = 160

BG = (5, 11, 18)
PANEL = (8, 18, 28, 230)
PANEL_SOFT = (10, 20, 32, 170)
TEXT = (235, 242, 248)
TEXT_SOFT = (168, 182, 198)
BLUE = (52, 142, 245)
BLUE_SOFT = (70, 180, 255)
RED = (232, 70, 86)
RED_SOFT = (255, 104, 118)
CYAN = (44, 219, 208)
LINE = (28, 58, 84)
GRID = (14, 26, 38)
WHITE = (248, 250, 252)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_counts(case_id: str):
    manifest_path = Path("evidence") / case_id / "evidence_manifest.json"
    correlations_path = Path("evidence") / case_id / "evidence_correlations.json"

    evidence_count = 0
    correlation_count = 0

    if manifest_path.exists():
        try:
            manifest = load_json(manifest_path)
            evidence_count = len(manifest.get("evidence_items", []))
        except Exception:
            evidence_count = 0

    if correlations_path.exists():
        try:
            correlations = load_json(correlations_path)
            if isinstance(correlations, dict):
                correlation_count = len(correlations.get("correlations", []))
            elif isinstance(correlations, list):
                correlation_count = len(correlations)
        except Exception:
            correlation_count = 0

    return evidence_count, correlation_count


def get_font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
                "C:/Windows/Fonts/arial.ttf",
            ]
        )

    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue

    return ImageFont.load_default()


FONT_TITLE = get_font(54, bold=True)
FONT_SUBTITLE = get_font(20, bold=False)
FONT_PANEL = get_font(18, bold=True)
FONT_LABEL = get_font(13, bold=True)
FONT_VALUE = get_font(15, bold=False)
FONT_SMALL = get_font(12, bold=False)
FONT_TINY = get_font(10, bold=False)
FONT_SCORE = get_font(62, bold=True)


def draw_text(draw, xy, text, font, fill=TEXT, anchor=None):
    draw.text(xy, str(text), font=font, fill=fill, anchor=anchor)


def truncate(draw, text, font, max_width):
    text = str(text)
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text

    while text:
        candidate = text[:-1] + "..."
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            return candidate
        text = text[:-1]

    return "..."


def wrap_text(draw, text, font, max_width, max_lines=2):
    words = str(text).split()
    if not words:
        return [""]

    lines = []
    current = words[0]

    for word in words[1:]:
        test = f"{current} {word}"
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            lines.append(current)
            current = word

    lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = truncate(draw, lines[-1], font, max_width)

    return lines


def draw_panel(draw, box, title, accent=BLUE):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=16, fill=PANEL, outline=accent, width=2)
    draw.line((x1 + 18, y1 + 44, x2 - 18, y1 + 44), fill=accent, width=2)
    draw_text(draw, (x1 + 18, y1 + 13), title, FONT_PANEL, fill=accent)


def draw_biohazard(draw, cx, cy, r, color):
    inner = int(r * 0.18)
    ring = int(r * 0.56)
    lobe = int(r * 0.34)

    draw.ellipse((cx - inner, cy - inner, cx + inner, cy + inner), outline=color, width=4)

    for angle_deg in (270, 30, 150):
        ang = math.radians(angle_deg)
        lx = cx + math.cos(ang) * ring
        ly = cy + math.sin(ang) * ring
        draw.ellipse(
            (lx - lobe, ly - lobe, lx + lobe, ly + lobe),
            outline=color,
            width=4,
        )
        draw.line((cx, cy, lx, ly), fill=color, width=3)

    outer = int(r * 0.95)
    draw.ellipse((cx - outer, cy - outer, cx + outer, cy + outer), outline=(24, 90, 110), width=2)


def make_texture(base: Image.Image):
    draw = ImageDraw.Draw(base)

    for y in range(0, HEIGHT, 40):
        draw.line((0, y, WIDTH, y), fill=GRID, width=1)

    for x in range(0, WIDTH, 38):
        draw.line((x, 0, x, HEIGHT), fill=GRID, width=1)

    for _ in range(180):
        x1 = random.randint(0, WIDTH)
        y1 = random.randint(0, HEIGHT)
        x2 = x1 + random.randint(20, 120)
        y2 = y1 + random.randint(-2, 2)
        color = (10, 20, 28, random.randint(18, 55))
        draw.line((x1, y1, x2, y2), fill=color, width=1)

    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse((1150, -80, 1500, 270), fill=(70, 100, 140, 18))
    gdraw.ellipse((1320, 250, 1750, 620), fill=(255, 40, 50, 10))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    base.alpha_composite(glow)


def build_background():
    base = Image.new("RGBA", (WIDTH, HEIGHT), BG)
    make_texture(base)
    draw = ImageDraw.Draw(base)

    # top accent bars
    draw.rectangle((0, 0, 540, 5), fill=BLUE)
    draw.rectangle((1260, 0, WIDTH, 5), fill=RED)

    # header strip
    draw.line((40, 105, WIDTH - 40, 105), fill=(34, 62, 88), width=2)

    # side rail
    draw.rounded_rectangle((34, 80, 118, 455), radius=10, fill=PANEL_SOFT, outline=CYAN, width=2)

    # panels
    draw_panel(draw, (1260, 35, 1760, 170), "EVIDENCE PACKAGE", accent=CYAN)
    draw_panel(draw, (1260, 182, 1470, 456), "CASE OVERVIEW", accent=CYAN)
    draw_panel(draw, (1485, 182, 1760, 456), "", accent=CYAN)

    draw_panel(draw, (250, 486, 560, 575), "ACTIVE CASE FEED", accent=CYAN)
    draw_panel(draw, (575, 486, 875, 575), "SYSTEM STATUS", accent=CYAN)
    draw_panel(draw, (890, 486, 1260, 575), "THREAT MONITOR", accent=RED)
    draw_panel(draw, (1260, 486, 1760, 575), "OPERATIONAL BRIEF", accent=CYAN)

    return base


def draw_metric_box(draw, box, label, value, accent):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=10, fill=(9, 18, 29, 220), outline=accent, width=2)
    draw_text(draw, (x1 + 12, y1 + 8), label.upper(), FONT_TINY, fill=TEXT_SOFT)
    draw_text(draw, (x2 - 12, y1 + 28), value, FONT_VALUE, fill=accent, anchor="ra")


def draw_bars(draw, box, values, accent):
    x1, y1, x2, y2 = box
    w = x2 - x1
    h = y2 - y1
    count = len(values)
    gap = 5
    bar_width = max(6, (w - gap * (count - 1)) // count)

    max_val = max(values) if values else 1

    for i, value in enumerate(values):
        bh = int((value / max_val) * (h - 10))
        bx1 = x1 + i * (bar_width + gap)
        bx2 = bx1 + bar_width
        by2 = y2
        by1 = by2 - bh
        draw.rectangle((bx1, by1, bx2, by2), fill=accent)


def draw_sparkline(draw, box, values, accent):
    if len(values) < 2:
        return

    x1, y1, x2, y2 = box
    w = x2 - x1
    h = y2 - y1
    max_v = max(values) or 1
    min_v = min(values)
    span = max(max_v - min_v, 1)

    points = []
    for i, v in enumerate(values):
        px = x1 + (w * i / (len(values) - 1))
        py = y2 - ((v - min_v) / span) * h
        points.append((px, py))

    draw.line(points, fill=accent, width=3)

    for point in points[::3]:
        draw.ellipse((point[0] - 3, point[1] - 3, point[0] + 3, point[1] + 3), fill=accent)


def build_frame(case, operation, frame_index):
    case_id = case.get("case_id", "BID-UNKNOWN")
    seed = sum(ord(ch) for ch in case_id) + frame_index
    random.seed(seed)

    evidence_count, correlation_count = load_counts(case_id)
    if evidence_count == 0:
        evidence_count = int(case.get("evidence_count", 0))
    if correlation_count == 0:
        correlation_count = int(case.get("evidence_count", 0))

    risk_score = int(case.get("risk_score", 0))
    confidence = int(case.get("confidence", 0))
    ioc_count = int(case.get("ioc_count", 0))
    assets = int(case.get("affected_assets", 0))

    threat_score = max(0, min(99, int((risk_score * 0.6) + (confidence * 0.4))))
    updated_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    img = build_background()
    draw = ImageDraw.Draw(img)

    # Title
    draw_text(draw, (44, 22), "BIODEFENSE INTELLIGENCE DIVISION", FONT_SUBTITLE, fill=CYAN)
    draw_text(draw, (320, 22), "// CASE SCAN INTERFACE v2.7.14", FONT_SUBTITLE, fill=TEXT_SOFT)

    draw_text(draw, (250, 120), "BioDefense-Intelligence-Division", FONT_TITLE, fill=WHITE)
    draw_text(draw, (250, 208), "Cyber-Biothreat Intelligence & Evidence Analysis", get_font(28, False), fill=CYAN)

    draw.line((250, 290, 1235, 290), fill=(20, 72, 92), width=2)

    # Procedure strip
    steps = ["CASE SCAN", "EVIDENCE REVIEW", "VALIDATION", "ASSESSMENT", "RECOVERY REVIEW"]
    step_x = [250, 445, 690, 930, 1175]
    active_step = frame_index % len(steps)

    for i, step in enumerate(steps):
        color = CYAN if i != active_step else BLUE_SOFT
        draw_text(draw, (step_x[i], 336), f"• {step}", FONT_SMALL, fill=color)

    # Left biohazard rail
    draw_biohazard(draw, 76, 215, 42, CYAN)
    draw_text(draw, (50, 342), "PORTFOLIO", FONT_LABEL, fill=RED)
    draw_text(draw, (50, 367), "SIMULATION", FONT_LABEL, fill=RED)
    draw_text(draw, (50, 398), "SYNTHETIC CASE DATA", FONT_TINY, fill=TEXT_SOFT)

    # Evidence package
    x = 1280
    draw_text(draw, (x, 90), "CASE ID", FONT_LABEL, fill=TEXT_SOFT)
    draw_text(draw, (x + 105, 90), case_id, FONT_VALUE, fill=TEXT)
    draw_text(draw, (x, 120), "EVIDENCE", FONT_LABEL, fill=TEXT_SOFT)
    draw_text(draw, (x + 105, 120), f"{evidence_count} RECORDS", FONT_VALUE, fill=TEXT)
    draw_text(draw, (x, 150), "INDICATORS", FONT_LABEL, fill=TEXT_SOFT)
    draw_text(draw, (x + 105, 150), str(ioc_count), FONT_VALUE, fill=TEXT)
    draw_text(draw, (x, 180), "UPDATED", FONT_LABEL, fill=TEXT_SOFT)
    draw_text(draw, (x + 105, 180), updated_utc, FONT_VALUE, fill=TEXT)

    # Overview
    box_x = 1280
    max_w = 170
    draw_text(draw, (box_x, 235), "TYPE", FONT_LABEL, fill=TEXT_SOFT)
    draw_text(
        draw,
        (box_x, 255),
        truncate(draw, case.get("classification", "Unknown"), FONT_VALUE, max_w),
        FONT_VALUE,
        fill=TEXT,
    )

    draw_text(draw, (box_x, 292), "THREAT", FONT_LABEL, fill=TEXT_SOFT)
    threat_lines = wrap_text(draw, case.get("threat_family", "Unknown"), FONT_VALUE, max_w, 2)
    for idx, line in enumerate(threat_lines):
        draw_text(draw, (box_x, 312 + idx * 18), line, FONT_VALUE, fill=TEXT)

    draw_text(draw, (box_x, 352), "STATUS", FONT_LABEL, fill=TEXT_SOFT)
    draw_text(
        draw,
        (box_x, 372),
        f"{case.get('severity', 'LOW')} / {case.get('priority', 'ROUTINE')}",
        FONT_VALUE,
        fill=RED_SOFT,
    )

    draw_text(draw, (box_x, 408), "ANALYST", FONT_LABEL, fill=TEXT_SOFT)
    analyst = truncate(draw, case.get("lead_analyst", "Unknown"), FONT_VALUE, max_w)
    draw_text(draw, (box_x, 428), analyst, FONT_VALUE, fill=TEXT)

    draw_text(draw, (box_x, 455), "CONFIDENCE", FONT_LABEL, fill=TEXT_SOFT)
    draw_text(draw, (box_x + 90, 455), f"{confidence}%", FONT_VALUE, fill=CYAN)

    # Right biohazard box
    if frame_index % 2 == 0:
        draw_biohazard(draw, 1625, 320, 58, CYAN)
    else:
        draw_biohazard(draw, 1625, 320, 58, RED_SOFT)

    # Feed bars
    bar_values = [random.randint(8, 48) for _ in range(22)]
    draw_bars(draw, (270, 520, 545, 565), bar_values, CYAN)
    draw_text(draw, (270, 565), f"case-feed://{case_id.lower()}", FONT_TINY, fill=TEXT_SOFT)

    # System status
    draw_text(draw, (595, 518), "• Evidence Integrity:", FONT_VALUE, fill=TEXT_SOFT)
    draw_text(draw, (770, 518), "VERIFIED", FONT_VALUE, fill=CYAN)
    draw_text(draw, (595, 543), "• Data Pipeline:", FONT_VALUE, fill=TEXT_SOFT)
    draw_text(draw, (735, 543), "STABLE", FONT_VALUE, fill=CYAN)
    draw_text(draw, (595, 568), "• Case Record:", FONT_VALUE, fill=TEXT_SOFT)
    draw_text(draw, (705, 568), "CURRENT", FONT_VALUE, fill=CYAN)

    # Threat monitor
    spark = [random.randint(10, 40) for _ in range(18)]
    spark[frame_index % len(spark)] += 18
    draw_text(draw, (910, 518), f"• Threat score: {threat_score}", FONT_VALUE, fill=RED_SOFT)
    level = "LOW" if threat_score < 35 else "ELEVATED" if threat_score < 70 else "HIGH"
    draw_text(draw, (910, 543), f"• Case posture: {level}", FONT_VALUE, fill=TEXT_SOFT)
    draw_sparkline(draw, (905, 548, 1240, 568), spark, RED_SOFT)

    # Operational brief
    campaign = truncate(draw, operation.get("operation", "Unknown Campaign"), FONT_VALUE, 430)
    draw_text(draw, (1280, 520), campaign, FONT_VALUE, fill=TEXT)
    draw_text(
        draw,
        (1280, 544),
        f"{operation.get('campaign_id', 'BDC-0000')}  •  {operation.get('campaign_phase', 'Monitoring')}",
        FONT_SMALL,
        fill=TEXT_SOFT,
    )
    recommended = case.get("recommended_action", "Continue review.")
    brief_lines = wrap_text(draw, recommended, FONT_SMALL, 430, 2)
    for i, line in enumerate(brief_lines):
        draw_text(draw, (1280, 565 + (i * 14)), line, FONT_SMALL, fill=TEXT)

    # Center scan line pulse
    pulse_x = 320 + ((frame_index * 70) % 470)
    draw.line((278, 140, 680, 140), fill=(24, 54, 72), width=4)
    draw.line((278, 140, pulse_x, 140), fill=CYAN, width=4)

    # Footer
    draw_text(
        draw,
        (34, 584),
        "Automated case generation • evidence reconstruction • structured threat analysis",
        FONT_SMALL,
        fill=TEXT_SOFT,
    )

    return img.convert("P", palette=Image.ADAPTIVE)


def main():
    case = load_json(CURRENT_CASE_FILE)
    operation = load_json(OPERATION_FILE)

    if not case:
        raise FileNotFoundError("Missing or empty data/current_case.json")
    if not operation:
        raise FileNotFoundError("Missing or empty operations/active_operation.json")

    OUTPUT_GIF.parent.mkdir(parents=True, exist_ok=True)

    frames = [build_frame(case, operation, i) for i in range(FRAMES)]
    frames[0].save(
        OUTPUT_GIF,
        save_all=True,
        append_images=frames[1:],
        optimize=False,
        duration=FRAME_DURATION_MS,
        loop=0,
        disposal=2,
    )

    print(f"Generated dynamic case banner: {OUTPUT_GIF}")
    print(f"Banner details: {WIDTH}x{HEIGHT}, {FRAMES} frames, case {case.get('case_id', 'UNKNOWN')}.")


if __name__ == "__main__":
    main()
