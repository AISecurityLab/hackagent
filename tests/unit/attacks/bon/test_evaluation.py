import unittest
from unittest.mock import MagicMock
import logging

from hackagent.attacks.techniques.bon.evaluation import BoNEvaluation


class TestBoNEvaluation(unittest.TestCase):
    def _make_eval(self, config=None):
        return BoNEvaluation(
            config=config or {"bon_params": {}, "judges": [], "filter_len": 10},
            logger=logging.getLogger("test"),
            client=MagicMock(),
        )

    def test_empty_input(self):
        ev = self._make_eval()
        self.assertEqual(ev.execute([]), [])

    def test_error_items_skipped(self):
        ev = self._make_eval()
        data = [{"goal": "test", "error": "failed", "response": None}]
        result = ev.execute(data)
        self.assertFalse(result[0]["success"])
        self.assertEqual(result[0]["best_score"], 0.0)

    def test_transform_rows_extracts_augmented_prompt(self):
        data = [
            {
                "goal": "test goal",
                "augmented_prompt": "tEst goAl",
                "response": "some response",
                "error": None,
            }
        ]
        rows, errors = BoNEvaluation._transform_to_eval_rows(data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(errors), 0)
        self.assertEqual(rows[0]["goal"], "test goal")
        self.assertEqual(rows[0]["prefix"], "tEst goAl")
        self.assertEqual(rows[0]["completion"], "some response")

    def test_transform_rows_handles_missing_augmented_prompt(self):
        data = [
            {
                "goal": "test goal",
                "response": "resp",
                "error": None,
            }
        ]
        rows, _ = BoNEvaluation._transform_to_eval_rows(data)
        # Falls back to goal text
        self.assertEqual(rows[0]["prefix"], "test goal")

    def test_transform_rows_counts_errors(self):
        data = [
            {"goal": "g1", "error": "fail", "response": None},
            {"goal": "g2", "error": None, "response": "ok", "augmented_prompt": "g2"},
        ]
        rows, errors = BoNEvaluation._transform_to_eval_rows(data)
        self.assertEqual(len(rows), 1)
        self.assertIn(0, errors)


if __name__ == "__main__":
    unittest.main()
