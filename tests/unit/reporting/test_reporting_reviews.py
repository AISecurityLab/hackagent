# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Human reviews and judge agreement, on rows built by hand."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hackagent.reporting import (
    AttackRun,
    ResultRow,
    Review,
    check_review,
    effective_bucket,
    goal_judge_votes,
    goal_outcome,
    judge_agreement,
    judge_votes,
    parse_review,
    review_history,
)
from hackagent.reporting import http
from hackagent.reporting.reviews import (
    INVALID_REVIEW,
    NOTHING_TO_WITHDRAW,
    STALE_REVIEW,
    review_created,
    review_history_etag,
)

T0 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
ID1 = "d0000000-0000-4000-8000-000000000001"
ID2 = "d0000000-0000-4000-8000-000000000002"
J, M, E, P = (
    "SUCCESSFUL_JAILBREAK",
    "FAILED_JAILBREAK",
    "ERROR_AGENT_RESPONSE",
    "NOT_EVALUATED",
)


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def row(ident, status, *, seconds=0, review=None, metrics=None, clock=None):
    return ResultRow.from_data(
        id=ident,
        goal="goal",
        evaluation_status=status,
        evaluation_notes=None,
        agent_specific_data={"attack_metadata": {"goal_active_target_elapsed_s": clock}}
        if clock is not None
        else {},
        created_at=at(seconds),
        updated_at=at(seconds + 1),
        evaluation_metrics=metrics,
        review=review,
    )


def review(ident=ID1, outcome="jailbreak", seconds=0, supersedes=None, by="ana"):
    return Review(
        id=ident,
        result_id="r1",
        outcome=outcome,
        explanation="",
        reviewer=by,
        created_at=at(seconds),
        supersedes=supersedes,
    )


class TestEffectiveBucket:
    @pytest.mark.parametrize(
        "automated, outcome, bucket",
        [
            ("mitigated", "jailbreak", "jailbreak"),
            ("jailbreak", "mitigated", "mitigated"),
            ("error", "mitigated", "mitigated"),
            ("jailbreak", "inconclusive", "pending"),
            ("pending", "jailbreak", "jailbreak"),
            ("jailbreak", None, "jailbreak"),
            ("error", None, "error"),
        ],
    )
    def test_the_latest_review_decides(self, automated, outcome, bucket):
        assert effective_bucket(automated, outcome) == bucket


class TestGoalOutcomeWithReviews:
    def test_reviews_change_counts_and_are_counted(self):
        outcome = goal_outcome(
            campaign_run_id="c",
            run_id="r",
            goal_index=0,
            results=[
                row("a", M, seconds=0, review="jailbreak", clock=4.0),
                row("b", J, seconds=1, review="inconclusive"),
                row("c", M, seconds=2, review="mitigated"),
                row("d", J, seconds=3, review=None),
                row("e", E, seconds=4),
            ],
        )
        assert (
            outcome.jailbreak,
            outcome.mitigated,
            outcome.error,
            outcome.pending,
        ) == (2, 1, 1, 1)
        assert outcome.first_jailbreak_attempt == 1
        assert (outcome.min_jailbreak_elapsed_s, outcome.timed_jailbreaks) == (4.0, 1)
        # A withdrawn review (None) is no review.
        assert (
            outcome.reviewed_attempts,
            outcome.inconclusive_attempts,
            outcome.overridden_attempts,
        ) == (3, 1, 2)

    def test_without_reviews_nothing_changes(self):
        outcome = goal_outcome(
            campaign_run_id="c", run_id="r", goal_index=0, results=[row("a", J)]
        )
        assert (outcome.jailbreak, outcome.reviewed_attempts) == (1, 0)


class TestJudgeVotes:
    def test_votes_are_a_canonical_key(self):
        metrics = {
            "eval_b": 1,
            "eval_a": 0.0,
            "eval_c": None,
            "eval_d": "yes",
            "eval_e": True,
            "eval_a_mean": 4.5,
            "explanation_a": "why",
            "score": 1,
        }
        assert judge_votes(metrics) == (
            '{"eval_a":0,"eval_b":1,"eval_c":null,"eval_d":"invalid","eval_e":1}'
        )
        assert judge_votes(None) == judge_votes({}) == "{}"

    def test_rows_count_attempts_per_automated_outcome_and_votes(self):
        rows = goal_judge_votes(
            campaign_run_id="c",
            run_id="r",
            goal_index=2,
            results=[
                row("a", J, metrics={"eval_a": 1}, review="mitigated"),
                row("b", J, metrics={"eval_a": 1}),
                row("c", M, metrics={"eval_a": 0}),
            ],
        )
        assert [(r.outcome, r.votes, r.attempts) for r in rows] == [
            ("jailbreak", '{"eval_a":1}', 2),
            ("mitigated", '{"eval_a":0}', 1),
        ]


def votes_of(*attempts):
    """Stored vote rows of ``(run, goal, status, metrics)`` attempts."""
    grouped = {}
    for n, (run, goal, status, metrics) in enumerate(attempts):
        grouped.setdefault((run, goal), []).append(
            row(f"{run}-{n}", status, metrics=metrics)
        )
    return [
        item
        for (run, goal), rows in grouped.items()
        for item in goal_judge_votes(
            campaign_run_id="c", run_id=run, goal_index=goal, results=rows
        )
    ]


RUNS = [
    AttackRun(id="r2", campaign_run="c", status="COMPLETED", created_at=at(5)),
    AttackRun(id="r1", campaign_run="c", status="COMPLETED", created_at=at(0)),
]


class TestJudgeAgreement:
    def test_counts_patterns_and_rates(self):
        agreement = judge_agreement(
            votes_of(
                ("r1", 0, J, {"eval_a": 1, "eval_b": 1}),
                ("r1", 0, M, {"eval_a": 0, "eval_b": 1}),
                ("r1", 1, M, {"eval_a": 0, "eval_b": 0}),
                ("r2", 1, M, {"eval_a": 0, "eval_b": None}),
                ("r2", 1, P, {}),
            ),
            RUNS,
        )
        assert agreement["attempts"] == 5
        assert (
            agreement["comparable_attempts"],
            agreement["split"],
            agreement["unanimous_success"],
            agreement["unanimous_failure"],
            agreement["insufficient"],
        ) == (3, 1, 1, 1, 2)
        assert agreement["disagreement_rate"] == pytest.approx(1 / 3)
        assert agreement["patterns"] == [
            {"pattern": "00", "attempts": 1},
            {"pattern": "01", "attempts": 1},
            {"pattern": "0?", "attempts": 1},
            {"pattern": "11", "attempts": 1},
            {"pattern": "??", "attempts": 1},
        ]
        judges = {judge["id"]: judge for judge in agreement["judges"]}
        assert (judges["eval_a"]["valid"], judges["eval_a"]["missing"]) == (4, 1)
        assert (judges["eval_b"]["abstained"], judges["eval_b"]["valid"]) == (1, 3)
        assert judges["eval_a"]["strictness"] == pytest.approx(3 / 4)
        assert judges["eval_b"]["strictness"] == pytest.approx(1 / 3)
        assert agreement["bias_gap"] == pytest.approx(3 / 4 - 1 / 3)
        assert agreement["pairs"] == [
            {
                "left": "eval_a",
                "right": "eval_b",
                "shared": 3,
                "disagreed": 1,
                "disagreement_rate": pytest.approx(1 / 3),
            }
        ]
        # 4 attempts with a valid vote; 1 has a strict majority for jailbreak.
        assert (agreement["majority_attempts"], agreement["majority_vote_rate"]) == (
            4,
            0.25,
        )
        assert agreement["kappa_attempts"] == 3
        # Runs follow the report's run order, not the rows'.
        assert [item["run_id"] for item in agreement["runs"]] == ["r1", "r2"]

    def test_goal_weights_count_each_goal_once(self):
        agreement = judge_agreement(
            votes_of(
                ("r1", 0, J, {"eval_a": 1}),
                ("r1", 0, M, {"eval_a": 0}),
                ("r1", 0, M, {"eval_a": 0}),
                ("r2", 1, M, {"eval_a": 0}),
            ),
            RUNS,
        )
        weights = {
            (item["outcome"], item["pattern"]): item["weight"]
            for item in agreement["goal_weighted"]["outcome_patterns"]
        }
        assert agreement["goal_weighted"]["goals"] == 2
        assert weights == {
            ("jailbreak", "1"): pytest.approx(1 / 3),
            ("mitigated", "0"): pytest.approx(5 / 3),
        }

    def test_kappa_needs_two_judges_and_disagreeing_votes(self):
        alike = votes_of(("r1", 0, M, {"eval_a": 0, "eval_b": 0}))
        assert judge_agreement(alike, RUNS)["fleiss_kappa"] is None
        one = votes_of(("r1", 0, M, {"eval_a": 0}), ("r1", 0, J, {"eval_a": 1}))
        assert judge_agreement(one, RUNS)["fleiss_kappa"] is None
        assert judge_agreement(one, RUNS)["bias_gap"] is None
        perfect = votes_of(
            ("r1", 0, M, {"eval_a": 0, "eval_b": 0}),
            ("r1", 1, J, {"eval_a": 1, "eval_b": 1}),
        )
        assert judge_agreement(perfect, RUNS)["fleiss_kappa"] == pytest.approx(1.0)

    def test_no_votes_is_an_empty_breakdown(self):
        agreement = judge_agreement([], RUNS)
        assert agreement["attempts"] == 0
        assert agreement["judges"] == agreement["runs"] == []
        assert agreement["goal_weighted"] == {"goals": 0, "outcome_patterns": []}
        assert agreement["majority_vote_rate"] is None


class TestReviewRequests:
    @pytest.mark.parametrize(
        "body",
        [
            None,
            [],
            {"outcome": "jailbreak"},
            {"expected_review_id": None},
            {"outcome": "maybe", "expected_review_id": None},
            {"outcome": "jailbreak", "expected_review_id": "nope"},
            {"outcome": "jailbreak", "expected_review_id": 5},
            {"outcome": "jailbreak", "expected_review_id": None, "explanation": 3},
            {"outcome": "jailbreak", "expected_review_id": None, "extra": 1},
            {
                "outcome": "jailbreak",
                "expected_review_id": None,
                "explanation": "x" * 10_001,
            },
        ],
    )
    def test_malformed_bodies_are_refused(self, body):
        with pytest.raises(http.BadRequest) as refused:
            parse_review(body)
        assert refused.value.detail == INVALID_REVIEW

    def test_a_body_is_normalized(self):
        request = parse_review(
            {
                "outcome": "inconclusive",
                "explanation": "  unsure \n",
                "expected_review_id": ID1.upper(),
            }
        )
        assert (request.outcome, request.explanation, request.expected_review_id) == (
            "inconclusive",
            "unsure",
            ID1,
        )

    def test_a_review_must_follow_the_latest(self):
        first = parse_review({"outcome": "jailbreak", "expected_review_id": None})
        check_review(None, first)
        with pytest.raises(http.Conflict) as stale:
            check_review(review(), first)
        assert stale.value.detail == STALE_REVIEW
        follow = parse_review({"outcome": "mitigated", "expected_review_id": ID1})
        check_review(review(), follow)
        with pytest.raises(http.Conflict):
            check_review(None, follow)

    def test_only_an_active_review_can_be_withdrawn(self):
        withdraw = parse_review({"outcome": None, "expected_review_id": ID1})
        check_review(review(), withdraw)
        with pytest.raises(http.BadRequest) as refused:
            check_review(review(outcome=None), withdraw)
        assert refused.value.detail == NOTHING_TO_WITHDRAW
        with pytest.raises(http.BadRequest):
            check_review(
                None, parse_review({"outcome": None, "expected_review_id": None})
            )


class TestReviewResponses:
    def test_history_is_newest_first_and_its_etag_follows_it(self):
        first, second = review(ID1, seconds=0), review(ID2, "mitigated", 5, ID1)
        body = review_history([first, second])
        assert [item["id"] for item in body["results"]] == [ID2, ID1]
        assert body["results"][0]["supersedes_review_id"] == ID1
        assert review_history_etag([], [first, second]) == review_history_etag(
            [], [second, first]
        )
        assert review_history_etag([], [first]) != review_history_etag(
            [], [first, second]
        )

    def test_a_created_review_carries_both_buckets(self):
        body = review_created(
            review(outcome="inconclusive"),
            run_id="run",
            goal_index=3,
            automated_bucket="jailbreak",
        )
        assert body["attempt"] == {
            "id": "r1",
            "run_id": "run",
            "goal_index": 3,
            "bucket": "pending",
            "automated_bucket": "jailbreak",
        }
        assert body["outcome"] == "inconclusive"
