import unittest
from unittest.mock import MagicMock

from hackagent.attacks.techniques.autodan_turbo import evaluation


class TestAutoDANTurboEvaluation(unittest.TestCase):
    def test_extract_autodan_score(self):
        self.assertEqual(
            evaluation.AutoDANTurboEvaluation._extract_autodan_score(
                {"autodan_score": 7}
            ),
            7.0,
        )
        self.assertEqual(
            evaluation.AutoDANTurboEvaluation._extract_autodan_score(
                {"attack_score": 5}
            ),
            5.0,
        )
        self.assertEqual(
            evaluation.AutoDANTurboEvaluation._extract_autodan_score({"score": 3}), 3.0
        )
        self.assertEqual(
            evaluation.AutoDANTurboEvaluation._extract_autodan_score({}), 0.0
        )

    def test_execute_enriches_results(self):
        step = evaluation.AutoDANTurboEvaluation(
            config={}, logger=MagicMock(), client=MagicMock()
        )
        step._resolve_judges_from_config = MagicMock(
            return_value=[{"identifier": "j", "type": "harmbench"}]
        )
        step._build_base_eval_config = MagicMock(return_value={})
        step._run_evaluation = MagicMock(
            return_value=[
                {
                    "goal": "g",
                    "prefix": "p",
                    "completion": "r",
                    "eval_hb": 1.0,
                    "explanation_hb": "ok",
                }
            ]
        )

        def _enrich(items, _errors):
            for item in items:
                item["best_score"] = 1.0
                item["success"] = True

        step._enrich_items_with_scores = MagicMock(side_effect=_enrich)
        step._update_tracker = MagicMock()
        step._sync_to_server = MagicMock()
        step._log_evaluation_asr = MagicMock()

        out = step.execute(
            [{"goal": "g", "prompt": "p", "response": "r", "score": 7.0}]
        )
        self.assertEqual(out[0]["autodan_score"], 7.0)
        self.assertEqual(out[0]["attack_score"], 7.0)
        self.assertTrue(out[0]["judge_success"])

    def test_module_execute_entrypoint(self):
        out = evaluation.execute([], config={}, client=MagicMock(), logger=MagicMock())
        self.assertEqual(out, [])

    def test_execute_with_only_errors_skips_judges(self):
        step = evaluation.AutoDANTurboEvaluation(
            config={}, logger=MagicMock(), client=MagicMock()
        )
        step._resolve_judges_from_config = MagicMock(
            return_value=[{"identifier": "j", "type": "harmbench"}]
        )
        step._enrich_items_with_scores = MagicMock()

        out = step.execute([{"goal": "g", "error": "x"}])
        self.assertEqual(out[0]["best_score"], 0.0)
        self.assertFalse(out[0]["success"])
        step._enrich_items_with_scores.assert_called_once()


if __name__ == "__main__":
    unittest.main()
