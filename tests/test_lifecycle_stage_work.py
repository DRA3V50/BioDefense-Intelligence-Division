from __future__ import annotations

import copy
import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys


PRODUCTION_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PRODUCTION_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from archive_case import archive_terminal_case
from case_lifecycle import ensure_active_case, update_active_case
from case_state import (
    atomic_write_json,
    csharp_level,
    current_case_path,
    events_path,
    iso_timestamp,
    load_active_case,
    load_json_document,
    save_active_case,
)
from process_active_case_stage import process_active_case_stage


UTC = timezone.utc
BASE_TIME = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
CASE_A = "BID-2026-3131"
CASE_B = "BID-2026-4242"
CAMPAIGN = "BDC-2026-042"


def case_payload(
    case_id: str = CASE_A,
    *,
    evidence_count: int = 22,
    severity: str = "LOW",
) -> dict:
    return {
        "case_id": case_id,
        "campaign_id": CAMPAIGN,
        "date": "2026-08-21",
        "operation": "Lifecycle Stage Work Fixture",
        "classification": "Laboratory Network Intrusion",
        "threat_family": "Test Family",
        "severity": severity,
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
        "evidence_count": evidence_count,
        "ioc_count": 3,
        "initial_access": "Credential Misuse",
        "lead_analyst": "Lifecycle Test Analyst",
        "priority": "HIGH",
        "recommended_action": "Complete deterministic lifecycle review.",
        "assessment": "A persisted test assessment is available.",
    }


def write_operation(root: Path) -> None:
    atomic_write_json(
        root / "operations" / "active_operation.json",
        {
            "campaign_id": CAMPAIGN,
            "operation": "Lifecycle Stage Work Fixture",
            "campaign_phase": "Detection",
            "containment_level": "Controlled",
            "next_objective": "Review evidence",
        },
    )


def write_manifest(root: Path, case: dict, review_status: str) -> None:
    items = []
    for number in range(1, int(case["evidence_count"]) + 1):
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
                "sha256": f"fixture-sha-{number:04d}",
                "classification": case["classification"],
                "review_status": review_status,
            }
        )
    atomic_write_json(
        root / "evidence" / case["case_id"] / "evidence_manifest.json",
        {
            "schema_version": 2,
            "case_id": case["case_id"],
            "generated_at": iso_timestamp(BASE_TIME),
            "evidence_count": len(items),
            "evidence_items": items,
        },
    )


def write_correlations(root: Path, case: dict, analysis_status: str) -> None:
    manifest = load_json_document(
        root / "evidence" / case["case_id"] / "evidence_manifest.json"
    )
    assert manifest is not None
    correlations = [
        {
            "case_id": case["case_id"],
            "evidence_id": item["evidence_id"],
            "artifact_type": item["artifact_type"],
            "artifact_path": item["artifact_path"],
            "related_indicator": f"IOC-{number:04d}",
            "finding": "Laboratory System Modification",
            "confidence": 88,
            "analysis_status": analysis_status,
        }
        for number, item in enumerate(manifest["evidence_items"], start=1)
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
            fieldnames=(
                "evidence_id",
                "case_id",
                "event_type",
                "performed_by",
                "timestamp",
                "storage_location",
                "integrity_status",
            ),
        )
        writer.writeheader()
        for number in range(1, int(case["evidence_count"]) + 1):
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
    score: int | None,
    *,
    report_case_id: str | None = None,
    report_revision: int | None = None,
) -> None:
    assessment: dict[str, object] = {}
    if score is not None:
        assessment["overallScore"] = score
        assessment["overallLevel"] = (
            csharp_level(score) if isinstance(score, int) and 0 <= score <= 100 else "LOW"
        )
    atomic_write_json(
        root / "reports" / "bioterror_threat_score_csharp.json",
        {
            "generatedAt": "2026-08-21 12:01 UTC",
            "investigation": {
                "caseId": report_case_id or case["case_id"],
                "caseRevision": (
                    int(case["state_revision"])
                    if report_revision is None
                    else report_revision
                ),
                "campaignId": case["campaign_id"],
            },
            "assessment": assessment,
        },
    )


class LifecycleStageWorkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        write_operation(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_case(
        self,
        *,
        evidence_count: int = 22,
        severity: str = "LOW",
        case_id: str = CASE_A,
    ) -> dict:
        return ensure_active_case(
            lambda: case_payload(
                case_id, evidence_count=evidence_count, severity=severity
            ),
            self.root,
            now=BASE_TIME,
        ).case

    def prepare_problem_review(
        self, *, score: int | None, severity: str = "LOW", mismatched_case: bool = False
    ) -> dict:
        case = self.create_case(evidence_count=3, severity="LOW")
        write_manifest(self.root, case, "Reviewed")
        write_correlations(self.root, case, "Validated")
        prepared = copy.deepcopy(case)
        prepared["severity"] = severity
        prepared["current_stage"] = "PROBLEM_REVIEW"
        prepared["stage_updated_at"] = iso_timestamp(BASE_TIME + timedelta(minutes=1))
        prepared["assessment_completed_at"] = iso_timestamp(
            BASE_TIME + timedelta(minutes=1)
        )
        prepared["updated_at"] = iso_timestamp(BASE_TIME + timedelta(minutes=1))
        prepared["state_revision"] = int(case["state_revision"]) + 1
        save_active_case(prepared, self.root, previous=case)
        write_csharp_report(
            self.root,
            prepared,
            score,
            report_case_id="BID-2026-9999" if mismatched_case else None,
        )
        return prepared

    def test_evidence_review_batches_are_deterministic_and_preserve_reviewed_records(self) -> None:
        case = self.create_case()
        write_manifest(self.root, case, "Pending Analyst Review")
        write_correlations(self.root, case, "Correlated")
        transitioned = update_active_case(self.root, now=BASE_TIME + timedelta(minutes=1))
        self.assertEqual(transitioned.transition, "EVIDENCE_REVIEW")
        stage_updated_at = transitioned.case["stage_updated_at"]
        first_reviewed_at: dict[str, str] = {}

        for batch_index, expected_size in enumerate((4, 4, 4, 4, 4, 2), start=1):
            before = load_active_case(self.root)
            assert before is not None
            result = process_active_case_stage(
                self.root, now=BASE_TIME + timedelta(minutes=1 + batch_index)
            )
            after = load_active_case(self.root)
            assert after is not None
            self.assertTrue(result.changed)
            self.assertEqual(result.action, "EVIDENCE_REVIEW_BATCH")
            self.assertEqual(len(result.processed_ids), expected_size)
            self.assertEqual(after["current_stage"], "EVIDENCE_REVIEW")
            self.assertEqual(after["stage_updated_at"], stage_updated_at)
            self.assertEqual(after["state_revision"], before["state_revision"] + 1)
            self.assertGreater(after["updated_at"], before["updated_at"])
            if batch_index == 1:
                manifest = load_json_document(
                    self.root / "evidence" / CASE_A / "evidence_manifest.json"
                )
                assert manifest is not None
                first_reviewed_at = {
                    item["evidence_id"]: item["reviewed_at"]
                    for item in manifest["evidence_items"][:4]
                }

        manifest = load_json_document(
            self.root / "evidence" / CASE_A / "evidence_manifest.json"
        )
        assert manifest is not None
        self.assertTrue(
            all(item["review_status"] == "Reviewed" for item in manifest["evidence_items"])
        )
        self.assertEqual(
            {
                item["evidence_id"]: item["reviewed_at"]
                for item in manifest["evidence_items"][:4]
            },
            first_reviewed_at,
        )
        self.assertTrue(
            all(
                item["sha256"] == f"fixture-sha-{number:04d}"
                and item["collected_at"] == iso_timestamp(BASE_TIME)
                for number, item in enumerate(manifest["evidence_items"], start=1)
            )
        )
        events = load_json_document(events_path(CASE_A, self.root))
        assert events is not None
        review_events = [
            event
            for event in events["events"]
            if event["event_type"] == "EVIDENCE_REVIEW_PROGRESS"
        ]
        self.assertEqual(len(review_events), 6)
        self.assertEqual(
            len({event["idempotency_key"] for event in review_events}), 6
        )

        validation = update_active_case(self.root, now=BASE_TIME + timedelta(minutes=9))
        self.assertEqual(validation.transition, "VALIDATION")

    def test_validation_requires_validated_records_and_batches_by_stable_evidence_id(self) -> None:
        case = self.create_case()
        write_manifest(self.root, case, "Reviewed")
        write_correlations(self.root, case, "Correlated")
        self.assertEqual(
            update_active_case(self.root, now=BASE_TIME + timedelta(minutes=1)).transition,
            "EVIDENCE_REVIEW",
        )
        entered_validation = update_active_case(
            self.root, now=BASE_TIME + timedelta(minutes=2)
        )
        self.assertEqual(entered_validation.transition, "VALIDATION")
        self.assertIsNone(
            update_active_case(self.root, now=BASE_TIME + timedelta(minutes=3)).transition
        )
        stage_updated_at = entered_validation.case["stage_updated_at"]
        first_validated_at: dict[str, str] = {}

        for batch_index, expected_size in enumerate((8, 8, 6), start=1):
            before = load_active_case(self.root)
            assert before is not None
            result = process_active_case_stage(
                self.root, now=BASE_TIME + timedelta(minutes=3 + batch_index)
            )
            after = load_active_case(self.root)
            assert after is not None
            self.assertTrue(result.changed)
            self.assertEqual(result.action, "CORRELATION_VALIDATION_BATCH")
            self.assertEqual(len(result.processed_ids), expected_size)
            self.assertEqual(tuple(sorted(result.processed_ids)), result.processed_ids)
            self.assertEqual(after["current_stage"], "VALIDATION")
            self.assertEqual(after["stage_updated_at"], stage_updated_at)
            self.assertEqual(after["state_revision"], before["state_revision"] + 1)
            if batch_index == 1:
                document = load_json_document(
                    self.root / "evidence" / CASE_A / "evidence_correlations.json"
                )
                assert document is not None
                first_validated_at = {
                    item["evidence_id"]: item["validated_at"]
                    for item in document["correlations"][:8]
                }

        document = load_json_document(
            self.root / "evidence" / CASE_A / "evidence_correlations.json"
        )
        assert document is not None
        self.assertTrue(
            all(item["analysis_status"] == "Validated" for item in document["correlations"])
        )
        self.assertEqual(
            {
                item["evidence_id"]: item["validated_at"]
                for item in document["correlations"][:8]
            },
            first_validated_at,
        )
        self.assertTrue(
            all(
                item["related_indicator"] == f"IOC-{number:04d}"
                for number, item in enumerate(document["correlations"], start=1)
            )
        )
        events = load_json_document(events_path(CASE_A, self.root))
        assert events is not None
        validation_events = [
            event
            for event in events["events"]
            if event["event_type"] == "CORRELATION_VALIDATION_PROGRESS"
        ]
        self.assertEqual(len(validation_events), 3)
        self.assertEqual(
            len({event["idempotency_key"] for event in validation_events}), 3
        )
        self.assertEqual(
            update_active_case(self.root, now=BASE_TIME + timedelta(minutes=7)).transition,
            "ASSESSMENT",
        )

    def test_terminal_disposition_boundaries_and_idempotent_audit_event(self) -> None:
        cases = (
            (0, "LOW", "CLOSED"),
            (19, "LOW", "CLOSED"),
            (0, "MODERATE", "RESOLVED"),
            (19, "MODERATE", "RESOLVED"),
            (20, "LOW", "RESOLVED"),
            (21, "LOW", "RESOLVED"),
            (59, "MODERATE", "RESOLVED"),
            (60, "LOW", "ESCALATED"),
            (100, "LOW", "ESCALATED"),
            (1, "HIGH", "ESCALATED"),
            (1, "CRITICAL", "ESCALATED"),
        )
        for score, severity, outcome in cases:
            with self.subTest(score=score, severity=severity, outcome=outcome):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    write_operation(root)
                    original_root = self.root
                    self.root = root
                    try:
                        prepared = self.prepare_problem_review(
                            score=score, severity=severity
                        )
                    finally:
                        self.root = original_root
                    result = process_active_case_stage(
                        root, now=BASE_TIME + timedelta(minutes=2)
                    )
                    self.assertTrue(result.changed)
                    self.assertEqual(result.outcome, outcome)
                    persisted = load_active_case(root)
                    assert persisted is not None
                    self.assertEqual(persisted["current_stage"], "PROBLEM_REVIEW")
                    self.assertEqual(persisted["lifecycle_status"], "ACTIVE")
                    events = load_json_document(events_path(CASE_A, root))
                    assert events is not None
                    disposition_events = [
                        event
                        for event in events["events"]
                        if event["event_type"] == "PROBLEM_REVIEW_OUTCOME_RECORDED"
                    ]
                    self.assertEqual(len(disposition_events), 1)
                    self.assertEqual(
                        disposition_events[0]["message"],
                        (
                            f"Problem review disposition: {outcome}; "
                            f"canonical_score={score}; severity={severity}; "
                            "policy=terminal-disposition-v1"
                        ),
                    )
                    repeat = process_active_case_stage(
                        root, now=BASE_TIME + timedelta(minutes=3)
                    )
                    self.assertFalse(repeat.changed)
                    events_after = load_json_document(events_path(CASE_A, root))
                    assert events_after is not None
                    self.assertEqual(events_after, events)

    def test_terminal_disposition_fails_closed_without_valid_authoritative_inputs(self) -> None:
        blockers = (
            (None, "LOW", False, False, "missing score"),
            (101, "LOW", False, False, "invalid score"),
            (21, "LOW", True, False, "mismatched case"),
            (21, "UNKNOWN", False, False, "unknown severity"),
            (21, "LOW", False, True, "incomplete prerequisites"),
        )
        for score, severity, mismatched_case, incomplete, label in blockers:
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    write_operation(root)
                    original_root = self.root
                    self.root = root
                    try:
                        prepared = self.prepare_problem_review(
                            score=score,
                            severity=severity,
                            mismatched_case=mismatched_case,
                        )
                        if incomplete:
                            manifest_path = (
                                root
                                / "evidence"
                                / prepared["case_id"]
                                / "evidence_manifest.json"
                            )
                            manifest = load_json_document(manifest_path)
                            assert manifest is not None
                            manifest["evidence_items"][0]["review_status"] = (
                                "Pending Analyst Review"
                            )
                            atomic_write_json(manifest_path, manifest)
                    finally:
                        self.root = original_root
                    before = current_case_path(root).read_bytes()
                    result = process_active_case_stage(
                        root, now=BASE_TIME + timedelta(minutes=2)
                    )
                    self.assertFalse(result.changed)
                    self.assertEqual(result.action, "BLOCKED")
                    self.assertEqual(current_case_path(root).read_bytes(), before)
                    persisted = load_active_case(root)
                    assert persisted is not None
                    self.assertEqual(persisted["current_stage"], "PROBLEM_REVIEW")
                    self.assertEqual(persisted["lifecycle_status"], "ACTIVE")

    def run_full_cycle(
        self, *, score: int, severity: str, expected_outcome: str
    ) -> None:
        case = self.create_case(severity=severity)
        write_manifest(self.root, case, "Pending Analyst Review")
        write_correlations(self.root, case, "Correlated")
        write_custody(self.root, case)
        transitions: list[str | None] = []
        stage_actions: list[str] = []

        for cycle in range(1, 14):
            now = BASE_TIME + timedelta(minutes=cycle)
            active = load_active_case(self.root)
            assert active is not None
            write_csharp_report(self.root, active, score)
            work = process_active_case_stage(self.root, now=now)
            stage_actions.append(work.action)
            lifecycle = update_active_case(self.root, now=now)
            transitions.append(lifecycle.transition)
            refreshed = load_active_case(self.root)
            assert refreshed is not None
            write_csharp_report(self.root, refreshed, score)
            if refreshed["lifecycle_status"] != "ACTIVE":
                archived, changed = archive_terminal_case(self.root, now=now)
                self.assertTrue(changed)
                self.assertEqual(archived["archive_status"], "ARCHIVED")

        terminal = load_active_case(self.root)
        assert terminal is not None
        self.assertEqual(terminal["case_id"], CASE_A)
        self.assertEqual(terminal["lifecycle_status"], expected_outcome)
        self.assertEqual(terminal["archive_status"], "ARCHIVED")
        self.assertEqual(stage_actions.count("EVIDENCE_REVIEW_BATCH"), 6)
        self.assertEqual(stage_actions.count("CORRELATION_VALIDATION_BATCH"), 3)
        self.assertEqual(stage_actions.count("ASSESSMENT_COMPLETED"), 1)
        self.assertEqual(stage_actions.count("PROBLEM_REVIEW_DISPOSITION"), 1)
        self.assertEqual(
            [transition for transition in transitions if transition],
            [
                "EVIDENCE_REVIEW",
                "VALIDATION",
                "ASSESSMENT",
                "PROBLEM_REVIEW",
                expected_outcome,
            ],
        )
        self.assertTrue(all(transition is None or isinstance(transition, str) for transition in transitions))

        next_cycle = ensure_active_case(
            lambda: case_payload(CASE_B, evidence_count=22, severity="LOW"),
            self.root,
            now=BASE_TIME + timedelta(minutes=14),
        )
        self.assertTrue(next_cycle.created)
        self.assertEqual(next_cycle.case["case_id"], CASE_B)
        self.assertEqual(next_cycle.case["current_stage"], "CASE_SCAN")

    def test_full_cycle_closes_in_fourteen_executions_and_creates_next_case_later(self) -> None:
        self.run_full_cycle(score=0, severity="LOW", expected_outcome="CLOSED")

    def test_full_cycle_resolves_in_fourteen_executions_and_creates_next_case_later(self) -> None:
        self.run_full_cycle(score=21, severity="LOW", expected_outcome="RESOLVED")

    def test_full_cycle_escalates_in_fourteen_executions_and_creates_next_case_later(self) -> None:
        self.run_full_cycle(score=60, severity="LOW", expected_outcome="ESCALATED")

    def test_workflow_declares_stage_work_before_the_single_lifecycle_evaluation(self) -> None:
        workflow = (PRODUCTION_ROOT / ".github" / "workflows" / "daily-investigation.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('cron: "17 0,8,16 * * *"', workflow)
        self.assertIn('timezone: "America/New_York"', workflow)
        self.assertLess(
            workflow.index("Process Active Case Stage Work"),
            workflow.index("Evaluate Persistent Lifecycle Once"),
        )
        self.assertEqual(workflow.count("python scripts/update_case_progress.py"), 1)


if __name__ == "__main__":
    unittest.main()
