# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for dashboard pure helper functions."""

import unittest

from hackagent.server.dashboard._helpers import (
    _duration_seconds,
    _eval_color,
    _eval_label,
    _format_latency,
    _result_bucket,
    _short_date,
)


class TestDashboardDateAndLatencyHelpers(unittest.TestCase):
    """Test timestamp and latency format helpers."""

    def test_short_date_valid_iso(self):
        self.assertEqual(_short_date("2026-03-31T10:20:30Z"), "31/03/2026")

    def test_short_date_invalid_or_empty(self):
        self.assertEqual(_short_date(None), "—")
        self.assertEqual(_short_date("not-a-date"), "—")

    def test_duration_seconds_valid_and_negative(self):
        self.assertEqual(
            _duration_seconds("2026-03-31T10:00:00Z", "2026-03-31T10:00:02.500000Z"),
            2.5,
        )
        self.assertEqual(
            _duration_seconds("2026-03-31T10:00:03Z", "2026-03-31T10:00:01Z"),
            0.0,
        )

    def test_duration_seconds_missing_or_invalid(self):
        self.assertIsNone(_duration_seconds(None, "2026-03-31T10:00:01Z"))
        self.assertIsNone(_duration_seconds("2026-03-31T10:00:01Z", None))
        self.assertIsNone(_duration_seconds("bad", "2026-03-31T10:00:01Z"))

    def test_format_latency_variants(self):
        self.assertEqual(_format_latency(None), "—")
        self.assertEqual(_format_latency(0.123), "123ms")
        self.assertEqual(_format_latency(3.2), "3.2s")
        self.assertEqual(_format_latency(65.0), "1m 05s")
        self.assertEqual(_format_latency(3661.0), "1h 01m 01s")


class TestDashboardEvaluationHelpers(unittest.TestCase):
    """Test result bucketing and evaluation labels/colors."""

    def test_result_bucket_classification(self):
        self.assertEqual(_result_bucket("SUCCESSFUL_JAILBREAK"), "jailbreak")
        self.assertEqual(_result_bucket("PASSED_CRITERIA"), "mitigated")
        self.assertEqual(_result_bucket("FAILED_JAILBREAK"), "mitigated")
        self.assertEqual(_result_bucket("FAILED_CRITERIA"), "failed")
        self.assertEqual(_result_bucket("NOT_EVALUATED"), "pending")

    def test_result_bucket_exception_note_overrides_status(self):
        self.assertEqual(
            _result_bucket("FAILED_JAILBREAK", notes="run failed with exception: x"),
            "failed",
        )

    def test_eval_label_uses_bucket_logic(self):
        self.assertEqual(_eval_label("SUCCESSFUL_JAILBREAK"), "Jailbreak")
        self.assertEqual(_eval_label("FAILED_JAILBREAK"), "Mitigated")
        self.assertEqual(_eval_label("FAILED_CRITERIA"), "Failed")
        self.assertEqual(_eval_label("NOT_EVALUATED"), "Pending")

    def test_eval_label_exception_note_overrides(self):
        self.assertEqual(
            _eval_label("FAILED_JAILBREAK", notes="FAILED WITH EXCEPTION"),
            "Failed",
        )

    def test_eval_color_uses_bucket_logic(self):
        self.assertEqual(_eval_color("SUCCESSFUL_JAILBREAK"), "negative")
        self.assertEqual(_eval_color("PASSED_CRITERIA"), "positive")
        self.assertEqual(_eval_color("FAILED_CRITERIA"), "warning")
        self.assertEqual(_eval_color("NOT_EVALUATED"), "grey-6")

    def test_eval_color_exception_note_overrides(self):
        self.assertEqual(
            _eval_color("FAILED_JAILBREAK", notes="failed with exception: err"),
            "warning",
        )


if __name__ == "__main__":
    unittest.main()
