#!/usr/bin/env python3

"""
update_operation.py

Advance the qualitative state of the active BioDefense campaign.

This script does NOT increment cumulative case, evidence, IOC, facility,
or intrusion totals. Those values are recalculated from
data/investigation_history.csv by recalculate_campaign_metrics.py.

The JSON key named "operation" is preserved for compatibility, but its
value is now a restrained campaign title rather than a cinematic
operation codename.
"""

import json
import random
from datetime import date
from pathlib import Path

CASE_FILE = Path("data/current_case.json")
OPERATION_FILE = Path("operations/active_operation.json")

CAMPAIGN_TITLE = "Coordinated Biomedical Systems Intrusion"
DEFAULT_THREAT_DESIGNATION = "BMSI-01"

LEGACY_DESIGNATIONS = {
    "NEMESIS-12",
    "BIOCELL-01",
}


def load_json(path: Path) -> dict:
    """Load a JSON object and fail clearly if it is unavailable."""

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected a JSON object in {path}"
        )

    return data


def determine_containment_level(
    phase: str,
    severity: str,
) -> str:
    """Determine containment level from phase and case severity."""

    phase_levels = {
        "Detection": "ELEVATED",
        "Intelligence Correlation": "HIGH",
        "Evidence Collection": "HIGH",
        "Infrastructure Analysis": "SEVERE",
        "Threat Attribution": "SEVERE",
        "Containment": "CRITICAL",
        "Operational Recovery": "HIGH",
    }

    severity_levels = {
        "LOW": 1,
        "MODERATE": 2,
        "HIGH": 3,
        "CRITICAL": 4,
    }

    level_rank = {
        "ELEVATED": 1,
        "HIGH": 2,
        "SEVERE": 3,
        "CRITICAL": 4,
    }

    phase_level = phase_levels.get(
        phase,
        "ELEVATED",
    )

    severity_rank = severity_levels.get(
        severity.upper(),
        1,
    )

    if severity_rank == 4:
        case_level = "CRITICAL"
    elif severity_rank == 3:
        case_level = "SEVERE"
    elif severity_rank == 2:
        case_level = "HIGH"
    else:
        case_level = "ELEVATED"

    if (
        level_rank[case_level]
        > level_rank[phase_level]
    ):
        return case_level

    return phase_level


def phase_summary(phase: str) -> str:
    """Return a campaign summary appropriate for the current phase."""

    summaries = {
        "Detection": (
            "Initial reporting indicates coordinated unauthorized "
            "activity affecting protected biomedical research "
            "infrastructure."
        ),
        "Intelligence Correlation": (
            "Analysts are correlating related investigations, access "
            "records, and digital artifacts to identify common "
            "infrastructure."
        ),
        "Evidence Collection": (
            "Investigators are expanding forensic acquisition across "
            "affected laboratory and research systems."
        ),
        "Infrastructure Analysis": (
            "Recovered evidence is being used to reconstruct the "
            "infrastructure supporting the coordinated intrusion "
            "activity."
        ),
        "Threat Attribution": (
            "Analysts are evaluating recurring access patterns, actor "
            "profiles, and linked investigations to support "
            "attribution."
        ),
        "Containment": (
            "Containment actions are underway across affected research "
            "networks while evidence preservation continues."
        ),
        "Operational Recovery": (
            "Affected environments are undergoing validation and "
            "controlled recovery while residual risk is monitored."
        ),
    }

    return summaries.get(
        phase,
        (
            "The active campaign remains under continuing "
            "investigative review."
        ),
    )


def next_objective(phase: str) -> str:
    """Return the next operational objective for the current phase."""

    objectives = {
        "Detection": (
            "Validate initial reporting and identify affected "
            "research systems."
        ),
        "Intelligence Correlation": (
            "Correlate newly recovered artifacts with related "
            "investigations."
        ),
        "Evidence Collection": (
            "Complete forensic acquisition and preserve "
            "chain-of-custody records."
        ),
        "Infrastructure Analysis": (
            "Map infrastructure associated with the coordinated "
            "intrusion activity."
        ),
        "Threat Attribution": (
            "Assess actor relationships and strengthen attribution "
            "confidence."
        ),
        "Containment": (
            "Complete containment actions and validate protected "
            "environments."
        ),
        "Operational Recovery": (
            "Verify recovery controls and prepare the final "
            "operational assessment."
        ),
    }

    return objectives.get(
        phase,
        "Continue investigative review and evidence validation.",
    )


def main() -> None:
    case = load_json(CASE_FILE)
    operation = load_json(OPERATION_FILE)

    phases = [
        "Detection",
        "Intelligence Correlation",
        "Evidence Collection",
        "Infrastructure Analysis",
        "Threat Attribution",
        "Containment",
        "Operational Recovery",
    ]

    current_phase = operation.get(
        "campaign_phase",
        phases[0],
    )

    if current_phase not in phases:
        current_phase = phases[0]

    current_index = phases.index(current_phase)

    # The campaign may move forward, but it can never move backward.
    if current_index < len(phases) - 1:
        if random.randint(1, 100) <= 25:
            current_phase = phases[current_index + 1]

    # Force a stable, professional campaign title on every run.
    operation["operation"] = CAMPAIGN_TITLE
    operation["campaign_phase"] = current_phase

    operation["containment_level"] = (
        determine_containment_level(
            current_phase,
            str(case.get("severity", "LOW")),
        )
    )

    current_designation = str(
        operation.get(
            "threat_designation",
            "",
        )
    ).strip()

    if (
        not current_designation
        or current_designation in LEGACY_DESIGNATIONS
    ):
        operation["threat_designation"] = (
            DEFAULT_THREAT_DESIGNATION
        )

    operation["campaign_summary"] = phase_summary(
        current_phase
    )

    operation["next_objective"] = next_objective(
        current_phase
    )

    operation["last_updated"] = (
        date.today().isoformat()
    )

    with OPERATION_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            operation,
            file,
            indent=4,
        )

    print(
        "Campaign updated: "
        f"{operation['operation']} — "
        f"{current_phase}"
    )

    print(
        "Threat designation: "
        f"{operation.get('threat_designation', 'Unknown')}"
    )


if __name__ == "__main__":
    main()
