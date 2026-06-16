import json
import os

with open("data/current_case.json") as f:
case = json.load(f)

evidence_file = "evidence/evidence_log.csv"

if os.path.exists(evidence_file):
with open(evidence_file, "r", encoding="utf-8") as f:
lines = f.readlines()

```
evidence_number = len(lines)
```

else:
evidence_number = 1

evidence_id = f"EV-{evidence_number:04d}"

artifact_types = {
"Bootloader Anomaly": "Boot Artifact",
"Firmware Integrity Alert": "Firmware Image",
"Unauthorized Firmware Modification": "Firmware Binary",
"Embedded Device Exposure": "Embedded Log",
"Persistence Indicator Review": "Configuration Artifact",
"Supply Chain Validation Review": "Supply Chain Record",
"Unsigned Firmware Detection": "Firmware Signature",
"Memory Artifact Investigation": "Memory Dump"
}

artifact = artifact_types.get(
case["classification"],
"Digital Artifact"
)

with open(evidence_file, "a", encoding="utf-8") as f:
f.write(
f"{evidence_id},"
f"{case['date']},"
f"{case['case_id']},"
f"{artifact},"
f"{case['assessment']}\n"
)

print("Evidence logged.")

