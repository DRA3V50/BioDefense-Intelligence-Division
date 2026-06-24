import json
import random

with open("data/current_case.json", "r", encoding="utf-8") as f:
    case = json.load(f)

architectures = [
    "ARM",
    "ARM64",
    "MIPS",
    "x86 Embedded",
    "PowerPC"
]

bootloaders = [
    "U-Boot",
    "Barebox",
    "Coreboot",
    "Vendor Proprietary"
]

content = f"""# Device Exposure Profile

## Case ID
{case['case_id']}

## Platform
{case['affected_platform']}

## Firmware Classification
{case['classification']}

## Processor Architecture
{random.choice(architectures)}

## Bootloader
{random.choice(bootloaders)}

## Exposure Status
Under Investigation

## Reconstruction Notes
Analysts are reconstructing firmware execution behavior and validating integrity indicators associated with this investigation.
"""

with open(
    "reconstruction/device_profile.md",
    "w",
    encoding="utf-8"
) as f:
    f.write(content)

print("Device profile updated.")
