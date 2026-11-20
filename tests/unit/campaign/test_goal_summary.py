# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The line that says how a goal ended for one attack."""

from __future__ import annotations

from hackagent.attacks.techniques.trace import TraceNode
from hackagent.core.contracts import Verdict
from hackagent.orchestrator.campaign.results import Attempt
from hackagent.orchestrator.campaign.runner import _goal_summary


def verdict(success: bool) -> Verdict:
    return Verdict(success=success, score=10.0 if success else 0.0)


def attempt(index, success=None, error=None, trace=()):
    return Attempt(
        0,
        index,
        "goal",
        verdict=None if success is None else verdict(success),
        error=error,
        trace=trace,
    )


def panel(path, success):
    return TraceNode(
        path=path,
        node="call",
        label="panel",
        data={"response": {"score": 10.0 if success else 0.0, "success": success}},
    )


def test_a_jailbreak_says_which_attempt_and_where_in_the_search():
    trace = (
        TraceNode(path=(0,), node="phase", label="round 2/3"),
        TraceNode(path=(0, 0), node="phase", label="stream 1/2"),
        panel((0, 0, 0), True),
    )
    attempts = [attempt(1, True, trace=trace), attempt(0, False)]
    assert _goal_summary(attempts) == "jailbroken at attempt 2 (round 2/3, stream 1/2)"


def test_a_round_kept_by_an_earlier_attempt_still_names_the_winner_s_place():
    # The goal's trace is split between attempts: the round both streams
    # share went to the first, the winning stream's nodes to the second.
    first = (
        TraceNode(path=(0,), node="phase", label="round 1/3"),
        TraceNode(path=(0, 0), node="phase", label="stream 1/2"),
        panel((0, 0, 0), False),
    )
    second = (
        TraceNode(path=(0, 1), node="phase", label="stream 2/2"),
        panel((0, 1, 0), True),
    )
    attempts = [attempt(0, False, trace=first), attempt(1, True, trace=second)]
    assert _goal_summary(attempts) == "jailbroken at attempt 2 (round 1/3, stream 2/2)"


def test_an_attack_without_steps_names_only_the_attempt():
    assert (
        _goal_summary([attempt(0, False), attempt(1, True)])
        == "jailbroken at attempt 2"
    )


def test_mitigated_unresolved_and_failed():
    assert _goal_summary([attempt(0, False), attempt(1, False)]) == "mitigated"
    assert _goal_summary([attempt(0, False), attempt(1, error="timeout")]) == (
        "mitigated · 1 error"
    )
    assert _goal_summary([attempt(0)]) == "unresolved"
    assert _goal_summary([attempt(0, error="generation failed: x")]) == (
        "failed: generation failed: x"
    )
