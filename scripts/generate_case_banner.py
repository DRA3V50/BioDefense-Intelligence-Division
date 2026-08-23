#!/usr/bin/env python3
"""Production entry point for the approved BioDefense dashboard renderer.

The workflow retains the historical ``generate_case_banner.py`` command, but
the final production entry point delegates solely to the #10 wrapper.  That
wrapper verifies and deploys the byte-frozen Subsystem #9 V2 renderer without
mutating persistent active-case state.  The legacy implementation is retained
only under ``reconstruction/legacy_reference``.
"""

from __future__ import annotations

from production_dashboard_wrapper import main


if __name__ == "__main__":
    raise SystemExit(main())
