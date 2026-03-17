import unittest
from unittest.mock import MagicMock
import logging

from hackagent.attacks.techniques.pap.evaluation import PAPEvaluation


class TestPAPEvaluation(unittest.TestCase):
    def _make_eval(self, config=None):
        cfg = config or {
            "pap_params": {},
            "judges": [],
            "output_dir": "./logs/runs",
        }
        return PAPEvaluation(
            config=cfg,
            logger=logging.getLogger("test"),
            client=MagicMock(),
        )

    def test_empty_input(self):
        ev = self._make_eval()
        self.assertEqual(ev.execute([]), [])

    def test_error_items_get_default_scores(self):
        ev = self._make_eval()
        data = [{"goal": "test", "error": "timeout", "response": None}]
        result = ev.execute(data)
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
        result = ev.execute(data)
        self.assertTrue(result[0]["success"])
        self.assertEqual(result[0]["best_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
