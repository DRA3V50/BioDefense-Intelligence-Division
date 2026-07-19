#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import date

CASE_FILE = Path("data/current_case.json")
DB_FILE = Path("intelligence/actor_database.json")

# -----------------------------
# Load current case
# -----------------------------

with open(CASE_FILE, "r", encoding="utf-8") as f:
    case = json.load(f)

# -----------------------------
# Load actor database
# -----------------------------

if DB_FILE.exists():

    with open(DB_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)

else:

    db = {
        "actors": []
    }

# -----------------------------
# Actor name
# -----------------------------

actor_name = case["threat_family"]

existing = None

for actor in db["actors"]:

    if actor["name"] == actor_name:
        existing = actor
        break

# -----------------------------
# Update existing actor
# -----------------------------

if existing:

    existing["cases"] += 1
    existing["last_seen"] = date.today().isoformat()

    existing["severity"] = case["severity"]
    existing["confidence"] = case["confidence"]

# -----------------------------
# Create new actor
# -----------------------------

else:

    db["actors"].append({

        "name": actor_name,

        "first_seen": date.today().isoformat(),

        "last_seen": date.today().isoformat(),

        "cases": 1,

        "severity": case["severity"],

        "confidence": case["confidence"]

    })

# -----------------------------
# Save database
# -----------------------------

DB_FILE.parent.mkdir(parents=True, exist_ok=True)

with open(DB_FILE, "w", encoding="utf-8") as f:
    json.dump(db, f, indent=4)

print("Threat actor database updated.")
