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

    def test_execute_uses_ctx_judge_when_present(self):
        from hackagent.core.contracts import Verdict

        class _Judge:
            def evaluate(self, sample):
                return Verdict(success=True, score=8.0, explanation="mocked")

            def score(self, sample):
                return 8.0

        step = evaluation.AutoDANTurboEvaluation(
            config={
                "autodan_turbo_params": {"break_score": 7.0},
                "_judge": _Judge(),
            },
            logger=MagicMock(),
            client=MagicMock(),
        )

        out = step.execute(
            [{"goal": "g", "prompt": "p", "response": "r", "score": 7.5}]
        )

        self.assertEqual(out[0]["autodan_score"], 7.5)
        self.assertEqual(out[0]["attack_score"], 7.5)
        self.assertEqual(out[0]["best_score"], 8.0)
        self.assertTrue(out[0]["success"])
        self.assertEqual(out[0]["explanation"], "mocked")

    def test_module_execute_entrypoint(self):
        out = evaluation.execute([], config={}, client=MagicMock(), logger=MagicMock())
        self.assertEqual(out, [])

    def test_execute_without_judge_uses_break_score(self):
        step = evaluation.AutoDANTurboEvaluation(
            config={"autodan_turbo_params": {"break_score": 7.0}},
            logger=MagicMock(),
            client=MagicMock(),
        )

        out = step.execute([{"goal": "g", "error": "x", "score": 0.0}])
        self.assertFalse(out[0]["success"])
        self.assertEqual(out[0]["autodan_score"], 0.0)
        self.assertEqual(out[0]["best_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
