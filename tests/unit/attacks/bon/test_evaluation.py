import unittest
from unittest.mock import MagicMock
import logging

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep


class TestBoNEvaluation(unittest.TestCase):
    def _make_eval(self, config=None):
        return BaseEvaluationStep(
            config=config or {"bon_params": {}, "judges": [], "filter_len": 10},
            logger=logging.getLogger("test"),
            client=MagicMock(),
        )

    def test_empty_input(self):
        ev = self._make_eval()
        result = ev._postprocess_inline_judge_results([], attack_label="BoN")
        self.assertEqual(result, [])

    def test_error_items_skipped(self):
        ev = self._make_eval()
        data = [{"goal": "test", "error": "failed", "response": None}]
        result = ev._postprocess_inline_judge_results(data, attack_label="BoN")
        self.assertFalse(result[0]["success"])
        self.assertEqual(result[0]["best_score"], 0.0)

    def test_augmented_prompt_preserved(self):
        ev = self._make_eval()
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
        result = ev._postprocess_inline_judge_results(data, attack_label="BoN")
        self.assertEqual(result[0]["augmented_prompt"], "tEst goAl")
        self.assertEqual(result[0]["goal"], "test goal")


if __name__ == "__main__":
    unittest.main()
