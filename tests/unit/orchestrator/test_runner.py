# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Judging runs once unless ``rejudge`` is set."""

import pytest

from hackagent.attacks.types import AttackResult
from hackagent.core.contracts import Verdict
from hackagent.orchestrator.runner import judge_unjudged
from tests.fakes.judge import FakeJudge


def _result(
    *, verdict=None, response="hello", prompt="prompt", metadata=None
) -> AttackResult:
    return AttackResult(
        goal="goal",
        prompt=prompt,
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
    assert judged[0] is original
    assert judged[0].verdict is None


def test_absent_judge_leaves_results_alone():
    original = _result()
    judged = judge_unjudged([original], None)
    assert judged[0] is original
    assert judged[0].verdict is None


def test_metadata_success_flags_count_as_already_judged():
    judge = FakeJudge(score=9.0, success=True)
    judged = judge_unjudged(
        [
            _result(metadata={"success": False}),
            _result(metadata={"is_success": 0}),
            _result(metadata={"success": None}),
        ],
        judge,
    )
    assert [item.verdict for item in judged] == [None, None, None]
    assert judge.samples == []


def test_rejudge_scores_a_metadata_flag_when_a_response_exists():
    judge = FakeJudge(score=3.0)
    judged = judge_unjudged(
        [_result(metadata={"is_success": True})],
        judge,
        rejudge=True,
    )
    assert judged[0].verdict is not None
    assert judged[0].verdict.score == 3.0
    assert len(judge.samples) == 1
    assert judge.samples[0].goal == "goal"
    assert judge.samples[0].response == "hello"


def test_rejudge_still_skips_an_empty_response():
    judge = FakeJudge(score=3.0)
    judged = judge_unjudged(
        [_result(response="", metadata={"success": True, "is_success": True})],
        judge,
        rejudge=True,
    )
    assert judged[0].verdict is None
    assert judge.samples == []


def test_empty_response_falls_back_to_completion_then_metadata():
    judge = FakeJudge(scores=[2.0, 6.0])
    judged = judge_unjudged(
        [
            _result(
                response="",
                metadata={"completion": "done", "response": "ignored"},
            ),
            _result(
                response="",
                prompt="",
                metadata={"response": "alt", "prefix": "pre"},
            ),
            _result(response="", metadata={"completion": "", "response": ""}),
        ],
        judge,
    )
    assert judged[0].verdict is not None
    assert judged[0].verdict.score == 2.0
    assert judged[0].verdict.success is False
    assert judged[1].verdict is not None
    assert judged[1].verdict.score == 6.0
    assert judged[1].verdict.success is True
    assert judged[2].verdict is None
    assert [(sample.prompt, sample.response) for sample in judge.samples] == [
        ("prompt", "done"),
        ("pre", "alt"),
    ]


def test_judge_errors_propagate_after_the_failing_sample():
    class _Boom(FakeJudge):
        def evaluate(self, sample):
            super().evaluate(sample)
            raise RuntimeError("judge down")

    judge = _Boom(score=1.0)
    with pytest.raises(RuntimeError, match="judge down"):
        judge_unjudged([_result(), _result(response="second")], judge)
    assert len(judge.samples) == 1
    assert judge.samples[0].response == "hello"
