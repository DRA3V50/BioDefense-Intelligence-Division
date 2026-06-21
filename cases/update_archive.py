import os

files = []

for file in os.listdir("cases"):
    if file.endswith(".md") and file != "archive.md":
        files.append(file)

files.sort(reverse=True)

content = "# Investigation Archive\n\n"

for item in files:
    content += f"- {item}\n"

with open(
    "cases/archive.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(content)

print("Archive updated.")
