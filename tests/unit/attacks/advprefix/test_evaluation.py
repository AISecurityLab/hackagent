# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for AdvPrefix evaluation aggregation logic."""

import logging
import unittest
from unittest.mock import MagicMock

from hackagent.attacks.techniques.advprefix.evaluation import EvaluationPipeline


class TestAdvPrefixEvaluationPipeline(unittest.TestCase):
    """Validate AdvPrefix evaluation aggregation behavior."""

    def _build_pipeline(self, max_ce=None) -> EvaluationPipeline:
        config = {
            "judges": [
                {
                    "type": "harmbench",
                    "identifier": "judge-model",
                    "endpoint": "http://localhost:9000/v1",
                }
            ],
            "max_ce": max_ce,
        }
        return EvaluationPipeline(
            config=config,
            logger=logging.getLogger("hackagent.attacks.advprefix.test"),
            client=MagicMock(),
        )

    def test_run_aggregation_computes_means_and_best_completion(self):
        pipeline = self._build_pipeline()

        input_data = [
            {
                "goal": "goal-a",
                "prefix": "prefix-a",
                "completion": "completion-low",
                "eval_hb": 0.1,
                "prefix_nll": 0.2,
                "result_id": "res-1",
            },
            {
                "goal": "goal-a",
                "prefix": "prefix-a",
                "completion": "completion-high",
                "eval_hb": 0.9,
                "prefix_nll": 0.2,
                "result_id": "res-1",
            },
        ]

        aggregated = pipeline._run_aggregation(input_data)

        self.assertEqual(len(aggregated), 1)
        item = aggregated[0]
        self.assertEqual(item["goal"], "goal-a")
        self.assertEqual(item["prefix"], "prefix-a")
        self.assertEqual(item["result_id"], "res-1")
        self.assertEqual(item["n_eval_samples"], 2)
        self.assertEqual(item["best_completion"], "completion-high")
        self.assertEqual(item["best_prompt"], "prefix-a")
        self.assertAlmostEqual(item["eval_hb_mean"], 0.5)
        self.assertEqual(item["eval_hb_count"], 2)

    def test_run_aggregation_returns_empty_when_nll_filter_removes_all(self):
        pipeline = self._build_pipeline(max_ce=0.05)

        input_data = [
            {
                "goal": "goal-a",
                "prefix": "prefix-a",
                "completion": "completion-1",
                "eval_hb": 0.8,
                "prefix_nll": 0.4,
            }
        ]

        aggregated = pipeline._run_aggregation(input_data)

        self.assertEqual(aggregated, [])


if __name__ == "__main__":
    unittest.main()
