# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""``mapping`` is the only orchestrator module that names ``eval_*`` columns."""

import re
from pathlib import Path

from hackagent.attacks.types import AttackResult
from hackagent.core.contracts import EvalStatus, JudgeVote, Verdict
from hackagent.orchestrator.results.mapping import (
    evaluation_metrics,
    evaluation_status,
    result_to_row,
)

_COLUMN = re.compile(r"""['"]eval_[A-Za-z0-9_]+['"]""")


def test_result_row_carries_eval_columns_from_the_verdict():
    result = AttackResult(
        goal="g",
        prompt="p",
        response="r",
        verdict=Verdict(
            success=True,
            score=8.0,
            votes=[JudgeVote(judge="harmbench", score=1.0, success=True)],
        ),
    )
    row = result_to_row(result)
    assert row["eval_hb"] == 1
    assert row["eval_hb_mean"] == 1.0
    metrics = evaluation_metrics(result)
    assert metrics["eval_hb"] == 1
    assert set(metrics) <= {
        key for key in row if key.startswith(("eval_", "explanation_"))
    }
    assert evaluation_status(result) == EvalStatus.SUCCESSFUL_JAILBREAK.value


def test_unjudged_result_has_no_eval_columns():
    result = AttackResult(goal="g", prompt="p", response="r")
    assert evaluation_status(result) is None
    assert evaluation_metrics(result) == {}
    row = result_to_row(result)
    assert not any(key.startswith("eval_") for key in row)


def test_only_mapping_names_eval_columns():
    root = Path(__file__).resolve().parents[3] / "hackagent" / "orchestrator"
    checked = []
    offenders = []
    for path in sorted(root.rglob("*.py")):
        name = path.relative_to(root).as_posix()
        if name == "results/mapping.py":
            continue
        checked.append(name)
        hits = _COLUMN.findall(path.read_text(encoding="utf-8"))
        if hits:
            offenders.append(f"{name}: {hits}")
    assert "execution/runner.py" in checked
    assert offenders == []


def test_abstaining_judge_column_is_none_not_zero():
    result = AttackResult(
        goal="g",
        response="r",
        verdict=Verdict(
            success=True,
            score=10.0,
            votes=[
                JudgeVote(judge="harmbench", score=1.0, success=True),
                JudgeVote(judge="jailbreakbench", error="rate limited"),
            ],
        ),
    )
    metrics = evaluation_metrics(result)
    assert metrics["eval_hb"] == 1
    assert metrics["eval_jb"] is None
    assert "eval_jb_mean" not in metrics
    assert metrics["explanation_jb"] == "rate limited"
    assert evaluation_status(result) == EvalStatus.SUCCESSFUL_JAILBREAK.value


def test_unjudged_verdict_is_a_framework_error():
    result = AttackResult(
        goal="g",
        response="r",
        verdict=Verdict(
            success=False,
            score=0.0,
            votes=[JudgeVote(judge="harmbench", error="judge down")],
            error="All 1 judge(s) abstained",
        ),
    )
    assert evaluation_status(result) == EvalStatus.ERROR_TEST_FRAMEWORK.value
    row = result_to_row(result)
    assert row["judge_error"] == "All 1 judge(s) abstained"
    assert row["success"] is False
    assert row["eval_hb"] is None
