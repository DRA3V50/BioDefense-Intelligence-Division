import json
import os

case_path = "data/current_case.json"
state_path = "data/investigation_state.json"

with open(case_path, "r", encoding="utf-8") as f:
    case = json.load(f)

phases = [
    "Detection",
    "Evidence Collection",
    "Firmware Analysis",
    "IOC Correlation",
    "Threat Assessment",
    "Containment",
    "Recovery",
    "Case Closed"
]

# Load previous state if it exists
if os.path.exists(state_path):
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)
else:
    state = {
        "case_id": case["case_id"],
        "phase_index": 0
    }

# If new case, reset lifecycle
if state.get("case_id") != case["case_id"]:
    state["case_id"] = case["case_id"]
    state["phase_index"] = 0
else:
    # Progress phase slightly each run (simulate investigation evolution)
    if state["phase_index"] < len(phases) - 1:
        state["phase_index"] += 1

current_phase = phases[state["phase_index"]]

state["current_phase"] = current_phase

# Save state
with open(state_path, "w", encoding="utf-8") as f:
    json.dump(state, f, indent=2)

print(f"Investigation phase updated: {current_phase}")
