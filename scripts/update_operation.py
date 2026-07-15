#!/usr/bin/env python3

import json
import random
import os
from datetime import date

today = date.today().isoformat()

CASE_FILE = "data/current_case.json"
OPERATION_FILE = "operations/active_operation.json"
STATUS_FILE = "operations/operation_status.json"

with open(CASE_FILE, "r", encoding="utf-8") as f:
    case = json.load(f)

with open(OPERATION_FILE, "r", encoding="utf-8") as f:
    operation = json.load(f)

###########################################################
# Advance Campaign Phase
###########################################################

phases = [
    "Detection",
    "Intelligence Correlation",
    "Evidence Collection",
    "Infrastructure Analysis",
    "Threat Attribution",
    "Containment",
    "Operational Recovery"
]

levels = [
    "ELEVATED",
    "HIGH",
    "SEVERE",
    "CRITICAL"
]

designations = [
    "BIOCELL-01",
    "BIOCELL-02",
    "CHIMERA-07",
    "NEMESIS-12",
    "UMBRA-05",
    "CERBERUS-09"
]

current = operation["campaign_phase"]

if current in phases:

    idx = phases.index(current)

    if random.randint(1, 100) <= 25 and idx < len(phases) - 1:
        operation["campaign_phase"] = phases[idx + 1]

###########################################################
# Update Active Operation
###########################################################

operation["containment_level"] = random.choice(levels)

operation["threat_designation"] = random.choice(designations)

operation["affected_facilities"] += random.randint(0, 2)

operation["confirmed_intrusions"] += random.randint(0, 2)

operation["active_cases"] += random.randint(1, 3)

operation["evidence_collected"] += case["evidence_count"]

operation["digital_artifacts"] += random.randint(2, 8)

operation["ioc_count"] += case["ioc_count"]

operation["last_updated"] = today

###########################################################
# Persistent Operation Statistics
###########################################################

if os.path.exists(STATUS_FILE):

    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        status = json.load(f)

else:

    status = {

        "campaign_id": operation["campaign_id"],

        "operation": operation["operation"],

        "campaign_phase": operation["campaign_phase"],

        "total_cases": 0,

        "active_cases": 0,

        "closed_cases": 0,

        "low_cases": 0,

        "moderate_cases": 0,

        "high_cases": 0,

        "critical_cases": 0,

        "affected_facilities": operation["affected_facilities"],

        "affected_states": operation["affected_states"],

        "evidence_items": 0,

        "digital_artifacts": 0,

        "ioc_count": 0,

        "containment_level": operation["containment_level"],

        "confidence": case["confidence"],

        "last_updated": today

    }

###########################################################
# Update Statistics
###########################################################

status["campaign_phase"] = operation["campaign_phase"]

status["total_cases"] += 1

status["active_cases"] = operation["active_cases"]

severity = case["severity"].upper()

if severity == "LOW":
    status["low_cases"] += 1

elif severity == "MODERATE":
    status["moderate_cases"] += 1

elif severity == "HIGH":
    status["high_cases"] += 1

elif severity == "CRITICAL":
    status["critical_cases"] += 1

status["affected_facilities"] = operation["affected_facilities"]

status["affected_states"] = operation["affected_states"]

status["evidence_items"] = operation["evidence_collected"]

status["digital_artifacts"] = operation["digital_artifacts"]

status["ioc_count"] = operation["ioc_count"]

status["containment_level"] = operation["containment_level"]

status["confidence"] = max(
    status["confidence"],
    case["confidence"]
)

status["last_updated"] = today

###########################################################
# Save
###########################################################

with open(OPERATION_FILE, "w", encoding="utf-8") as f:
    json.dump(operation, f, indent=4)

with open(STATUS_FILE, "w", encoding="utf-8") as f:
    json.dump(status, f, indent=4)

print("Operation updated.")
