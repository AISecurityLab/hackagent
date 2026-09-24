# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Convert attack results to and from storage records.

This is the only module that produces ``eval_*`` column names. Technique
code may carry a :class:`~hackagent.core.contracts.Verdict`; the column
layout written onto result rows and ``evaluation_metrics`` is decided here.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from hackagent.attacks.types import AttackResult
from hackagent.core.contracts import EvalStatus, Verdict

# Judge type → binary score column. Means are the same stem plus ``_mean``.
JUDGE_SCORE_COLUMNS: Dict[str, str] = {
    "nuanced": "eval_nj",
    "jailbreakbench": "eval_jb",
    "harmbench": "eval_hb",
    "harmbench_variant": "eval_hbv",
    "strongreject": "eval_sj_binary",
    "on_topic": "eval_on_topic",
    "scorer": "eval_scorer",
    "rag_outcome": "eval_rag",
}


def eval_columns(
    verdict: Optional[Verdict] = None,
    *,
    evaluations: Optional[list] = None,
) -> Dict[str, Any]:
    """Build the ``eval_*`` / ``explanation_*`` columns for one result.

    A verdict's votes become one binary column per known judge type. The
    aggregate score is also stored as ``best_score``. Unknown judge names
    are kept as ``eval_<name>`` so a new judge type still lands a column.
    """
    columns: Dict[str, Any] = {}
    if verdict is None and not evaluations:
        return columns

    if verdict is not None:
        columns["success"] = bool(verdict.success)
        columns["best_score"] = float(verdict.score)
        if verdict.explanation:
            columns["explanation"] = verdict.explanation
        for vote in verdict.votes:
            _put_vote(columns, vote.judge, vote.score, vote.success, vote.explanation)

    for item in evaluations or []:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or item.get("judge") or "")
        if not name:
            continue
        _put_vote(
            columns,
            name,
            item.get("score"),
            item.get("success"),
            str(item.get("notes") or item.get("explanation") or ""),
        )
    return columns


def result_to_row(result: AttackResult) -> Dict[str, Any]:
    """Result → the dict row ``hack`` returns, with ``eval_*`` columns applied."""
    row = result.to_row()
    produced = eval_columns(result.verdict, evaluations=_evaluation_dicts(result))
    # Columns produced here win over any same-named keys carried in metadata.
    row.update(produced)
    if result.verdict is not None and "success" not in row:
        row["success"] = bool(result.verdict.success)
    return row


def row_to_result(row: Mapping[str, Any]) -> AttackResult:
    """Record/row dict → :class:`AttackResult`."""
    return AttackResult.from_row(dict(row))


def evaluation_metrics(result: AttackResult) -> Dict[str, Any]:
    """The ``evaluation_metrics`` payload stored on a result record.

    Only ``eval_*`` and ``explanation_*`` keys are included, so this dict
    is exactly the column set this module produces.
    """
    columns = eval_columns(result.verdict, evaluations=_evaluation_dicts(result))
    return {
        key: value
        for key, value in columns.items()
        if key.startswith("eval_") or key.startswith("explanation_")
    }


def evaluation_status(result: AttackResult) -> Optional[str]:
    """Wire status for a judged result, or ``None`` when it has no verdict."""
    if result.verdict is None:
        return None
    if result.verdict.success:
        return EvalStatus.SUCCESSFUL_JAILBREAK.value
    return EvalStatus.FAILED_JAILBREAK.value


def _evaluation_dicts(result: AttackResult) -> list:
    out = []
    for item in result.evaluations:
        out.append(item.model_dump())
    return out


def _put_vote(
    columns: Dict[str, Any],
    judge: str,
    score: Any,
    success: Any,
    explanation: str,
) -> None:
    column = _column_for(judge)
    if success is None and isinstance(score, (int, float)):
        flag = 1 if float(score) > 0 else 0
    else:
        flag = 1 if success else 0
    columns[column] = flag
    if isinstance(score, (int, float)):
        columns[f"{column}_mean"] = float(score)
    if explanation:
        stem = column[len("eval_") :]
        columns[f"explanation_{stem}"] = explanation


def _column_for(judge: str) -> str:
    key = (judge or "").strip().lower().replace(" ", "_")
    if key in JUDGE_SCORE_COLUMNS:
        return JUDGE_SCORE_COLUMNS[key]
    if key.startswith("eval_"):
        return key
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in key) or "judge"
    return f"eval_{safe}"


__all__ = [
    "JUDGE_SCORE_COLUMNS",
    "eval_columns",
    "evaluation_metrics",
    "evaluation_status",
    "result_to_row",
    "row_to_result",
]
