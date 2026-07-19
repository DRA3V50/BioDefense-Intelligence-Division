#!/usr/bin/env python3

import csv
import json
from pathlib import Path

HISTORY = Path("data/investigation_history.csv")
OPERATION = Path("operations/active_operation.json")

with open(OPERATION,"r",encoding="utf-8") as f:
    operation=json.load(f)

rows=[]

if HISTORY.exists():

    with open(HISTORY,newline="",encoding="utf-8") as f:

        rows=list(csv.DictReader(f))

total=len(rows)

high=0
critical=0

evidence=0
iocs=0

families=set()
labs=set()

for r in rows:

    sev=r.get("severity","").upper()

    if sev=="HIGH":
        high+=1

    elif sev=="CRITICAL":
        critical+=1

    try:
        evidence+=int(r.get("evidence_count",0))
    except:
        pass

    try:
        iocs+=int(r.get("ioc_count",0))
    except:
        pass

    if r.get("threat_family"):
        families.add(r["threat_family"])

    if r.get("affected_platform"):
        labs.add(r["affected_platform"])

operation["active_cases"]=total

operation["confirmed_intrusions"]=critical

operation["evidence_collected"]=evidence

operation["ioc_count"]=iocs

operation["known_threat_families"]=len(families)

operation["affected_facilities"]=len(labs)

with open(OPERATION,"w",encoding="utf-8") as f:

    json.dump(operation,f,indent=4)

print("Campaign metrics recalculated.")
