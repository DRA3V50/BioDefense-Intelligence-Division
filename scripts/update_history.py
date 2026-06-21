import json

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

line = (
    f"{case['date']},"
    f"{case['case_id']},"
    f"{case['classification']},"
    f"{case['severity']},"
    f"{case['status']},"
    f"{case['confidence']}\n"
)

with open(
    "data/investigation_history.csv",
    "a",
    encoding="utf-8"
) as f:
    f.write(line)

print("History updated.")
