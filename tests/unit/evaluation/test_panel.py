# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.core.contracts import Sample
from hackagent.evaluation.panel import LLMJudge, Panel, normalize_score
from tests.fakes.judge import FakeJudge
from tests.fakes.llm import FakeLLM


class TestNormalize(unittest.TestCase):
    def test_binary_maps_onto_ten(self):
        self.assertEqual(normalize_score(1, "binary"), 10.0)
        self.assertEqual(normalize_score(0, "binary"), 0.0)

    def test_decimal_stays_on_ten(self):
        self.assertEqual(normalize_score(7.5, "decimal"), 7.5)


class TestPanel(unittest.TestCase):
    def test_mean_of_port_judges(self):
        panel = Panel(
            [FakeJudge(score=10.0, success=True), FakeJudge(score=0.0, success=False)],
            aggregation="mean",
            threshold=7.0,
        )
        verdict = panel.evaluate(Sample(goal="g", prompt="p", response="r"))
        self.assertEqual(verdict.score, 5.0)
        self.assertFalse(verdict.success)
        self.assertEqual(panel.score(Sample(goal="g", response="r")), 5.0)

    def test_any_follows_vote_count(self):
        panel = Panel(
            [FakeJudge(score=10.0, success=True), FakeJudge(score=0.0)],
            aggregation="any",
            threshold=7.0,
        )
        verdict = panel.evaluate(Sample(goal="g", response="r"))
        self.assertTrue(verdict.success)
        self.assertEqual(verdict.score, 10.0)

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
        verdict = panel.evaluate(Sample(goal="g", response="r"))
        self.assertTrue(verdict.success)

    def test_llm_judge_binary_is_normalised(self):
        judge = LLMJudge("harmbench", FakeLLM(script=["yes"]), name="hb")
        panel = Panel([judge], aggregation="mean", threshold=7.0)
        verdict = panel.evaluate(Sample(goal="g", prompt="p", response="harmful"))
        self.assertEqual(verdict.score, 10.0)
        self.assertTrue(verdict.success)
        self.assertEqual(verdict.votes[0].score, 1.0)

    def test_requires_a_judge(self):
        with self.assertRaises(ValueError):
            Panel([])


if __name__ == "__main__":
    unittest.main()
