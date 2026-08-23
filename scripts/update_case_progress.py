#!/usr/bin/env python3
"""Evaluate the persistent active-case state machine once.

The old file advanced a separate phase index on every run. The authoritative
workflow state now lives on data/current_case.json as current_stage and only
changes when validated case artifacts satisfy a documented transition.
"""

from case_lifecycle import update_active_case


def main() -> None:
    result = update_active_case()
    message = (
        f"Active case {result.case['case_id']} "
        f"stage={result.case['current_stage']} "
        f"lifecycle={result.case['lifecycle_status']}."
    )
    if result.transition:
        message += f" Transitioned to {result.transition}."
    else:
        message += f" No transition: {result.reason}"
    if result.stale_threat_report_rejected:
        message += " A stale C# threat report was rejected."
    print(message)


if __name__ == "__main__":
    main()
