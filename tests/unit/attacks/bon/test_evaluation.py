# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import unittest

from hackagent.attacks._lib.inline_judge import postprocess_inline_results


class TestBoNEvaluation(unittest.TestCase):
    def test_empty_input(self):
        result = postprocess_inline_results(
            [], attack_label="BoN", logger=logging.getLogger("test")
        )
        self.assertEqual(result, [])

    def test_error_items_skipped(self):
        data = [{"goal": "test", "error": "failed", "response": None}]
        result = postprocess_inline_results(
            data, attack_label="BoN", logger=logging.getLogger("test")
        )
        self.assertFalse(result[0]["success"])
        self.assertEqual(result[0]["best_score"], 0.0)

    def test_augmented_prompt_preserved(self):
        data = [
            {
                "goal": "test goal",
                "augmented_prompt": "tEst goAl",
                "response": "some response",
                "error": None,
                "best_score": 1.0,
                "success": True,
            }
        ]
        result = postprocess_inline_results(
            data, attack_label="BoN", logger=logging.getLogger("test")
        )
        self.assertEqual(result[0]["augmented_prompt"], "tEst goAl")
        self.assertEqual(result[0]["goal"], "test goal")


if __name__ == "__main__":
    unittest.main()
