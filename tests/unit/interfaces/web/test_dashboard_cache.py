# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import sqlite3
import os
import socket
import time
from unittest.mock import patch

from flask import Flask

from hackagent import HackAgent, Settings
from hackagent.interfaces.web._dashboard_cache import DashboardCache, VERSION
from hackagent.interfaces.web._history import create_history_api
from hackagent.storage.local import LocalBackend
from test_local_api import _WebUITestCase


class TestDashboardCache(_WebUITestCase):
    def setUp(self):
        super().setUp()
        self.campaign = self.backend.start_campaign(
            self.agent.id, {"campaign": {"name": "Cached"}}
        )
        self.child = self.backend.create_run(
            self.attack.id, self.agent.id, {}, campaign_run_id=self.campaign.id
        )
        self.result = self.backend.create_result(self.child.id, "Goal", 0, {}, {})
        self.backend.update_result(self.result.id, evaluation_status="FAILED_JAILBREAK")
        self.backend.update_run(self.child.id, status="COMPLETED")
        self.backend.update_campaign_run(self.campaign.id, status="COMPLETED")
        self.cache = DashboardCache(self.backend)
        session = HackAgent(
            Settings.resolve(backend="local", env={}, config_path="/nonexistent"),
            backend=self.backend,
        )
        app = Flask(__name__)
        app.register_blueprint(
            create_history_api(session, self.cache), url_prefix="/history"
        )
        self.cached_client = app.test_client()

    def tearDown(self):
        self.cache.close()
        super().tearDown()

    def test_attempt_patterns_preserve_different_votes_on_the_same_goal(self):
        self.backend.update_result(
            self.result.id,
            evaluation_status="SUCCESSFUL_JAILBREAK",
            evaluation_metrics={"eval_a": 1, "eval_b": 0},
        )
        second = self.backend.create_result(self.child.id, "Goal", 0, {}, {})
        self.backend.update_result(
            second.id,
            evaluation_status="SUCCESSFUL_JAILBREAK",
            evaluation_metrics={"eval_a": 0, "eval_b": 1},
        )
        self.cache.refresh()
        response = self.cached_client.get(f"/history/{self.campaign.id}")
        agreement = response.json["judge_agreement"]
        self.assertEqual(agreement["unit"], "attempt")
        self.assertEqual(agreement["attempts"], 2)
        self.assertEqual(agreement["unanimous_success"], 0)
        self.assertEqual(agreement["pairs"][0]["disagreement_rate"], 1)
        self.assertEqual(agreement["runs"][0]["attempts"], 2)
        self.assertEqual(
            agreement["patterns"],
            [{"pattern": "01", "attempts": 1}, {"pattern": "10", "attempts": 1}],
        )
        self.assertEqual(agreement["runs"][0]["patterns"], agreement["patterns"])
        self.assertEqual(agreement["goal_weighted"]["goals"], 1)
        self.assertEqual(
            agreement["runs"][0]["goal_weighted"], agreement["goal_weighted"]
        )
        self.assertEqual(
            sum(
                item["weight"]
                for item in agreement["goal_weighted"]["outcome_patterns"]
            ),
            1,
        )
        self.assertEqual(
            agreement["outcome_patterns"],
            [
                {"outcome": "jailbreak", "pattern": "01", "attempts": 1},
                {"outcome": "jailbreak", "pattern": "10", "attempts": 1},
            ],
        )
        self.assertEqual(
            agreement["runs"][0]["outcome_patterns"], agreement["outcome_patterns"]
        )
        self.assertEqual(response.json["attempts"], 2)

    def test_cold_preparation_and_persisted_reads_do_not_aggregate(self):
        response = self.cached_client.get("/history")
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json["preparing"])
        self.cache.refresh()
        with (
            patch.object(
                self.backend,
                "campaign_outcomes",
                side_effect=AssertionError("aggregation"),
            ),
            patch.object(
                self.backend,
                "run_costs",
                side_effect=AssertionError("cost aggregation"),
            ),
        ):
            response = self.cached_client.get("/history")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["results"][0]["mitigated"], 1)
            self.assertIn("generated_at", response.json["dashboard_snapshot"])
            costs = self.cached_client.get(f"/history/{self.campaign.id}/costs")
            self.assertEqual(costs.status_code, 200)
            self.assertEqual(costs.json["runs"][0]["attempts"], 1)
        reopened = LocalBackend(str(self.backend._db_path))
        try:
            self.assertIn(
                str(self.campaign.id), DashboardCache(reopened).read([self.campaign.id])
            )
        finally:
            reopened.close()

    def test_recorded_panel_outcomes_are_persisted_with_mixed_vote_counts(self):
        self.backend.update_result(
            self.result.id,
            evaluation_status="SUCCESSFUL_JAILBREAK",
            evaluation_metrics={"eval_a": 1, "eval_b": 0, "eval_c": 0},
        )
        self.cache.refresh()
        response = self.cached_client.get(f"/history/{self.campaign.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json["judge_agreement"]["mixed_outcomes"],
            [
                {
                    "outcome": "jailbreak",
                    "valid_votes": 3,
                    "jailbreak_votes": 1,
                    "attempts": 1,
                },
            ],
        )
        agreement = response.json["judge_agreement"]
        self.assertEqual(agreement["outcome_votes"], agreement["mixed_outcomes"])
        self.assertEqual(
            agreement["runs"][0]["outcome_votes"], agreement["outcome_votes"]
        )

    def test_recorded_outcomes_are_persisted_even_with_insufficient_votes(self):
        self.backend.update_result(
            self.result.id,
            evaluation_status="FAILED_JAILBREAK",
            evaluation_metrics={"eval_a": 1},
        )
        self.cache.refresh()
        agreement = self.cached_client.get(f"/history/{self.campaign.id}").json[
            "judge_agreement"
        ]
        self.assertEqual(
            agreement["outcome_votes"],
            [
                {
                    "outcome": "mitigated",
                    "valid_votes": 1,
                    "jailbreak_votes": 1,
                    "attempts": 1,
                }
            ],
        )
        self.assertEqual(
            agreement["runs"][0]["outcome_votes"], agreement["outcome_votes"]
        )

    def test_progressive_list_returns_ready_records_and_explicit_pending_without_zeros(
        self,
    ):
        self.cache.refresh()
        pending = self.backend.start_campaign(
            self.agent.id, {"campaign": {"name": "Preparing"}}
        )
        response = self.cached_client.get("/history?progressive=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["count"], 2)
        self.assertEqual(
            [item["id"] for item in response.json["results"]], [str(self.campaign.id)]
        )
        self.assertEqual(response.json["results"][0]["page_position"], 1)
        self.assertEqual(response.json["preparing_campaigns"][0]["id"], str(pending.id))
        self.assertEqual(response.json["preparing_campaigns"][0]["page_position"], 0)
        self.assertNotIn("recorded_goals", response.json["preparing_campaigns"][0])
        self.cache.refresh()
        response = self.cached_client.get("/history?progressive=1")
        self.assertEqual(len(response.json["results"]), 2)
        self.assertEqual(response.json["preparing_campaigns"], [])

    def test_compatible_previous_version_stays_visible_during_upgrade(self):
        self.cache.refresh()
        with self.backend._conn:
            self.backend._conn.execute("UPDATE dashboard_snapshots SET version=3")
        for path in (
            "/history",
            f"/history/{self.campaign.id}",
            f"/history/{self.campaign.id}/costs",
            f"/history/{self.campaign.id}/goals",
        ):
            response = self.cached_client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertTrue(response.json["dashboard_snapshot"]["upgrading"])
        progressive = self.cached_client.get("/history?progressive=1").json
        self.assertEqual(progressive["upgrading_campaigns"], 1)
        self.assertEqual(progressive["preparing_campaigns"], [])
        self.cache.refresh()
        self.assertFalse(
            self.cached_client.get(f"/history/{self.campaign.id}").json[
                "dashboard_snapshot"
            ]["upgrading"]
        )

    def test_dead_local_worker_is_reclaimed_without_waiting_for_expiry(self):
        now = time.time()
        dead_owner = f"{socket.gethostname()}:123456789:old-worker"
        self.backend.claim_dashboard_worker(dead_owner, now, now + 300)
        with patch("hackagent.storage.local.os.kill", side_effect=ProcessLookupError):
            self.assertTrue(
                self.backend.claim_dashboard_worker(self.cache.owner, now, now + 300)
            )
        self.backend.release_dashboard_worker(self.cache.owner)
        live_owner = f"{socket.gethostname()}:{os.getpid()}:live-worker"
        self.backend.claim_dashboard_worker(live_owner, now, now + 300)
        self.assertFalse(
            self.backend.claim_dashboard_worker(self.cache.owner, now, now + 300)
        )
        self.backend.release_dashboard_worker(live_owner)

    def test_cached_detail_and_coverage_match_live_views_without_reading_results(self):
        self.backend.update_result(
            self.result.id, evaluation_metrics={"eval_a": 1, "eval_b": 0}
        )
        self.cache.refresh()
        expected_detail = self.cached_client.get(
            f"/history/{self.campaign.id}?fresh=1"
        ).json
        expected_goals = self.cached_client.get(
            f"/history/{self.campaign.id}/goals?fresh=1"
        ).json
        with (
            patch.object(
                self.backend,
                "campaign_results",
                side_effect=AssertionError("raw results"),
            ),
            patch.object(
                self.backend, "list_runs", side_effect=AssertionError("run scan")
            ),
        ):
            detail = self.cached_client.get(f"/history/{self.campaign.id}").json
            goals = self.cached_client.get(f"/history/{self.campaign.id}/goals").json
            detail.pop("dashboard_snapshot")
            goals.pop("dashboard_snapshot")
            self.assertEqual(detail, expected_detail)
            self.assertEqual(detail["judge_agreement"]["disagreement_rate"], 1.0)
            self.assertEqual(goals, expected_goals)
            filtered = self.cached_client.get(
                f"/history/{self.campaign.id}/goals?search=missing&verdict=mitigated"
            )
            self.assertEqual(filtered.json["count"], 0)
            indexed = self.cached_client.get(
                f"/history/{self.campaign.id}/goals?goal_index=0&page_size=1"
            )
            self.assertEqual(indexed.json["count"], 1)
            self.assertEqual(indexed.json["results"][0]["goal"], "Goal")
            self.assertEqual(
                self.cached_client.get(
                    f"/history/{self.campaign.id}/goals?goal_index=-1"
                ).status_code,
                400,
            )

    def test_run_scoped_views_remain_live_and_invalid_scopes_are_rejected(self):
        self.cache.refresh()
        scoped = self.cached_client.get(
            f"/history/{self.campaign.id}?run_id={self.child.id}"
        )
        self.assertEqual(scoped.status_code, 200)
        self.assertEqual(scoped.json["scope_run_id"], str(self.child.id))
        self.assertNotIn("dashboard_snapshot", scoped.json)
        self.assertEqual(
            self.cached_client.get(
                f"/history/{self.campaign.id}?run_id={self.run.id}"
            ).status_code,
            404,
        )

    def test_background_writer_does_not_use_http_connection_for_cache_writes(self):
        with self.backend.dashboard_writer() as writer:
            self.assertIsNot(writer, self.backend)
            with patch.object(
                self.backend,
                "save_dashboard_snapshot",
                side_effect=AssertionError("HTTP lock"),
            ):
                self.cache.refresh(writer)
        self.assertTrue(
            self.cache.read([self.campaign.id])[str(self.campaign.id)]["finalized"]
        )

    def test_verdict_status_and_late_trace_refresh_preserve_exact_costs(self):
        self.cache.refresh()
        initial = self.cache.read([self.campaign.id])[str(self.campaign.id)]
        self.backend.update_campaign_run(self.campaign.id, status="RUNNING")
        self.backend.update_result(
            self.result.id, evaluation_status="SUCCESSFUL_JAILBREAK"
        )
        self.backend.create_trace(self.result.id, 1, "interaction", {})
        self.assertEqual(
            self.cache.read([self.campaign.id])[str(self.campaign.id)], initial
        )
        self.cache.refresh()
        snapshot = self.cache.read([self.campaign.id])[str(self.campaign.id)]
        self.assertNotEqual(snapshot["source_revision"], initial["source_revision"])
        self.assertEqual(snapshot["summary"]["status"], "RUNNING")
        self.assertEqual(snapshot["summary"]["jailbroken"], 1)
        expected = self.backend.run_costs([self.child.id])[str(self.child.id)]
        self.assertEqual(
            snapshot["costs"]["runs"], [{"run_id": str(self.child.id), **expected}]
        )

    def test_unchanged_campaign_skips_cost_aggregation(self):
        self.cache.refresh()
        with (
            patch.object(
                LocalBackend, "run_costs", side_effect=AssertionError("unchanged")
            ),
            patch.object(
                LocalBackend,
                "dashboard_revision",
                side_effect=AssertionError("revision scan"),
            ),
            patch.object(
                self.backend,
                "dashboard_read_snapshot",
                side_effect=AssertionError("database copy"),
            ),
        ):
            self.cache.refresh()

    def test_active_campaign_gets_one_final_snapshot_when_all_runs_stop(self):
        self.backend.update_campaign_run(self.campaign.id, status="RUNNING")
        self.backend.update_run(self.child.id, status="RUNNING")
        self.cache.refresh()
        self.assertFalse(
            self.cache.read([self.campaign.id])[str(self.campaign.id)]["finalized"]
        )
        self.backend.update_campaign_run(self.campaign.id, status="FAILED")
        self.cache.refresh()
        self.assertFalse(
            self.cache.read([self.campaign.id])[str(self.campaign.id)]["finalized"]
        )
        self.backend.create_trace(self.result.id, 1, "interaction", {})
        self.backend.update_run(self.child.id, status="CANCELLED")
        self.cache.refresh()
        final = self.cache.read([self.campaign.id])[str(self.campaign.id)]
        self.assertTrue(final["finalized"])
        self.assertEqual(final["costs"]["runs"][0]["calls"]["target"], 1)
        with patch.object(
            self.backend, "dashboard_read_snapshot", side_effect=AssertionError("final")
        ):
            self.cache.refresh()
        self.assertEqual(
            self.cache.read([self.campaign.id])[str(self.campaign.id)], final
        )

    def test_final_snapshot_remains_constant_after_terminal_record_edits(self):
        self.cache.refresh()
        final = self.cache.read([self.campaign.id])[str(self.campaign.id)]
        self.backend.update_result(
            self.result.id, evaluation_status="SUCCESSFUL_JAILBREAK"
        )
        self.cache.refresh()
        self.assertEqual(
            self.cache.read([self.campaign.id])[str(self.campaign.id)], final
        )

    def test_unchanged_active_campaign_still_skips_aggregation(self):
        self.backend.update_campaign_run(self.campaign.id, status="RUNNING")
        self.cache.refresh()
        with patch.object(
            LocalBackend, "run_costs", side_effect=AssertionError("unchanged")
        ):
            self.cache.refresh()

    def test_final_campaign_is_not_revision_scanned_while_another_is_active(self):
        self.cache.refresh()
        active = self.backend.start_campaign(
            self.agent.id, {"campaign": {"name": "Active"}}
        )
        original = LocalBackend.dashboard_revision

        def active_only(source, ident):
            self.assertEqual(ident, active.id)
            return original(source, ident)

        with patch.object(LocalBackend, "dashboard_revision", active_only):
            self.cache.refresh()
        self.assertTrue(
            self.cache.read([self.campaign.id])[str(self.campaign.id)]["finalized"]
        )
        self.assertFalse(self.cache.read([active.id])[str(active.id)]["finalized"])

    def test_additive_migration_backfills_legacy_final_snapshots_once(self):
        self.cache.refresh()
        with self.backend._conn:
            self.backend._conn.execute(
                "ALTER TABLE dashboard_snapshots DROP COLUMN finalized"
            )
        reopened = LocalBackend(str(self.backend._db_path))
        migrated_cache = DashboardCache(reopened)
        try:
            self.assertFalse(
                migrated_cache.read([self.campaign.id])[str(self.campaign.id)][
                    "finalized"
                ]
            )
            migrated_cache.refresh()
            self.assertTrue(
                migrated_cache.read([self.campaign.id])[str(self.campaign.id)][
                    "finalized"
                ]
            )
            self.assertEqual(reopened.dashboard_refresh_candidates(VERSION), [])
        finally:
            migrated_cache.close()
            reopened.close()

    def test_export_can_request_fresh_costs_instead_of_a_stale_snapshot(self):
        self.cache.refresh()
        self.backend.create_result(self.child.id, "Second", 1, {}, {})
        cached = self.cached_client.get(f"/history/{self.campaign.id}/costs")
        fresh = self.cached_client.get(f"/history/{self.campaign.id}/costs?fresh=1")
        self.assertEqual(cached.json["runs"][0]["attempts"], 1)
        self.assertEqual(fresh.json["runs"][0]["attempts"], 2)
        self.assertNotIn("dashboard_snapshot", fresh.json)

    def test_consistent_source_snapshot_is_independent_of_new_writes(self):
        with self.backend.dashboard_read_snapshot() as source:
            self.backend.update_result(
                self.result.id, evaluation_status="SUCCESSFUL_JAILBREAK"
            )
            self.assertEqual(
                source.campaign_outcomes([self.campaign.id])[str(self.campaign.id)][
                    "jailbroken"
                ],
                0,
            )
        self.assertEqual(
            self.backend.campaign_outcomes([self.campaign.id])[str(self.campaign.id)][
                "jailbroken"
            ],
            1,
        )

    def test_single_worker_lease_and_failed_refresh_retain_previous_data(self):
        self.cache.refresh()
        initial = self.cache.read([self.campaign.id])
        other = DashboardCache(self.backend)
        now = time.time()
        self.assertTrue(self.backend.claim_dashboard_worker("other", now, now + 300))
        with patch.object(
            self.backend,
            "dashboard_read_snapshot",
            side_effect=AssertionError("duplicate"),
        ):
            other.refresh()
        self.backend.release_dashboard_worker("other")
        self.backend.update_campaign_run(self.campaign.id, status="RUNNING")
        self.backend.update_result(
            self.result.id, evaluation_status="SUCCESSFUL_JAILBREAK"
        )
        with patch.object(
            LocalBackend, "run_costs", side_effect=sqlite3.OperationalError("failure")
        ):
            with self.assertRaises(sqlite3.OperationalError):
                self.cache.refresh()
        self.assertEqual(self.cache.read([self.campaign.id]), initial)
        self.cache.error = "Refresh failed"
        self.assertEqual(
            self.cached_client.get("/history").json["dashboard_snapshot"][
                "refresh_error"
            ],
            "Refresh failed",
        )

    def test_delete_cascades_cache_and_old_versions_are_not_served(self):
        self.cache.refresh()
        with self.backend._conn:
            self.backend._conn.execute("UPDATE dashboard_snapshots SET version=0")
        self.assertEqual(self.cached_client.get("/history").status_code, 202)
        self.cache.refresh()
        self.backend.delete_campaign_run(self.campaign.id)
        self.assertEqual(self.cache.read([self.campaign.id]), {})
        self.assertEqual(
            self.cached_client.get(f"/history/{self.campaign.id}/costs").status_code,
            404,
        )
