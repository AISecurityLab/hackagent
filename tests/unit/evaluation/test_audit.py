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
    Disagreement,
    RobustnessSpec,
    audit_panel,
    best_threshold,
    binary_metrics,
    compare_rules,
    correct_rate,
    expected_independent_j,
    sweep_rules,
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


# --- balanced accuracy and Youden's J ---------------------------------------


def test_metrics_report_both_class_conditional_rates():
    # Two harmful (one found), two safe (one alarmed on).
    metrics = binary_metrics([True, False, True, False], [True, True, False, False])

    assert (metrics.recall, metrics.specificity) == (0.5, 0.5)
    assert metrics.false_positive_rate == 0.5
    assert metrics.balanced_accuracy == 0.5
    # Detections no better than false alarms: no signal at all.
    assert metrics.youden_j == 0.0


def test_a_perfect_judge_has_j_of_one_and_a_coin_has_zero():
    perfect = binary_metrics([True, False], [True, False])
    inverted = binary_metrics([False, True], [True, False])

    assert (perfect.balanced_accuracy, perfect.youden_j) == (1.0, 1.0)
    # Wrong every time is as informative as right every time, with a sign.
    assert (inverted.balanced_accuracy, inverted.youden_j) == (0.0, -1.0)


def test_balanced_accuracy_ignores_the_mix_accuracy_follows():
    # The same judge, measured on a balanced sample and a lopsided one:
    # it finds every harmful sample and alarms on half the safe ones.
    balanced = binary_metrics([True, True, False], [True, False, False])
    lopsided = binary_metrics(
        [True, True, False, True, False], [True, False, False, False, False]
    )

    assert balanced.accuracy != lopsided.accuracy
    assert balanced.balanced_accuracy == lopsided.balanced_accuracy == 0.75
    assert balanced.youden_j == lopsided.youden_j == 0.5


def test_j_is_undefined_when_the_sample_holds_only_one_class():
    metrics = binary_metrics([True, False], [True, True])

    assert metrics.accuracy == 0.5
    assert metrics.specificity is None
    assert metrics.balanced_accuracy is None
    assert metrics.youden_j is None


# --- correcting a rate a judge reported --------------------------------------


def test_a_perfect_judge_leaves_a_rate_alone():
    perfect = binary_metrics([True, False], [True, False])

    assert correct_rate(0.4, perfect).corrected == 0.4


def test_a_judge_that_shrinks_a_rate_has_it_restored():
    # Finds 3 of 4 harmful, alarms on 1 of 4 safe: J = 0.75 - 0.25 = 0.5.
    metrics = binary_metrics(
        [True, True, True, False, True, False, False, False],
        [True, True, True, True, False, False, False, False],
    )
    assert (metrics.youden_j, metrics.false_positive_rate) == (0.5, 0.25)

    # Traffic that is truly 40% harmful reads as 0.4*0.75 + 0.6*0.25 = 0.45.
    assert correct_rate(0.45, metrics).corrected == 0.4


def test_a_weak_judge_widens_the_corrected_rate():
    strong = binary_metrics([True, False], [True, False])
    # Finds half the harmful samples, alarms on a quarter of the safe ones.
    weak = binary_metrics(
        [True, True, False, False, True, False, False, False],
        [True, True, True, True, False, False, False, False],
    )

    sure = correct_rate(0.5, strong, samples=100)
    unsure = correct_rate(0.5, weak, samples=100)

    assert weak.youden_j < strong.youden_j
    assert unsure.standard_error > sure.standard_error


def test_a_rate_the_judge_could_not_have_produced_is_flagged():
    # Alarms on half the safe samples, so it cannot report less than 0.25.
    metrics = binary_metrics(
        [True, True, False, False, True, False, False, False],
        [True, True, True, True, False, False, False, False],
    )
    corrected = correct_rate(0.0, metrics)

    assert corrected.clamped is True
    assert corrected.corrected == 0.0


def test_a_judge_with_no_signal_cannot_correct_anything():
    coin = binary_metrics([True, False, True, False], [True, True, False, False])

    with pytest.raises(ValueError, match="no signal to invert"):
        correct_rate(0.5, coin)


def test_correcting_needs_a_judge_measured_on_both_classes():
    one_sided = binary_metrics([True, False], [True, True])

    with pytest.raises(ValueError, match="only one class"):
        correct_rate(0.5, one_sided)


# --- where the panel cuts its score -----------------------------------------


def test_the_sweep_finds_the_cut_that_separates_the_labels():
    scores = [9.0, 8.0, 3.0, 2.0]
    labels = [True, True, False, False]

    sweep = best_threshold(scores, labels, current=2.0)

    # At 2.0 everything is a detection; at 8.0 the two classes come apart.
    assert sweep.youden_j == 0.0
    assert (sweep.best_threshold, sweep.best_youden_j) == (8.0, 1.0)
    assert sweep.improvement == 1.0


def test_a_threshold_already_as_good_as_any_is_left_alone():
    sweep = best_threshold(
        [9.0, 8.0, 3.0, 2.0], [True, True, False, False], current=8.0
    )

    assert sweep.best_threshold == 8.0
    assert sweep.improvement == 0.0


def test_a_sweep_needs_both_labels():
    assert best_threshold([9.0, 2.0], [True, True], current=7.0) is None


def test_the_audit_sweeps_a_panel_that_decides_on_its_score():
    judge = ScriptedJudge("j", {"a": True})
    report = audit(
        Panel([judge], aggregation="mean"), labelled(("a", True), ("b", False))
    )

    assert report.threshold is not None
    assert report.threshold.threshold == 7.0


def test_a_panel_that_counts_votes_is_not_swept():
    judge = ScriptedJudge("j", {"a": True})
    report = audit(
        Panel([judge], aggregation="majority"), labelled(("a", True), ("b", False))
    )

    assert report.threshold is None


# --- is the panel worth its judges? -----------------------------------------


def votes(**columns: str) -> dict[str, tuple[bool, ...]]:
    """Vote columns written as strings of 1 and 0, one character per sample."""
    return {
        name: tuple(character == "1" for character in column)
        for name, column in columns.items()
    }


def test_identical_judges_predict_a_gain_that_never_arrives():
    # Three judges that always agree: the vote cannot beat any one of them,
    # but the independence arithmetic says it should.
    column = "11100000"
    labels = [True, True, True, True, False, False, False, False]

    report = compare_rules(
        votes(a=column, b=column, c=column),
        tuple(character == "1" for character in column),
        labels,
        aggregation="majority",
    )

    assert report.configured.metrics.youden_j == report.best_single.metrics.youden_j
    assert report.worth_it is False
    # The arithmetic promised more than perfectly correlated judges can give.
    assert report.correlation_penalty > 0


def test_judges_with_different_blind_spots_make_a_panel_worth_having():
    labels = [True, True, True, True, False, False, False, False]
    # Each judge misses two harmful samples, but not the same two.
    report = compare_rules(
        votes(a="11000000", b="01100000", c="10100000"),
        # Majority of the three: samples 0, 1 and 2 each carry two votes.
        (True, True, True, False, False, False, False, False),
        labels,
        aggregation="majority",
    )

    assert report.worth_it is True


def test_two_weak_judges_outvote_a_strong_one():
    labels = [True, True, True, True, False, False, False, False]
    sharp = "11110000"  # perfect
    blunt = "10000000"  # finds one of four, never alarms
    # Majority needs 2 of 3, so the blunt pair vetoes the sharp judge.
    panel = (True, False, False, False, False, False, False, False)

    report = compare_rules(
        votes(sharp=sharp, blunt1=blunt, blunt2=blunt),
        panel,
        labels,
        aggregation="majority",
    )

    assert report.best_single.judges == ("sharp",)
    assert report.best_single.metrics.youden_j == 1.0
    assert report.worth_it is False
    # Weighting by evidence recovers the strong judge the majority buried.
    assert report.weighted.metrics.youden_j > report.configured.metrics.youden_j


def test_the_sweep_finds_a_better_rule_than_the_one_configured():
    labels = [True, True, True, True, False, False, False, False]
    report = compare_rules(
        votes(sharp="11110000", blunt1="10000000", blunt2="10000000"),
        (True, False, False, False, False, False, False, False),
        labels,
        aggregation="majority",
    )

    # Dropping the dead weight is the best rule available.
    assert report.best_rule.metrics.youden_j == 1.0
    assert "sharp" in report.best_rule.judges


def test_disagreement_counts_only_where_they_differ():
    labels = [True, True, False, False]
    report = compare_rules(
        votes(a="1100", b="1000"),
        (True, False, False, False),  # panel misses sample 1
        labels,
        aggregation="majority",
    )

    assert report.disagreement.panel_right + report.disagreement.judge_right >= 1
    assert (
        report.disagreement.agreed
        + report.disagreement.panel_right
        + report.disagreement.judge_right
        == len(labels)
    )


def test_a_panel_of_one_is_not_a_panel():
    assert compare_rules(votes(a="10"), (True, False), [True, False]) is None


def test_the_independence_estimate_matches_the_textbook_case():
    # Three identical coins at recall 0.8, alarm 0.1; majority is 2 of 3.
    rates = [(0.8, 0.1)] * 3
    detections = 3 * 0.8**2 * 0.2 + 0.8**3  # exactly two, or all three
    alarms = 3 * 0.1**2 * 0.9 + 0.1**3

    assert expected_independent_j(rates, 2) == pytest.approx(detections - alarms)


def test_every_subset_and_vote_count_is_scored():
    labels = [True, False]
    ranked = sweep_rules(votes(a="10", b="10", c="10"), labels)

    # 3 singles + 3 pairs x 2 counts + 1 triple x 3 counts.
    assert len(ranked) == 3 + 6 + 3
    assert ranked[0].metrics.youden_j == 1.0


def test_the_audit_reports_whether_the_panel_earned_its_judges():
    sharp = ScriptedJudge("sharp", {"a": True, "b": True})
    blunt = ScriptedJudge("blunt", {"a": True})
    panel = Panel([sharp, blunt], aggregation="majority")

    report = audit(panel, labelled(("a", True), ("b", True), ("c", False)))

    assert report.ensemble is not None
    assert report.ensemble.best_single.judges == ("sharp",)
    assert report.ensemble.worth_it is False


def test_a_single_judge_audit_has_no_ensemble_to_report():
    report = audit(
        Panel([ScriptedJudge("j", {"a": True})]), labelled(("a", True), ("b", False))
    )

    assert report.ensemble is None


def test_a_gap_resting_on_a_few_disagreements_is_not_a_finding():
    # Panel right on 3 of the 4 samples they differ on: a coin does that
    # often enough that nothing has been shown.
    close = Disagreement(panel_right=3, judge_right=1, agreed=500)

    assert close.p_value > 0.05


def test_a_one_sided_split_of_many_disagreements_is():
    assert Disagreement(panel_right=30, judge_right=3, agreed=500).p_value < 0.01


def test_judges_that_never_disagreed_show_nothing_either_way():
    assert Disagreement(panel_right=0, judge_right=0, agreed=100).p_value == 1.0


def test_the_audit_carries_the_disagreement_test():
    sharp = ScriptedJudge("sharp", {"a": True, "b": True})
    blunt = ScriptedJudge("blunt", {"a": True})
    report = audit(
        Panel([sharp, blunt], aggregation="majority"),
        labelled(("a", True), ("b", True), ("c", False)),
    )

    assert report.ensemble.disagreement.p_value <= 1.0
