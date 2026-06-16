import json
import csv
import os

with open("data/current_case.json") as f:
case = json.load(f)

history_file = "data/investigation_history.csv"

file_exists = os.path.exists(history_file)

with open(history_file, "a", newline="", encoding="utf-8") as csvfile:
fieldnames = [
"date",
"case_id",
"classification",
"severity",
"status",
"confidence"
]

```
writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

if not file_exists or os.path.getsize(history_file) == 0:
    writer.writeheader()

writer.writerow({
    "date": case["date"],
    "case_id": case["case_id"],
    "classification": case["classification"],
    "severity": case["severity"],
    "status": case["status"],
    "confidence": case["confidence"]
})
```

print("History updated.")
