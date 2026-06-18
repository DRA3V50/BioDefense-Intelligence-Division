import json
import os

with open("data/current_case.json") as f:
case = json.load(f)

timeline_file = "reconstruction/exposure_timeline.md"

entry = (
f"- {case['date']} | "
f"{case['case_id']} | "
f"{case['classification']} | "
f"{case['severity']} | "
f"{case['status']}\n"
)

if not os.path.exists(timeline_file):
with open(timeline_file, "w", encoding="utf-8") as f:
f.write("# Exposure Reconstruction Timeline\n\n")

with open(timeline_file, "a", encoding="utf-8") as f:
f.write(entry)

print("Timeline updated.")
