import json
from pathlib import Path
from datetime import date

campaign_file = Path("operations/active_operation.json")

with open(campaign_file, "r", encoding="utf-8") as f:
    campaign = json.load(f)

# -----------------------
# Update operational stats
# -----------------------

campaign["active_cases"] += 1
campaign["confirmed_intrusions"] += 1
campaign["evidence_collected"] += 2
campaign["digital_artifacts"] += 1
campaign["ioc_count"] += 1

campaign["last_updated"] = date.today().isoformat()

# -----------------------
# Campaign progression
# -----------------------

cases = campaign["active_cases"]

if cases >= 75:
    campaign["campaign_phase"] = "Containment Operations"
    campaign["containment_level"] = "CRITICAL"

elif cases >= 50:
    campaign["campaign_phase"] = "Threat Attribution"
    campaign["containment_level"] = "HIGH"

elif cases >= 25:
    campaign["campaign_phase"] = "Evidence Correlation"
    campaign["containment_level"] = "ELEVATED"

else:
    campaign["campaign_phase"] = "Initial Investigation"
    campaign["containment_level"] = "GUARDED"

# -----------------------
# Save
# -----------------------

with open(campaign_file, "w", encoding="utf-8") as f:
    json.dump(campaign, f, indent=4)

print("Operational campaign updated.")
