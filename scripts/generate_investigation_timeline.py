#!/usr/bin/env python3

"""
Generate a chronological timeline for the active investigation.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


CURRENT_CASE = Path("data/current_case.json")
ACTIVE_OPERATION = Path("operations/active_operation.json")
OUTPUT_FILE = Path("operations/investigation_timeline.md")


def load_json(path):
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def format_time(timestamp):
    return timestamp.strftime("%Y-%m-%d %H:%M UTC")


def main():
    case = load_json(CURRENT_CASE)
    operation = load_json(ACTIVE_OPERATION)

    now = datetime.now(timezone.utc)

    events = [
        (
            now - timedelta(hours=6),
            "Initial Detection",
            (
                f"Potential activity associated with "
                f"{case.get('threat_family', 'an unidentified threat')} "
                f"was detected."
            ),
        ),
        (
            now - timedelta(hours=5),
            "Case Opened",
            (
                f"Investigation {case.get('case_id', 'Unknown')} was opened "
                f"and assigned to {case.get('lead_analyst', 'an analyst team')}."
            ),
        ),
        (
            now - timedelta(hours=4),
            "Initial Access Reviewed",
            (
                f"Analysts identified the suspected initial access vector as "
                f"{case.get('initial_access', 'Unknown')}."
            ),
        ),
        (
            now - timedelta(hours=3),
            "Evidence Collection",
            (
                f"{case.get('evidence_count', 0)} evidence items and "
                f"{case.get('ioc_count', 0)} indicators were associated "
                f"with the active investigation."
            ),
        ),
        (
            now - timedelta(hours=2),
            "Containment Assessment",
            (
                f"Containment was assessed at "
                f"{operation.get('containment_level', 'Unknown')}."
            ),
        ),
        (
            now - timedelta(hours=1),
            "Operational Review",
            case.get(
                "assessment",
                "Analysts reviewed the available evidence and intelligence.",
            ),
        ),
        (
            now,
            "Current Priority",
            case.get(
                "recommended_action",
                "Continue investigation and review available evidence.",
            ),
        ),
    ]

    timeline_rows = []

    for timestamp, event, description in events:
        timeline_rows.append(
            f"| {format_time(timestamp)} | {event} | {description} |"
        )

    report = f"""# Investigation Timeline

**Operation:** {operation.get("operation", "Unknown")}

**Case ID:** {case.get("case_id", "Unknown")}

**Generated:** {format_time(now)}

---

| Timestamp | Event | Description |
|---|---|---|
{chr(10).join(timeline_rows)}

---

## Current Status

**Severity:** {case.get("severity", "Unknown")}

**Priority:** {case.get("priority", "Unknown")}

**Confidence:** {case.get("confidence", "Unknown")}%

**Campaign Phase:** {operation.get("campaign_phase", "Unknown")}

**Containment Level:** {operation.get("containment_level", "Unknown")}

---

End of Investigation Timeline
"""

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(report, encoding="utf-8")

    print("Investigation timeline generated.")


if __name__ == "__main__":
    main()
