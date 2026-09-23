# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PAIR rows are scored inline; post-processing only fills ``success``."""

import logging
import unittest

from hackagent.attacks._lib.inline_judge import postprocess_inline_results

LOGGER = logging.getLogger("test")


class TestPAIRPostProcessing(unittest.TestCase):
    def test_empty_input_returns_unchanged(self):
        self.assertEqual(
            postprocess_inline_results([], attack_label="PAIR", logger=LOGGER), []
        )

    def test_rows_with_best_score_are_preserved(self):
        rows = postprocess_inline_results(
            [{"best_score": 8.0, "success": True, "goal": "test", "response": "yes"}],
            attack_label="PAIR",
            logger=LOGGER,
        )
        self.assertTrue(rows[0]["success"])
        self.assertEqual(rows[0]["best_score"], 8.0)

    def test_error_items_get_zero_score(self):
        rows = postprocess_inline_results(
            [{"goal": "test", "error": "timeout", "response": None}],
            attack_label="PAIR",
            logger=LOGGER,
        )
        self.assertFalse(rows[0]["success"])
        self.assertEqual(rows[0]["best_score"], 0.0)

    def test_existing_success_field_is_preserved(self):
        rows = postprocess_inline_results(
            [{"best_score": 0.0, "success": True, "response": "yes"}],
            attack_label="PAIR",
            logger=LOGGER,
        )
        self.assertTrue(rows[0]["success"])

    def test_is_success_field_is_used_when_success_is_absent(self):
        rows = postprocess_inline_results(
            [
                {"goal": "g1", "best_score": 3, "is_success": False, "response": "no"},
                {"goal": "g2", "best_score": 9, "is_success": True, "response": "yes"},
            ],
            attack_label="PAIR",
            logger=LOGGER,
        )
        self.assertFalse(rows[0]["success"])
        self.assertTrue(rows[1]["success"])


if __name__ == "__main__":
    unittest.main()
