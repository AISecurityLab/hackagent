# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for PAIR post-processing via BaseEvaluationStep.

PAIR scores responses inline; this tests that _postprocess_inline_judge_results
correctly normalises pre-scored rows into the shared output contract.
"""

import unittest
from unittest.mock import MagicMock

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep


def _eval(config=None):
    return BaseEvaluationStep(
        config=config or {}, logger=MagicMock(), client=MagicMock()
    )


class TestPAIRPostProcessing(unittest.TestCase):
    def test_empty_input_returns_unchanged(self):
        result = _eval()._postprocess_inline_judge_results([], attack_label="PAIR")
        self.assertEqual(result, [])

    def test_rows_with_best_score_are_preserved(self):
        step = _eval()
        rows = step._postprocess_inline_judge_results(
            [{"best_score": 8.0, "success": True, "goal": "test"}],
            attack_label="PAIR",
        )
        self.assertTrue(rows[0]["success"])
        self.assertEqual(rows[0]["best_score"], 8.0)

    def test_error_items_get_zero_score(self):
        step = _eval()
        rows = step._postprocess_inline_judge_results(
            [{"goal": "test", "error": "timeout", "response": None}],
            attack_label="PAIR",
        )
        self.assertFalse(rows[0]["success"])
        self.assertEqual(rows[0]["best_score"], 0.0)

    def test_existing_success_field_is_preserved(self):
        step = _eval()
        rows = step._postprocess_inline_judge_results(
            [{"best_score": 0.0, "success": True}],
            attack_label="PAIR",
        )
        self.assertTrue(rows[0]["success"])


if __name__ == "__main__":
    unittest.main()
