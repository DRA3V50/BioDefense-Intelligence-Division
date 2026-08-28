from __future__ import annotations

"""Regression coverage for renderer presentation after bounded stage work.

This test deliberately keeps all state changes inside a temporary fixture.  It
reproduces the production ordering that exposed run #244: a revision-2
EVIDENCE_REVIEW case receives one real four-record review batch, then its
current-revision C# report projection and derived support state are refreshed
before the production wrapper renders with ``deploy=False``.
"""

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import numpy as np


PRODUCTION_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PRODUCTION_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import consolidated_dashboard_renderer as renderer
import production_dashboard_wrapper as wrapper
from archive_case import archive_terminal_case
from case_lifecycle import ensure_active_case, update_active_case
from case_state import (
    atomic_write_json,
    csharp_level,
    load_active_case,
    load_json_document,
)
from process_active_case_stage import process_active_case_stage
from synchronize_case_support_state import synchronize_case_support_state


UTC = timezone.utc
FIXTURE_TIME = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
CASE_ID = "BID-2026-9736"
CAMPAIGN_ID = "BDC-2026-001"


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_case_payload() -> dict[str, object]:
    """Return a stable production-shaped low-severity review fixture."""

    return {
        "case_id": CASE_ID,
        "campaign_id": CAMPAIGN_ID,
        "date": "2026-08-21",
        "operation": "Renderer Stage-Work Regression",
        "classification": "Laboratory Security Breach Investigation",
        "threat_family": "Clinical Research Data Manipulation",
        "severity": "LOW",
        "status": "Evidence Collection",
        "containment_phase": "Operational Recovery",
        "affected_platform": "Genome Sequencing Environment",
        "device_family": "Evidence Repository",
        "vendor": "Test Vendor",
        "network_zone": "Evidence Network",
        "firmware_version": "2.1.7",
        "confidence": 86,
        "risk_score": 22,
        "affected_assets": 7,
        "evidence_count": 22,
        "ioc_count": 4,
        "initial_access": "Third-Party Access",
        "lead_analyst": "National Response Cell",
        "priority": "ROUTINE",
        "recommended_action": "Verify recovery controls and prepare the final operational assessment.",
        "assessment": "Correlated records suggest a multi-stage intrusion affecting research evidence.",
    }


def write_operation(root: Path) -> None:
    atomic_write_json(
        root / "operations" / "active_operation.json",
        {
            "campaign_id": CAMPAIGN_ID,
            "operation": "Renderer Stage-Work Regression",
            "campaign_phase": "Detection",
            "containment_level": "Controlled",
            "next_objective": "Review evidence",
        },
    )


def write_manifest(root: Path, case: dict[str, object]) -> None:
    evidence_items = []
    for number in range(1, 23):
        evidence_items.append(
            {
                "evidence_id": f"{CASE_ID}-EV-{number:04d}",
                "case_id": CASE_ID,
                "artifact_type": "Laboratory System Configuration",
                "artifact_path": "artifacts/device_configuration.json",
                "source_system": str(case["device_family"]),
                "platform": str(case["affected_platform"]),
                "vendor": str(case["vendor"]),
                "zone": str(case["network_zone"]),
                "collected_by": str(case["lead_analyst"]),
                "collected_at": "2026-08-21T12:00:00Z",
                "integrity_status": "Verified",
                "sha256": f"renderer-stage-work-{number:04d}",
                "classification": str(case["classification"]),
                "review_status": "Pending Analyst Review",
            }
        )
    atomic_write_json(
        root / "evidence" / CASE_ID / "evidence_manifest.json",
        {
            "schema_version": 2,
            "case_id": CASE_ID,
            "generated_at": "2026-08-21T12:00:00Z",
            "evidence_count": len(evidence_items),
            "evidence_items": evidence_items,
        },
    )


def write_correlations(root: Path) -> None:
    manifest = load_json_document(root / "evidence" / CASE_ID / "evidence_manifest.json")
    assert manifest is not None
    correlations = [
        {
            "case_id": CASE_ID,
            "evidence_id": item["evidence_id"],
            "artifact_type": item["artifact_type"],
            "artifact_path": item["artifact_path"],
            "related_indicator": f"IOC-{number:04d}",
            "finding": "Laboratory System Modification",
            "confidence": 88,
            "analysis_status": "Correlated",
        }
        for number, item in enumerate(manifest["evidence_items"], start=1)
    ]
    atomic_write_json(
        root / "evidence" / CASE_ID / "evidence_correlations.json",
        {
            "schema_version": 2,
            "case_id": CASE_ID,
            "generated_at": "2026-08-21T12:00:00Z",
            "correlation_count": len(correlations),
            "correlations": correlations,
        },
    )


def write_current_csharp_projection(root: Path, case: dict[str, object]) -> None:
    """Write a fixture C#-report-shaped current-revision projection.

    The existing lifecycle suite uses this verified C# JSON shape for Python
    integration tests.  C# engine execution has separate coverage; this test
    exercises the post-score support synchronization and renderer contract.
    """

    score = 21
    atomic_write_json(
        root / "reports" / "bioterror_threat_score_csharp.json",
        {
            "generatedAt": "2026-08-21 12:10 UTC",
            "investigation": {
                "caseId": CASE_ID,
                "caseRevision": int(case["state_revision"]),
                "campaignId": CAMPAIGN_ID,
            },
            "assessment": {
                "overallScore": score,
                "overallLevel": csharp_level(score),
            },
        },
    )


class RendererStageWorkIntegrationTests(unittest.TestCase):
    """Ensure persisted event counts cannot alter the renderer-owned LIVE loop."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="bd-run244-renderer-")
        self.baseline_temporary = tempfile.TemporaryDirectory(
            prefix="bd-run244-baseline-"
        )
        self.root = Path(self.temporary.name)
        self.baseline_root = Path(self.baseline_temporary.name) / "fixture"
        self.renderer_state = self._make_revision_three_fixture()

    def tearDown(self) -> None:
        self.temporary.cleanup()
        self.baseline_temporary.cleanup()

    def _make_revision_three_fixture(self) -> dict[str, object]:
        write_operation(self.root)
        created = ensure_active_case(
            fixture_case_payload,
            self.root,
            now=FIXTURE_TIME,
        ).case
        write_manifest(self.root, created)
        write_correlations(self.root)

        entered_review = update_active_case(
            self.root,
            now=FIXTURE_TIME + timedelta(minutes=1),
        )
        self.assertEqual(entered_review.transition, "EVIDENCE_REVIEW")
        revision_two = load_active_case(self.root)
        assert revision_two is not None
        self.assertEqual(revision_two["case_id"], CASE_ID)
        self.assertEqual(revision_two["state_revision"], 2)
        self.assertEqual(revision_two["current_stage"], "EVIDENCE_REVIEW")

        write_current_csharp_projection(self.root, revision_two)
        initial_sync = synchronize_case_support_state(self.root)
        self.assertEqual(initial_sync["state_revision"], 2)

        events_path = self.root / "cases" / "state" / CASE_ID / "events.json"
        before_events = load_json_document(events_path)
        assert before_events is not None
        self.assertEqual(len(before_events["events"]), 2)

        # Preserve a genuinely revision-2/two-event input for the baseline
        # regression.  It never shares files with the post-work fixture.
        shutil.copytree(self.root, self.baseline_root)
        baseline = wrapper.build_renderer_state(self.baseline_root)
        self.baseline_renderer_state, baseline_projection = (
            wrapper.current_revision_threat_projection(baseline)
        )
        wrapper.apply_display_text_projection(self.baseline_renderer_state)
        self.assertEqual(baseline_projection["current_state_revision"], 2)
        self.assertEqual(len(self.baseline_renderer_state["events"]), 2)

        stage_updated_at = revision_two["stage_updated_at"]
        batch = process_active_case_stage(
            self.root,
            now=FIXTURE_TIME + timedelta(minutes=2),
        )
        self.assertTrue(batch.changed)
        self.assertEqual(batch.action, "EVIDENCE_REVIEW_BATCH")
        self.assertEqual(batch.completed_count, 4)
        self.assertEqual(batch.total_count, 22)
        self.assertEqual(
            batch.processed_ids,
            tuple(f"{CASE_ID}-EV-{number:04d}" for number in range(1, 5)),
        )

        revision_three = load_active_case(self.root)
        assert revision_three is not None
        self.assertEqual(revision_three["case_id"], CASE_ID)
        self.assertEqual(revision_three["current_stage"], "EVIDENCE_REVIEW")
        self.assertEqual(revision_three["stage_updated_at"], stage_updated_at)
        self.assertEqual(revision_three["state_revision"], 3)
        manifest = load_json_document(self.root / "evidence" / CASE_ID / "evidence_manifest.json")
        assert manifest is not None
        reviewed = [
            item for item in manifest["evidence_items"] if item["review_status"] == "Reviewed"
        ]
        pending = [
            item
            for item in manifest["evidence_items"]
            if item["review_status"] == "Pending Analyst Review"
        ]
        self.assertEqual(len(reviewed), 4)
        self.assertEqual(len(pending), 18)
        staged_events = load_json_document(events_path)
        assert staged_events is not None
        progress_events = [
            event
            for event in staged_events["events"]
            if event["event_type"] == "EVIDENCE_REVIEW_PROGRESS"
        ]
        self.assertEqual(len(progress_events), 1)
        self.assertEqual(progress_events[0]["message"], "Evidence review progress: 4/22 reviewed")
        self.assertEqual(len(staged_events["events"]), 3)

        lifecycle = update_active_case(
            self.root,
            now=FIXTURE_TIME + timedelta(minutes=3),
        )
        self.assertIsNone(lifecycle.transition)
        self.assertTrue(lifecycle.stale_threat_report_rejected)

        # This is the post-lifecycle C# score refresh plus #8 sidecar sync in
        # the real workflow ordering.  It supplies the current revision that
        # the renderer is required to consume.
        write_current_csharp_projection(self.root, revision_three)
        synchronized = synchronize_case_support_state(self.root)
        self.assertEqual(synchronized["state_revision"], 3)
        self.assertEqual(synchronized["current_stage"], "EVIDENCE_REVIEW")
        self.assertEqual(synchronized["threat_score"], 21)

        # The archive stage is an explicit active-case no-op; its existence in
        # this fixture documents the same non-terminal workflow path.
        archived_case, archived = archive_terminal_case(
            self.root,
            now=FIXTURE_TIME + timedelta(minutes=4),
        )
        self.assertFalse(archived)
        self.assertEqual(archived_case["state_revision"], 3)
        write_current_csharp_projection(self.root, revision_three)
        final_sync = synchronize_case_support_state(self.root)
        self.assertEqual(final_sync["state_revision"], 3)

        state = wrapper.build_renderer_state(self.root)
        projected, projection = wrapper.current_revision_threat_projection(state)
        wrapper.apply_display_text_projection(projected)
        self.assertEqual(projection["authoritative_sample_count"], 2)
        self.assertEqual(projection["projected_current_revision_sample_count"], 1)
        self.assertEqual(projection["current_state_revision"], 3)
        self.assertEqual(
            projected["dashboard"]["threat_monitor"]["threat_history"][0]["case_revision"],
            3,
        )
        return projected

    @staticmethod
    def _state_with_visible_event_count(
        renderer_state: dict[str, object], count: int
    ) -> dict[str, object]:
        """Use only persisted-shaped chronological fixtures for 1..5 coverage."""

        state = copy.deepcopy(renderer_state)
        events = list(state["events"])
        if count > len(events):
            newest = copy.deepcopy(events[-1])
            for sequence in range(len(events) + 1, count + 1):
                event = copy.deepcopy(newest)
                event["event_id"] = f"{CASE_ID}-EVT-{sequence:04d}"
                event["sequence"] = sequence
                event["timestamp"] = f"2026-08-21T12:{sequence:02d}:00Z"
                event["event_type"] = "EVIDENCE_REVIEW_PROGRESS"
                event["message"] = f"Evidence review progress: {min(sequence * 4, 22)}/22 reviewed"
                event["intensity"] = 45
                event["idempotency_key"] = f"renderer-count-fixture-{sequence}"
                events.append(event)
        visible = copy.deepcopy(events[:count])
        state["events"] = visible
        state["dashboard"]["active_case_feed"]["events"] = copy.deepcopy(visible)
        return state

    @staticmethod
    def _row_activity_mask(context: renderer.RenderContext, visible_count: int) -> np.ndarray:
        """Lift the frozen local row masks into one full-canvas audit mask."""

        mask = np.zeros((renderer.CANVAS_SIZE[1], renderer.CANVAS_SIZE[0]), dtype=bool)
        panel_x1, panel_y1, panel_x2, panel_y2 = context.helpers.s04.PANEL_BOUNDS
        local = np.zeros((panel_y2 - panel_y1, panel_x2 - panel_x1), dtype=bool)
        for row_mask in context.s04_row_masks[:visible_count]:
            local |= row_mask
        mask[panel_y1:panel_y2, panel_x1:panel_x2] = local
        return mask

    @staticmethod
    def _helper_row_activity(
        context: renderer.RenderContext, visible_count: int
    ) -> dict[str, int]:
        """Measure the preserved frozen #4 row scan before text-lane restore.

        The production composite deliberately restores dynamic text lanes after
        the helper so a source glyph can never remain underneath a live value.
        That post-helper safeguard is outside this repair.  This audit proves
        the normal event-driven helper row scan itself is still scheduled and
        active for every visible persisted-event count.
        """

        panels: list[np.ndarray] = []
        for frame_index in range(renderer.FRAME_COUNT):
            feed_values = renderer.feed_values_for_frame(context, frame_index)
            feed_event, feed_strength, feed_progress = renderer.feed_event_for_frame(
                context, frame_index
            )
            panel, _tops, _heights = context.helpers.s04.render_frame(
                context.s04_empty,
                context.s04_source,
                context.s04_live_mask,
                context.s04_severity_masks,
                context.s04_row_masks,
                context.s04_bars,
                feed_values,
                feed_event,
                feed_strength,
                feed_progress,
                frame_index,
            )
            panels.append(panel)
        row_mask = np.zeros_like(context.s04_row_masks[0])
        for item in context.s04_row_masks[:visible_count]:
            row_mask |= item
        return renderer.temporal_mask_metrics(panels, row_mask)

    def _render_count_qc(
        self, count: int, output_dir: Path
    ) -> tuple[dict[str, object], renderer.RenderContext, list[np.ndarray], list[np.ndarray]]:
        state = self._state_with_visible_event_count(self.renderer_state, count)
        events_before = copy.deepcopy(state["events"])
        context = renderer.prepare_context(state)
        source_frames = renderer.render_frames(context)
        gif_path = output_dir / f"visible_event_count_{count}.gif"
        renderer.save_gif(
            context,
            source_frames,
            gif_path,
            renderer.build_gif_palette_plan(context, source_frames),
        )
        decoded = renderer.decode_gif(gif_path)
        current_case = self.root / "data" / "current_case.json"
        state_hash = sha256_path(current_case)
        qc, _qc_text = renderer.make_qc(
            context,
            source_frames,
            decoded,
            gif_path,
            0.0,
            {"not_run": "focused event-count regression"},
            state_hash,
            state_hash,
            [renderer.sha256_array(frame) for frame in source_frames],
        )
        self.assertEqual(context.renderer_state["events"], events_before)
        return qc, context, source_frames, decoded

    def _assert_live_reset_is_surgical(
        self, context: renderer.RenderContext, frame_index: int
    ) -> None:
        """Verify the new hook replaces exactly the frozen LIVE source ROI."""

        feed_values = renderer.feed_values_for_frame(context, frame_index)
        feed_event, feed_strength, feed_progress = renderer.feed_event_for_frame(
            context, frame_index
        )
        helper_panel, _tops, _heights = context.helpers.s04.render_frame(
            context.s04_empty,
            context.s04_source,
            context.s04_live_mask,
            context.s04_severity_masks,
            context.s04_row_masks,
            context.s04_bars,
            feed_values,
            feed_event,
            feed_strength,
            feed_progress,
            frame_index,
        )
        restored = renderer.restore_active_feed_live_source_roi(context, helper_panel)
        global_x1, global_y1, global_x2, global_y2 = context.helpers.s04.LIVE_ROI_GLOBAL
        panel_x1, panel_y1, panel_x2, panel_y2 = context.helpers.s04.PANEL_BOUNDS
        local_mask = np.zeros((panel_y2 - panel_y1, panel_x2 - panel_x1), dtype=bool)
        local_mask[
            global_y1 - panel_y1:global_y2 - panel_y1,
            global_x1 - panel_x1:global_x2 - panel_x1,
        ] = True
        self.assertTrue(np.array_equal(restored[local_mask], context.s04_source[local_mask]))
        self.assertTrue(np.array_equal(restored[~local_mask], helper_panel[~local_mask]))

    def test_live_indicator_is_count_independent_after_stage_work(self) -> None:
        """Decode 1..5 persisted event counts, including non-aligned 1/3/5 slots."""

        results: dict[int, dict[str, object]] = {}
        with tempfile.TemporaryDirectory(prefix="bd-run244-gif-") as temporary:
            output_dir = Path(temporary)
            for count in range(1, 6):
                qc, context, source_frames, decoded = self._render_count_qc(
                    count, output_dir
                )
                self._assert_live_reset_is_surgical(context, 60)
                x1, y1, x2, y2 = context.helpers.s04.LIVE_ROI_GLOBAL
                live = [frame[y1:y2, x1:x2] for frame in decoded]
                self.assertTrue(np.array_equal(live[0], live[60]), msg=f"count={count}")
                self.assertTrue(np.array_equal(live[30], live[90]), msg=f"count={count}")
                self.assertFalse(np.array_equal(live[0], live[30]), msg=f"count={count}")
                self.assertGreaterEqual(qc["active_feed_live_unique_states"], 30, msg=f"count={count}")
                self.assertGreater(qc["active_feed_live_temporal_change"], 0, msg=f"count={count}")
                self.assertTrue(qc["active_feed_live_indicator_three_second_cycle"], msg=f"count={count}")
                self.assertGreater(qc["active_feed_real_bar_glow_temporal_change"], 0, msg=f"count={count}")
                self.assertTrue(qc["active_feed_authoritative_heights_unchanged"], msg=f"count={count}")
                self.assertEqual(qc["active_feed_fake_events_created"], 0, msg=f"count={count}")
                self.assertTrue(qc["active_feed_newest_bar_emphasis"], msg=f"count={count}")
                self.assertTrue(qc["active_feed_graph_geometry_unchanged"], msg=f"count={count}")
                self.assertTrue(qc["active_feed_row_dividers_removed"], msg=f"count={count}")
                scheduled_rows = {
                    int(event["row_index"])
                    for index in range(renderer.FRAME_COUNT)
                    for event, _strength, _progress in [
                        renderer.feed_event_for_frame(context, index)
                    ]
                    if event is not None
                }
                self.assertEqual(scheduled_rows, set(range(count)), msg=f"count={count}")
                row_activity = self._helper_row_activity(context, count)
                self.assertGreater(row_activity["temporal_change"], 0, msg=f"count={count}")
                results[count] = {
                    "live_unique_states": qc["active_feed_live_unique_states"],
                    "live_temporal_change": qc["active_feed_live_temporal_change"],
                    "fake_events_created": qc["active_feed_fake_events_created"],
                    "bar_glow_temporal_change": qc["active_feed_bar_glow_temporal_change"],
                    "real_bar_glow_temporal_change": qc["active_feed_real_bar_glow_temporal_change"],
                    "row_temporal_change": row_activity["temporal_change"],
                    "three_second_cycle": qc["active_feed_live_indicator_three_second_cycle"],
                    "authoritative_heights_unchanged": qc["active_feed_authoritative_heights_unchanged"],
                    "newest_bar_emphasis": qc["active_feed_newest_bar_emphasis"],
                    "graph_geometry_unchanged": qc["active_feed_graph_geometry_unchanged"],
                    "row_dividers_removed": qc["active_feed_row_dividers_removed"],
                }

            # Compare the sole new renderer hook to an identity hook on the
            # same three-event state.  This reconstructs the immediate
            # pre-repair behavior without changing a checked-in source file.
            pre_context = renderer.prepare_context(
                self._state_with_visible_event_count(self.renderer_state, 3)
            )
            with mock.patch.object(
                renderer,
                "restore_active_feed_live_source_roi",
                side_effect=lambda _context, panel: panel,
            ):
                before = renderer.render_frames(pre_context)
            after = renderer.render_frames(pre_context)
            changed = np.any(np.asarray(before) != np.asarray(after), axis=3)
            x1, y1, x2, y2 = pre_context.helpers.s04.LIVE_ROI_GLOBAL
            allowed = np.zeros((renderer.CANVAS_SIZE[1], renderer.CANVAS_SIZE[0]), dtype=bool)
            allowed[y1:y2, x1:x2] = True
            outside_counts = [int(np.count_nonzero(frame & ~allowed)) for frame in changed]
            self.assertEqual(max(outside_counts, default=0), 0)
            self.assertGreater(int(np.count_nonzero(changed)), 0)

        print(
            "RUN244_EVENT_COUNT_QC="
            + json.dumps(
                {
                    "counts": results,
                    "three_event": results[3],
                    "source_max_changed_pixels_outside_live_roi": 0,
                },
                sort_keys=True,
            )
        )

    def test_original_revision_two_two_event_baseline_keeps_the_full_contract(self) -> None:
        """The pre-stage revision-2/two-event renderer input remains valid."""

        context = renderer.prepare_context(self.baseline_renderer_state)
        baseline_case = self.baseline_root / "data" / "current_case.json"
        baseline_hash = sha256_path(baseline_case)
        with tempfile.TemporaryDirectory(prefix="bd-run244-baseline-output-") as temporary:
            results = renderer.write_review_outputs(
                context,
                Path(temporary),
                self.baseline_root,
                run_safety_checks=True,
            )
            verification = wrapper.verify_candidate(
                results["gif"], results["png"], results["qc_data"]
            )
        self.assertEqual(sha256_path(baseline_case), baseline_hash)
        self.assertEqual(verification["gif"]["frame_count"], 120)
        self.assertEqual(verification["gif"]["unique_decoded_frames"], 120)
        self.assertTrue(results["qc_data"]["active_feed_live_indicator_three_second_cycle"])
        self.assertTrue(results["qc_data"]["active_feed_authoritative_heights_unchanged"])
        self.assertEqual(results["qc_data"]["active_feed_fake_events_created"], 0)

    def test_three_event_stage_work_passes_through_real_wrapper_no_deploy(self) -> None:
        """Exercise the production wrapper's verifier on the revision-3 fixture."""

        fixture_renderer = self.root / "scripts" / "consolidated_dashboard_renderer.py"
        fixture_renderer.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            PRODUCTION_ROOT / "scripts" / "consolidated_dashboard_renderer.py",
            fixture_renderer,
        )
        candidate_dir = self.root / "assets" / "deployment_candidate"
        candidate_renderer_hash = sha256_path(fixture_renderer)
        fixture_hashes_before = wrapper.hash_authoritative_state(self.root, CASE_ID)
        case_path = self.root / "data" / "current_case.json"
        case_hash_before = sha256_path(case_path)
        deployed_gif = PRODUCTION_ROOT / "assets" / "biodefense-case-scan.gif"
        deployed_png = PRODUCTION_ROOT / "assets" / "biodefense-dashboard-current.png"
        deployed_hashes_before = (sha256_path(deployed_gif), sha256_path(deployed_png))

        # The production wrapper must accept the fixture renderer through its
        # real pinned trust value; no in-memory trust override is permitted.
        self.assertEqual(wrapper.FROZEN_V2_SHA256, candidate_renderer_hash)
        result = wrapper.render_and_deploy(
            self.root,
            candidate_dir=candidate_dir,
            deploy=False,
        )

        self.assertEqual(result["deployed"], {})
        candidate = result["candidate"]
        self.assertTrue((candidate_dir / "biodefense-case-scan.gif").is_file())
        self.assertTrue((candidate_dir / "biodefense-dashboard-current.png").is_file())
        self.assertEqual(candidate["state_hashes_before"], fixture_hashes_before)
        self.assertEqual(candidate["state_hashes_after"], fixture_hashes_before)
        self.assertTrue(candidate["state_read_only"])
        self.assertEqual(candidate["frozen_v2_renderer_sha256"], candidate_renderer_hash)
        self.assertEqual(candidate["threat_history_projection"]["authoritative_sample_count"], 2)
        self.assertEqual(candidate["threat_history_projection"]["projected_current_revision_sample_count"], 1)
        self.assertEqual(candidate["threat_history_projection"]["current_state_revision"], 3)
        self.assertEqual(sha256_path(case_path), case_hash_before)
        self.assertEqual(wrapper.hash_authoritative_state(self.root, CASE_ID), fixture_hashes_before)
        self.assertEqual(
            (sha256_path(deployed_gif), sha256_path(deployed_png)),
            deployed_hashes_before,
        )

        gif = candidate["verification"]["gif"]
        self.assertEqual(gif["format"], "GIF")
        self.assertEqual(gif["size"], [1727, 911])
        self.assertEqual(gif["frame_count"], 120)
        self.assertEqual(gif["duration_ms"], 50)
        self.assertEqual(gif["loop"], 0)
        self.assertEqual(gif["full_canvas_frames"], 120)
        self.assertEqual(gif["disposal_2_frames"], 120)
        self.assertEqual(gif["duration_50ms_frames"], 120)
        self.assertEqual(gif["unique_decoded_frames"], 120)
        self.assertFalse(candidate["verification"]["renderer_mutates_case_state"])

        qc_text = (candidate_dir / "full_dashboard_qc.txt").read_text(encoding="utf-8")
        for expected_line in (
            "frame_count=120",
            "gif_total_duration_ms=6000",
            "decoded_unique_frames=120/120",
            "read_only_state_unchanged=True",
            "active_feed_live_indicator_three_second_cycle=True",
        ):
            self.assertIn(expected_line, qc_text)


if __name__ == "__main__":
    unittest.main()
