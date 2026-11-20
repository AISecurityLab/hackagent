# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""How the judges of a panel agree, from the stored vote patterns.

The unit is the attempt: each one carries the vote of every judge that
recorded one (:func:`~hackagent.reporting.tallies.judge_votes`). The judges
of a scope are every ``eval_<judge>`` key any of its attempts recorded,
sorted. Per attempt, a judge has a valid vote (``1`` jailbreak, ``0``
mitigated), abstained (``null``), recorded something else (invalid) or is
missing.

An attempt is *comparable* with at least two valid votes: ``split`` when they
differ, else ``unanimous_success`` or ``unanimous_failure``; with fewer it is
``insufficient``. Its *pattern* is one character per judge, in judge order:
``1``, ``0``, or ``?`` for anything but a valid vote. Its *outcome* is the
automated bucket, ``jailbreak``, ``mitigated`` or ``unresolved`` (an error or
pending attempt). Human reviews do not enter: this measures the judges.

Fleiss' kappa uses the attempts every judge voted on validly (at least two
judges, and not all votes alike); the majority rate the attempts with a valid
vote, a strict majority of which say jailbreak; a judge's strictness is the
share of its valid votes that say mitigated, and ``bias_gap`` the spread of
strictness across judges (at least two with valid votes).

Goal-weighted patterns count each goal once: an attempt weighs ``1 / n`` for
the ``n`` attempts its goal has in the scope (per attack run, in that run's
own breakdown).

Weights are summed as fractions and rounded once, so both servers return the
same floats whatever order they read the rows in.
"""

from __future__ import annotations

import json
from collections import Counter
from fractions import Fraction
from itertools import combinations
from typing import Any, Iterable, Optional, Sequence

from hackagent.reporting.buckets import JAILBREAK, MITIGATED
from hackagent.reporting.goals import run_order
from hackagent.reporting.rows import AttackRun
from hackagent.reporting.tallies import INVALID_VOTE, GoalJudgeVotes

_VALID = (0, 1)


def _outcome(bucket: str) -> str:
    return bucket if bucket in (JAILBREAK, MITIGATED) else "unresolved"


def _category(votes: dict[str, int]) -> str:
    if len(votes) < 2:
        return "insufficient"
    if len(set(votes.values())) > 1:
        return "split"
    return "unanimous_success" if next(iter(votes.values())) else "unanimous_failure"


def _totals(count: Counter[str]) -> dict[str, Any]:
    comparable = sum(
        count[key] for key in ("split", "unanimous_success", "unanimous_failure")
    )
    return {
        "attempts": sum(count.values()),
        "comparable_attempts": comparable,
        "split": count["split"],
        "unanimous_success": count["unanimous_success"],
        "unanimous_failure": count["unanimous_failure"],
        "insufficient": count["insufficient"],
        "disagreement_rate": count["split"] / comparable if comparable else None,
    }


def _histogram(count: Counter[tuple[str, int, int]]) -> list[dict[str, Any]]:
    return [
        {
            "outcome": outcome,
            "valid_votes": valid,
            "jailbreak_votes": positive,
            "attempts": attempts,
        }
        for (outcome, valid, positive), attempts in sorted(count.items())
    ]


def _patterns(count: Counter[tuple[str, str]]) -> list[dict[str, Any]]:
    return [
        {"outcome": outcome, "pattern": pattern, "attempts": attempts}
        for (outcome, pattern), attempts in sorted(count.items())
    ]


def _weighted(
    rows: Sequence[tuple[GoalJudgeVotes, str, str]], key: Any
) -> dict[str, Any]:
    """Goal-weighted outcome patterns of ``rows``, goals grouped by ``key``."""
    per_goal: Counter[Any] = Counter()
    for row, _, _ in rows:
        per_goal[key(row)] += row.attempts
    weights: dict[tuple[str, str], Fraction] = {}
    for row, outcome, pattern in rows:
        share = Fraction(row.attempts, per_goal[key(row)])
        weights[(outcome, pattern)] = weights.get((outcome, pattern), 0) + share
    return {
        "goals": len({row.goal_index for row, _, _ in rows}),
        "outcome_patterns": [
            {"outcome": outcome, "pattern": pattern, "weight": float(weight)}
            for (outcome, pattern), weight in sorted(weights.items())
        ],
    }


def _kappa(complete: Counter[int], judges: int) -> Optional[float]:
    """Fleiss' kappa over attempts every judge voted on, keyed by how many
    said jailbreak."""
    items = sum(complete.values())
    if not items or judges < 2:
        return None
    positive = sum(count * attempts for count, attempts in complete.items())
    if positive in (0, items * judges):
        return None
    p_yes = Fraction(positive, items * judges)
    p_e = p_yes**2 + (1 - p_yes) ** 2
    agreement = sum(
        attempts
        * Fraction(
            count * (count - 1) + (judges - count) * (judges - count - 1),
            judges * (judges - 1),
        )
        for count, attempts in complete.items()
    )
    p_bar = agreement / items
    return float((p_bar - p_e) / (1 - p_e))


def judge_agreement(
    rows: Iterable[GoalJudgeVotes], runs: Sequence[AttackRun]
) -> dict[str, Any]:
    """The ``judge_agreement`` of a report: agreement across the attempts of
    ``runs`` (their stored vote rows; rows of other runs are ignored)."""
    ids = {run.id for run in runs}
    counted = sorted(
        (row for row in rows if row.run_id in ids and row.attempts > 0),
        key=lambda row: (row.run_id, row.goal_index, row.outcome, row.votes),
    )
    parsed = [(row, json.loads(row.votes)) for row in counted]
    judges = sorted({judge for _, votes in parsed for judge in votes})

    status: dict[str, Counter[str]] = {judge: Counter() for judge in judges}
    pairs = {pair: Counter() for pair in combinations(judges, 2)}
    distribution: Counter[str] = Counter()
    vote_counts: Counter[tuple[int, int]] = Counter()
    outcome_votes: Counter[tuple[str, int, int]] = Counter()
    mixed: Counter[tuple[str, int, int]] = Counter()
    patterns: Counter[str] = Counter()
    outcome_patterns: Counter[tuple[str, str]] = Counter()
    by_run: dict[str, dict[str, Counter[Any]]] = {}
    labelled: list[tuple[GoalJudgeVotes, str, str]] = []
    complete: Counter[int] = Counter()
    voted = majority = 0

    for row, recorded in parsed:
        n = row.attempts
        valid: dict[str, int] = {}
        for judge in judges:
            if judge not in recorded:
                status[judge]["missing"] += n
            elif recorded[judge] is None:
                status[judge]["abstained"] += n
            elif recorded[judge] != INVALID_VOTE and recorded[judge] in _VALID:
                valid[judge] = recorded[judge]
                status[judge]["valid"] += n
                status[judge]["success"] += n * recorded[judge]
            else:
                status[judge]["invalid"] += n
        pattern = "".join(
            str(valid[judge]) if judge in valid else "?" for judge in judges
        )
        outcome = _outcome(row.outcome)
        positive = sum(valid.values())
        category = _category(valid)
        labelled.append((row, outcome, pattern))

        distribution[category] += n
        vote_counts[(len(valid), positive)] += n
        outcome_votes[(outcome, len(valid), positive)] += n
        if category == "split":
            mixed[(outcome, len(valid), positive)] += n
        patterns[pattern] += n
        outcome_patterns[(outcome, pattern)] += n
        mine = by_run.setdefault(
            row.run_id,
            {
                "distribution": Counter(),
                "votes": Counter(),
                "patterns": Counter(),
                "outcome_patterns": Counter(),
            },
        )
        mine["distribution"][category] += n
        mine["votes"][(outcome, len(valid), positive)] += n
        mine["patterns"][pattern] += n
        mine["outcome_patterns"][(outcome, pattern)] += n
        if valid:
            voted += n
            majority += n * (positive * 2 > len(valid))
            if len(valid) == len(judges) and len(judges) >= 2:
                complete[positive] += n
        for pair, count in pairs.items():
            if all(judge in valid for judge in pair):
                count["shared"] += n
                count["disagreed"] += n * (valid[pair[0]] != valid[pair[1]])

    strictness = {
        judge: 1 - count["success"] / count["valid"]
        for judge, count in status.items()
        if count["valid"]
    }
    return {
        "unit": "attempt",
        "goal_weighted": _weighted(labelled, lambda row: row.goal_index)
        if labelled
        else {"goals": 0, "outcome_patterns": []},
        "outcome_patterns": _patterns(outcome_patterns),
        "patterns": [
            {"pattern": pattern, "attempts": count}
            for pattern, count in sorted(patterns.items())
        ],
        **_totals(distribution),
        "outcome_votes": _histogram(outcome_votes),
        "vote_counts": [
            {"valid_votes": valid, "jailbreak_votes": positive, "attempts": count}
            for (valid, positive), count in sorted(vote_counts.items())
        ],
        "mixed_outcomes": _histogram(mixed),
        "fleiss_kappa": _kappa(complete, len(judges)),
        "kappa_attempts": sum(complete.values()),
        "majority_vote_rate": majority / voted if voted else None,
        "majority_attempts": voted,
        "bias_gap": max(strictness.values()) - min(strictness.values())
        if len(strictness) >= 2
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
            for judge, count in status.items()
        ],
        "pairs": [
            {
                "left": left,
                "right": right,
                "shared": count["shared"],
                "disagreed": count["disagreed"],
                "disagreement_rate": count["disagreed"] / count["shared"]
                if count["shared"]
                else None,
            }
            for (left, right), count in pairs.items()
        ],
        "runs": [
            {
                "run_id": run.id,
                "goal_weighted": _weighted(
                    [item for item in labelled if item[0].run_id == run.id],
                    lambda row: row.goal_index,
                ),
                "outcome_patterns": _patterns(by_run[run.id]["outcome_patterns"]),
                "patterns": [
                    {"pattern": pattern, "attempts": count}
                    for pattern, count in sorted(by_run[run.id]["patterns"].items())
                ],
                **_totals(by_run[run.id]["distribution"]),
                "outcome_votes": _histogram(by_run[run.id]["votes"]),
            }
            for run in run_order(runs)
            if run.id in by_run
        ],
    }


__all__ = ["judge_agreement"]
