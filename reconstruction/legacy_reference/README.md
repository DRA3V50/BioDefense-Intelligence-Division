# LEGACY / REFERENCE ONLY

generate_case_banner_legacy.py is the byte-for-byte preserved pre-Subsystem #9 renderer.

- Preserved SHA-256: 356b74c0373d301521998b3b7ac3416cb1b8ef0ec73258721017c89e3e087161
- It is not a production entry point.
- `scripts/generate_case_banner.py` is the production wrapper entry point for
  the byte-frozen Subsystem #9 V2 renderer; it never invokes this legacy file.
- The production workflow does not invoke this directory.
