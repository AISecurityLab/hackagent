from hackagent.interfaces.web._judge_agreement import judge_agreement
from itertools import product
import pytest


def test_goal_weighting_equalizes_goals_and_pools_goal_identity_across_attacks():
    rows = [
        {
            "run_id": "one",
            "goal_index": 0,
            "metrics": {"eval_a": 1},
            "outcome": "jailbreak",
        }
        for _ in range(9)
    ] + [
        {
            "run_id": "one",
            "goal_index": 1,
            "metrics": {"eval_a": 0},
            "outcome": "mitigated",
        },
        {
            "run_id": "two",
            "goal_index": 0,
            "metrics": {"eval_a": None},
            "outcome": None,
        },
    ]
    result = judge_agreement(rows)
    weighted = result["goal_weighted"]
    assert weighted["goals"] == 2
    weights = {
        (item["outcome"], item["pattern"]): item["weight"]
        for item in weighted["outcome_patterns"]
    }
    assert weights == pytest.approx(
        {("jailbreak", "1"): 0.9, ("mitigated", "0"): 1, ("unresolved", "?"): 0.1}
    )
    first, second = result["runs"]
    assert first["goal_weighted"] == {
        "goals": 2,
        "outcome_patterns": [
            {"outcome": "jailbreak", "pattern": "1", "weight": pytest.approx(1)},
            {"outcome": "mitigated", "pattern": "0", "weight": 1},
        ],
    }
    assert second["goal_weighted"]["goals"] == 1
    assert second["goal_weighted"]["outcome_patterns"][0]["weight"] == 1
    for column in [weighted, first["goal_weighted"], second["goal_weighted"]]:
        assert sum(
            item["weight"] for item in column["outcome_patterns"]
        ) == pytest.approx(column["goals"])
    rows[0].pop("goal_index")
    missing = judge_agreement(rows)
    assert missing["goal_weighted"] is None
    assert missing["runs"][0]["goal_weighted"] is None
    assert missing["runs"][1]["goal_weighted"]["goals"] == 1


def test_recorded_outcomes_are_not_inferred_from_majority_votes():
    result = judge_agreement(
        [
            {
                "run_id": "one",
                "metrics": {"eval_a": 0, "eval_b": 0, "eval_c": 1},
                "outcome": outcome,
            }
            for outcome in ("jailbreak", "mitigated", None, "error")
        ]
        + [
            {
                "run_id": "two",
                "metrics": {"eval_a": 0, "eval_b": 0, "eval_c": 1},
                "outcome": "jailbreak",
            }
        ]
    )
    assert result["outcome_patterns"] == [
        {"outcome": "jailbreak", "pattern": "001", "attempts": 2},
        {"outcome": "mitigated", "pattern": "001", "attempts": 1},
        {"outcome": "unresolved", "pattern": "001", "attempts": 2},
    ]
    assert result["runs"][1]["outcome_patterns"] == [
        {"outcome": "jailbreak", "pattern": "001", "attempts": 1},
    ]
    for run in result["runs"]:
        assert (
            sum(item["attempts"] for item in run["outcome_patterns"]) == run["attempts"]
        )


def test_all_binary_patterns_keep_fixed_judge_order_and_per_run_counts():
    rows = [
        {
            "run_id": "one" if a == 0 else "two",
            "metrics": {"eval_c": c, "eval_a": a, "eval_b": b},
        }
        for a, b, c in product((0, 1), repeat=3)
    ]
    rows.extend(
        [
            {"run_id": "one", "metrics": {"eval_a": None, "eval_b": 0, "eval_c": 1}},
            {"run_id": "one", "metrics": {"eval_a": "bad", "eval_b": 0, "eval_c": 1}},
            {"run_id": "one", "metrics": {"eval_b": 0, "eval_c": 1}},
        ]
    )
    result = judge_agreement(rows)
    assert [judge["id"] for judge in result["judges"]] == ["eval_a", "eval_b", "eval_c"]
    patterns = {item["pattern"]: item["attempts"] for item in result["patterns"]}
    assert patterns == {
        **{"".join(map(str, bits)): 1 for bits in product((0, 1), repeat=3)},
        "?01": 3,
    }
    for run in result["runs"]:
        assert sum(item["attempts"] for item in run["patterns"]) == run["attempts"]
        assert all(len(item["pattern"]) == 3 for item in run["patterns"])
    assert sum(patterns.values()) == result["attempts"]


def test_patterns_preserve_response_disagreement_not_goal_success():
    def row(goal, a, b, run="one", status="COMPLETED"):
        return {
            "goal_index": goal,
            "run_id": run,
            "run_status": status,
            "outcome": "jailbreak" if a == 1 or b == 1 else "mitigated",
            "metrics": {"eval_a": a, "eval_b": b},
        }

    rows = [row(0, 1, 0), row(0, 0, 1)] + [row(1, 0, 0)] * 20
    result = judge_agreement(rows)
    assert result["unit"] == "attempt"
    assert result["attempts"] == 22
    assert result["judges"][0]["success"] == result["judges"][1]["success"] == 1
    assert result["pairs"][0]["disagreement_rate"] == 2 / 22
    assert result["patterns"] == [
        {"pattern": "00", "attempts": 20},
        {"pattern": "01", "attempts": 1},
        {"pattern": "10", "attempts": 1},
    ]
    pooled = judge_agreement([row(0, 1, 0), row(0, 0, 1, run="two")])
    assert pooled["attempts"] == 2
    assert pooled["pairs"][0]["disagreement_rate"] == 1
    assert len(pooled["runs"]) == 2
    assert all(run["split"] == 1 for run in pooled["runs"])


def test_patterns_keep_missing_and_abstaining_votes_unknown_on_active_runs():
    rows = [
        {
            "goal_index": 0,
            "run_id": "one",
            "run_status": "RUNNING",
            "outcome": "mitigated",
            "metrics": {"eval_a": 0, "eval_b": 1},
        },
        {
            "goal_index": 1,
            "run_id": "one",
            "run_status": "COMPLETED",
            "outcome": "mitigated",
            "metrics": {"eval_a": 0, "eval_b": None},
        },
        {
            "goal_index": 2,
            "run_id": "one",
            "run_status": "COMPLETED",
            "outcome": "mitigated",
            "metrics": {"eval_a": 0},
        },
    ]
    result = judge_agreement(rows)
    assert result["attempts"] == 3
    assert result["judges"][0]["valid"] == 3
    assert result["judges"][0]["abstained"] == 0
    assert result["judges"][1]["success"] == 1
    assert result["judges"][1]["missing"] == 1
    assert result["kappa_attempts"] == 1
    assert result["patterns"] == [
        {"pattern": "01", "attempts": 1},
        {"pattern": "0?", "attempts": 2},
    ]


def test_binary_votes_exclude_scores_missing_and_abstentions():
    rows = [
        {"run_id": "one", "metrics": {"eval_a": 1, "eval_b": 0, "eval_a_mean": 10}},
        {"run_id": "one", "metrics": {"eval_a": 0, "eval_b": 0}},
        {"run_id": "two", "metrics": {"eval_a": 1, "eval_b": 1}},
        {"run_id": "two", "metrics": {"eval_a": None, "eval_b": 1}},
        {"run_id": "two", "metrics": {}},
        {"run_id": "two", "metrics": {"eval_a": 5}},
    ]
    result = judge_agreement(rows)
    assert result["attempts"] == 6
    assert result["comparable_attempts"] == 3
    assert result["split"] == 1
    assert result["disagreement_rate"] == 1 / 3
    assert result["unanimous_success"] == result["unanimous_failure"] == 1
    assert result["insufficient"] == 3
    assert sum(item["attempts"] for item in result["vote_counts"]) == 6
    assert result["judges"][0] == {
        "id": "eval_a",
        "valid": 3,
        "success": 2,
        "abstained": 1,
        "missing": 1,
        "invalid": 1,
        "abstention_rate": 0.25,
        "strictness": 1 - 2 / 3,
    }
    assert result["pairs"][0]["shared"] == 3
    assert result["pairs"][0]["disagreed"] == 1
    assert result["runs"][0]["disagreement_rate"] == 0.5
    assert result["kappa_attempts"] == 3
    assert abs(result["fleiss_kappa"] - 1 / 3) < 1e-10
    assert result["majority_attempts"] == 4
    assert result["majority_vote_rate"] == 0.5


def test_no_or_single_judge_does_not_claim_agreement():
    assert judge_agreement([])["disagreement_rate"] is None
    result = judge_agreement([{"run_id": "one", "metrics": {"eval_a": 1}}])
    assert result["comparable_attempts"] == 0
    assert result["insufficient"] == 1
    assert result["disagreement_rate"] is None
    assert result["pairs"] == []
    assert result["fleiss_kappa"] is None


def test_degenerate_complete_votes_leave_kappa_undefined():
    result = judge_agreement([{"run_id": "one", "metrics": {"eval_a": 1, "eval_b": 1}}])
    assert result["kappa_attempts"] == 1
    assert result["fleiss_kappa"] is None


def test_pairwise_denominators_only_count_shared_valid_votes():
    result = judge_agreement(
        [
            {"run_id": "one", "metrics": {"eval_a": 1, "eval_b": 0, "eval_c": None}},
            {"run_id": "one", "metrics": {"eval_a": 1, "eval_c": 1}},
        ]
    )
    assert [
        (pair["shared"], pair["disagreement_rate"]) for pair in result["pairs"]
    ] == [
        (1, 1.0),
        (1, 0.0),
        (0, None),
    ]


def test_split_votes_keep_one_and_two_positive_votes_and_partial_panels_separate():
    result = judge_agreement(
        [
            {"run_id": "one", "metrics": {"eval_a": 1, "eval_b": 0, "eval_c": 0}},
            {"run_id": "one", "metrics": {"eval_a": 1, "eval_b": 1, "eval_c": 0}},
            {"run_id": "one", "metrics": {"eval_a": 1, "eval_b": 0, "eval_c": None}},
        ]
    )
    assert result["split"] == 3
    assert result["vote_counts"] == [
        {"valid_votes": 2, "jailbreak_votes": 1, "attempts": 1},
        {"valid_votes": 3, "jailbreak_votes": 1, "attempts": 1},
        {"valid_votes": 3, "jailbreak_votes": 2, "attempts": 1},
    ]


def test_mixed_outcomes_follow_recorded_verdict_not_vote_majority():
    result = judge_agreement(
        [
            {
                "run_id": "one",
                "outcome": "jailbreak",
                "metrics": {"eval_a": 1, "eval_b": 0, "eval_c": 0},
            },
            {
                "run_id": "one",
                "outcome": "mitigated",
                "metrics": {"eval_a": 1, "eval_b": 1, "eval_c": 0},
            },
            {
                "run_id": "one",
                "outcome": "mitigated",
                "metrics": {"eval_a": 1, "eval_b": 0},
            },
            {
                "run_id": "one",
                "outcome": "error",
                "metrics": {"eval_a": 1, "eval_b": 0},
            },
            {"run_id": "one", "metrics": {"eval_a": 1, "eval_b": 0}},
            {
                "run_id": "one",
                "outcome": "jailbreak",
                "metrics": {"eval_a": 1, "eval_b": 1},
            },
        ]
    )
    assert result["mixed_outcomes"] == [
        {"outcome": "jailbreak", "valid_votes": 3, "jailbreak_votes": 1, "attempts": 1},
        {"outcome": "mitigated", "valid_votes": 2, "jailbreak_votes": 1, "attempts": 1},
        {"outcome": "mitigated", "valid_votes": 3, "jailbreak_votes": 2, "attempts": 1},
        {
            "outcome": "unresolved",
            "valid_votes": 2,
            "jailbreak_votes": 1,
            "attempts": 2,
        },
    ]
    assert sum(item["attempts"] for item in result["mixed_outcomes"]) == result["split"]


def test_outcome_histograms_cover_all_attempts_and_partition_by_attack():
    rows = [
        {
            "run_id": "one",
            "outcome": "jailbreak",
            "metrics": {"eval_a": 1, "eval_b": 0, "eval_c": 0},
        },
        {
            "run_id": "one",
            "outcome": "mitigated",
            "metrics": {"eval_a": 1, "eval_b": 1},
        },
        {"run_id": "one", "outcome": "mitigated", "metrics": {"eval_a": 1}},
        {
            "run_id": "two",
            "outcome": "jailbreak",
            "metrics": {"eval_a": 0, "eval_b": 0},
        },
        {
            "run_id": "two",
            "outcome": "mitigated",
            "metrics": {"eval_a": 1, "eval_b": 0},
        },
        {"run_id": "two", "outcome": "error", "metrics": {}},
        {"run_id": "two", "metrics": {}},
    ]
    result = judge_agreement(rows)
    assert result["outcome_votes"] == [
        {"outcome": "jailbreak", "valid_votes": 2, "jailbreak_votes": 0, "attempts": 1},
        {"outcome": "jailbreak", "valid_votes": 3, "jailbreak_votes": 1, "attempts": 1},
        {"outcome": "mitigated", "valid_votes": 1, "jailbreak_votes": 1, "attempts": 1},
        {"outcome": "mitigated", "valid_votes": 2, "jailbreak_votes": 1, "attempts": 1},
        {"outcome": "mitigated", "valid_votes": 2, "jailbreak_votes": 2, "attempts": 1},
        {
            "outcome": "unresolved",
            "valid_votes": 0,
            "jailbreak_votes": 0,
            "attempts": 2,
        },
    ]
    assert sum(item["attempts"] for item in result["outcome_votes"]) == len(rows)
    for run in result["runs"]:
        assert (
            run["outcome_votes"]
            == judge_agreement([row for row in rows if row["run_id"] == run["run_id"]])[
                "outcome_votes"
            ]
        )
        assert sum(item["attempts"] for item in run["outcome_votes"]) == run["attempts"]
    assert judge_agreement([])["outcome_votes"] == []
