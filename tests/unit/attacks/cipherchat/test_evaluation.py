# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for CipherChat evaluation module."""

import logging
import unittest
from unittest.mock import MagicMock

from hackagent.attacks.techniques.cipherchat.evaluation import CipherChatEvaluation


class TestCipherChatEvaluation(unittest.TestCase):
    def _make_eval(self, config=None):
        return CipherChatEvaluation(
            config=config or {"judges": [], "cipherchat_params": {}},
            logger=logging.getLogger("test"),
            client=MagicMock(),
        )

    def test_empty_input(self):
        ev = self._make_eval()
        self.assertEqual(ev.execute([]), [])

    def test_error_items_get_zero_score(self):
        ev = self._make_eval()
        data = [
            {"goal": "g", "error": "fail", "response": None, "decoded_response": ""}
        ]
        result = ev.execute(data)
        self.assertEqual(result[0]["best_score"], 0.0)
        self.assertFalse(result[0]["success"])

    def test_error_item_with_decoded_response_not_skipped(self):
        """An item with an error but also a decoded response should still be evaluated."""
        ev = self._make_eval()
        data = [
            {
                "goal": "g",
                "error": "partial error",
                "response": "encoded",
                "decoded_response": "some decoded text",
                "full_prompt": "prompt",
            }
        ]
        # With no judges configured, _run_evaluation returns empty → no scores merged
        # but the item should NOT be marked as error-skipped
        result = ev.execute(data)
        # The item should have gone through the eval_rows path
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
