#!/usr/bin/env python3

import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


CURRENT_CASE_FILE = Path("data/current_case.json")
ACTIVE_OPERATION_FILE = Path("operations/active_operation.json")
BASE_IMAGE_FILE = Path("assets/biodefense-dashboard-base.png")
OUTPUT_GIF_FILE = Path("assets/biodefense-case-scan.gif")

WIDTH = 2048
HEIGHT = 620
FRAME_COUNT = 16
FRAME_DURATION_MS = 120

BG = (3, 9, 12, 255)
PANEL_FILL = (4, 14, 18, 220)
PANEL_FILL_SOFT = (2, 10, 14, 175)
CYAN = (22, 211, 216, 255)
CYAN_SOFT = (18, 150, 155, 255)
BLUE = (41, 153, 255, 255)
RED = (255, 72, 84, 255)
WHITE = (235, 241, 245, 255)
MUTED = (130, 145, 160, 255)
MUTED_2 = (90, 110, 125, 255)
LINE = (24, 88, 92, 255)
LINE_SOFT = (18, 54, 58, 255)
BLACK_FADE = (0, 0, 0, 85)


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")

    return data


def safe_text(value, fallback="N/A") -> str:
    if value is None:
        return fallback

    text = str(value).strip()
    return text if text else fallback


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = []

    if bold:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
                "/Library/Fonts/Arial Bold.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
                "/Library/Fonts/Arial.ttf",
                "C:/Windows/Fonts/arial.ttf",
            ]
        )

    mono_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationMono-Regular.ttf",
        "C:/Windows/Fonts/consola.ttf",
    ]

    for path in candidates + mono_candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue

    return ImageFont.load_default()


def text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def ellipsize(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    if text_width(draw, text, font) <= max_width:
        return text

    trimmed = text
    while trimmed:
        candidate = trimmed.rstrip() + "..."
        if text_width(draw, candidate, font) <= max_width:
            return candidate
        trimmed = trimmed[:-1]

    return "..."


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
    max_lines: int = 2,
):
    words = text.split()
    if not words:
        return [""]

    lines = []
    current = words[0]

    for word in words[1:]:
        candidate = f"{current} {word}"
        if text_width(draw, candidate, font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word

    lines.append(current)

    if len(lines) <= max_lines:
        return lines

    lines = lines[:max_lines]
    lines[-1] = ellipsize(draw, lines[-1], font, max_width)
    return lines


def draw_panel(draw: ImageDraw.ImageDraw, box, title: str, title_color=CYAN):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(
        box,
        radius=10,
        fill=PANEL_FILL,
        outline=LINE,
        width=2,
    )
    draw.text(
        (x1 + 18, y1 + 14),
        title,
        font=load_font(16, bold=True),
        fill=title_color,
    )
    draw.line((x1 + 16, y1 + 42, x2 - 16, y1 + 42), fill=title_color, width=2)


def draw_biohazard(draw: ImageDraw.ImageDraw, center, size: int, color):
    cx, cy = center
    r = size

    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(0, 95, 100, 255), width=2)

    inner_r = int(r * 0.18)
    draw.ellipse(
        (cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r),
        outline=color,
        width=4,
    )

    lobe_r = int(r * 0.33)
    orbit = int(r * 0.42)

    for angle_deg in (270, 30, 150):
        angle = math.radians(angle_deg)
        lx = cx + int(math.cos(angle) * orbit)
        ly = cy + int(math.sin(angle) * orbit)

        draw.ellipse(
            (lx - lobe_r, ly - lobe_r, lx + lobe_r, ly + lobe_r),
            outline=color,
            width=4,
        )
        draw.line((cx, cy, lx, ly), fill=color, width=3)

    spoke_r = int(r * 0.63)
    for angle_deg in (90, 210, 330):
        angle = math.radians(angle_deg)
        px = cx + int(math.cos(angle) * spoke_r)
        py = cy + int(math.sin(angle) * spoke_r)
        draw.line((cx, cy, px, py), fill=(0, 70, 72, 255), width=2)


def draw_shield(draw: ImageDraw.ImageDraw, box, color):
    x1, y1, x2, y2 = box
    cx = (x1 + x2) // 2
    top = y1 + 24
    bottom = y2 - 24
    width = (x2 - x1) * 0.26

    points = [
        (cx, top),
        (cx + width, top + 28),
        (cx + width * 0.78, bottom - 40),
        (cx, bottom),
        (cx - width * 0.78, bottom - 40),
        (cx - width, top + 28),
    ]
    draw.polygon(points, outline=color, width=4)

    draw.line((cx - 18, top + 64, cx + 18, top + 64), fill=color, width=3)
    draw.line((cx - 14, top + 90, cx + 14, top + 90), fill=color, width=3)
    draw.line((cx - 10, top + 116, cx + 10, top + 116), fill=color, width=3)


def draw_data_bars(draw: ImageDraw.ImageDraw, box, frame_index: int, seed: int):
    x1, y1, x2, y2 = box
    width = x2 - x1
    height = y2 - y1

    count = 20
    bar_w = max(8, width // (count * 2))
    gap = bar_w // 2

    for i in range(count):
        rng = random.Random(seed + (frame_index * 73) + (i * 97))
        phase = (i * 0.55) + rng.random() * 1.4
        wave = math.sin((frame_index * 0.55) + phase)
        noise = rng.randint(-10, 14)

        bar_h = int((height * 0.18) + ((wave + 1) / 2) * height * 0.52 + noise)
        bar_h = max(10, min(height - 6, bar_h))

        x = x1 + 18 + i * (bar_w + gap)
        draw.rectangle((x, y2 - bar_h, x + bar_w, y2), fill=CYAN)


def draw_wave_line(draw: ImageDraw.ImageDraw, box, frame_index: int, seed: int, color):
    x1, y1, x2, y2 = box
    width = x2 - x1
    mid_y = y1 + (y2 - y1) // 2

    points = []
    segments = 26
    for i in range(segments + 1):
        ratio = i / segments
        x = x1 + int(ratio * width)

        rng = random.Random(seed + i * 43)
        base_phase = rng.random() * 2.8
        amplitude = 10 + rng.randint(0, 18)

        y = int(
            mid_y
            + math.sin((frame_index * 0.6) + (i * 0.55) + base_phase) * amplitude
            + math.cos((frame_index * 0.33) + (i * 0.25)) * 6
        )
        points.append((x, y))

    if len(points) > 1:
        draw.line(points, fill=color, width=2)


def current_procedure_index(case_status: str, campaign_phase: str) -> int:
    status = case_status.lower()
    phase = campaign_phase.lower()

    if "open" in status or "detection" in phase:
        return 0
    if "evidence" in status or "collection" in phase:
        return 1
    if "field" in status or "correlation" in phase or "analysis" in status:
        return 2
    if "containment" in status or "containment" in phase:
        return 3
    if "recovery" in phase or "monitoring" in status:
        return 4

    return 2


def draw_procedure_strip(draw: ImageDraw.ImageDraw, y: int, active_index: int):
    steps = [
        "COLLECTION",
        "CORRELATION",
        "VALIDATION",
        "ASSESSMENT",
        "RECOVERY REVIEW",
    ]
    x = 292

    for index, step in enumerate(steps):
        fill = CYAN if index == active_index else MUTED_2
        marker = "◆" if index == active_index else "•"
        draw.text(
            (x, y),
            f"{marker}  {step}",
            font=load_font(14, bold=False),
            fill=fill,
        )
        x += 260 if index < 4 else 0


def build_background() -> Image.Image:
    if BASE_IMAGE_FILE.exists():
        base = Image.open(BASE_IMAGE_FILE).convert("RGBA").resize((WIDTH, HEIGHT))
    else:
        base = Image.new("RGBA", (WIDTH, HEIGHT), BG)

    dark_layer = Image.new("RGBA", base.size, BLACK_FADE)
    return Image.alpha_composite(base, dark_layer)


def compose_frame(case: dict, operation: dict, frame_index: int) -> Image.Image:
    image = build_background()
    draw = ImageDraw.Draw(image)

    title_font = load_font(90, bold=True)
    subtitle_font = load_font(36, bold=False)
    small_header_font = load_font(13, bold=False)
    body_font = load_font(17, bold=False)
    body_bold_font = load_font(17, bold=True)
    mono_font = load_font(15, bold=False)
    tiny_font = load_font(12, bold=False)

    case_id = safe_text(case.get("case_id"))
    classification = safe_text(case.get("classification"))
    threat_family = safe_text(case.get("threat_family"))
    severity = safe_text(case.get("severity"))
    priority = safe_text(case.get("priority"))
    confidence = safe_text(case.get("confidence"))
    affected_assets = safe_text(case.get("affected_assets"))
    risk_score = int(case.get("risk_score", 0))
    evidence_count = safe_text(case.get("evidence_count", 0))
    ioc_count = safe_text(case.get("ioc_count", 0))
    analyst = safe_text(case.get("lead_analyst"))
    status = safe_text(case.get("status"))
    initial_access = safe_text(case.get("initial_access"))
    platform = safe_text(case.get("affected_platform"))
    vendor = safe_text(case.get("vendor"))
    device = safe_text(case.get("device_family"))
    zone = safe_text(case.get("network_zone"))
    assessment = safe_text(case.get("assessment"))
    operation_name = safe_text(operation.get("operation"))
    campaign_id = safe_text(operation.get("campaign_id"))
    designation = safe_text(operation.get("threat_designation", "BMSI-01"))
    campaign_phase = safe_text(operation.get("campaign_phase", "Operational Recovery"))
    containment_level = safe_text(operation.get("containment_level", "HIGH"))
    next_objective = safe_text(operation.get("next_objective"))
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    seed = sum(ord(ch) for ch in case_id)

    # Header
    draw.text(
        (44, 20),
        "BIODEFENSE INTELLIGENCE DIVISION",
        font=small_header_font,
        fill=CYAN,
    )
    draw.text(
        (382, 20),
        "// CASE SCAN INTERFACE v2.7.14",
        font=small_header_font,
        fill=MUTED,
    )

    # Left badge area
    draw.rounded_rectangle(
        (26, 76, 228, 532),
        radius=10,
        fill=PANEL_FILL_SOFT,
        outline=LINE,
        width=2,
    )
    draw.text((70, 122), "BIODEFENSE ANALYSIS", font=tiny_font, fill=CYAN)
    draw_biohazard(draw, (126, 238), 58, CYAN)
    draw.text((48, 360), "PORTFOLIO SIMULATION", font=load_font(16, bold=True), fill=RED)
    draw.text((68, 392), "SYNTHETIC CASE DATA", font=load_font(13), fill=MUTED)

    # Main title
    draw.text(
        (282, 178),
        "BioDefense-Intelligence-Division",
        font=title_font,
        fill=WHITE,
    )
    draw.text(
        (284, 286),
        "Cyber-Biothreat Intelligence & Evidence Analysis",
        font=subtitle_font,
        fill=CYAN_SOFT,
    )

    # Case scan header line and animated scan segment
    draw.text((280, 118), "✦  CASE SCAN", font=load_font(15, bold=True), fill=CYAN_SOFT)
    draw.line((302, 166, 760, 166), fill=LINE, width=6)
    sweep_start = 350 + ((frame_index * 28) % 250)
    draw.line((sweep_start, 166, sweep_start + 85, 166), fill=CYAN, width=6)

    # Main separators
    draw.line((280, 362, 1514, 362), fill=LINE, width=2)
    draw_procedure_strip(
        draw,
        400,
        current_procedure_index(status, campaign_phase),
    )

    # Top-right evidence package
    evidence_box = (1532, 30, 2010, 228)
    draw_panel(draw, evidence_box, "EVIDENCE PACKAGE", title_color=WHITE)

    row_label_font = load_font(15, bold=False)
    row_value_font = load_font(17, bold=False)

    rows = [
        ("CASE ID", case_id),
        ("EVIDENCE", f"{evidence_count} RECORDS"),
        ("INDICATORS", f"{ioc_count}"),
        ("UPDATED", updated),
    ]
    row_y = 88
    for label, value in rows:
        draw.text((1560, row_y), label, font=row_label_font, fill=MUTED)
        draw.text(
            (1670, row_y),
            ellipsize(draw, value, row_value_font, 300),
            font=row_value_font,
            fill=WHITE,
        )
        row_y += 38

    draw.text(
        (1560, 182),
        "SOURCE RECORD: PORTFOLIO SIMULATION",
        font=load_font(12, bold=False),
        fill=RED,
    )

    # Right middle case overview
    overview_box = (1532, 248, 1756, 500)
    draw_panel(draw, overview_box, "CASE OVERVIEW", title_color=CYAN)

    overview_x = 1560
    overview_y = 286
    overview_fields = [
        ("TYPE", classification),
        ("THREAT", threat_family),
        ("STATUS", f"{severity} / {priority}"),
        ("ANALYST", analyst),
        ("CONFIDENCE", f"{confidence}%"),
    ]

    for label, value in overview_fields:
        draw.text((overview_x, overview_y), label, font=load_font(14), fill=MUTED)
        lines = wrap_text(draw, value, load_font(15), 170, max_lines=2)
        line_y = overview_y + 16
        for line in lines:
            draw.text((overview_x, line_y), line, font=load_font(15), fill=WHITE)
            line_y += 17
        overview_y += 44

    # Right icon / switch box
    icon_box = (1782, 248, 2010, 500)
    draw.rounded_rectangle(
        icon_box,
        radius=10,
        fill=PANEL_FILL_SOFT,
        outline=LINE,
        width=2,
    )

    # Alternate right-side symbol each frame cycle
    if frame_index % 2 == 0:
        draw_biohazard(draw, (1896, 368), 64, CYAN_SOFT)
    else:
        draw_shield(draw, (1836, 282, 1958, 440), CYAN_SOFT)

    # Animated scan bar on far right
    bar_top = 268 + ((frame_index * 14) % 170)
    draw.rectangle((1978, 266, 1988, 480), fill=(8, 34, 36, 255))
    draw.rectangle((1978, bar_top, 1988, min(bar_top + 80, 480)), fill=CYAN)

    # Bottom-right operational brief
    brief_box = (1532, 518, 2010, 604)
    draw_panel(draw, brief_box, "OPERATIONAL BRIEF", title_color=CYAN_SOFT)

    draw.text(
        (1560, 548),
        ellipsize(draw, operation_name, body_bold_font, 420),
        font=body_bold_font,
        fill=WHITE,
    )
    draw.text(
        (1560, 572),
        ellipsize(
            draw,
            f"{campaign_id}  •  {designation}  •  {campaign_phase}",
            mono_font,
            430,
        ),
        font=mono_font,
        fill=MUTED,
    )
    objective_lines = wrap_text(draw, next_objective, load_font(14), 438, max_lines=2)
    y = 592
    for line in objective_lines[:1]:
        draw.text((1560, y), line, font=load_font(14), fill=WHITE)

    # Bottom left active case feed
    feed_box = (260, 476, 646, 604)
    draw_panel(draw, feed_box, "ACTIVE CASE FEED", title_color=CYAN)
    draw_data_bars(draw, (280, 498, 620, 578), frame_index, seed)
    draw.text(
        (280, 582),
        f"case-feed://{case_id.lower()}",
        font=load_font(12),
        fill=MUTED,
    )

    # Bottom center system status
    status_box = (668, 476, 1102, 604)
    draw_panel(draw, status_box, "SYSTEM STATUS", title_color=CYAN_SOFT)

    status_lines = [
        ("Evidence Integrity", "VERIFIED"),
        ("Data Pipeline", "STABLE"),
        ("Case Record", "CURRENT"),
        ("Initial Access", initial_access),
    ]
    line_y = 506
    for label, value in status_lines:
        draw.text((690, line_y), f"• {label}:", font=load_font(15), fill=MUTED)
        draw.text(
            (870, line_y),
            ellipsize(draw, value, load_font(15, bold=True), 200),
            font=load_font(15, bold=True),
            fill=CYAN if label != "Initial Access" else WHITE,
        )
        line_y += 24

    # Bottom threat monitor
    threat_box = (1124, 476, 1512, 604)
    draw_panel(draw, threat_box, "THREAT MONITOR", title_color=RED)

    threat_level = "CRITICAL" if risk_score >= 85 else "HIGH" if risk_score >= 65 else "ELEVATED" if risk_score >= 40 else "GUARDED"
    monitor_lines = [
        f"Threat score: {risk_score} ({threat_level})",
        f"Containment posture: {containment_level}",
        f"Zone: {zone}",
    ]

    monitor_y = 508
    for line in monitor_lines:
        draw.text((1148, monitor_y), f"• {line}", font=load_font(15), fill=WHITE if "Threat score" not in line else RED)
        monitor_y += 24

    draw_wave_line(draw, (1146, 556, 1492, 590), frame_index, seed, RED)

    # Small dynamic details line
    details_line = (
        f"{platform} • {vendor} • {device} • "
        f"{confidence}% confidence • {affected_assets} assets"
    )
    draw.text(
        (282, 440),
        ellipsize(draw, details_line, load_font(16), 1220),
        font=load_font(16),
        fill=WHITE,
    )

    # Bottom footer line
    draw.line((34, 546, 2012, 546), fill=LINE_SOFT, width=1)
    draw.text(
        (58, 570),
        "Automated case generation • evidence reconstruction • structured threat analysis",
        font=load_font(14),
        fill=MUTED,
    )

    # Slight pulse dot
    pulse_radius = 7 + int(2 * math.sin(frame_index * 0.8))
    draw.ellipse(
        (
            1478 - pulse_radius,
            500 - pulse_radius,
            1478 + pulse_radius,
            500 + pulse_radius,
        ),
        fill=RED,
        outline=WHITE,
    )

    return image


def main():
    case = load_json(CURRENT_CASE_FILE)
    operation = load_json(ACTIVE_OPERATION_FILE)

    frames = []
    for frame_index in range(FRAME_COUNT):
        frame = compose_frame(case, operation, frame_index)
        frames.append(frame.convert("P", palette=Image.ADAPTIVE))

    OUTPUT_GIF_FILE.parent.mkdir(parents=True, exist_ok=True)

    frames[0].save(
        OUTPUT_GIF_FILE,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=False,
        disposal=2,
    )

    print(f"Generated dynamic case banner: {OUTPUT_GIF_FILE}")
    print(
        f"Banner details: {WIDTH}x{HEIGHT}, "
        f"{FRAME_COUNT} frames, case {case.get('case_id', 'UNKNOWN')}."
    )


if __name__ == "__main__":
    main()
