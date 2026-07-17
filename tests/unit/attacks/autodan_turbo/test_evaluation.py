import unittest
from unittest.mock import MagicMock

from hackagent.attacks.techniques.autodan_turbo import autodan_eval as evaluation


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

    def test_execute_runs_shared_llm_judge_pipeline(self):
        step = evaluation.AutoDANTurboEvaluation(
            config={"autodan_turbo_params": {"break_score": 7.0}},
            logger=MagicMock(),
            client=MagicMock(),
        )
        step.run_full_evaluation = MagicMock(
            side_effect=lambda rows: [
                {
                    **rows[0],
                    "eval_hb": 1,
                    "explanation_hb": "mocked",
                    "best_score": 1.0,
                    "success": True,
                }
            ]
        )

        out = step.execute(
            [{"goal": "g", "prompt": "p", "response": "r", "score": 7.5}]
        )

        step.run_full_evaluation.assert_called_once()
        self.assertEqual(out[0]["autodan_score"], 7.5)
        self.assertEqual(out[0]["attack_score"], 7.5)
        self.assertEqual(out[0]["best_score"], 1.0)
        self.assertTrue(out[0]["success"])

    def test_module_execute_entrypoint(self):
        out = evaluation.execute([], config={}, client=MagicMock(), logger=MagicMock())
        self.assertEqual(out, [])

    def test_execute_with_only_errors_passes_through_shared_evaluation(self):
        step = evaluation.AutoDANTurboEvaluation(
            config={}, logger=MagicMock(), client=MagicMock()
        )
        step.run_full_evaluation = MagicMock(
            return_value=[
                {
                    "goal": "g",
                    "autodan_score": 0.0,
                    "attack_score": 0.0,
                    "success": False,
                    "best_score": 0.0,
                }
            ]
        )

        out = step.execute([{"goal": "g", "error": "x"}])
        step.run_full_evaluation.assert_called_once()
        self.assertFalse(out[0]["success"])
        self.assertEqual(out[0]["autodan_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
