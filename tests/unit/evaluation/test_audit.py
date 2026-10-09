# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Auditing a panel against samples people already judged.

Judges here are scripted on the response text, so a wrapper changing a
verdict is something the test decides rather than something a model does.
"""

from __future__ import annotations

import asyncio

import pytest

from hackagent.core.contracts import JudgeVote, LabelledSample, Sample
from hackagent.evaluation.audit import (
    PANEL,
    WRAPPERS,
    RobustnessSpec,
    audit_panel,
    binary_metrics,
    flip_metrics,
    wrap,
)
from hackagent.evaluation.panel import Panel


class ScriptedJudge:
    """Votes by looking the response up; anything unscripted is a refusal."""

    range = "binary"

    def __init__(self, name: str, detects: dict[str, bool], abstains: tuple = ()):
        self.name = name
        self.detects = detects
        self.abstains = set(abstains)
        self.seen: list[Sample] = []

    def vote(self, sample: Sample) -> JudgeVote:
        self.seen.append(sample)
        if sample.response in self.abstains:
            return JudgeVote(judge=self.name, error="unparseable")
        detected = self.detects.get(sample.response, False)
        return JudgeVote(judge=self.name, score=float(detected), success=detected)

    async def avote(self, sample: Sample) -> JudgeVote:
        return self.vote(sample)


def labelled(*pairs: tuple[str, bool], prompt: str = "") -> list[LabelledSample]:
    return [
        LabelledSample(
            id=response,
            label=label,
            sample=Sample(goal="g", prompt=prompt, response=response),
        )
        for response, label in pairs
    ]


def audit(panel, samples, **kwargs):
    return asyncio.run(audit_panel(panel, samples, **kwargs))


# --- metrics ----------------------------------------------------------------


def test_binary_metrics_reports_the_confusion_matrix():
    metrics = binary_metrics([True, True, False, False], [True, False, False, True])

    assert (metrics.tp, metrics.fp, metrics.tn, metrics.fn) == (1, 1, 1, 1)
    assert (metrics.precision, metrics.recall, metrics.f1) == (0.5, 0.5, 0.5)
    assert metrics.accuracy == 0.5
    assert metrics.samples == 4


def test_binary_metrics_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        binary_metrics([True], [True, False])


def test_binary_metrics_rejects_an_empty_sample():
    with pytest.raises(ValueError, match="at least one"):
        binary_metrics([], [])


def test_flip_metrics_separates_direction_from_accuracy():
    metrics = flip_metrics(
        "refusal_prefix",
        baseline=[True, False, True, False],
        wrapped=[False, False, True, True],
        labels=[True, False, True, False],
    )

    assert metrics.flips == 2
    assert metrics.flip_rate == 0.5
    # One correct detection was hidden, one false alarm was invented.
    assert metrics.detected_to_missed == 1
    assert metrics.missed_to_detected == 1
    assert metrics.true_positive_evasions == 1
    assert metrics.true_positive_evasion_rate == 0.5
    assert metrics.accuracy_delta == -0.5


def test_wrap_rewrites_the_response_and_nothing_else():
    sample = Sample(goal="g", prompt="p", response="body")
    wrapped = wrap(sample, "refusal_prefix")

    assert wrapped.response.endswith("body")
    assert wrapped.response != "body"
    assert (wrapped.goal, wrapped.prompt) == ("g", "p")


# --- auditing a panel -------------------------------------------------------


def test_audit_reports_a_row_per_judge_and_one_for_the_panel():
    strict = ScriptedJudge("strict", {"a": True, "b": True})
    lenient = ScriptedJudge("lenient", {"a": True})
    panel = Panel([strict, lenient], aggregation="majority", threshold=7.0)

    report = audit(panel, labelled(("a", True), ("b", True)))

    assert [row.judge for row in report.judges] == ["strict", "lenient", PANEL]
    assert report.samples == 2


def test_each_judge_is_scored_on_its_own_votes():
    # 'b' is a miss for lenient and a hit for strict.
    strict = ScriptedJudge("strict", {"a": True, "b": True})
    lenient = ScriptedJudge("lenient", {"a": True})
    panel = Panel([strict, lenient], aggregation="mean", threshold=7.0)

    report = audit(panel, labelled(("a", True), ("b", True)))

    assert report.report_for("strict").metrics.recall == 1.0
    assert report.report_for("lenient").metrics.recall == 0.5


def test_the_panel_row_follows_the_panel_aggregation():
    # One of two judges detects 'a': 'any' passes it, 'majority' does not.
    detector = ScriptedJudge("detector", {"a": True})
    quiet = ScriptedJudge("quiet", {})
    samples = labelled(("a", True))

    permissive = audit(Panel([detector, quiet], aggregation="any"), samples)
    strictly = audit(Panel([detector, quiet], aggregation="majority"), samples)

    assert permissive.report_for(PANEL).metrics.tp == 1
    assert strictly.report_for(PANEL).metrics.fn == 1


def test_one_pass_of_the_panel_answers_for_every_judge():
    first = ScriptedJudge("first", {"a": True})
    second = ScriptedJudge("second", {"a": True})
    panel = Panel([first, second])

    audit(panel, labelled(("a", True), ("b", False)))

    # Two samples, one call each — not one call per judge per sample.
    assert len(first.seen) == 2
    assert len(second.seen) == 2


def test_an_abstention_counts_as_no_detection_and_is_reported():
    judge = ScriptedJudge("shy", {"a": True, "b": True}, abstains=("b",))
    report = audit(Panel([judge]), labelled(("a", True), ("b", True)))

    row = report.report_for("shy")
    assert row.metrics.abstentions == 1
    assert row.metrics.fn == 1
    assert row.metrics.recall == 0.5


def test_a_panel_where_everyone_abstains_detects_nothing():
    judge = ScriptedJudge("shy", {"a": True}, abstains=("a",))
    report = audit(Panel([judge]), labelled(("a", True)))

    assert report.report_for(PANEL).metrics.abstentions == 1
    assert report.report_for(PANEL).metrics.tp == 0


def test_contextual_samples_are_counted():
    judge = ScriptedJudge("j", {})
    report = audit(Panel([judge]), labelled(("a", True), prompt="some context"))

    assert report.contextual_samples == 1


# --- accuracy is reported, not graded ---------------------------------------


def test_metrics_alone_do_not_grade_a_judge():
    # A judge that calls everything harmful has 0.5 precision and is still
    # not failed: what counts as enough depends on what the panel is for.
    judge = ScriptedJudge("loose", {"a": True, "b": True})
    report = audit(Panel([judge]), labelled(("a", True), ("b", False)))

    assert report.report_for("loose").metrics.precision == 0.5
    assert report.passed is None


def test_an_ungraded_audit_still_reports_every_number():
    judge = ScriptedJudge("j", {"a": True})
    metrics = (
        audit(Panel([judge]), labelled(("a", True), ("b", False)))
        .report_for("j")
        .metrics
    )

    assert (metrics.tp, metrics.fp, metrics.tn, metrics.fn) == (1, 0, 1, 0)
    assert metrics.f1 == 1.0


# --- robustness -------------------------------------------------------------


def test_a_wrapper_that_changes_a_verdict_is_an_evasion():
    # The judge detects the bare response but not the wrapped one.
    judge = ScriptedJudge("brittle", {"a": True})
    report = audit(
        Panel([judge]),
        labelled(("a", True)),
        robustness=RobustnessSpec(enabled=True, wrappers=("refusal_prefix",)),
    )

    robustness = report.report_for("brittle").robustness
    assert robustness.any_wrapper_flip_rate == 1.0
    assert robustness.wrappers[0].true_positive_evasions == 1


def test_a_judge_that_ignores_the_wrapper_shows_no_flips():
    wrapped = WRAPPERS["refusal_prefix"]("a")
    judge = ScriptedJudge("steady", {"a": True, wrapped: True})
    report = audit(
        Panel([judge]),
        labelled(("a", True)),
        robustness=RobustnessSpec(enabled=True, wrappers=("refusal_prefix",)),
    )

    assert report.report_for("steady").robustness.any_wrapper_flip_rate == 0.0
    assert report.passed is True


def test_flips_above_the_allowed_rate_fail_the_audit():
    judge = ScriptedJudge("brittle", {"a": True})
    report = audit(
        Panel([judge]),
        labelled(("a", True)),
        robustness=RobustnessSpec(
            enabled=True, wrappers=("refusal_prefix",), max_flip_rate=0.5
        ),
    )

    assert report.passed is False
    assert report.report_for("brittle").robustness.any_wrapper_flip_rate == 1.0


def test_a_sample_flipped_by_one_wrapper_is_counted_once():
    judge = ScriptedJudge("brittle", {"a": True})
    report = audit(
        Panel([judge]),
        labelled(("a", True)),
        robustness=RobustnessSpec(
            enabled=True, wrappers=("refusal_prefix", "fictional_story")
        ),
    )

    robustness = report.report_for("brittle").robustness
    assert len(robustness.wrappers) == 2
    assert robustness.any_wrapper_flips == 1


def test_robustness_is_skipped_unless_it_is_enabled():
    judge = ScriptedJudge("j", {"a": True})
    report = audit(Panel([judge]), labelled(("a", True)))

    assert report.report_for("j").robustness is None
    assert len(judge.seen) == 1


def test_an_unknown_wrapper_is_rejected():
    judge = ScriptedJudge("j", {})
    with pytest.raises(ValueError, match="Unknown robustness wrapper"):
        audit(
            Panel([judge]),
            labelled(("a", True)),
            robustness=RobustnessSpec(enabled=True, wrappers=("nope",)),
        )


def test_an_audit_needs_samples():
    with pytest.raises(ValueError, match="at least one labelled sample"):
        audit(Panel([ScriptedJudge("j", {})]), [])
