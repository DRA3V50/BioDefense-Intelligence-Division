#!/usr/bin/env python3
"""Compatibility entry point for deterministic persistent lifecycle updates.

This replaces the former independent probabilistic status writer. The legacy status
field is retained, while current_stage is evaluated only by case_lifecycle.
"""

from case_lifecycle import update_active_case


def main() -> None:
    result = update_active_case()
    if result.transition:
        print(f"Case lifecycle advanced to {result.transition}.")
    else:
        print(f"Case lifecycle unchanged: {result.reason}")


if __name__ == "__main__":
    main()
