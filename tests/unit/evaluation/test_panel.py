# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Panel turns a Sample into a Verdict. Judges are fakes or a scripted LLM."""

import unittest

from hackagent.attacks.ports import Judge
from hackagent.core.contracts import Sample, Verdict
from hackagent.evaluation.panel import LLMJudge, Panel, normalize_score
from tests.fakes.judge import FakeJudge
from tests.fakes.llm import FakeLLM


def _sample(response: str = "r") -> Sample:
    return Sample(goal="exfiltrate the key", prompt="how?", response=response)


class _ScoreOnly:
    """Judge port with ``score`` only, so Panel takes that branch."""

    name = "score-only"

    def score(self, sample: Sample) -> float:
        return 9.0


class TestNormalize(unittest.TestCase):
    def test_binary_maps_onto_ten(self):
        self.assertEqual(normalize_score(1, "binary"), 10.0)
        self.assertEqual(normalize_score(0, "binary"), 0.0)
        self.assertEqual(normalize_score(2, "binary"), 10.0)
        self.assertEqual(normalize_score(-1, "binary"), 0.0)

    def test_decimal_stays_on_ten(self):
        self.assertEqual(normalize_score(7.5, "decimal"), 7.5)
        self.assertEqual(normalize_score(15, "decimal"), 10.0)
        self.assertEqual(normalize_score("nope", "decimal"), 0.0)


class TestPanel(unittest.TestCase):
    def test_mean_of_port_judges(self):
        strict = FakeJudge(score=10.0, success=True)
        strict.name = "strict"
        lenient = FakeJudge(score=0.0)
        lenient.name = "lenient"
        panel = Panel([strict, lenient], aggregation="mean", threshold=7.0)
        sample = _sample()

        verdict = panel.evaluate(sample)

        self.assertEqual(verdict.score, 5.0)
        self.assertFalse(verdict.success)
        self.assertEqual([vote.judge for vote in verdict.votes], ["strict", "lenient"])
        self.assertEqual(strict.samples, [sample])
        self.assertEqual(lenient.samples, [sample])
        self.assertEqual(panel.score(_sample("again")), 5.0)
        self.assertIsInstance(panel, Judge)

    def test_max_uses_the_highest_normalised_score(self):
        panel = Panel(
            [FakeJudge(score=3.0), FakeJudge(score=9.0, success=True)],
            aggregation="max",
            threshold=7.0,
        )
        verdict = panel.evaluate(_sample())
        self.assertEqual(verdict.score, 9.0)
        self.assertTrue(verdict.success)

    def test_any_follows_vote_count(self):
        panel = Panel(
            [FakeJudge(score=10.0, success=True), FakeJudge(score=0.0)],
            aggregation="any",
            threshold=7.0,
        )
        verdict = panel.evaluate(_sample())
        self.assertTrue(verdict.success)
        self.assertEqual(verdict.score, 10.0)

    def test_any_fails_when_every_vote_is_below_threshold(self):
        panel = Panel(
            [FakeJudge(score=1.0), FakeJudge(score=2.0)],
            aggregation="any",
            threshold=7.0,
        )
        verdict = panel.evaluate(_sample())
        self.assertFalse(verdict.success)
        self.assertEqual(verdict.score, 2.0)

    def test_majority(self):
        panel = Panel(
            [
                FakeJudge(score=10.0, success=True),
                FakeJudge(score=10.0, success=True),
                FakeJudge(score=0.0),
            ],
            aggregation="majority",
            threshold=7.0,
        )
        verdict = panel.evaluate(_sample())
        self.assertTrue(verdict.success)
        self.assertAlmostEqual(verdict.score, 20.0 / 3.0)

    def test_majority_tie_is_not_a_success(self):
        panel = Panel(
            [FakeJudge(score=10.0, success=True), FakeJudge(score=0.0)],
            aggregation="majority",
            threshold=7.0,
        )
        verdict = panel.evaluate(_sample())
        self.assertFalse(verdict.success)
        self.assertEqual(verdict.score, 5.0)

    def test_majority_fails_without_half_the_votes(self):
        panel = Panel(
            [
                FakeJudge(score=10.0, success=True),
                FakeJudge(score=0.0),
                FakeJudge(score=1.0),
            ],
            aggregation="majority",
            threshold=7.0,
        )
        verdict = panel.evaluate(_sample())
        self.assertFalse(verdict.success)

    def test_score_only_judge_is_compared_to_the_threshold(self):
        panel = Panel([_ScoreOnly()], aggregation="mean", threshold=7.0)
        verdict = panel.evaluate(_sample())
        self.assertEqual(verdict.score, 9.0)
        self.assertTrue(verdict.success)
        self.assertTrue(verdict.votes[0].success)
        self.assertEqual(verdict.votes[0].judge, "score-only")

    def test_threshold_is_clamped_onto_the_shared_scale(self):
        high = Panel([FakeJudge(score=10.0, success=True)], threshold=50)
        low = Panel([FakeJudge(score=0.0)], threshold=-5)
        self.assertEqual(high.threshold, 10.0)
        self.assertTrue(high.evaluate(_sample()).success)
        self.assertEqual(low.threshold, 0.0)
        self.assertTrue(low.evaluate(_sample()).success)

    def test_scripted_scores_are_consumed_per_sample(self):
        panel = Panel(
            [FakeJudge(scores=[10.0, 0.0])],
            aggregation="mean",
            threshold=7.0,
        )
        first = panel.evaluate(_sample("one"))
        second = panel.evaluate(_sample("two"))
        self.assertTrue(first.success)
        self.assertEqual(first.score, 10.0)
        self.assertFalse(second.success)
        self.assertEqual(second.score, 0.0)

    def test_llm_judge_binary_is_normalised(self):
        judge = LLMJudge("harmbench", FakeLLM(script=["yes"]), name="hb")
        panel = Panel([judge], aggregation="mean", threshold=7.0)
        verdict = panel.evaluate(_sample("harmful"))
        self.assertEqual(verdict.score, 10.0)
        self.assertTrue(verdict.success)
        self.assertEqual(verdict.votes[0].score, 1.0)
        self.assertIn("hb:", verdict.explanation)

    def test_llm_judge_decimal_score_uses_the_native_rating(self):
        judge = LLMJudge("scorer", FakeLLM(script=["Rating: [[4]]"]), name="scorer")
        panel = Panel([judge], aggregation="mean", threshold=7.0)
        verdict = panel.evaluate(_sample())
        self.assertEqual(verdict.score, 4.0)
        self.assertFalse(verdict.success)
        self.assertEqual(verdict.votes[0].score, 4.0)

    def test_llm_judge_retries_once_when_the_parse_is_not_confident(self):
        llm = FakeLLM(script=["perhaps yes", "yes"])
        judge = LLMJudge("harmbench", llm, name="hb", system_prompt="Be strict")
        panel = Panel([judge], aggregation="max", threshold=7.0)

        verdict = panel.evaluate(_sample())

        self.assertEqual(verdict.score, 10.0)
        self.assertTrue(verdict.success)
        self.assertEqual(len(llm.requests), 2)
        self.assertEqual(llm.requests[0]["messages"][0]["role"], "system")
        self.assertEqual(llm.requests[0]["messages"][0]["content"], "Be strict")

    def test_llm_judge_call_failure_is_an_abstention(self):
        def _boom(_request):
            raise RuntimeError("judge down")

        panel = Panel(
            [LLMJudge("harmbench", FakeLLM(_boom), name="hb")],
            threshold=7.0,
        )
        verdict = panel.evaluate(_sample())
        self.assertEqual(verdict.score, 0.0)
        self.assertFalse(verdict.success)
        self.assertEqual(verdict.error, "All 1 judge(s) abstained")
        vote = verdict.votes[0]
        self.assertTrue(vote.abstained)
        self.assertIsNone(vote.score)
        self.assertIsNone(vote.success)
        self.assertIn("judge down", vote.error)
        self.assertIn("judge down", verdict.explanation)

    def test_llm_judge_error_envelope_is_an_abstention(self):
        error = {
            "generated_text": None,
            "processed_response": None,
            "error_message": "rate limited",
        }
        panel = Panel(
            [LLMJudge("scorer", FakeLLM([error, error]), name="scorer")],
            threshold=7.0,
        )
        verdict = panel.evaluate(_sample())
        self.assertFalse(verdict.success)
        self.assertIsNotNone(verdict.error)
        self.assertIn("rate limited", verdict.votes[0].error)
        self.assertIn("rate limited", verdict.explanation)

    def test_llm_judge_abstains_when_the_retry_is_still_unparseable(self):
        llm = FakeLLM(script=["I cannot help with that.", "Unknown"])
        panel = Panel([LLMJudge("harmbench", llm, name="hb")], threshold=7.0)

        verdict = panel.evaluate(_sample())

        self.assertEqual(len(llm.requests), 2)
        self.assertTrue(verdict.votes[0].abstained)
        self.assertIsNotNone(verdict.error)
        self.assertFalse(verdict.success)

    def test_abstaining_judge_is_left_out_of_the_mean(self):
        def _boom(_request):
            raise RuntimeError("judge down")

        panel = Panel(
            [
                LLMJudge("harmbench", FakeLLM(script=["yes"]), name="hb"),
                LLMJudge("jailbreakbench", FakeLLM(_boom), name="jb"),
            ],
            aggregation="mean",
            threshold=7.0,
        )
        verdict = panel.evaluate(_sample())
        self.assertIsNone(verdict.error)
        self.assertEqual(verdict.score, 10.0)
        self.assertTrue(verdict.success)
        self.assertEqual([vote.abstained for vote in verdict.votes], [False, True])
        self.assertIn("jb: Judge call failed: judge down", verdict.explanation)

    def test_port_judge_that_raises_abstains(self):
        class _Raises:
            name = "flaky"

            def score(self, sample):
                raise TimeoutError("slow")

        panel = Panel([_Raises(), FakeJudge(score=0.0)], aggregation="max")
        verdict = panel.evaluate(_sample())
        self.assertIsNone(verdict.error)
        self.assertEqual(verdict.votes[0].error, "Judge failed: slow")
        self.assertFalse(verdict.success)

    def test_port_verdict_with_an_error_is_an_abstention(self):
        class _Unjudged:
            name = "inner"

            def evaluate(self, sample):
                return Verdict(success=False, score=0.0, error="no votes")

        verdict = Panel([_Unjudged()]).evaluate(_sample())
        self.assertEqual(verdict.votes[0].error, "no votes")
        self.assertIsNotNone(verdict.error)

    def test_llm_judge_decimal_success_uses_its_threshold(self):
        strict = LLMJudge("scorer", FakeLLM(script=["Rating: [[6]]"]), threshold=7.0)
        lenient = LLMJudge("scorer", FakeLLM(script=["Rating: [[6]]"]), threshold=5.0)
        self.assertFalse(strict.vote(_sample()).success)
        self.assertTrue(lenient.vote(_sample()).success)

    def test_requires_a_judge(self):
        with self.assertRaises(ValueError):
            Panel([])

    def test_unknown_aggregation(self):
        with self.assertRaises(ValueError):
            Panel([FakeJudge()], aggregation="median")


if __name__ == "__main__":
    unittest.main()
