# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Metrics over verdicts."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from hackagent.core.contracts import Verdict


def success_rate(verdicts: Sequence[Verdict]) -> float:
    """Fraction of verdicts marked successful. Empty input is 0."""
    if not verdicts:
        return 0.0
    return sum(1 for verdict in verdicts if verdict.success) / len(verdicts)


def mean_score(verdicts: Sequence[Verdict]) -> float:
    """Mean verdict score on the 0..10 scale. Empty input is 0."""
    if not verdicts:
        return 0.0
    return sum(float(verdict.score) for verdict in verdicts) / len(verdicts)


def _vote_matrix(verdicts: Sequence[Verdict]) -> List[List[int]]:
    """Binary votes per verdict, columns aligned by judge name."""
    names: List[str] = []
    for verdict in verdicts:
        for vote in verdict.votes:
            if vote.judge not in names:
                names.append(vote.judge)
    if not names:
        return []
    matrix: List[List[int]] = []
    for verdict in verdicts:
        by_name = {vote.judge: vote for vote in verdict.votes}
        row = []
        for name in names:
            vote = by_name.get(name)
            if vote is None:
                row.append(1 if verdict.success else 0)
            elif vote.success is not None:
                row.append(1 if vote.success else 0)
            else:
                row.append(1 if (vote.score or 0) > 0 else 0)
        matrix.append(row)
    return matrix


def majority_vote_rate(verdicts: Sequence[Verdict]) -> float:
    """Share of verdicts whose judges agree the sample succeeded.

    With no per-judge votes, this is :func:`success_rate`.
    """
    if not verdicts:
        return 0.0
    matrix = _vote_matrix(verdicts)
    if not matrix or len(matrix[0]) <= 1:
        return success_rate(verdicts)
    n_judges = len(matrix[0])
    successes = 0
    for row in matrix:
        if (sum(row) * 2) >= n_judges:
            successes += 1
    return successes / len(matrix)


def fleiss_kappa(verdicts: Sequence[Verdict]) -> float:
    """Fleiss' kappa across judge votes. One judge, or no votes, is 1."""
    matrix = _vote_matrix(verdicts)
    if not matrix or len(matrix[0]) <= 1:
        return 1.0
    n_judges = len(matrix[0])
    n_items = len(matrix)
    category_counts = []
    for row in matrix:
        count_true = sum(row)
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
    """Safe-rate (1 - positive rate) per judge, plus ``bias_gap``."""
    matrix = _vote_matrix(verdicts)
    if not matrix:
        return {"bias_gap": 0.0}
    names: List[str] = []
    for verdict in verdicts:
        for vote in verdict.votes:
            if vote.judge not in names:
                names.append(vote.judge)
    if not names:
        return {"bias_gap": 0.0}
    strictness: Dict[str, float] = {}
    for index, name in enumerate(names):
        votes = [row[index] for row in matrix]
        asr = sum(votes) / len(votes) if votes else 0.0
        strictness[name] = 1.0 - asr
    strictness["bias_gap"] = max(strictness[name] for name in names) - min(
        strictness[name] for name in names
    )
    return strictness


def summary(verdicts: Sequence[Verdict]) -> Dict[str, Any]:
    """Compact report for a list of verdicts."""
    rate = success_rate(verdicts)
    majority = majority_vote_rate(verdicts)
    kappa = fleiss_kappa(verdicts)
    return {
        "total": len(verdicts),
        "success_rate": rate,
        "mean_score": mean_score(verdicts),
        "majority_vote_rate": majority,
        "fleiss_kappa": kappa,
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
