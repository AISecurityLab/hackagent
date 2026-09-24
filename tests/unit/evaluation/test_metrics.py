# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Metrics take Verdicts. Panel.evaluate is the producer."""

import unittest

from hackagent.core.contracts import JudgeVote, Sample, Verdict
from hackagent.evaluation.metrics import (
    fleiss_kappa,
    majority_vote_rate,
    mean_score,
    per_judge_strictness,
    success_rate,
    summary,
)
from hackagent.evaluation.panel import Panel
from tests.fakes.judge import FakeJudge


def _verdict(success: bool, score: float, *votes: JudgeVote) -> Verdict:
    return Verdict(success=success, score=score, votes=list(votes))


def _vote(judge: str, success: bool, score: float = 1.0) -> JudgeVote:
    return JudgeVote(judge=judge, score=score, success=success)


class TestVerdictMetrics(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(success_rate([]), 0.0)
        self.assertEqual(mean_score([]), 0.0)
        self.assertEqual(majority_vote_rate([]), 0.0)
        self.assertEqual(fleiss_kappa([]), 1.0)
        self.assertEqual(per_judge_strictness([]), {"bias_gap": 0.0})
        report = summary([])
        self.assertEqual(report["total"], 0)
        self.assertEqual(report["success_rate"], 0.0)
        self.assertEqual(report["mean_score"], 0.0)
        self.assertEqual(report["fleiss_kappa"], 1.0)

    def test_success_and_mean(self):
        verdicts = [
            _verdict(True, 10.0),
            _verdict(False, 0.0),
            _verdict(True, 5.0),
        ]
        self.assertAlmostEqual(success_rate(verdicts), 2 / 3)
        self.assertEqual(mean_score(verdicts), 5.0)

    def test_single_judge_or_no_votes_agrees_with_itself(self):
        verdicts = [_verdict(True, 8.0, _vote("only", True, 8.0))]
        self.assertEqual(fleiss_kappa(verdicts), 1.0)
        self.assertEqual(majority_vote_rate(verdicts), success_rate(verdicts))
        self.assertEqual(majority_vote_rate([_verdict(False, 1.0)]), 0.0)

    def test_fleiss_perfect_agreement(self):
        votes = [_vote("a", True), _vote("b", True)]
        verdicts = [
            _verdict(True, 10.0, *votes),
            _verdict(True, 10.0, *votes),
        ]
        self.assertEqual(fleiss_kappa(verdicts), 1.0)
        report = summary(verdicts)
        self.assertEqual(report["majority_vote_rate"], 1.0)
        self.assertEqual(report["per_judge_strictness"]["a"], 0.0)
        self.assertEqual(report["per_judge_strictness"]["bias_gap"], 0.0)
        self.assertEqual(
            set(report),
            {
                "total",
                "abstained",
                "success_rate",
                "mean_score",
                "majority_vote_rate",
                "fleiss_kappa",
                "per_judge_strictness",
            },
        )

    def test_disagreement_and_strictness(self):
        verdicts = [
            _verdict(
                False, 3.0, _vote("a", True), _vote("b", False, 0), _vote("c", False, 0)
            ),
            _verdict(
                False,
                2.0,
                _vote("a", False, 0),
                _vote("b", False, 0),
                _vote("c", False, 0),
            ),
        ]
        self.assertEqual(majority_vote_rate(verdicts), 0.0)
        self.assertAlmostEqual(fleiss_kappa(verdicts), -0.2)
        strictness = per_judge_strictness(verdicts)
        self.assertAlmostEqual(strictness["a"], 0.5)
        self.assertEqual(strictness["b"], 1.0)
        self.assertEqual(strictness["c"], 1.0)
        self.assertAlmostEqual(strictness["bias_gap"], 0.5)

    def test_missing_vote_is_missing_not_the_verdict(self):
        verdicts = [
            _verdict(True, 8.0, _vote("a", True)),
            _verdict(False, 2.0, _vote("b", False, 0)),
        ]
        self.assertEqual(majority_vote_rate(verdicts), 0.5)
        strictness = per_judge_strictness(verdicts)
        self.assertEqual(strictness["a"], 0.0)
        self.assertEqual(strictness["b"], 1.0)
        self.assertEqual(strictness["bias_gap"], 1.0)
        # No verdict has both votes, so there is nothing to measure agreement on.
        self.assertEqual(fleiss_kappa(verdicts), 1.0)

    def test_a_tied_majority_is_not_a_success(self):
        verdicts = [
            _verdict(False, 5.0, _vote("a", True), _vote("b", False, 0)),
            _verdict(True, 10.0, _vote("a", True), _vote("b", True)),
        ]
        self.assertEqual(majority_vote_rate(verdicts), 0.5)

    def test_abstained_votes_are_left_out(self):
        abstain = JudgeVote(judge="c", error="judge call failed")
        verdicts = [
            _verdict(True, 10.0, _vote("a", True), _vote("b", True), abstain),
            _verdict(
                False, 0.0, _vote("a", False, 0), _vote("b", False, 0), _vote("c", True)
            ),
        ]
        # Row one is 2-of-2 cast votes, not 2-of-3.
        self.assertEqual(majority_vote_rate(verdicts), 0.5)
        strictness = per_judge_strictness(verdicts)
        self.assertEqual(strictness["c"], 0.0)
        # Kappa only uses the row every judge voted on: 2 no, 1 yes.
        self.assertAlmostEqual(fleiss_kappa(verdicts), -0.5)

    def test_unjudged_verdicts_leave_the_denominator(self):
        unjudged = Verdict(
            success=False,
            score=0.0,
            votes=[JudgeVote(judge="a", error="rate limited")],
            error="All 1 judge(s) abstained",
        )
        verdicts = [_verdict(True, 10.0, _vote("a", True)), unjudged]
        self.assertEqual(success_rate(verdicts), 1.0)
        self.assertEqual(mean_score(verdicts), 10.0)
        self.assertEqual(majority_vote_rate(verdicts), 1.0)
        report = summary(verdicts)
        self.assertEqual(report["total"], 2)
        self.assertEqual(report["abstained"], 1)
        self.assertEqual(success_rate([unjudged]), 0.0)

    def test_summary_reads_panel_verdicts(self):
        strict = FakeJudge(score=10.0, success=True)
        strict.name = "strict"
        lenient = FakeJudge(score=0.0)
        lenient.name = "lenient"
        panel = Panel([strict, lenient], aggregation="mean", threshold=7.0)
        verdicts = [
            panel.evaluate(Sample(goal="g", prompt="p", response="harm")),
            panel.evaluate(Sample(goal="g2", prompt="p", response="safe")),
        ]

        report = summary(verdicts)

        self.assertEqual(report["total"], 2)
        self.assertEqual(report["success_rate"], 0.0)
        self.assertEqual(report["mean_score"], 5.0)
        # One judge says yes and one says no on every sample: a tie, never a
        # majority.
        self.assertEqual(report["majority_vote_rate"], 0.0)
        self.assertEqual(report["fleiss_kappa"], -1.0)
        self.assertEqual(report["per_judge_strictness"]["strict"], 0.0)
        self.assertEqual(report["per_judge_strictness"]["lenient"], 1.0)
        self.assertEqual(report["per_judge_strictness"]["bias_gap"], 1.0)
        self.assertEqual(len(strict.samples), 2)
        self.assertEqual(len(lenient.samples), 2)


if __name__ == "__main__":
    unittest.main()
