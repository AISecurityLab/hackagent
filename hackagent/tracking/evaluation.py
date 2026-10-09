"""Map provider-neutral verdicts onto stored evaluation fields."""

from typing import Any, Mapping, Optional

from hackagent.core.contracts import EvalStatus, Verdict

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
