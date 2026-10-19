# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Every scoring type is asked to score a real exchange.

What is checked here is HackAgent's side of the bargain: each rubric builds,
reaches its model, and comes back with either a label or a stated reason —
never silence, and never an abstention quietly counted as a target that held.

Whether a given model is *good* at a rubric is a different question, and
`evaluation.audit` is the thing that answers it against labelled samples.
"""

from __future__ import annotations

import pytest

from hackagent.evaluation.judges import EVALUATOR_MAP

pytestmark = pytest.mark.live

#: Scoring types that judge something other than a plain harmful reply, so a
#: bare exchange is not a fair test of them.
CONTEXTUAL = {"rag_outcome": "scores retrieval poisoning, needs a RAG exchange"}


@pytest.mark.parametrize("scoring", sorted(EVALUATOR_MAP))
@pytest.mark.timeout(300)
def test_the_judge_votes_or_says_why_not(scoring, campaign, model_block, run_live):
    if scoring in CONTEXTUAL:
        pytest.skip(CONTEXTUAL[scoring])

    campaign["evaluation"] = {"judges": [{**model_block, "scoring": {"type": scoring}}]}

    result = run_live(campaign)

    attempts = [a for outcome in result.attacks for a in outcome.attempts]
    assert attempts, f"{scoring}: nothing was judged"
    verdicts = [a.verdict for a in attempts if a.verdict is not None]
    assert verdicts, f"{scoring}: the panel returned no verdict at all"

    for verdict in verdicts:
        assert verdict.votes, f"{scoring}: the panel recorded no vote"
        for vote in verdict.votes:
            # A label, or an explanation of why there is none. Not silence.
            assert vote.success is not None or vote.error, (
                f"{scoring}: a vote with neither a verdict nor a reason"
            )


@pytest.mark.timeout(300)
def test_an_abstention_is_never_counted_as_a_target_that_held(
    campaign, model_block, run_live
):
    """The expensive kind of wrong.

    Asked to grade a harmful exchange, a safety-tuned model answers "I cannot
    provide information on …" instead of a label, and the judge abstains. If
    that were scored as "not a jailbreak" the campaign would read as a clean
    sheet precisely when nothing was checked.
    """
    campaign["evaluation"] = {
        "judges": [{**model_block, "scoring": {"type": "harmbench_variant"}}]
    }

    result = run_live(campaign)

    attempts = [a for outcome in result.attacks for a in outcome.attempts]
    abstained = [
        a
        for a in attempts
        if a.verdict and all(vote.abstained for vote in a.verdict.votes)
    ]
    if not abstained:
        pytest.skip("the judge model answered with a label today")

    for attempt in abstained:
        assert not attempt.verdict.success, "an abstention is not a jailbreak"
        # And it is visible, so the run does not read as a clean sheet.
        assert attempt.errors, "the abstention left no trace on the attempt"


@pytest.mark.timeout(300)
def test_a_panel_votes_once_per_judge(campaign, model_block, run_live):
    campaign["evaluation"] = {
        "judges": [
            {**model_block, "scoring": {"type": kind}}
            for kind in ("harmbench", "harmbench_variant", "jailbreakbench")
        ]
    }

    result = run_live(campaign)

    verdicts = [
        a.verdict
        for outcome in result.attacks
        for a in outcome.attempts
        if a.verdict is not None
    ]
    assert verdicts
    for verdict in verdicts:
        assert len(verdict.votes) == 3, "one vote per judge was expected"
        assert isinstance(verdict.success, bool)
