# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Judging runs once unless ``rejudge`` is set."""

from hackagent.attacks.types import AttackResult
from hackagent.core.contracts import Verdict
from hackagent.orchestrator.runner import judge_unjudged
from tests.fakes.judge import FakeJudge


def _result(*, verdict=None, response="hello", metadata=None) -> AttackResult:
    return AttackResult(
        goal="goal",
        prompt="prompt",
        response=response,
        verdict=verdict,
        metadata=metadata or {},
    )


def test_unjudged_results_are_scored_once():
    judge = FakeJudge(score=1.0, success=False)
    existing = Verdict(success=True, score=9.0)
    judged = judge_unjudged(
        [
            _result(verdict=existing),
            _result(),
            _result(response=""),
        ],
        judge,
    )
    assert judged[0].verdict.score == 9.0
    assert judged[0].verdict.success is True
    assert judged[1].verdict is not None
    assert judged[1].verdict.score == 1.0
    assert judged[2].verdict is None
    assert len(judge.samples) == 1


def test_rejudge_scores_results_that_already_have_a_verdict():
    judge = FakeJudge(score=2.0, success=False)
    judged = judge_unjudged(
        [_result(verdict=Verdict(success=True, score=9.0)), _result()],
        judge,
        rejudge=True,
    )
    assert [item.verdict.score for item in judged] == [2.0, 2.0]
    assert len(judge.samples) == 2


def test_missing_judge_leaves_results_alone():
    class _Missing:
        available = False

    original = _result()
    judged = judge_unjudged([original], _Missing())
    assert judged[0].verdict is None
