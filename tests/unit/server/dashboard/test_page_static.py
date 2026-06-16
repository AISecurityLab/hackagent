# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for DashboardPage static helper methods."""

import unittest

from hackagent.server.dashboard._page import DashboardPage


class TestDashboardPageStaticMethods(unittest.TestCase):
    """Test static utility methods that do not require UI state."""

    def test_extract_row_from_supported_payload_shapes(self):
        self.assertEqual(
            DashboardPage._extract_row({"row": {"id": "run-1"}}),
            {"id": "run-1"},
        )
        self.assertEqual(
            DashboardPage._extract_row({"id": "run-2", "value": 1}),
            {"id": "run-2", "value": 1},
        )
        self.assertEqual(
            DashboardPage._extract_row([{"x": 1}, {"row": {"id": "run-3"}}]),
            {"id": "run-3"},
        )
        self.assertIsNone(DashboardPage._extract_row({"x": 1}))
        self.assertIsNone(DashboardPage._extract_row("bad"))

    def test_derive_run_status_priority(self):
        self.assertEqual(
            DashboardPage._derive_run_status(
                [("SUCCESSFUL_JAILBREAK", None), ("NOT_EVALUATED", None)]
            ),
            "RUNNING",
        )
        self.assertEqual(
            DashboardPage._derive_run_status(
                [("FAILED_CRITERIA", None), ("PASSED_CRITERIA", None)]
            ),
            "COMPLETED",
        )
        self.assertEqual(
            DashboardPage._derive_run_status(
                [("SUCCESSFUL_JAILBREAK", None), ("PASSED_CRITERIA", None)]
            ),
            "COMPLETED",
        )
        self.assertEqual(
            DashboardPage._derive_run_status([], fallback="QUEUED"), "QUEUED"
        )
        self.assertEqual(DashboardPage._derive_run_status([]), "PENDING")

    def test_compute_run_latency_seconds(self):
        run_data = {
            "created_at": "2026-03-31T10:00:00Z",
            "updated_at": "2026-03-31T10:00:02Z",
        }
        self.assertEqual(DashboardPage._compute_run_latency_seconds(run_data), 2.0)

    def test_extract_goal_latency_seconds_prefers_elapsed_s(self):
        result_data = {
            "metadata": {"elapsed_s": 1.5, "latency_s": 99},
            "evaluation_metrics": {"elapsed_s": 2.0},
            "created_at": "2026-03-31T10:00:00Z",
            "updated_at": "2026-03-31T10:00:03Z",
        }
        self.assertEqual(DashboardPage._extract_goal_latency_seconds(result_data), 1.5)

    def test_extract_goal_latency_seconds_uses_fallback_fields(self):
        self.assertEqual(
            DashboardPage._extract_goal_latency_seconds(
                {
                    "metadata": {"latency_s": 2.25},
                    "evaluation_metrics": {},
                }
            ),
            2.25,
        )
        self.assertEqual(
            DashboardPage._extract_goal_latency_seconds(
                {
                    "metadata": {},
                    "evaluation_metrics": {"duration_s": 3.0},
                }
            ),
            3.0,
        )

    def test_extract_goal_latency_seconds_falls_back_to_timestamps(self):
        result_data = {
            "metadata": {},
            "evaluation_metrics": {},
            "created_at": "2026-03-31T10:00:00Z",
            "updated_at": "2026-03-31T10:00:04Z",
        }
        self.assertEqual(DashboardPage._extract_goal_latency_seconds(result_data), 4.0)

    def test_extract_category_label_from_supported_sources(self):
        self.assertEqual(
            DashboardPage._extract_category_label(
                {"metadata": {"risk_category": "Prompt Injection"}}
            ),
            "Prompt Injection",
        )
        self.assertEqual(
            DashboardPage._extract_category_label(
                {"evaluation_metrics": {"taxonomy": {"l3": "Data Exfiltration"}}}
            ),
            "Data Exfiltration",
        )
        self.assertIsNone(DashboardPage._extract_category_label({}))

    def test_risk_level_from_asr_thresholds(self):
        self.assertEqual(
            DashboardPage._risk_level_from_asr(75.0), ("CRITICAL", "negative")
        )
        self.assertEqual(DashboardPage._risk_level_from_asr(40.0), ("HIGH", "warning"))
        self.assertEqual(DashboardPage._risk_level_from_asr(10.0), ("MEDIUM", "orange"))
        self.assertEqual(DashboardPage._risk_level_from_asr(9.9), ("LOW", "positive"))

    def test_build_judge_metadata_handles_duplicate_types(self):
        judges_cfg = [
            {"type": "harmbench", "identifier": "hb-main"},
            {"type": "harmbench", "agent_name": "hb-backup"},
            {"type": "jailbreakbench", "identifier": "jb-main"},
        ]

        judge_meta, declared_eval_keys = DashboardPage._build_judge_metadata(judges_cfg)

        self.assertEqual(
            declared_eval_keys,
            ["eval_hb_1", "eval_hb_2", "eval_jb"],
        )
        self.assertEqual(judge_meta["eval_hb_1"]["id"], 0)
        self.assertEqual(judge_meta["eval_hb_1"]["name"], "hb-main")
        self.assertEqual(judge_meta["eval_hb_1"]["type"], "Harmbench")
        self.assertEqual(judge_meta["eval_hb_2"]["id"], 1)
        self.assertEqual(judge_meta["eval_hb_2"]["name"], "hb-backup")
        self.assertEqual(judge_meta["eval_jb"]["id"], 2)
        self.assertEqual(judge_meta["eval_jb"]["name"], "jb-main")

    def test_build_judge_metadata_fallbacks_and_invalid_entries(self):
        judges_cfg = [
            "invalid",
            {},
            {"type": "unknown_custom", "agent_name": "custom-judge"},
            {"type": "on_topic"},
        ]

        judge_meta, declared_eval_keys = DashboardPage._build_judge_metadata(judges_cfg)

        self.assertEqual(
            declared_eval_keys,
            ["eval_unknown", "eval_unknown_custom", "eval_on_topic"],
        )
        self.assertEqual(judge_meta["eval_unknown"]["name"], "unknown")
        self.assertEqual(judge_meta["eval_unknown_custom"]["type"], "Unknown Custom")
        self.assertEqual(judge_meta["eval_on_topic"]["name"], "on_topic")

    def test_build_judge_metadata_empty_when_not_list(self):
        self.assertEqual(DashboardPage._build_judge_metadata(None), ({}, []))
        self.assertEqual(DashboardPage._build_judge_metadata({"judges": []}), ({}, []))


if __name__ == "__main__":
    unittest.main()
