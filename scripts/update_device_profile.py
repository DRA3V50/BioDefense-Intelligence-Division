import json
import random

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

operating_systems = [
    "Windows Server 2025",
    "Ubuntu Server 24.04 LTS",
    "Red Hat Enterprise Linux 10",
    "VMware ESXi 9",
    "Hardened Research Appliance OS"
]

security_zones = [
    "Level III Laboratory",
    "Level IV Biosecurity",
    "Federal Operations Segment",
    "Research Isolation Network",
    "Evidence Processing Network",
    "Critical Infrastructure Segment"
]

asset_status = [
    "Evidence Acquisition",
    "Under Forensic Preservation",
    "Active Investigation",
    "Isolated From Production",
    "Awaiting Laboratory Review"
]

facilities = [
    "Raccoon Research Annex",
    "Ashcroft Biomedical Center",
    "Federal Biosecurity Laboratory",
    "National Pathogen Research Facility",
    "Central Evidence Processing Center",
    "Advanced Genome Security Laboratory"
]

notes = [
    "Analysts continue reconstructing attacker activity across protected biomedical systems.",
    "Digital evidence preserved for laboratory forensic examination.",
    "System isolated pending malware reverse engineering.",
    "Protected research assets remain under continuous monitoring.",
    "No destructive activity observed following initial containment.",
    "Evidence indicates unauthorized access to restricted research resources."
]

content = f"""# Protected Asset Profile

## Investigation

Case ID:
{case["case_id"]}

Operation:
{case["operation"]}

Classification:
{case["classification"]}

Threat Family:
{case["threat_family"]}

---

## Protected Asset

Facility:
{random.choice(facilities)}

Platform:
{case["affected_platform"]}

Device:
{case["device_family"]}

Vendor:
{case["vendor"]}

Operating System:
{random.choice(operating_systems)}

Security Zone:
{case["network_zone"]}

---

## Investigation Status

Current Phase:
{case["containment_phase"]}

Status:
{random.choice(asset_status)}

Priority:
{case["priority"]}

Confidence:
{case["confidence"]}%

---

## Analyst Assessment

Lead Analyst:
{case["lead_analyst"]}

Recommended Action:
{case["recommended_action"]}

---

## Reconstruction Notes

{random.choice(notes)}
"""

with open(
    "reconstruction/device_profile.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(content)

print("Protected asset profile updated.")
