# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for BaseEvaluationStep judge type resolution."""

import unittest
from unittest.mock import MagicMock

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep


class TestBaseEvaluationStepJudgeResolution(unittest.TestCase):
    """Validate judge type inference and config resolution precedence."""

    def setUp(self):
        self.step = BaseEvaluationStep(
            config={},
            logger=MagicMock(),
            client=MagicMock(),
        )

    def test_infer_judge_type_harmbench_variant_identifier(self):
        """Model ids containing HarmBenchVariant must map to harmbench_variant."""
        inferred = self.step.infer_judge_type("foo/HarmBenchVariant-7B")
        self.assertEqual(inferred, "harmbench_variant")

    def test_prepare_judge_configs_prefers_type_over_evaluator_type(self):
        """If both keys are present, explicit 'type' should win."""
        judges_to_run = self.step._prepare_judge_configs(
            [
                {
                    "identifier": "Abel-24-HarmClassifier",
                    "type": "harmbench_variant",
                    "evaluator_type": "harmbench",
                }
            ],
            base_config={},
        )

        self.assertEqual(len(judges_to_run), 1)
        judge_type, _cfg = judges_to_run[0]
        self.assertEqual(judge_type, "harmbench_variant")


if __name__ == "__main__":
    unittest.main()
