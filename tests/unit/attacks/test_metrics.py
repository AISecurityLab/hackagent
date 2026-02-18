# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for hackagent.attacks.evaluator.metrics module."""

import unittest

from hackagent.attacks.evaluator.metrics import (
    calculate_confidence_score,
    calculate_per_goal_metrics,
    calculate_success_rate,
    generate_summary_report,
    group_by_goal,
)


class TestCalculateSuccessRate(unittest.TestCase):
    """Test calculate_success_rate function."""

    def test_empty_results(self):
        """Empty list returns 0.0."""
        self.assertEqual(calculate_success_rate([]), 0.0)

    def test_all_successful(self):
        """All results successful returns 1.0."""
        results = [{"success": True}, {"success": True}, {"success": True}]
        self.assertAlmostEqual(calculate_success_rate(results), 1.0)

    def test_all_failed(self):
        """All results failed returns 0.0."""
        results = [{"success": False}, {"success": False}]
        self.assertAlmostEqual(calculate_success_rate(results), 0.0)

    def test_mixed_results(self):
        """Mixed results return correct ratio."""
        results = [{"success": True}, {"success": False}, {"success": True}]
        self.assertAlmostEqual(calculate_success_rate(results), 2 / 3)

    def test_missing_success_key(self):
        """Missing 'success' key defaults to False."""
        results = [{"other": "data"}, {"success": True}]
        self.assertAlmostEqual(calculate_success_rate(results), 0.5)

    def test_single_success(self):
        """Single successful result."""
        results = [{"success": True}]
        self.assertAlmostEqual(calculate_success_rate(results), 1.0)

    def test_single_failure(self):
        """Single failed result."""
        results = [{"success": False}]
        self.assertAlmostEqual(calculate_success_rate(results), 0.0)


class TestCalculateConfidenceScore(unittest.TestCase):
    """Test calculate_confidence_score function."""

    def test_empty_results(self):
        """Empty list returns 0.0."""
        self.assertEqual(calculate_confidence_score([]), 0.0)

    def test_all_same_confidence(self):
        """All same confidence returns that value."""
        results = [{"confidence": 0.8}, {"confidence": 0.8}, {"confidence": 0.8}]
        self.assertAlmostEqual(calculate_confidence_score(results), 0.8)

    def test_mixed_confidence(self):
        """Mixed confidence returns average."""
        results = [{"confidence": 0.6}, {"confidence": 0.8}, {"confidence": 1.0}]
        self.assertAlmostEqual(calculate_confidence_score(results), 0.8)

    def test_missing_confidence_key(self):
        """Missing 'confidence' key defaults to 0.0."""
        results = [{"other": "data"}, {"confidence": 0.6}]
        self.assertAlmostEqual(calculate_confidence_score(results), 0.3)

    def test_zero_confidence(self):
        """All zero confidence."""
        results = [{"confidence": 0.0}, {"confidence": 0.0}]
        self.assertAlmostEqual(calculate_confidence_score(results), 0.0)

    def test_single_result(self):
        """Single result returns its confidence."""
        results = [{"confidence": 0.95}]
        self.assertAlmostEqual(calculate_confidence_score(results), 0.95)


class TestGroupByGoal(unittest.TestCase):
    """Test group_by_goal function."""

    def test_empty_results(self):
        """Empty list returns empty dict."""
        self.assertEqual(group_by_goal([]), {})

    def test_single_goal(self):
        """All results with the same goal."""
        results = [
            {"goal": "hack AI", "success": True},
            {"goal": "hack AI", "success": False},
        ]
        grouped = group_by_goal(results)
        self.assertEqual(len(grouped), 1)
        self.assertIn("hack AI", grouped)
        self.assertEqual(len(grouped["hack AI"]), 2)

    def test_multiple_goals(self):
        """Results with different goals."""
        results = [
            {"goal": "goal1", "success": True},
            {"goal": "goal2", "success": False},
            {"goal": "goal1", "success": True},
        ]
        grouped = group_by_goal(results)
        self.assertEqual(len(grouped), 2)
        self.assertEqual(len(grouped["goal1"]), 2)
        self.assertEqual(len(grouped["goal2"]), 1)

    def test_missing_goal_key(self):
        """Missing 'goal' key defaults to 'unknown'."""
        results = [{"success": True}, {"goal": "real_goal"}]
        grouped = group_by_goal(results)
        self.assertIn("unknown", grouped)
        self.assertIn("real_goal", grouped)

    def test_preserves_all_data(self):
        """Grouped results preserve all original data."""
        results = [{"goal": "g1", "success": True, "extra": "data"}]
        grouped = group_by_goal(results)
        self.assertEqual(grouped["g1"][0]["extra"], "data")


class TestCalculatePerGoalMetrics(unittest.TestCase):
    """Test calculate_per_goal_metrics function."""

    def test_empty_results(self):
        """Empty list returns empty dict."""
        self.assertEqual(calculate_per_goal_metrics([]), {})

    def test_single_goal_metrics(self):
        """Metrics for a single goal."""
        results = [
            {"goal": "g1", "success": True, "confidence": 0.9},
            {"goal": "g1", "success": False, "confidence": 0.3},
        ]
        metrics = calculate_per_goal_metrics(results)
        self.assertIn("g1", metrics)
        self.assertEqual(metrics["g1"]["total_attempts"], 2)
        self.assertEqual(metrics["g1"]["successful_attacks"], 1)
        self.assertAlmostEqual(metrics["g1"]["success_rate"], 0.5)
        self.assertAlmostEqual(metrics["g1"]["avg_confidence"], 0.6)

    def test_multiple_goals_metrics(self):
        """Metrics for multiple goals."""
        results = [
            {"goal": "g1", "success": True, "confidence": 1.0},
            {"goal": "g2", "success": False, "confidence": 0.2},
            {"goal": "g2", "success": True, "confidence": 0.8},
        ]
        metrics = calculate_per_goal_metrics(results)
        self.assertEqual(len(metrics), 2)
        self.assertEqual(metrics["g1"]["total_attempts"], 1)
        self.assertAlmostEqual(metrics["g1"]["success_rate"], 1.0)
        self.assertEqual(metrics["g2"]["total_attempts"], 2)
        self.assertAlmostEqual(metrics["g2"]["success_rate"], 0.5)

    def test_all_successful_per_goal(self):
        """All attempts for a goal are successful."""
        results = [
            {"goal": "g1", "success": True, "confidence": 0.9},
            {"goal": "g1", "success": True, "confidence": 0.8},
        ]
        metrics = calculate_per_goal_metrics(results)
        self.assertAlmostEqual(metrics["g1"]["success_rate"], 1.0)
        self.assertEqual(metrics["g1"]["successful_attacks"], 2)


class TestGenerateSummaryReport(unittest.TestCase):
    """Test generate_summary_report function."""

    def test_empty_results(self):
        """Empty list returns zeroed report."""
        report = generate_summary_report([])
        self.assertEqual(report["total_attacks"], 0)
        self.assertAlmostEqual(report["overall_success_rate"], 0.0)
        self.assertAlmostEqual(report["overall_confidence"], 0.0)
        self.assertEqual(report["per_goal_metrics"], {})
        self.assertEqual(report["unique_goals"], 0)

    def test_full_report(self):
        """Full report with mixed data."""
        results = [
            {"goal": "g1", "success": True, "confidence": 0.9},
            {"goal": "g1", "success": False, "confidence": 0.3},
            {"goal": "g2", "success": True, "confidence": 0.7},
        ]
        report = generate_summary_report(results)
        self.assertEqual(report["total_attacks"], 3)
        self.assertAlmostEqual(report["overall_success_rate"], 2 / 3)
        self.assertAlmostEqual(report["overall_confidence"], (0.9 + 0.3 + 0.7) / 3)
        self.assertEqual(report["unique_goals"], 2)
        self.assertIn("g1", report["per_goal_metrics"])
        self.assertIn("g2", report["per_goal_metrics"])

    def test_single_result_report(self):
        """Report with a single result."""
        results = [{"goal": "g1", "success": True, "confidence": 1.0}]
        report = generate_summary_report(results)
        self.assertEqual(report["total_attacks"], 1)
        self.assertAlmostEqual(report["overall_success_rate"], 1.0)
        self.assertEqual(report["unique_goals"], 1)

    def test_report_structure(self):
        """Report has all expected keys."""
        results = [{"goal": "g1", "success": True, "confidence": 0.5}]
        report = generate_summary_report(results)
        expected_keys = {
            "total_attacks",
            "overall_success_rate",
            "overall_confidence",
            "per_goal_metrics",
            "unique_goals",
        }
        self.assertEqual(set(report.keys()), expected_keys)


if __name__ == "__main__":
    unittest.main()
