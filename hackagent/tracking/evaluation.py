"""Map provider-neutral verdicts onto stored evaluation fields.

The judges produce a :class:`~hackagent.core.contracts.Verdict`; the store
and the result views read flat ``eval_*`` columns. The campaign runner uses
:func:`eval_columns` to fill a result's ``evaluation_metrics``.
"""

from typing import Any, Mapping, Optional

from hackagent.core.contracts import EvalStatus, Verdict

#: Short column names of the built-in judges; any other judge gets
#: ``eval_<name>`` with non-alphanumerics replaced by ``_``.
JUDGE_SCORE_COLUMNS = {
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
) -> dict[str, Any]:
    """Flatten a verdict and per-judge evaluations into stored result columns.

    Each judge gets an ``eval_<judge>`` column holding 1 or 0 (known judges use
    the short names in :data:`JUDGE_SCORE_COLUMNS`), plus ``eval_<judge>_mean``
    for a numeric score and ``explanation_<judge>`` for its reasoning. An
    abstaining judge's column is None. The verdict itself adds ``success``,
    ``best_score`` and, when present, ``judge_error`` and ``explanation``.

    Args:
        verdict: The aggregated verdict, with one vote per judge.
        evaluations: Extra per-judge results as mappings with ``name`` (or
            ``judge``), ``score``, ``success`` and ``notes`` (or
            ``explanation``); non-mappings are skipped.

    Returns:
        The columns, keyed by name.
    """
    columns: dict[str, Any] = {}
    if verdict is not None:
        columns["success"] = bool(verdict.success)
        columns["best_score"] = float(verdict.score)
        if verdict.error:
            columns["judge_error"] = verdict.error
        if verdict.explanation:
            columns["explanation"] = verdict.explanation
        for vote in verdict.votes:
            if vote.abstained:
                column = _column_for(vote.judge)
                columns[column] = None
                if vote.error:
                    columns[f"explanation_{column[len('eval_') :]}"] = vote.error
            else:
                _put_vote(
                    columns, vote.judge, vote.score, vote.success, vote.explanation
                )
    for item in evaluations or []:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or item.get("judge") or "")
        if name:
            _put_vote(
                columns,
                name,
                item.get("score"),
                item.get("success"),
                str(item.get("notes") or item.get("explanation") or ""),
            )
    return columns


def evaluation_metrics(result: Any) -> dict[str, Any]:
    """Return only the ``eval_*`` and ``explanation_*`` columns of a result.

    Args:
        result: An object with a ``verdict`` and a list of pydantic
            ``evaluations``.
    """
    columns = eval_columns(
        result.verdict,
        evaluations=[item.model_dump() for item in result.evaluations],
    )
    return {
        key: value
        for key, value in columns.items()
        if key.startswith("eval_") or key.startswith("explanation_")
    }


def evaluation_status(result: Any) -> Optional[str]:
    """Map a result's verdict to its stored ``EvalStatus`` value.

    Returns:
        ``ERROR_TEST_FRAMEWORK`` when the judges failed,
        ``SUCCESSFUL_JAILBREAK`` or ``FAILED_JAILBREAK`` otherwise, and None
        when the result has no verdict yet.
    """
    if result.verdict is None:
        return None
    if result.verdict.error:
        return EvalStatus.ERROR_TEST_FRAMEWORK.value
    if result.verdict.success:
        return EvalStatus.SUCCESSFUL_JAILBREAK.value
    return EvalStatus.FAILED_JAILBREAK.value


def _put_vote(
    columns: dict[str, Any], judge: str, score: Any, success: Any, explanation: str
) -> None:
    column = _column_for(judge)
    flag = (
        (1 if float(score) > 0 else 0)
        if success is None and isinstance(score, (int, float))
        else (1 if success else 0)
    )
    columns[column] = flag
    if isinstance(score, (int, float)):
        columns[f"{column}_mean"] = float(score)
    if explanation:
        columns[f"explanation_{column[len('eval_') :]}"] = explanation


def _column_for(judge: str) -> str:
    key = (judge or "").strip().lower().replace(" ", "_")
    if key in JUDGE_SCORE_COLUMNS:
        return JUDGE_SCORE_COLUMNS[key]
    if key.startswith("eval_"):
        return key
    safe = (
        "".join(
            character if character.isalnum() or character == "_" else "_"
            for character in key
        )
        or "judge"
    )
    return f"eval_{safe}"
