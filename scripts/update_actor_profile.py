"""
update_actor_profile.py

Generates a deterministic Threat Actor Intelligence Profile for the
active investigation, based on the current case file.

Reads:
    data/current_case.json          -> active investigation snapshot

Writes:
    intelligence/threat_actor.md    -> generated intelligence profile

Design note:
    All "randomized" selections (alias, motivation, sophistication, and
    observed techniques) are seeded from the case_id, so the same case
    always produces the same profile. This keeps the generated
    intelligence artifact stable across repeated runs / daily commits,
    rather than reshuffling every time the workflow executes.
"""

import hashlib
import json
import random
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CASE_FILE = Path("data/current_case.json")
OUTPUT_PATH = Path("intelligence/threat_actor.md")


# ---------------------------------------------------------------------------
# Reference data
#
# All entries below describe cyber intrusion activity against biosecurity-
# adjacent digital infrastructure (networks, systems, data, devices). None
# of these represent biological, chemical, or physical attack capability -
# this repository models digital forensics and incident response only.
# ---------------------------------------------------------------------------

ALIASES = [
    "Project Chimera",
    "Ghost Genome",
    "Vector-9",
    "Black Helix",
    "Silent Culture",
    "Crimson Cell",
    "Umbra Bio",
    "Genome Phantom",
    "Dark Sequence",
    "Cerberus Group",
]

# Cyber intrusion techniques only - describes how the actor moves through
# and manipulates IT/OT systems, not any physical or biological action.
# Naming leans into the "shadowy bio-corporation" investigative tone of the
# repository while staying strictly grounded in real cyber/OT tradecraft.
TTPS = [
    "Credential Abuse",
    "Supply Chain Compromise",
    "Research Data Exfiltration",
    "Concealed Internal Movement",
    "Lateral Movement",
    "Privilege Escalation",
    "Long-Term Network Foothold",
    "Command and Control",
    "Laboratory Network Reconnaissance",
    "Laboratory Control System Manipulation",
    "Laboratory Data Manipulation",
    "Biosecurity System Tampering",
    "Insider Access Abuse",
    "Covert Remote Access Tooling",
    "Encrypted Data Staging",
]

MOTIVATIONS = [
    "Strategic Intelligence Collection",
    "Research Data Theft",
    "Medical Infrastructure Disruption",
    "Laboratory System Sabotage",
    "Espionage Against Research Programs",
    "Disruption of Biosecurity Operations",
]

ATTRIBUTIONS = [
    "Unknown",
    "Unattributed",
    "Multiple Regions",
    "International Infrastructure",
    "Foreign Intelligence Interest",
]

SOPHISTICATION_LEVELS = [
    "Moderate",
    "High",
    "Advanced",
    "Nation-State Level",
]

# Original investigator callsigns used to attribute the profile to a
# specific in-universe analyst. These are wholly original identifiers
# created for this repository - not drawn from any copyrighted work.
ANALYST_CALLSIGNS = [
    "Analyst Ashworth",
    "Analyst Reyes",
    "Analyst Kovac",
    "Analyst Whitlock",
    "Analyst Marchetti",
    "Analyst Odell",
    "Analyst Bracken",
    "Analyst Serrano",
]

# Short first-person style notes an analyst might attach to a profile.
# Kept generic and procedural - no dialogue, no narrative embellishment.
ANALYST_NOTES = [
    "Cross-referencing this actor against prior containment cases for overlap.",
    "Pattern of access suggests familiarity with internal lab procedures.",
    "Recommend elevating monitoring on adjacent facility networks.",
    "Technique overlap with prior campaigns is circumstantial at this stage.",
    "Awaiting corroborating evidence before escalating attribution confidence.",
    "Flagging for follow-up once additional artifacts are processed.",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_case(path: Path) -> dict:
    """Load the current case file, returning an empty dict on any failure."""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


# ---------------------------------------------------------------------------
# Deterministic selection helpers
# ---------------------------------------------------------------------------

def deterministic_rng(case_id: str) -> random.Random:
    """
    Build a Random instance seeded from the case_id, so every selection
    derived from it is stable across repeated runs for the same case.
    """
    digest = hashlib.sha256(case_id.encode("utf-8")).hexdigest()
    seed = int(digest, 16)
    return random.Random(seed)


def pick_one(rng: random.Random, options: list, default: str = "Unknown") -> str:
    """Deterministically pick a single item from a list."""
    if not options:
        return default
    return rng.choice(options)


def pick_techniques(rng: random.Random, options: list, count: int, required: str = None) -> list:
    """
    Deterministically pick a set of techniques, optionally guaranteeing
    that a required technique (e.g. the case's initial_access) is included.
    """
    pool = [t for t in options if t != required]
    sample_size = min(count - 1, len(pool)) if required else min(count, len(pool))
    selected = rng.sample(pool, sample_size) if pool else []

    if required:
        selected = [required] + selected

    return selected


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def build_report(case: dict) -> str:
    """Build the full threat actor intelligence profile as markdown."""

    case_id = str(case.get("case_id", "UNKNOWN-CASE"))
    rng = deterministic_rng(case_id)

    threat_family = case.get("threat_family", "Unknown")
    operation = case.get("operation", "Unknown")
    classification = case.get("classification", "Unknown")
    confidence = case.get("confidence", 90)
    initial_access = case.get("initial_access")

    alias = pick_one(rng, ALIASES)
    attribution = pick_one(rng, ATTRIBUTIONS)
    motivation = pick_one(rng, MOTIVATIONS)
    sophistication = pick_one(rng, SOPHISTICATION_LEVELS)

    # Prefer the analyst already recorded on the case (keeps this profile
    # consistent with the README's "Lead Analyst" field for the same case).
    # Fall back to a deterministically-picked callsign if the case doesn't
    # specify one, so every case still reads as reviewed by a named analyst.
    analyst = case.get("lead_analyst") or pick_one(rng, ANALYST_CALLSIGNS, default="Unassigned Analyst")
    analyst_note = pick_one(rng, ANALYST_NOTES, default="No additional notes on file.")

    # Incorporate the case's actual initial_access as one of the observed
    # techniques, so the profile stays tied to the real investigation data
    # rather than describing an unrelated set of techniques.
    techniques = pick_techniques(rng, TTPS, count=6, required=initial_access)

    techniques_block = "\n".join(f"- {t}" for t in techniques) if techniques else "- No techniques on record"

    report = f"""# Threat Actor Intelligence Profile

## Threat Designation
{threat_family}

---

## Primary Alias
{alias}

---

## Attribution
{attribution}

---

## Observed Motivation
{motivation}

---

## Operational Sophistication
{sophistication}

---

## Confidence
{confidence}%

---

## Observed Techniques
{techniques_block}

---

## Reviewing Analyst
{analyst}

**Analyst Note:** {analyst_note}

---

## Current Campaign
{operation}

---

## Primary Target
{classification}

---

## Last Updated
{date.today().isoformat()}
"""
    return report


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    case = load_case(CASE_FILE)
    report = build_report(case)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report, encoding="utf-8")

    print("Threat actor profile updated.")


if __name__ == "__main__":
    main()
