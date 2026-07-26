from pathlib import Path
import json

README_FILE = Path("README.md")
CURRENT_CASE_FILE = Path("data/current_case.json")
EVIDENCE_ROOT = Path("evidence")


def load_current_case():
    pass


def load_evidence_manifest(case_id):
    pass


def load_evidence_correlations(case_id):
    pass


def build_dashboard(case, manifest, correlations):
    pass


def update_readme(dashboard):
    pass


def main():
    case = load_current_case()

    manifest = load_evidence_manifest(
        case["case_id"]
    )

    correlations = load_evidence_correlations(
        case["case_id"]
    )

    dashboard = build_dashboard(
        case,
        manifest,
        correlations,
    )

    update_readme(dashboard)

    print("Evidence dashboard updated.")


if __name__ == "__main__":
    main()
