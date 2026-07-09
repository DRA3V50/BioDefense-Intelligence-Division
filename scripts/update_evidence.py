import csv
import json
import os

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

evidence_file = "evidence/evidence_log.csv"

artifact_map = {
    "Unauthorized Research System Access": "Authentication Logs",
    "Synthetic Genome Theft": "Research Database Export",
    "Memory Artifact Investigation": "Memory Capture",
    "Laboratory Network Intrusion": "Network Packet Capture",
    "Biomedical Data Exfiltration": "Data Archive",
    "Embedded Device Exposure": "Embedded Device Image",
    "Unauthorized Firmware Modification": "Firmware Binary",
    "Firmware Integrity Alert": "Firmware Image"
}

artifact = artifact_map.get(
    case["classification"],
    "Digital Evidence"
)

headers = [
    "Evidence ID",
    "Case ID",
    "Date",
    "Operation",
    "Classification",
    "Artifact Type",
    "Platform",
    "Device",
    "Collected By",
    "Status"
]

write_header = (
    not os.path.exists(evidence_file)
    or os.path.getsize(evidence_file) == 0
)

evidence_number = 1

if os.path.exists(evidence_file):

    with open(evidence_file, newline="", encoding="utf-8") as f:

        reader = csv.reader(f)

        evidence_number = max(len(list(reader)), 1)

evidence_id = f"EV-{evidence_number:05d}"

with open(evidence_file, "a", newline="", encoding="utf-8") as f:

    writer = csv.writer(f)

    if write_header:
        writer.writerow(headers)

    writer.writerow([
        evidence_id,
        case["case_id"],
        case["date"],
        case["operation"],
        case["classification"],
        artifact,
        case["affected_platform"],
        case["device_family"],
        case["lead_analyst"],
        "Collected"
    ])

print(f"Evidence recorded: {evidence_id}")
