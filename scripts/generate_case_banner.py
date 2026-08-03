#!/usr/bin/env python3

"""
generate_case_banner.py

Creates an animated GIF banner for the README using the current
BioDefense investigation data.

Reads:
    data/current_case.json
    operations/active_operation.json
    reports/bioterror_threat_score_csharp.json   (optional)
    assets/biodefense-dashboard-base.png         (optional)

Writes:
    assets/biodefense-case-scan.gif

Notes:
- If the base PNG does not exist, this script generates its own
  dashboard-style background automatically.
- The GIF is animated, but the case data only refreshes whenever the
  GitHub Actions workflow runs.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# ============================================================
# Paths
# ============================================================

CURRENT_CASE_FILE = Path("data/current_case.json")
OPERATION_FILE = Path("operations/active_operation.json")
THREAT_SCORE_FILE = Path("reports/bioterror_threat_score_csharp.json")

ASSETS_DIR = Path("assets")
BASE_IMAGE_FILE = ASSETS_DIR / "biodefense-dashboard-base.png"
OUTPUT_GIF_FILE = ASSETS_DIR / "biodefense-case-scan.gif"


# ============================================================
# Helpers
# ============================================================

def load_json_file(path: Path) -> dict:
    """Load a JSON object from disk."""
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")

    return data


def load_optional_json_file(path: Path) -> dict:
    """Load a JSON object if present, otherwise return an empty dict."""
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_font(size: int, bold: bool = False):
    """
    Try to load a nicer TrueType font. If unavailable, fall back to
    the default Pillow bitmap font.
    """
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",

        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",

        "C:/Windows/Fonts/arialbd.ttf"
        if bold else
        "C:/Windows/Fonts/arial.ttf",
    ]

    for candidate in font_candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue

    return ImageFont.load_default()


def safe_text(value, default="N/A") -> str:
    """Convert a value to a safe string."""
    if value is None:
        return default

    text = str(value).strip()
    return text if text else default


def safe_int(value, default=0) -> int:
    """Convert a value to int safely."""
    try:
        return int(value)
    except Exception:
        return default


def utc_now_string() -> str:
    """Return current UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def draw_text(draw, xy, text, font, fill, anchor=None):
    """Small wrapper for text drawing."""
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def draw_box(draw, xy, outline, fill=None, width=2, radius=10):
    """Draw rounded rectangle."""
    draw.rounded_rectangle(xy, radius=radius, outline=outline, fill=fill, width=width)


# ============================================================
# Base dashboard creation
# ============================================================

def create_fallback_base_image(width: int = 1280, height: int = 720) -> Image.Image:
    """
    Create a clean dark dashboard background if no base image exists.
    """
    image = Image.new("RGBA", (width, height), (8, 12, 18, 255))
    draw = ImageDraw.Draw(image)

    # Color palette
    bg_panel = (16, 24, 34, 255)
    line = (60, 160, 120, 255)
    soft_line = (36, 72, 58, 255)
    text_main = (220, 232, 226, 255)
    text_dim = (140, 166, 156, 255)
    accent = (78, 220, 170, 255)
    amber = (210, 180, 90, 255)

    title_font = get_font(34, bold=True)
    heading_font = get_font(18, bold=True)
    body_font = get_font(16, bold=False)
    small_font = get_font(13, bold=False)

    # Subtle grid
    for x in range(0, width, 40):
        draw.line([(x, 0), (x, height)], fill=(16, 28, 24, 255), width=1)
    for y in range(0, height, 40):
        draw.line([(0, y), (width, y)], fill=(16, 28, 24, 255), width=1)

    # Header
    draw_box(draw, (20, 20, width - 20, 90), outline=line, fill=bg_panel, width=2, radius=12)
    draw_text(draw, (40, 33), "BioDefense Intelligence Division", title_font, text_main)
    draw_text(draw, (42, 66), "Active Case Monitoring Interface", body_font, text_dim)

    # Left large panel
    draw_box(draw, (20, 110, 615, 690), outline=line, fill=bg_panel, width=2, radius=12)
    draw_text(draw, (35, 125), "ACTIVE CASE", heading_font, accent)

    # Right top
    draw_box(draw, (640, 110, 1260, 285), outline=line, fill=bg_panel, width=2, radius=12)
    draw_text(draw, (655, 125), "CAMPAIGN STATUS", heading_font, accent)

    # Right middle
    draw_box(draw, (640, 305, 1260, 500), outline=line, fill=bg_panel, width=2, radius=12)
    draw_text(draw, (655, 320), "THREAT SCORE", heading_font, amber)

    # Right bottom
    draw_box(draw, (640, 520, 1260, 690), outline=line, fill=bg_panel, width=2, radius=12)
    draw_text(draw, (655, 535), "EVIDENCE SUMMARY", heading_font, accent)

    # Decorative horizontal separators in left panel
    for y in [165, 240, 315, 390, 465, 540, 615]:
        draw.line([(35, y), (600, y)], fill=soft_line, width=1)

    # Decorative bars / widgets
    for i in range(10):
        x0 = 665 + i * 55
        y1 = 470
        bar_height = 25 + (i * 8) % 90
        draw.rectangle((x0, y1 - bar_height, x0 + 26, y1), fill=(42, 130, 102, 255))

    # Small waveform strip
    base_y = 660
    points = []
    for x in range(660, 1240, 18):
        offset = ((x // 18) % 5) * 5
        y = base_y - offset
        points.append((x, y))
    draw.line(points, fill=accent, width=2)

    # Footer micro text
    draw_text(draw, (40, 700 - 20), "Automated analytical display • synthetic defensive data", small_font, text_dim)

    return image


# ============================================================
# Content extraction
# ============================================================

def build_display_data(case: dict, operation: dict, threat_score: dict) -> dict:
    """Collect the main fields used by the animated banner."""

    assessment = threat_score.get("assessment", {})
    evidence_basis = threat_score.get("evidenceBasis", {})

    overall_score = safe_int(
        assessment.get("overallScore", case.get("risk_score", 0)),
        safe_int(case.get("risk_score", 0), 0),
    )

    overall_level = safe_text(
        assessment.get("overallLevel", case.get("severity", "UNKNOWN")),
        safe_text(case.get("severity", "UNKNOWN")),
    )

    evidence_records = safe_int(
        evidence_basis.get("evidenceRecords", case.get("evidence_count", 0)),
        safe_int(case.get("evidence_count", 0), 0),
    )

    indicator_records = safe_int(
        case.get("ioc_count", operation.get("ioc_count", 0)),
        safe_int(operation.get("ioc_count", 0), 0),
    )

    return {
        "campaign_id": safe_text(operation.get("campaign_id")),
        "operation": safe_text(operation.get("operation")),
        "designation": safe_text(operation.get("threat_designation")),
        "phase": safe_text(operation.get("campaign_phase")),
        "containment": safe_text(operation.get("containment_level")),
        "intrusions": safe_int(operation.get("confirmed_intrusions", 0)),
        "case_id": safe_text(case.get("case_id")),
        "classification": safe_text(case.get("classification")),
        "threat_family": safe_text(case.get("threat_family")),
        "severity": safe_text(case.get("severity")),
        "priority": safe_text(case.get("priority")),
        "platform": safe_text(case.get("affected_platform")),
        "vendor": safe_text(case.get("vendor")),
        "device": safe_text(case.get("device_family")),
        "zone": safe_text(case.get("network_zone")),
        "lead": safe_text(case.get("lead_analyst")),
        "initial_access": safe_text(case.get("initial_access")),
        "confidence": f"{safe_int(case.get('confidence', 0))}%",
        "assets": safe_int(case.get("affected_assets", 0)),
        "evidence": evidence_records,
        "indicators": indicator_records,
        "risk_score": safe_int(case.get("risk_score", 0)),
        "overall_score": overall_score,
        "overall_level": overall_level,
        "updated": utc_now_string(),
    }


# ============================================================
# Rendering
# ============================================================

def severity_color(severity: str):
    """Return color by severity."""
    severity = severity.upper()

    if severity == "CRITICAL":
        return (220, 72, 72, 255)
    if severity == "HIGH":
        return (245, 160, 64, 255)
    if severity == "MODERATE":
        return (220, 200, 80, 255)
    return (78, 220, 170, 255)


def draw_dashboard_content(base: Image.Image, data: dict, frame_index: int, frame_count: int) -> Image.Image:
    """Draw one animation frame."""
    image = base.copy()
    draw = ImageDraw.Draw(image, "RGBA")

    title_font = get_font(30, bold=True)
    label_font = get_font(16, bold=True)
    body_font = get_font(17, bold=False)
    body_bold_font = get_font(18, bold=True)
    small_font = get_font(13, bold=False)
    huge_font = get_font(62, bold=True)

    text_main = (232, 240, 235, 255)
    text_dim = (145, 172, 162, 255)
    accent = (78, 220, 170, 255)
    white = (245, 248, 246, 255)
    soft_fill = (20, 42, 34, 170)
    score_color = severity_color(data["overall_level"])

    # --------------------------------------------------------
    # Left panel content
    # --------------------------------------------------------
    x = 40
    y = 155

    def left_row(label, value, row_y):
        draw_text(draw, (x, row_y), label, label_font, text_dim)
        draw_text(draw, (x + 170, row_y), value, body_font, text_main)

    left_row("Case ID", data["case_id"], y)
    left_row("Classification", data["classification"], y + 40)
    left_row("Threat Family", data["threat_family"], y + 80)
    left_row("Severity", data["severity"], y + 120)
    left_row("Priority", data["priority"], y + 160)
    left_row("Platform", data["platform"], y + 200)
    left_row("Vendor", data["vendor"], y + 240)
    left_row("Device", data["device"], y + 280)
    left_row("Zone", data["zone"], y + 320)
    left_row("Lead Analyst", data["lead"], y + 360)
    left_row("Initial Access", data["initial_access"], y + 400)
    left_row("Confidence", data["confidence"], y + 440)
    left_row("Affected Assets", str(data["assets"]), y + 480)

    # status pill
    pill_color = severity_color(data["severity"])
    draw.rounded_rectangle((390, 273, 575, 305), radius=12, fill=(pill_color[0], pill_color[1], pill_color[2], 60), outline=pill_color, width=2)
    draw_text(draw, (482, 289), f"{data['severity']} / {data['priority']}", small_font, white, anchor="mm")

    # --------------------------------------------------------
    # Campaign panel
    # --------------------------------------------------------
    draw_text(draw, (660, 155), "Campaign ID", label_font, text_dim)
    draw_text(draw, (780, 155), data["campaign_id"], body_font, white)

    draw_text(draw, (660, 185), "Campaign", label_font, text_dim)
    draw_text(draw, (780, 185), data["operation"], body_font, text_main)

    draw_text(draw, (660, 215), "Designation", label_font, text_dim)
    draw_text(draw, (780, 215), data["designation"], body_font, text_main)

    draw_text(draw, (660, 245), "Phase", label_font, text_dim)
    draw_text(draw, (780, 245), data["phase"], body_font, text_main)

    draw_text(draw, (980, 155), "Containment", label_font, text_dim)
    draw_text(draw, (1110, 155), data["containment"], body_bold_font, accent)

    draw_text(draw, (980, 190), "Intrusions", label_font, text_dim)
    draw_text(draw, (1110, 190), str(data["intrusions"]), body_bold_font, white)

    # Blinking activity indicator
    blink_on = frame_index % 2 == 0
    blink_color = (255, 82, 82, 255) if blink_on else (80, 40, 40, 255)
    draw.ellipse((1158, 235, 1178, 255), fill=blink_color, outline=(255, 120, 120, 255))
    draw_text(draw, (1186, 245), "ACTIVE TRACKING", small_font, text_dim)

    # --------------------------------------------------------
    # Threat score panel
    # --------------------------------------------------------
    draw_text(draw, (675, 355), str(data["overall_score"]), huge_font, score_color)
    draw_text(draw, (675, 425), f"Overall Level: {data['overall_level']}", body_bold_font, white)
    draw_text(draw, (675, 455), f"Case Risk Score: {data['risk_score']}", body_font, text_dim)

    # simple pulse box
    pulse_alpha = 45 + int((frame_index / max(frame_count - 1, 1)) * 90)
    draw.rounded_rectangle(
        (950, 350, 1210, 445),
        radius=14,
        outline=score_color,
        fill=(score_color[0], score_color[1], score_color[2], pulse_alpha),
        width=2,
    )
    draw_text(draw, (1080, 378), "THREAT SCORING ENGINE", small_font, white, anchor="mm")
    draw_text(draw, (1080, 408), "C# ANALYTICAL OUTPUT", small_font, text_dim, anchor="mm")

    # --------------------------------------------------------
    # Evidence panel
    # --------------------------------------------------------
    draw_text(draw, (660, 565), "Evidence Records", label_font, text_dim)
    draw_text(draw, (860, 565), str(data["evidence"]), body_bold_font, white)

    draw_text(draw, (660, 595), "Indicators", label_font, text_dim)
    draw_text(draw, (860, 595), str(data["indicators"]), body_bold_font, white)

    draw_text(draw, (660, 625), "Updated", label_font, text_dim)
    draw_text(draw, (860, 625), data["updated"], body_font, text_main)

    # --------------------------------------------------------
    # Animated scan line
    # --------------------------------------------------------
    height = image.height
    width = image.width

    scan_y = int(115 + ((height - 170) * frame_index / max(frame_count - 1, 1)))
    draw.rectangle((24, scan_y, width - 24, scan_y + 3), fill=(90, 255, 190, 80))
    draw.rectangle((24, scan_y - 8, width - 24, scan_y + 8), fill=(90, 255, 190, 25))

    # Animated tiny waveform pulse
    pulse_x = 665 + (frame_index * 20)
    if pulse_x > 1235:
        pulse_x = 665
    draw.rectangle((pulse_x, 648, pulse_x + 8, 672), fill=(255, 255, 255, 180))

    # Footer signature
    draw.rectangle((20, 690, 1260, 716), fill=(0, 0, 0, 100))
    draw_text(
        draw,
        (38, 696),
        "BioDefense Intelligence Division • Daily automated case scan",
        small_font,
        (145, 172, 162, 255),
    )

    return image


# ============================================================
# Main
# ============================================================

def main() -> None:
    case = load_json_file(CURRENT_CASE_FILE)
    operation = load_json_file(OPERATION_FILE)
    threat_score = load_optional_json_file(THREAT_SCORE_FILE)

    data = build_display_data(case, operation, threat_score)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    if BASE_IMAGE_FILE.exists():
        base_image = Image.open(BASE_IMAGE_FILE).convert("RGBA")
    else:
        base_image = create_fallback_base_image()

    frames = []
    frame_count = 12

    for index in range(frame_count):
        frame = draw_dashboard_content(base_image, data, index, frame_count)
        frames.append(frame.convert("P", palette=Image.ADAPTIVE))

    frames[0].save(
        OUTPUT_GIF_FILE,
        save_all=True,
        append_images=frames[1:],
        optimize=False,
        duration=120,
        loop=0,
        disposal=2,
    )

    print(f"Generated animated banner: {OUTPUT_GIF_FILE}")


if __name__ == "__main__":
    main()
