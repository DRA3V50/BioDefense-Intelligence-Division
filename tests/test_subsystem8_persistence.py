from __future__ import annotations

import csv
import hashlib
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


PRODUCTION_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PRODUCTION_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from archive_case import archive_terminal_case
from case_lifecycle import (
    ensure_active_case,
    mark_assessment_complete,
    record_problem_review_outcome,
    update_active_case,
)
from case_state import (
    CaseStateError,
    MalformedStateError,
    StaleDataError,
    StateValidationError,
    atomic_write_json,
    current_case_path,
    iso_timestamp,
    load_active_case,
    load_json_document,
    validate_active_case,
)
from correlate_evidence import artifact_path_for_item, main as correlate_evidence_main
from dashboard_state import build_dashboard_state
from generate_evidence_repository import (
    artifact_path_for_type,
    environment_values,
    generate_evidence_items,
    main as generate_evidence_repository_main,
)
from update_evidence import (
    LEGACY_HEADER,
    V2_HEADER,
    append_case_index,
    ensure_compatible_evidence_log,
)


UTC = timezone.utc
BASE_TIME = datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)
CASE_A = "BID-2026-1111"
CASE_B = "BID-2026-2222"
CAMPAIGN = "BDC-2026-001"


def case_payload(case_id: str = CASE_A) -> dict:
    return {
        "case_id": case_id,
        "campaign_id": CAMPAIGN,
        "date": "2026-08-21",
        "operation": "Persistent Case Test",
        "classification": "Laboratory Network Intrusion",
        "threat_family": "Test Family",
        "severity": "HIGH",
        "status": "Open",
        "containment_phase": "Detection",
        "affected_platform": "Laboratory Information System",
        "device_family": "Sequencing Controller",
        "vendor": "Test Vendor",
        "network_zone": "Evidence Network",
        "firmware_version": "1.2.3",
        "confidence": 78,
        "risk_score": 71,
        "affected_assets": 4,
        "evidence_count": 2,
        "ioc_count": 3,
        "initial_access": "Credential Misuse",
        "lead_analyst": "Test Analyst",
        "priority": "HIGH",
        "recommended_action": "Complete controlled review.",
        "assessment": "Controlled assessment is available.",
    }


def write_operation(root: Path) -> None:
    atomic_write_json(
        root / "operations" / "active_operation.json",
        {
            "campaign_id": CAMPAIGN,
            "operation": "Persistent Case Test",
            "campaign_phase": "Detection",
            "containment_level": "Controlled",
            "next_objective": "Review evidence",
        },
    )


def write_manifest(root: Path, case: dict, review_status: str) -> None:
    case_directory = root / "evidence" / case["case_id"]
    items = []
    for number in range(1, case["evidence_count"] + 1):
        evidence_id = f"{case['case_id']}-EV-{number:04d}"
        items.append(
            {
                "evidence_id": evidence_id,
                "case_id": case["case_id"],
                "artifact_type": "Laboratory System Configuration",
                "artifact_path": "artifacts/device_configuration.json",
                "source_system": case["device_family"],
                "platform": case["affected_platform"],
                "vendor": case["vendor"],
                "zone": case["network_zone"],
                "collected_by": case["lead_analyst"],
                "collected_at": iso_timestamp(BASE_TIME),
                "integrity_status": "Verified",
                "sha256": f"fixture-{number}",
                "classification": case["classification"],
                "review_status": review_status,
            }
        )
    atomic_write_json(
        case_directory / "evidence_manifest.json",
        {
            "schema_version": 2,
            "case_id": case["case_id"],
            "generated_at": iso_timestamp(BASE_TIME),
            "evidence_count": len(items),
            "evidence_items": items,
        },
    )


def set_manifest_review_status(root: Path, case_id: str, review_status: str) -> None:
    path = root / "evidence" / case_id / "evidence_manifest.json"
    manifest = load_json_document(path)
    for item in manifest["evidence_items"]:
        item["review_status"] = review_status
    atomic_write_json(path, manifest)


def write_correlations(root: Path, case: dict) -> None:
    manifest = load_json_document(
        root / "evidence" / case["case_id"] / "evidence_manifest.json"
    )
    correlations = [
        {
            "case_id": case["case_id"],
            "evidence_id": item["evidence_id"],
            "artifact_type": item["artifact_type"],
            "artifact_path": item["artifact_path"],
            "related_indicator": f"IOC-{index}",
            "finding": "Laboratory System Modification",
            "confidence": 88,
            "analysis_status": "Correlated",
        }
        for index, item in enumerate(manifest["evidence_items"], start=1)
    ]
    atomic_write_json(
        root / "evidence" / case["case_id"] / "evidence_correlations.json",
        {
            "schema_version": 2,
            "case_id": case["case_id"],
            "generated_at": iso_timestamp(BASE_TIME),
            "correlation_count": len(correlations),
            "correlations": correlations,
        },
    )


def write_custody(root: Path, case: dict) -> None:
    path = root / "evidence" / case["case_id"] / "chain_of_custody.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "evidence_id",
                "case_id",
                "event_type",
                "performed_by",
                "timestamp",
                "storage_location",
                "integrity_status",
            ],
        )
        writer.writeheader()
        for number in range(1, case["evidence_count"] + 1):
            writer.writerow(
                {
                    "evidence_id": f"{case['case_id']}-EV-{number:04d}",
                    "case_id": case["case_id"],
                    "event_type": "Collected",
                    "performed_by": case["lead_analyst"],
                    "timestamp": iso_timestamp(BASE_TIME),
                    "storage_location": "fixture",
                    "integrity_status": "Verified",
                }
            )


def write_csharp_report(
    root: Path,
    case: dict,
    revision: int,
    *,
    case_id: str | None = None,
    campaign_id: str | None = None,
) -> None:
    atomic_write_json(
        root / "reports" / "bioterror_threat_score_csharp.json",
        {
            "generatedAt": "2026-08-21 12:10 UTC",
            "investigation": {
                "caseId": case_id or case["case_id"],
                "caseRevision": revision,
                "campaignId": campaign_id or case["campaign_id"],
            },
            "assessment": {
                "overallScore": 71,
                "overallLevel": "HIGH",
            },
        },
    )


class Subsystem8PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        write_operation(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_case_a(self):
        return ensure_active_case(
            lambda: case_payload(CASE_A),
            self.root,
            now=BASE_TIME,
        )

    def test_persistent_case_reuse_progression_archive_and_new_case_gate(self) -> None:
        run_a = self.create_case_a()
        self.assertTrue(run_a.created)
        self.assertEqual(run_a.case["case_id"], CASE_A)
        self.assertEqual(run_a.case["current_stage"], "CASE_SCAN")
        self.assertEqual(run_a.case["lifecycle_status"], "ACTIVE")

        run_b = ensure_active_case(
            lambda: self.fail("A non-terminal case must be reused."),
            self.root,
            now=BASE_TIME + timedelta(minutes=1),
        )
        run_c = ensure_active_case(
            lambda: self.fail("A non-terminal case must be reused."),
            self.root,
            now=BASE_TIME + timedelta(minutes=2),
        )
        self.assertFalse(run_b.created)
        self.assertFalse(run_c.created)
        self.assertEqual(run_b.case["case_id"], CASE_A)
        self.assertEqual(run_c.case["case_id"], CASE_A)

        write_manifest(self.root, run_a.case, "Pending Analyst Review")
        first_transition = update_active_case(
            self.root, now=BASE_TIME + timedelta(minutes=3)
        )
        self.assertEqual(first_transition.transition, "EVIDENCE_REVIEW")

        no_progression = update_active_case(
            self.root, now=BASE_TIME + timedelta(minutes=4)
        )
        self.assertIsNone(no_progression.transition)
        self.assertEqual(no_progression.case["current_stage"], "EVIDENCE_REVIEW")
        self.assertEqual(no_progression.case["case_id"], CASE_A)

        set_manifest_review_status(self.root, CASE_A, "REVIEWED")
        review_transition = update_active_case(
            self.root, now=BASE_TIME + timedelta(minutes=5)
        )
        self.assertEqual(review_transition.transition, "VALIDATION")

        write_correlations(self.root, review_transition.case)
        validation_transition = update_active_case(
            self.root, now=BASE_TIME + timedelta(minutes=6)
        )
        self.assertEqual(validation_transition.transition, "ASSESSMENT")

        case = load_active_case(self.root)
        self.assertIsNotNone(case)
        write_csharp_report(self.root, case, case["state_revision"])
        assessment_wait = update_active_case(
            self.root, now=BASE_TIME + timedelta(minutes=7)
        )
        self.assertIsNone(assessment_wait.transition)
        dashboard = build_dashboard_state(self.root)
        self.assertEqual(dashboard["shared"]["case_id"], CASE_A)
        self.assertEqual(dashboard["workflow"]["current_stage"], "ASSESSMENT")
        self.assertEqual(dashboard["threat_monitor"]["threat"]["score"], 71)
        self.assertEqual(
            dashboard["threat_monitor"]["threat"]["canonical_classification"],
            "HIGH",
        )
        self.assertEqual(dashboard["system_status"]["telemetry_source"], "SIMULATED")
        for branch_name in (
            "workflow",
            "active_case_feed",
            "evidence_package",
            "threat_monitor",
            "case_overview",
        ):
            self.assertEqual(dashboard[branch_name]["case_id"], CASE_A)
        self.assertEqual(dashboard["system_status"]["case_id"], CASE_A)

        assessed = mark_assessment_complete(
            self.root, now=BASE_TIME + timedelta(minutes=8)
        )
        write_csharp_report(self.root, assessed, assessed["state_revision"])
        problem_review_transition = update_active_case(
            self.root, now=BASE_TIME + timedelta(minutes=9)
        )
        self.assertEqual(problem_review_transition.transition, "PROBLEM_REVIEW")

        record_problem_review_outcome(
            "RESOLVED",
            self.root,
            now=BASE_TIME + timedelta(minutes=10),
        )
        terminal_transition = update_active_case(
            self.root, now=BASE_TIME + timedelta(minutes=11)
        )
        self.assertEqual(terminal_transition.transition, "RESOLVED")
        self.assertEqual(terminal_transition.case["lifecycle_status"], "RESOLVED")
        self.assertEqual(terminal_transition.case["archive_status"], "PENDING")

        blocked = ensure_active_case(
            lambda: case_payload(CASE_B),
            self.root,
            now=BASE_TIME + timedelta(minutes=12),
        )
        self.assertFalse(blocked.created)
        self.assertEqual(blocked.case["case_id"], CASE_A)

        with self.assertRaises(CaseStateError):
            archive_terminal_case(self.root, now=BASE_TIME + timedelta(minutes=13))
        self.assertEqual(load_active_case(self.root)["archive_status"], "PENDING")

        write_custody(self.root, terminal_transition.case)
        archived, changed = archive_terminal_case(
            self.root, now=BASE_TIME + timedelta(minutes=14)
        )
        self.assertTrue(changed)
        self.assertEqual(archived["archive_status"], "ARCHIVED")
        self.assertTrue(
            (self.root / "cases" / "archive" / "json" / f"{CASE_A}.json").exists()
        )
        archived_again, changed_again = archive_terminal_case(
            self.root, now=BASE_TIME + timedelta(minutes=14)
        )
        self.assertFalse(changed_again)
        self.assertEqual(archived_again["case_id"], CASE_A)

        next_case = ensure_active_case(
            lambda: case_payload(CASE_B),
            self.root,
            now=BASE_TIME + timedelta(minutes=15),
        )
        self.assertTrue(next_case.created)
        self.assertEqual(next_case.case["case_id"], CASE_B)

    def test_malformed_state_is_backed_up_without_silent_replacement(self) -> None:
        path = current_case_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ not valid JSON", encoding="utf-8")

        with self.assertRaises(MalformedStateError):
            ensure_active_case(lambda: case_payload(CASE_A), self.root, now=BASE_TIME)
        self.assertEqual(path.read_text(encoding="utf-8"), "{ not valid JSON")
        backups = list(path.parent.glob("current_case.malformed-*.json"))
        self.assertEqual(len(backups), 1)
        self.assertFalse((self.root / "cases" / "state" / CASE_A).exists())

    def test_stale_csharp_report_and_invalid_schema_are_rejected(self) -> None:
        created = self.create_case_a().case
        write_manifest(self.root, created, "Pending Analyst Review")
        update_active_case(self.root, now=BASE_TIME + timedelta(minutes=1))
        set_manifest_review_status(self.root, CASE_A, "REVIEWED")
        update_active_case(self.root, now=BASE_TIME + timedelta(minutes=2))
        write_correlations(self.root, load_active_case(self.root))
        update_active_case(self.root, now=BASE_TIME + timedelta(minutes=3))
        current = load_active_case(self.root)

        write_csharp_report(
            self.root,
            current,
            current["state_revision"],
            case_id=CASE_B,
        )
        with self.assertRaises(StaleDataError):
            build_dashboard_state(self.root)

        write_csharp_report(
            self.root,
            current,
            current["state_revision"] - 1,
        )
        with self.assertRaises(StaleDataError):
            build_dashboard_state(self.root)

        write_csharp_report(
            self.root,
            current,
            current["state_revision"],
            campaign_id="BDC-2026-999",
        )
        with self.assertRaises(StaleDataError):
            build_dashboard_state(self.root)

        write_csharp_report(self.root, current, current["state_revision"])
        update_active_case(self.root, now=BASE_TIME + timedelta(minutes=4))
        self.assertEqual(build_dashboard_state(self.root)["shared"]["case_id"], CASE_A)
        system_path = (
            self.root / "cases" / "state" / CASE_A / "system_status.json"
        )
        stale_system = load_json_document(system_path)
        stale_system["state_revision"] = current["state_revision"] - 1
        atomic_write_json(system_path, stale_system)
        with self.assertRaises(StaleDataError):
            build_dashboard_state(self.root)

        broken = dict(current)
        broken["current_stage"] = "RANDOM_STAGE"
        with self.assertRaises(StateValidationError):
            validate_active_case(broken)

    def test_evidence_aliases_csv_migration_and_index_idempotence(self) -> None:
        case = case_payload(CASE_A)
        values = environment_values(case)
        self.assertEqual(values["device"], case["device_family"])
        self.assertEqual(values["platform"], case["affected_platform"])
        self.assertEqual(values["zone"], case["network_zone"])
        items = generate_evidence_items(case)
        self.assertEqual(len(items), case["evidence_count"])
        self.assertTrue(all(item["source_system"] == case["device_family"] for item in items))
        self.assertEqual(
            artifact_path_for_type("Biomedical Device Configuration"),
            "artifacts/device_configuration.json",
        )
        self.assertEqual(
            artifact_path_for_item({"artifact_type": "Biomedical Device Configuration"}),
            "artifacts/device_configuration.json",
        )

        log_path = self.root / "evidence" / "evidence_log.csv"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_row = ["EV-00001", "2026-08-20", CASE_A, "Firewall Log", "legacy"]
        former_row = [
            "EV-00002",
            CASE_A,
            "2026-08-21",
            "Persistent Case Test",
            "SECRET",
            "Access Control Log",
            "Platform",
            "Device",
            "Analyst",
            "Collected",
        ]
        with log_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(LEGACY_HEADER)
            writer.writerow(legacy_row)
            writer.writerow(former_row)
        raw_before = log_path.read_bytes()

        rows, migrated = ensure_compatible_evidence_log(log_path)
        self.assertTrue(migrated)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][:5], legacy_row)
        self.assertEqual(
            rows[1][0:4],
            ["EV-00002", "2026-08-21", CASE_A, "Access Control Log"],
        )
        self.assertEqual(
            list(csv.reader(log_path.read_text(encoding="utf-8").splitlines()))[0],
            V2_HEADER,
        )
        backups = list(log_path.parent.glob("evidence_log.csv.pre-v2-*.bak"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(
            hashlib.sha256(backups[0].read_bytes()).digest(),
            hashlib.sha256(raw_before).digest(),
        )

        _, migrated_again = ensure_compatible_evidence_log(log_path)
        self.assertFalse(migrated_again)
        added = append_case_index(case, log_path)
        self.assertIsNone(added)

        unknown_path = self.root / "evidence" / "unknown.csv"
        unknown_path.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
        original = unknown_path.read_bytes()
        with self.assertRaises(ValueError):
            ensure_compatible_evidence_log(unknown_path)
        self.assertEqual(unknown_path.read_bytes(), original)

    def test_per_case_evidence_and_correlations_are_preserved_on_repeat_run(self) -> None:
        created = self.create_case_a().case
        original_directory = Path.cwd()
        try:
            os.chdir(self.root)
            generate_evidence_repository_main()
            correlate_evidence_main()
            manifest_path = (
                self.root / "evidence" / CASE_A / "evidence_manifest.json"
            )
            correlations_path = (
                self.root / "evidence" / CASE_A / "evidence_correlations.json"
            )
            first_manifest = manifest_path.read_bytes()
            first_correlations = correlations_path.read_bytes()

            generate_evidence_repository_main()
            correlate_evidence_main()
        finally:
            os.chdir(original_directory)

        manifest = load_json_document(manifest_path)
        self.assertEqual(manifest["case_id"], CASE_A)
        self.assertEqual(manifest["evidence_count"], created["evidence_count"])
        self.assertTrue(
            all(item["source_system"] == created["device_family"] for item in manifest["evidence_items"])
        )
        self.assertTrue(
            all(item["platform"] == created["affected_platform"] for item in manifest["evidence_items"])
        )
        self.assertTrue(
            all(item["zone"] == created["network_zone"] for item in manifest["evidence_items"])
        )
        self.assertEqual(manifest_path.read_bytes(), first_manifest)
        self.assertEqual(correlations_path.read_bytes(), first_correlations)


if __name__ == "__main__":
    unittest.main()
