#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import date

CASE_FILE = Path("data/current_case.json")
DB_FILE = Path("intelligence/actor_database.json")

with open(CASE_FILE, "r", encoding="utf-8") as f:
case = json.load(f)

if DB_FILE.exists():

```
with open(DB_FILE, "r", encoding="utf-8") as f:
    db = json.load(f)
```

else:

```
db = {"actors": []}
```

actor_name = case["threat_family"]

existing = None

for actor in db["actors"]:

```
if actor["name"] == actor_name:
    existing = actor
    break
```

if existing:

```
existing["cases"] += 1
existing["last_seen"] = date.today().isoformat()
```

else:

```
db["actors"].append({

    "name": actor_name,
    "first_seen": date.today().isoformat(),
    "last_seen": date.today().isoformat(),
    "cases": 1,
    "severity": case["severity"],
    "confidence": case["confidence"]

})
```

with open(DB_FILE, "w", encoding="utf-8") as f:
json.dump(db, f, indent=4)

print("Actor database updated.")
