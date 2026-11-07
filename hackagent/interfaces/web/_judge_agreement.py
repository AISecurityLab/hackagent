# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Attempt-level agreement and identity-preserving binary judge patterns."""

from collections import Counter
from itertools import combinations
from typing import Any
from hackagent.core.contracts import JudgeVote, Verdict
from hackagent.evaluation.metrics import (
    fleiss_kappa,
    majority_vote_rate,
    per_judge_strictness,
)


def judge_agreement(rows: list[dict[str, Any]]) -> dict[str, Any]:
    goal_counts = Counter(row.get("goal_index") for row in rows)
    run_goal_counts = Counter((row["run_id"], row.get("goal_index")) for row in rows)
    goal_weights: Counter[tuple[str, str]] = Counter()
    attack_goal_weights: dict[str, Counter[tuple[str, str]]] = {}
    judges = sorted(
        {
            key
            for row in rows
            for key in row["metrics"]
            if key.startswith("eval_") and not key.endswith("_mean")
        }
    )
    counts = {judge: Counter() for judge in judges}
    pairs = {pair: Counter() for pair in combinations(judges, 2)}
    distribution: Counter[str] = Counter()
    vote_counts: Counter[tuple[int, int]] = Counter()
    mixed_outcomes: Counter[tuple[str, int, int]] = Counter()
    outcome_votes: Counter[tuple[str, int, int]] = Counter()
    attack_votes: dict[str, Counter[tuple[str, int, int]]] = {}
    attacks: dict[str, Counter[str]] = {}
    patterns: Counter[str] = Counter()
    attack_patterns: dict[str, Counter[str]] = {}
    outcome_patterns: Counter[tuple[str, str]] = Counter()
    attack_outcome_patterns: dict[str, Counter[tuple[str, str]]] = {}
    verdicts = []
    complete_verdicts = []
    for row in rows:
        votes = {}
        for judge in judges:
            metrics = row["metrics"]
            if judge not in metrics:
                counts[judge]["missing"] += 1
            elif metrics[judge] is None:
                counts[judge]["abstained"] += 1
            elif metrics[judge] in (0, 1):
                vote = int(metrics[judge])
                votes[judge] = vote
                counts[judge]["valid"] += 1
                counts[judge]["success"] += vote
            else:
                counts[judge]["invalid"] += 1
        pattern = "".join(
            str(votes[judge]) if judge in votes else "?" for judge in judges
        )
        patterns[pattern] += 1
        attack_patterns.setdefault(row["run_id"], Counter())[pattern] += 1
        bucket = "insufficient"
        if len(votes) >= 2:
            bucket = (
                "split"
                if len(set(votes.values())) > 1
                else (
                    "unanimous_success"
                    if next(iter(votes.values()))
                    else "unanimous_failure"
                )
            )
        distribution[bucket] += 1
        vote_counts[(len(votes), sum(votes.values()))] += 1
        outcome = row.get("outcome")
        outcome_key = (
            outcome if outcome in ("jailbreak", "mitigated") else "unresolved",
            len(votes),
            sum(votes.values()),
        )
        outcome_votes[outcome_key] += 1
        outcome_patterns[(outcome_key[0], pattern)] += 1
        goal = row.get("goal_index")
        if goal is not None:
            goal_weights[(outcome_key[0], pattern)] += 1 / goal_counts[goal]
            attack_goal_weights.setdefault(row["run_id"], Counter())[
                (outcome_key[0], pattern)
            ] += 1 / run_goal_counts[(row["run_id"], goal)]
        attack_outcome_patterns.setdefault(row["run_id"], Counter())[
            (outcome_key[0], pattern)
        ] += 1
        attack_votes.setdefault(row["run_id"], Counter())[outcome_key] += 1
        if bucket == "split":
            mixed_outcomes[outcome_key] += 1
        if votes:
            verdict = Verdict(
                success=sum(votes.values()) * 2 > len(votes),
                score=0,
                votes=[
                    JudgeVote(judge=judge, success=bool(votes[judge]))
                    if judge in votes
                    else JudgeVote(judge=judge, error="Missing or abstaining vote")
                    for judge in judges
                ],
            )
            verdicts.append(verdict)
            if len(votes) == len(judges) and len(judges) >= 2:
                complete_verdicts.append(verdict)
        attacks.setdefault(row["run_id"], Counter())[bucket] += 1
        for pair, count in pairs.items():
            if all(judge in votes for judge in pair):
                count["shared"] += 1
                count["disagreed"] += votes[pair[0]] != votes[pair[1]]

    def totals(count: Counter[str]) -> dict[str, Any]:
        eligible = sum(
            count[key] for key in ("split", "unanimous_success", "unanimous_failure")
        )
        return {
            "attempts": sum(count.values()),
            "comparable_attempts": eligible,
            "split": count["split"],
            "unanimous_success": count["unanimous_success"],
            "unanimous_failure": count["unanimous_failure"],
            "insufficient": count["insufficient"],
            "disagreement_rate": count["split"] / eligible if eligible else None,
        }

    complete_votes = [
        vote.success for verdict in complete_verdicts for vote in verdict.votes
    ]
    kappa = (
        fleiss_kappa(complete_verdicts)
        if complete_verdicts and len(set(complete_votes)) > 1
        else None
    )
    strictness = per_judge_strictness(verdicts)

    def histogram(count: Counter[tuple[str, int, int]]) -> list[dict[str, Any]]:
        return [
            {
                "outcome": outcome,
                "valid_votes": valid,
                "jailbreak_votes": positive,
                "attempts": attempts,
            }
            for (outcome, valid, positive), attempts in sorted(count.items())
        ]

    def weighted(ident: str | None = None) -> dict[str, Any] | None:
        goals = (
            {goal for run, goal in run_goal_counts if run == ident}
            if ident is not None
            else set(goal_counts)
        )
        if None in goals:
            return None
        weights = (
            attack_goal_weights.get(ident, Counter())
            if ident is not None
            else goal_weights
        )
        return {
            "goals": len(goals),
            "outcome_patterns": [
                {"outcome": outcome, "pattern": pattern, "weight": weight}
                for (outcome, pattern), weight in sorted(weights.items())
            ],
        }

    return {
        "unit": "attempt",
        "goal_weighted": weighted(),
        "outcome_patterns": [
            {"outcome": outcome, "pattern": pattern, "attempts": count}
            for (outcome, pattern), count in sorted(outcome_patterns.items())
        ],
        "patterns": [
            {"pattern": pattern, "attempts": count}
            for pattern, count in sorted(patterns.items())
        ],
        **totals(distribution),
        "outcome_votes": histogram(outcome_votes),
        "vote_counts": [
            {"valid_votes": valid, "jailbreak_votes": positive, "attempts": attempts}
            for (valid, positive), attempts in sorted(vote_counts.items())
        ],
        "mixed_outcomes": histogram(mixed_outcomes),
        "fleiss_kappa": kappa,
        "kappa_attempts": len(complete_verdicts),
        "majority_vote_rate": majority_vote_rate(verdicts) if verdicts else None,
        "majority_attempts": len(verdicts),
        "bias_gap": strictness.get("bias_gap")
        if sum(count["valid"] > 0 for count in counts.values()) >= 2
        else None,
        "judges": [
            {
                "id": judge,
                "valid": count["valid"],
                "success": count["success"],
                "strictness": strictness.get(judge),
                "abstained": count["abstained"],
                "missing": count["missing"],
                "invalid": count["invalid"],
                "abstention_rate": count["abstained"]
                / (count["valid"] + count["abstained"])
                if count["valid"] + count["abstained"]
                else None,
            }
            for judge, count in counts.items()
        ],
        "pairs": [
            {
                "left": pair[0],
                "right": pair[1],
                "shared": count["shared"],
                "disagreed": count["disagreed"],
                "disagreement_rate": count["disagreed"] / count["shared"]
                if count["shared"]
                else None,
            }
            for pair, count in pairs.items()
        ],
        "runs": [
            {
                "run_id": ident,
                "goal_weighted": weighted(ident),
                "outcome_patterns": [
                    {"outcome": outcome, "pattern": pattern, "attempts": count}
                    for (outcome, pattern), count in sorted(
                        attack_outcome_patterns[ident].items()
                    )
                ],
                "patterns": [
                    {"pattern": pattern, "attempts": count}
                    for pattern, count in sorted(attack_patterns[ident].items())
                ],
                **totals(count),
                "outcome_votes": histogram(attack_votes[ident]),
            }
            for ident, count in attacks.items()
        ],
    }
