import unittest
from unittest.mock import MagicMock
import logging

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep


class TestPAPEvaluation(unittest.TestCase):
    def _make_eval(self, config=None):
        cfg = config or {
            "pap_params": {},
            "judges": [],
            "output_dir": "./logs/runs",
        }
        return BaseEvaluationStep(
            config=cfg,
            logger=logging.getLogger("test"),
            client=MagicMock(),
        )

    def test_empty_input(self):
        ev = self._make_eval()
        result = ev._postprocess_inline_judge_results([], attack_label="PAP")
        self.assertEqual(result, [])

    def test_error_items_get_default_scores(self):
        ev = self._make_eval()
        data = [{"goal": "test", "error": "timeout", "response": None}]
        result = ev._postprocess_inline_judge_results(data, attack_label="PAP")
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["success"])
        self.assertEqual(result[0]["best_score"], 0.0)

    def test_success_items_preserve_scores(self):
        ev = self._make_eval()
        data = [
            {
                "goal": "test",
                "response": "harmful content",
                "error": None,
                "best_score": 1.0,
                "success": True,
            }
        ]
        result = ev._postprocess_inline_judge_results(data, attack_label="PAP")
        self.assertTrue(result[0]["success"])
        self.assertEqual(result[0]["best_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
