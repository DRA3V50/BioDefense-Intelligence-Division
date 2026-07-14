#!/usr/bin/env python3

import json
import random
from datetime import date

operation_file = "operations/active_operation.json"

with open(operation_file, "r", encoding="utf-8") as f:
    operation = json.load(f)

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

    index = phases.index(current)

    if random.randint(1,100) <= 25:

        if index < len(phases)-1:
            operation["campaign_phase"] = phases[index+1]

operation["containment_level"] = random.choice(levels)

operation["threat_designation"] = random.choice(designations)

operation["affected_facilities"] += random.randint(0,2)

operation["active_cases"] += random.randint(1,4)

operation["evidence_collected"] += random.randint(3,10)

operation["digital_artifacts"] += random.randint(2,8)

operation["ioc_count"] += random.randint(1,5)

operation["confirmed_intrusions"] += random.randint(0,2)

operation["last_updated"] = date.today().isoformat()

with open(operation_file,"w",encoding="utf-8") as f:
    json.dump(operation,f,indent=4)

print("Operation updated.")
