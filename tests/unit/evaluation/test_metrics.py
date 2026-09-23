# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.core.contracts import JudgeVote, Verdict
from hackagent.evaluation.metrics import (
    fleiss_kappa,
    mean_score,
    success_rate,
    summary,
)


def _verdict(success: bool, score: float, *votes: JudgeVote) -> Verdict:
    return Verdict(success=success, score=score, votes=list(votes))


class TestVerdictMetrics(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(success_rate([]), 0.0)
        self.assertEqual(mean_score([]), 0.0)
        report = summary([])
        self.assertEqual(report["total"], 0)
        self.assertEqual(report["success_rate"], 0.0)

    def test_success_and_mean(self):
        verdicts = [
            _verdict(True, 10.0),
            _verdict(False, 0.0),
        ]
        self.assertEqual(success_rate(verdicts), 0.5)
        self.assertEqual(mean_score(verdicts), 5.0)

    def test_fleiss_perfect_agreement(self):
        votes = [
            JudgeVote(judge="a", score=1, success=True),
            JudgeVote(judge="b", score=1, success=True),
        ]
        verdicts = [
            _verdict(True, 10.0, *votes),
            _verdict(True, 10.0, *votes),
        ]
        self.assertEqual(fleiss_kappa(verdicts), 1.0)
        report = summary(verdicts)
        self.assertEqual(report["majority_vote_rate"], 1.0)
        self.assertIn("a", report["per_judge_strictness"])


if __name__ == "__main__":
    unittest.main()
