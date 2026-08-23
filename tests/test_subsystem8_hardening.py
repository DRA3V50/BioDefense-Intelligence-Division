from __future__ import annotations

import copy
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


PRODUCTION_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PRODUCTION_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from archive_case import archive_terminal_case
from case_lifecycle import (
    ensure_active_case,
    load_validated_artifact_snapshot,
    record_problem_review_outcome,
    update_active_case,
)
from case_state import (
    CaseStateError,
    MalformedStateError,
    StaleDataError,
    StateValidationError,
    append_case_event,
    atomic_write_json,
    build_relationships,
    build_system_status,
    csharp_level,
    current_case_path,
    iso_timestamp,
    load_active_case,
    load_json_document,
    normalize_case_metadata,
    relationship_fingerprint,
    save_active_case,
    synchronize_anomaly_history,
    synchronize_relationships,
    synchronize_threat_history,
    threat_display_level,
    validate_active_case,
    validate_support_state,
)
from dashboard_state import build_dashboard_state
from generate_evidence_repository import main as generate_evidence_repository_main
from update_evidence import LEGACY_HEADER, V2_HEADER, ensure_compatible_evidence_log


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


def write_manifest(root: Path, case: dict, review_status: str = "REVIEWED") -> None:
    directory = root / "evidence" / case["case_id"]
    items = []
    for number in range(1, case["evidence_count"] + 1):
        items.append(
            {
                "evidence_id": f"{case['case_id']}-EV-{number:04d}",
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
        directory / "evidence_manifest.json",
        {
            "schema_version": 2,
            "case_id": case["case_id"],
            "generated_at": iso_timestamp(BASE_TIME),
            "evidence_count": len(items),
            "evidence_items": items,
        },
    )


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
    *,
    score: int = 71,
    revision: int | None = None,
    generated_at: str = "2026-08-21 12:10 UTC",
) -> None:
    atomic_write_json(
        root / "reports" / "bioterror_threat_score_csharp.json",
        {
            "generatedAt": generated_at,
            "investigation": {
                "caseId": case["case_id"],
                "campaignId": case["campaign_id"],
                "caseRevision": case["state_revision"]
                if revision is None
                else revision,
            },
            "assessment": {
                "overallScore": score,
                "overallLevel": csharp_level(score),
            },
        },
    )


def make_terminal_case(case_id: str = CASE_A) -> dict:
    case, _ = normalize_case_metadata(case_payload(case_id), BASE_TIME)
    case.update(
        {
            "status": "RESOLVED",
            "current_stage": "PROBLEM_REVIEW",
            "stage_updated_at": iso_timestamp(BASE_TIME),
            "lifecycle_status": "RESOLVED",
            "terminal_state": "RESOLVED",
            "terminal_at": iso_timestamp(BASE_TIME),
            "archive_status": "PENDING",
            "archived_at": None,
            "problem_review_outcome": "RESOLVED",
            "problem_reviewed_at": iso_timestamp(BASE_TIME),
            "state_revision": 1,
        }
    )
    validate_active_case(case)
    return case


class Subsystem8HardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        write_operation(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_case(self, case_id: str = CASE_A) -> dict:
        return ensure_active_case(
            lambda: case_payload(case_id), self.root, now=BASE_TIME
        ).case

    def test_legacy_current_case_migrates_once_without_losing_fields(self) -> None:
        legacy = case_payload()
        atomic_write_json(current_case_path(self.root), legacy)

        first = ensure_active_case(
            lambda: self.fail("A legacy active case must not be replaced."),
            self.root,
            now=BASE_TIME,
        )
        migrated = first.case
        self.assertTrue(first.migrated)
        for field, value in legacy.items():
            self.assertEqual(migrated[field], value)
        self.assertEqual(migrated["case_id"], CASE_A)
        self.assertEqual(migrated["campaign_id"], CAMPAIGN)
        self.assertEqual(migrated["current_stage"], "CASE_SCAN")
        self.assertEqual(migrated["state_revision"], 1)
        self.assertEqual(migrated["created_at"], iso_timestamp(BASE_TIME))
        self.assertEqual(migrated["state_migrated_at"], iso_timestamp(BASE_TIME))

        second = ensure_active_case(
            lambda: self.fail("A migrated active case must be reused."),
            self.root,
            now=BASE_TIME + timedelta(minutes=1),
        )
        self.assertFalse(second.migrated)
        self.assertEqual(second.case["state_revision"], 1)
        self.assertEqual(second.case["created_at"], iso_timestamp(BASE_TIME))

    def test_state_revision_rejects_same_revision_mutations_and_jumps(self) -> None:
        case = self.create_case()
        unchanged = copy.deepcopy(case)
        validate_active_case(unchanged, previous=case)

        same_revision_change = copy.deepcopy(case)
        same_revision_change["risk_score"] = 72
        same_revision_change["updated_at"] = iso_timestamp(
            BASE_TIME + timedelta(minutes=1)
        )
        with self.assertRaises(StateValidationError):
            validate_active_case(same_revision_change, previous=case)

        jumped_revision = copy.deepcopy(case)
        jumped_revision["risk_score"] = 72
        jumped_revision["updated_at"] = iso_timestamp(
            BASE_TIME + timedelta(minutes=1)
        )
        jumped_revision["state_revision"] = case["state_revision"] + 2
        with self.assertRaises(StateValidationError):
            validate_active_case(jumped_revision, previous=case)

        write_manifest(self.root, case, review_status="Pending Analyst Review")
        transitioned = update_active_case(
            self.root, now=BASE_TIME + timedelta(minutes=1)
        )
        self.assertEqual(transitioned.transition, "EVIDENCE_REVIEW")
        self.assertEqual(
            transitioned.case["state_revision"], case["state_revision"] + 1
        )
        no_change = update_active_case(self.root, now=BASE_TIME + timedelta(minutes=2))
        self.assertIsNone(no_change.transition)
        self.assertEqual(
            no_change.case["state_revision"], transitioned.case["state_revision"]
        )

    def test_terminal_transition_changes_revision_once_and_repeated_evaluation_does_not(self) -> None:
        case = self.create_case()
        prepared = copy.deepcopy(case)
        prepared["current_stage"] = "PROBLEM_REVIEW"
        prepared["stage_updated_at"] = iso_timestamp(BASE_TIME + timedelta(minutes=1))
        prepared["updated_at"] = iso_timestamp(BASE_TIME + timedelta(minutes=1))
        prepared["state_revision"] = case["state_revision"] + 1
        save_active_case(prepared, self.root, previous=case)

        reviewed = record_problem_review_outcome(
            "RESOLVED", self.root, now=BASE_TIME + timedelta(minutes=2)
        )
        self.assertEqual(reviewed["state_revision"], prepared["state_revision"] + 1)
        terminal = update_active_case(self.root, now=BASE_TIME + timedelta(minutes=3))
        self.assertEqual(terminal.transition, "RESOLVED")
        self.assertEqual(
            terminal.case["state_revision"], reviewed["state_revision"] + 1
        )
        rerun = update_active_case(self.root, now=BASE_TIME + timedelta(minutes=4))
        self.assertIsNone(rerun.transition)
        self.assertEqual(rerun.case["state_revision"], terminal.case["state_revision"])

    def test_system_status_uses_count_for_queue_depth_and_is_deterministic(self) -> None:
        case = self.create_case()
        first = build_system_status(case, event_count=1, threat=None)
        second = build_system_status(case, event_count=1, threat=None)
        self.assertEqual(first, second)
        self.assertEqual(first["telemetry"]["queue_depth"]["unit"], "count")
        for name in ("cpu_percent", "memory_percent", "network_percent", "disk_percent"):
            self.assertEqual(first["telemetry"][name]["unit"], "percent")
            self.assertTrue(
                all(0 <= value <= 100 for value in first["telemetry"][name]["samples"])
            )
        self.assertTrue(
            all(value >= 0 for value in first["telemetry"]["queue_depth"]["samples"])
        )
        changed_case = copy.deepcopy(case)
        changed_case["state_revision"] += 1
        changed = build_system_status(changed_case, event_count=1, threat=None)
        self.assertNotEqual(first["source_fingerprint"], changed["source_fingerprint"])

        system_path = self.root / "cases" / "state" / CASE_A / "system_status.json"
        system = load_json_document(system_path)
        system["telemetry"]["queue_depth"]["unit"] = "percent"
        atomic_write_json(system_path, system)
        with self.assertRaises(StateValidationError):
            validate_support_state(case, self.root)

    def test_threat_threshold_boundaries_and_explicit_adapter_contract(self) -> None:
        expected = {
            19: ("LOW", "LOW"),
            20: ("GUARDED", "LOW"),
            44: ("GUARDED", "MEDIUM"),
            45: ("ELEVATED", "MEDIUM"),
            69: ("ELEVATED", "HIGH"),
            70: ("HIGH", "HIGH"),
            79: ("HIGH", "HIGH"),
            80: ("HIGH", "CRITICAL"),
            84: ("HIGH", "CRITICAL"),
            85: ("CRITICAL", "CRITICAL"),
            100: ("CRITICAL", "CRITICAL"),
        }
        for score, (canonical, display) in expected.items():
            self.assertEqual(csharp_level(score), canonical)
            self.assertEqual(threat_display_level(score), display)

        case = self.create_case()
        write_manifest(self.root, case, review_status="Pending Analyst Review")
        write_csharp_report(self.root, case, score=80)
        ensure_active_case(
            lambda: self.fail("The existing case must remain active."),
            self.root,
            now=BASE_TIME + timedelta(minutes=1),
        )
        state = build_dashboard_state(self.root)
        threat = state["threat_monitor"]["threat"]
        self.assertEqual(threat["score"], 80)
        self.assertEqual(threat["canonical_classification"], "HIGH")
        self.assertEqual(threat["display_level_for_subsystem_06"], "CRITICAL")
        self.assertNotIn("threat_score", state["threat_monitor"])

    def test_event_anomaly_and_threat_history_idempotency(self) -> None:
        case = self.create_case()
        events_path = self.root / "cases" / "state" / CASE_A / "events.json"
        before = events_path.read_bytes()
        with self.assertRaises(StateValidationError):
            append_case_event(
                case,
                event_type="TEST",
                message="Invalid severity.",
                severity="UNTRUSTED",
                idempotency_key="invalid-severity",
                timestamp=BASE_TIME + timedelta(minutes=1),
                root=self.root,
            )
        self.assertEqual(events_path.read_bytes(), before)
        with self.assertRaises(StateValidationError):
            append_case_event(
                case,
                event_type="TEST",
                message="Out-of-order timestamp.",
                severity="INFO",
                idempotency_key="out-of-order",
                timestamp=BASE_TIME - timedelta(seconds=1),
                root=self.root,
            )
        self.assertEqual(events_path.read_bytes(), before)

        event = append_case_event(
            case,
            event_type="TEST",
            message="Deterministic event.",
            severity="INFO",
            idempotency_key="same-event",
            timestamp=BASE_TIME + timedelta(minutes=1),
            root=self.root,
        )
        duplicate = append_case_event(
            case,
            event_type="TEST",
            message="Deterministic event.",
            severity="INFO",
            idempotency_key="same-event",
            timestamp=BASE_TIME + timedelta(minutes=1),
            root=self.root,
        )
        self.assertEqual(event["event_id"], duplicate["event_id"])
        synchronize_anomaly_history(case, self.root)
        first_history = load_json_document(
            self.root / "cases" / "state" / CASE_A / "anomaly_history.json"
        )
        synchronize_anomaly_history(case, self.root)
        second_history = load_json_document(
            self.root / "cases" / "state" / CASE_A / "anomaly_history.json"
        )
        self.assertEqual(first_history, second_history)
        self.assertEqual(
            len(second_history["samples"]),
            len(load_json_document(events_path)["events"]),
        )

        write_csharp_report(self.root, case, generated_at="2026-08-21 12:10 UTC")
        synchronize_threat_history(case, self.root)
        write_csharp_report(self.root, case, generated_at="2026-08-21 12:11 UTC")
        synchronize_threat_history(case, self.root)
        threats = load_json_document(
            self.root / "cases" / "state" / CASE_A / "threat_history.json"
        )
        self.assertEqual(len(threats["samples"]), 1)

    def test_relationship_derivation_rejects_fabricated_current_revision_state(self) -> None:
        case = self.create_case()
        write_manifest(self.root, case)
        write_correlations(self.root, case)
        write_csharp_report(self.root, case)
        artifacts = load_validated_artifact_snapshot(case, self.root)
        from case_state import load_normalized_csharp_threat

        threat = load_normalized_csharp_threat(case, self.root)
        first = synchronize_relationships(
            case,
            self.root,
            evidence_count=artifacts.evidence_count,
            correlation_count=artifacts.correlation_count,
            threat=threat,
        )
        second = synchronize_relationships(
            case,
            self.root,
            evidence_count=artifacts.evidence_count,
            correlation_count=artifacts.correlation_count,
            threat=threat,
        )
        self.assertEqual(first, second)
        expected = build_relationships(
            case,
            evidence_count=artifacts.evidence_count,
            correlation_count=artifacts.correlation_count,
            threat=threat,
        )
        self.assertEqual(first["source_fingerprint"], relationship_fingerprint(expected))

        path = self.root / "cases" / "state" / CASE_A / "relationships.json"
        forged = load_json_document(path)
        forged["relationships"][3]["attributes"]["count"] = 999
        atomic_write_json(path, forged)
        with self.assertRaises(StateValidationError):
            validate_support_state(
                case,
                self.root,
                evidence_count=artifacts.evidence_count,
                correlation_count=artifacts.correlation_count,
                threat=threat,
                validate_relationship_inputs=True,
            )

    def test_strict_correlation_case_linkage_rejects_missing_case_id(self) -> None:
        case = self.create_case()
        write_manifest(self.root, case)
        write_correlations(self.root, case)
        path = self.root / "evidence" / CASE_A / "evidence_correlations.json"
        correlations = load_json_document(path)
        correlations["correlations"][0]["case_id"] = None
        atomic_write_json(path, correlations)
        with self.assertRaises(StaleDataError):
            load_validated_artifact_snapshot(case, self.root)

    def test_evidence_manifest_is_final_commit_marker_and_partial_bundle_is_preserved(self) -> None:
        case = self.create_case()
        original_directory = Path.cwd()
        try:
            os.chdir(self.root)
            with mock.patch(
                "generate_evidence_repository.write_analyst_notes",
                side_effect=RuntimeError("injected support-file failure"),
            ):
                with self.assertRaises(RuntimeError):
                    generate_evidence_repository_main()
        finally:
            os.chdir(original_directory)
        manifest_path = self.root / "evidence" / CASE_A / "evidence_manifest.json"
        self.assertFalse(manifest_path.exists())

        write_manifest(self.root, case)
        (self.root / "evidence" / CASE_A / "chain_of_custody.csv").unlink()
        partial_bytes = manifest_path.read_bytes()
        try:
            os.chdir(self.root)
            with self.assertRaises(ValueError):
                generate_evidence_repository_main()
        finally:
            os.chdir(original_directory)
        self.assertEqual(manifest_path.read_bytes(), partial_bytes)

    def test_csv_migration_is_idempotent_and_malformed_or_invalid_state_is_rejected(self) -> None:
        log_path = self.root / "evidence" / "evidence_log.csv"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_row = ["EV-00001", "2026-08-20", CASE_A, "Firewall Log", "legacy"]
        with log_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(LEGACY_HEADER)
            writer.writerow(legacy_row)
        rows, migrated = ensure_compatible_evidence_log(log_path)
        self.assertTrue(migrated)
        self.assertEqual(rows[0][:5], legacy_row)
        self.assertEqual(
            list(csv.reader(log_path.read_text(encoding="utf-8").splitlines()))[0],
            V2_HEADER,
        )
        _, migrated_again = ensure_compatible_evidence_log(log_path)
        self.assertFalse(migrated_again)
        self.assertEqual(len(list(log_path.parent.glob("evidence_log.csv.pre-v2-*.bak"))), 1)

        invalid = case_payload()
        invalid["current_stage"] = "NOT_A_WORKFLOW_STAGE"
        atomic_write_json(current_case_path(self.root), invalid)
        with self.assertRaises(StateValidationError):
            ensure_active_case(lambda: self.fail("Invalid state must not reset."), self.root)

        malformed_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, malformed_root, ignore_errors=True)
        write_operation(malformed_root)
        malformed_path = current_case_path(malformed_root)
        malformed_path.parent.mkdir(parents=True, exist_ok=True)
        malformed_path.write_text("{ invalid", encoding="utf-8")
        with self.assertRaises(MalformedStateError):
            ensure_active_case(lambda: case_payload(), malformed_root, now=BASE_TIME)
        self.assertEqual(malformed_path.read_text(encoding="utf-8"), "{ invalid")
        self.assertEqual(
            len(list(malformed_path.parent.glob("current_case.malformed-*.json"))),
            1,
        )

    def _run_cli(self, root: Path, relative_program: str, *args: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, relative_program, *args],
            cwd=root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def _copy_script_chain_fixture(self, root: Path) -> None:
        names = (
            "case_state.py",
            "case_lifecycle.py",
            "generate_case.py",
            "update_operation.py",
            "update_case_progress.py",
            "update_case_status.py",
            "generate_evidence_repository.py",
            "correlate_evidence.py",
            "update_evidence.py",
            "archive_case.py",
            "update_history.py",
            "dashboard_state.py",
        )
        destination = root / "scripts"
        destination.mkdir(parents=True, exist_ok=True)
        for name in names:
            shutil.copy2(SCRIPTS / name, destination / name)
        tools = root / "tools"
        tools.mkdir(parents=True, exist_ok=True)
        for name in ("Program.cs", "BioterrorThreatScoringEngine.csproj"):
            shutil.copy2(PRODUCTION_ROOT / "tools" / name, tools / name)

    def test_actual_generate_case_entry_point_reuses_and_enforces_verified_archive_gate(self) -> None:
        fixture_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, fixture_root, ignore_errors=True)
        self._copy_script_chain_fixture(fixture_root)
        write_operation(fixture_root)

        created = self._run_cli(fixture_root, "scripts/generate_case.py")
        self.assertEqual(created.returncode, 0, created.stderr)
        first = load_json_document(current_case_path(fixture_root))
        self.assertRegex(first["case_id"], r"^BID-\d{4}-\d{4}$")
        first_bytes = current_case_path(fixture_root).read_bytes()
        reused = self._run_cli(fixture_root, "scripts/generate_case.py")
        self.assertEqual(reused.returncode, 0, reused.stderr)
        self.assertEqual(load_json_document(current_case_path(fixture_root))["case_id"], first["case_id"])
        self.assertEqual(current_case_path(fixture_root).read_bytes(), first_bytes)

        terminal_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, terminal_root, ignore_errors=True)
        self._copy_script_chain_fixture(terminal_root)
        write_operation(terminal_root)
        terminal = make_terminal_case()
        atomic_write_json(current_case_path(terminal_root), terminal)

        blocked = self._run_cli(terminal_root, "scripts/generate_case.py")
        self.assertEqual(blocked.returncode, 0, blocked.stderr)
        self.assertEqual(load_active_case(terminal_root)["case_id"], CASE_A)

        unverified = load_active_case(terminal_root)
        unverified["archive_status"] = "ARCHIVED"
        atomic_write_json(current_case_path(terminal_root), unverified)
        still_blocked = self._run_cli(terminal_root, "scripts/generate_case.py")
        self.assertEqual(still_blocked.returncode, 0, still_blocked.stderr)
        self.assertEqual(load_active_case(terminal_root)["case_id"], CASE_A)

        pending = load_active_case(terminal_root)
        pending["archive_status"] = "PENDING"
        atomic_write_json(current_case_path(terminal_root), pending)
        write_manifest(terminal_root, pending)
        write_correlations(terminal_root, pending)
        write_custody(terminal_root, pending)
        archived = self._run_cli(terminal_root, "scripts/archive_case.py")
        self.assertEqual(archived.returncode, 0, archived.stderr)
        self.assertEqual(load_active_case(terminal_root)["archive_status"], "ARCHIVED")
        history_path = terminal_root / "data" / "investigation_history.csv"
        archive_json = terminal_root / "cases" / "archive" / "json" / f"{CASE_A}.json"
        history_before = history_path.read_bytes()
        archive_before = archive_json.read_bytes()
        archived_again = self._run_cli(terminal_root, "scripts/archive_case.py")
        self.assertEqual(archived_again.returncode, 0, archived_again.stderr)
        self.assertEqual(history_path.read_bytes(), history_before)
        self.assertEqual(archive_json.read_bytes(), archive_before)

        replacement = self._run_cli(terminal_root, "scripts/generate_case.py")
        self.assertEqual(replacement.returncode, 0, replacement.stderr)
        self.assertNotEqual(load_active_case(terminal_root)["case_id"], CASE_A)

    @unittest.skipUnless(shutil.which("dotnet"), "dotnet SDK is required for the C# chain test")
    def test_real_production_script_chain_dry_run_accepts_valid_and_rejects_stale_data(self) -> None:
        fixture_root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, fixture_root, ignore_errors=True)
        self._copy_script_chain_fixture(fixture_root)
        write_operation(fixture_root)

        for program in (
            "scripts/generate_case.py",
            "scripts/update_operation.py",
            "scripts/update_case_progress.py",
            "scripts/update_case_status.py",
            "scripts/generate_evidence_repository.py",
            "scripts/correlate_evidence.py",
            "scripts/archive_case.py",
            "scripts/update_history.py",
            "scripts/update_evidence.py",
        ):
            result = self._run_cli(fixture_root, program)
            self.assertEqual(result.returncode, 0, f"{program}: {result.stderr}")

        build_root = fixture_root / "build"
        environment = os.environ.copy()
        environment["DOTNET_CLI_HOME"] = str(build_root / "cli")
        environment["NUGET_PACKAGES"] = str(build_root / "packages")
        build = subprocess.run(
            [
                "dotnet",
                "build",
                "tools/BioterrorThreatScoringEngine.csproj",
                "--nologo",
                "-p:BaseOutputPath=" + str(build_root / "bin") + os.sep,
                "-p:BaseIntermediateOutputPath=" + str(build_root / "obj") + os.sep,
            ],
            cwd=fixture_root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
        assemblies = list((build_root / "bin").rglob("BioterrorThreatScoringEngine.dll"))
        self.assertEqual(len(assemblies), 1)
        scored = subprocess.run(
            ["dotnet", str(assemblies[0])],
            cwd=fixture_root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(scored.returncode, 0, scored.stdout + scored.stderr)

        refreshed = self._run_cli(fixture_root, "scripts/generate_case.py")
        self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
        dashboard = self._run_cli(fixture_root, "scripts/dashboard_state.py")
        self.assertEqual(dashboard.returncode, 0, dashboard.stderr)
        dashboard_state = json.loads(dashboard.stdout)
        case = load_active_case(fixture_root)
        manifest = load_json_document(
            fixture_root / "evidence" / case["case_id"] / "evidence_manifest.json"
        )
        correlations = load_json_document(
            fixture_root / "evidence" / case["case_id"] / "evidence_correlations.json"
        )
        report_path = fixture_root / "reports" / "bioterror_threat_score_csharp.json"
        report = load_json_document(report_path)
        self.assertEqual(dashboard_state["shared"]["case_id"], case["case_id"])
        self.assertEqual(manifest["case_id"], case["case_id"])
        self.assertEqual(correlations["case_id"], case["case_id"])
        self.assertEqual(report["investigation"]["caseId"], case["case_id"])
        self.assertEqual(report["investigation"]["campaignId"], case["campaign_id"])
        self.assertEqual(report["investigation"]["caseRevision"], case["state_revision"])

        report["investigation"]["caseRevision"] -= 1
        atomic_write_json(report_path, report)
        stale = self._run_cli(fixture_root, "scripts/dashboard_state.py")
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("state revision", stale.stderr)


if __name__ == "__main__":
    unittest.main()
