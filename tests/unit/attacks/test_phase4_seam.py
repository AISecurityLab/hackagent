# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Phase 4 attack-seam smoke tests (ports, AttackConfig.roles, make_ctx)."""

from __future__ import annotations

from hackagent.attacks.config import AttackConfig, roles_from_paths, ui
from hackagent.attacks.ports import RunContext, Step
from hackagent.attacks.techniques.pair.config import PairConfig
from hackagent.attacks.types import AttackResult
from hackagent.core.contracts import Sample, Verdict
from hackagent.core.defaults import DEFAULT_MAX_OUTPUT_TOKENS
from hackagent.models.target_params import TargetParams
from hackagent.orchestrator import RunSpec
from tests.fakes import FakeJudge, make_ctx


def test_ui_helper_keys():
    meta = ui(label="X", section="Y", advanced=True, choices=["a", "b"])
    assert meta == {
        "label": "X",
        "section": "Y",
        "advanced": True,
        "choices": ["a", "b"],
    }


def test_roles_from_paths_pair():
    roles = roles_from_paths(
        "pair",
        {"attacker": {"identifier": "a"}, "judge": {"identifier": "j"}},
    )
    assert {r["role"] for r in roles} == {"attacker", "judge"}


def test_attack_config_roles_empty_by_default():
    assert AttackConfig().roles() == []


def test_pair_config_attacker_max_tokens_is_500():
    assert PairConfig().attacker["max_tokens"] == 500


def test_attack_result_verdict_roundtrip():
    result = AttackResult(
        goal="g",
        verdict=Verdict(success=True, score=8.0, explanation="ok"),
    )
    row = result.to_row()
    assert row["verdict"]["success"] is True
    restored = AttackResult.from_row(row)
    assert restored.verdict is not None
    assert restored.verdict.score == 8.0


def test_make_ctx_and_fake_judge():
    ctx = make_ctx()
    assert isinstance(ctx, RunContext)
    assert ctx.run_id == "test-run"
    judge = FakeJudge(score=7.0, success=True)
    assert judge.score(Sample(goal="g", prompt="p", response="r")) == 7.0
    assert len(judge.samples) == 1


def test_run_spec_and_target_params():
    assert RunSpec().rejudge is False
    assert TargetParams().max_tokens == DEFAULT_MAX_OUTPUT_TOKENS


def test_step_dataclass():
    step = Step(name="gen", kind="GENERATION", fn=lambda **kw: kw)
    assert step.input_arg == "input_data"
