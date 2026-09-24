# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Metrics over verdicts.

A verdict whose judges all abstained (``Verdict.error``) is not a judgement.
Rates and means leave it out of the denominator; ``summary`` counts it under
``abstained``. An abstaining or missing vote is missing, not a safe vote.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from hackagent.core.contracts import Verdict


def _judged(verdicts: Sequence[Verdict]) -> List[Verdict]:
    return [verdict for verdict in verdicts if verdict.error is None]


def success_rate(verdicts: Sequence[Verdict]) -> float:
    """Fraction of judged verdicts marked successful. Empty input is 0."""
    judged = _judged(verdicts)
    if not judged:
        return 0.0
    return sum(1 for verdict in judged if verdict.success) / len(judged)


def mean_score(verdicts: Sequence[Verdict]) -> float:
    """Mean judged verdict score on the 0..10 scale. Empty input is 0."""
    judged = _judged(verdicts)
    if not judged:
        return 0.0
    return sum(float(verdict.score) for verdict in judged) / len(judged)


def _judge_names(verdicts: Sequence[Verdict]) -> List[str]:
    names: List[str] = []
    for verdict in verdicts:
        for vote in verdict.votes:
            if vote.judge not in names:
                names.append(vote.judge)
    return names


def _vote_matrix(verdicts: Sequence[Verdict]) -> List[List[Optional[int]]]:
    """Binary votes per judged verdict, columns aligned by judge name.

    A judge that abstained or did not vote on a verdict is ``None``.
    """
    names = _judge_names(verdicts)
    if not names:
        return []
    matrix: List[List[Optional[int]]] = []
    for verdict in _judged(verdicts):
        by_name = {vote.judge: vote for vote in verdict.votes}
        row: List[Optional[int]] = []
        for name in names:
            vote = by_name.get(name)
            if vote is None or vote.abstained:
                row.append(None)
            elif vote.success is not None:
                row.append(1 if vote.success else 0)
            else:
                row.append(1 if (vote.score or 0) > 0 else 0)
        matrix.append(row)
    return matrix


def majority_vote_rate(verdicts: Sequence[Verdict]) -> float:
    """Share of judged verdicts where more than half the votes cast say success.

    A tie is not a success. With at most one judge, this is
    :func:`success_rate`.
    """
    matrix = _vote_matrix(verdicts)
    if not matrix or len(matrix[0]) <= 1:
        return success_rate(verdicts)
    successes = 0
    counted = 0
    for row in matrix:
        cast = [vote for vote in row if vote is not None]
        if not cast:
            continue
        counted += 1
        if sum(cast) * 2 > len(cast):
            successes += 1
    return successes / counted if counted else 0.0


def fleiss_kappa(verdicts: Sequence[Verdict]) -> float:
    """Fleiss' kappa across judge votes.

    Only verdicts every judge voted on are used, since kappa assumes a fixed
    number of raters per item. One judge, or no such verdicts, is 1.
    """
    matrix = [
        row for row in _vote_matrix(verdicts) if all(vote is not None for vote in row)
    ]
    if not matrix or len(matrix[0]) <= 1:
        return 1.0
    n_judges = len(matrix[0])
    n_items = len(matrix)
    category_counts = []
    for row in matrix:
        count_true = sum(vote or 0 for vote in row)
        category_counts.append([n_judges - count_true, count_true])
    p_j = [
        sum(item[j] for item in category_counts) / (n_items * n_judges)
        for j in range(2)
    ]
    p_i = [
        sum(count * (count - 1) for count in item) / (n_judges * (n_judges - 1))
        for item in category_counts
    ]
    p_bar = sum(p_i) / n_items
    p_e = sum(p**2 for p in p_j)
    if p_e == 1.0:
        return 1.0
    return (p_bar - p_e) / (1 - p_e)


def per_judge_strictness(verdicts: Sequence[Verdict]) -> Dict[str, float]:
    """Safe-rate (1 - positive rate) per judge over its cast votes, plus ``bias_gap``."""
    matrix = _vote_matrix(verdicts)
    names = _judge_names(verdicts)
    if not matrix or not names:
        return {"bias_gap": 0.0}
    strictness: Dict[str, float] = {}
    for index, name in enumerate(names):
        cast = [row[index] for row in matrix if row[index] is not None]
        if not cast:
            continue
        strictness[name] = 1.0 - sum(1 for vote in cast if vote) / len(cast)
    rated = list(strictness.values())
    strictness["bias_gap"] = (max(rated) - min(rated)) if rated else 0.0
    return strictness


def summary(verdicts: Sequence[Verdict]) -> Dict[str, Any]:
    """Compact report for a list of verdicts."""
    return {
        "total": len(verdicts),
        "abstained": len(verdicts) - len(_judged(verdicts)),
        "success_rate": success_rate(verdicts),
        "mean_score": mean_score(verdicts),
        "majority_vote_rate": majority_vote_rate(verdicts),
        "fleiss_kappa": fleiss_kappa(verdicts),
        "per_judge_strictness": per_judge_strictness(verdicts),
    }


__all__ = [
    "fleiss_kappa",
    "majority_vote_rate",
    "mean_score",
    "per_judge_strictness",
    "success_rate",
    "summary",
]
