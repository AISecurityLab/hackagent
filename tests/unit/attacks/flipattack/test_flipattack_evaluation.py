# Copyright 2025 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for FlipAttack evaluation logic via BaseEvaluationStep.run()."""

import logging
import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep

logger = logging.getLogger(__name__)


def _prefix_fn(item):
    return item.get("full_prompt") or ""


def _make_eval_config(**kwargs):
    cfg = {
        "flipattack_params": {},
        "judges": [],
        "filter_len": 0,
        "output_dir": "./logs/runs",
    }
    cfg.update(kwargs)
    return cfg


def _make_eval(config=None):
    return BaseEvaluationStep(
        config=config or _make_eval_config(),
        logger=logger,
        client=MagicMock(),
    )


class TestFlipAttackEvaluationViaRun(unittest.TestCase):
    def test_empty_input_returns_empty(self):
        ev = _make_eval()
        result = ev.run(
            [], prefix_fn=_prefix_fn, technique_params_key="flipattack_params"
        )
        self.assertEqual(result, [])

    def test_error_items_get_zero_score_and_failure(self):
        ev = _make_eval()
        data = [
            {
                "goal": "bad goal",
                "error": "execution failed",
                "response": None,
                "full_prompt": None,
            }
        ]
        result = ev.run(
            data, prefix_fn=_prefix_fn, technique_params_key="flipattack_params"
        )
        self.assertEqual(result[0]["best_score"], 0.0)
        self.assertFalse(result[0]["success"])
        self.assertIn("evaluation_notes", result[0])

    def test_valid_items_go_through_evaluation(self):
        ev = _make_eval()
        data = [
            {
                "goal": "test goal",
                "response": "response text",
                "full_prompt": "full prompt text",
                "error": None,
            }
        ]
        result = ev.run(
            data, prefix_fn=_prefix_fn, technique_params_key="flipattack_params"
        )
        self.assertEqual(len(result), 1)
        self.assertIn("best_score", result[0])
        self.assertIn("success", result[0])

    def test_full_prompt_used_as_prefix(self):
        """The prefix_fn must pick up full_prompt."""
        item = {"full_prompt": "Full prompt content", "goal": "goal"}
        self.assertEqual(_prefix_fn(item), "Full prompt content")

    def test_statistics_are_initialized(self):
        ev = _make_eval()
        self.assertEqual(ev._statistics["input_count"], 0)
        self.assertEqual(ev._statistics["evaluated_count"], 0)

    @patch(
        "hackagent.attacks.evaluator.evaluation_step.BaseEvaluationStep._sync_to_server"
    )
    def test_statistics_updated_after_run(self, mock_sync):
        mock_sync.return_value = None
        ev = _make_eval()
        data = [
            {"goal": "g1", "response": "r1", "full_prompt": "p1"},
            {"goal": "g2", "response": "r2", "full_prompt": "p2"},
        ]
        ev.run(data, prefix_fn=_prefix_fn, technique_params_key="flipattack_params")
        self.assertEqual(ev._statistics["input_count"], 2)


if __name__ == "__main__":
    unittest.main()
