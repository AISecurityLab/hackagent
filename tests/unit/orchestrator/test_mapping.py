# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""``mapping`` is the only orchestrator module that names ``eval_*`` columns."""

import re
from pathlib import Path

from hackagent.attacks.types import AttackResult
from hackagent.core.contracts import EvalStatus, JudgeVote, Verdict
from hackagent.orchestrator.mapping import (
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
    offenders = []
    for path in sorted(root.glob("*.py")):
        if path.name == "mapping.py":
            continue
        hits = _COLUMN.findall(path.read_text(encoding="utf-8"))
        if hits:
            offenders.append(f"{path.name}: {hits}")
    assert offenders == []
