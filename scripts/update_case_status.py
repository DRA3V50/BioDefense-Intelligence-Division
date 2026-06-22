import json
import random

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

workflow = [
    "Open",
    "Evidence Collection",
    "Active Investigation",
    "Containment",
    "Monitoring",
    "Closed"
]

current = case["status"]

if current in workflow:
    position = workflow.index(current)

    if position < len(workflow) - 1:
        if random.randint(1, 100) <= 20:
            case["status"] = workflow[position + 1]

with open("data/current_case.json", "w", encoding="utf-8") as f:
    json.dump(case, f, indent=2)

print("Case status updated.")
