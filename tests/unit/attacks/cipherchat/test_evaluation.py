# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for CipherChat evaluation logic via BaseEvaluationStep."""

import logging
import unittest
from unittest.mock import MagicMock

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep


def _completion_fn(item):
    return item.get("decoded_response") or item.get("response", "") or ""


def _prefix_fn(item):
    return item.get("full_prompt", "")


class TestCipherChatEvaluation(unittest.TestCase):
    def _make_eval(self, config=None):
        return BaseEvaluationStep(
            config=config or {"judges": [], "cipherchat_params": {}},
            logger=logging.getLogger("test"),
            client=MagicMock(),
        )

    def test_empty_input(self):
        ev = self._make_eval()
        result = ev.run(
            [],
            prefix_fn=_prefix_fn,
            completion_fn=_completion_fn,
            technique_params_key="cipherchat_params",
        )
        self.assertEqual(result, [])

    def test_error_items_get_zero_score(self):
        ev = self._make_eval()
        data = [
            {"goal": "g", "error": "fail", "response": None, "decoded_response": ""}
        ]
        result = ev.run(
            data,
            prefix_fn=_prefix_fn,
            completion_fn=_completion_fn,
            technique_params_key="cipherchat_params",
        )
        self.assertEqual(result[0]["best_score"], 0.0)
        self.assertFalse(result[0]["success"])

    def test_error_item_with_response_not_skipped(self):
        """An item with an error but a response should still pass through eval."""
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
        result = ev.run(
            data,
            prefix_fn=_prefix_fn,
            completion_fn=_completion_fn,
            technique_params_key="cipherchat_params",
        )
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
