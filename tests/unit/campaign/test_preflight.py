# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""With preflight on, any unreachable model stops the run up front."""

from __future__ import annotations

import asyncio

import pytest

from hackagent.models import embedder_is_reachable
from hackagent.orchestrator.campaign import load_campaign, run_campaign
from hackagent.orchestrator.campaign.preflight import PreflightError

from .fakes import FakeBuilder, ScriptedModel, campaign, failure, goals, model

TARGET_REPLY = "a reply the judge will read"


def run(values, *, models=None):
    from tests.fakes import RecordingStore

    builder = FakeBuilder(models or {})
    return run_campaign(
        values, build=builder, load=goals("goal one"), store=RecordingStore()
    )


def models_for(target=TARGET_REPLY, judge="yes", **others):
    return {
        "target": ScriptedModel(target),
        "judge": ScriptedModel(judge),
        **others,
    }


def with_preflight(attacks=None, **sections):
    execution = {"preflight": True, **sections.pop("execution", {})}
    return campaign(
        attacks=attacks or [{"name": "baseline"}], execution=execution, **sections
    )


def down(message="down"):
    return ScriptedModel(lambda _m: failure(message))


def with_attacker(*names):
    return [{"name": name, "roles": {"attacker": model("attacker")}} for name in names]


# --- on by default -----------------------------------------------------------


def test_preflight_is_on_by_default():
    values = campaign()
    del values["execution"]["preflight"]
    assert load_campaign(values).execution.preflight is True


def test_turning_preflight_off_lets_a_run_proceed():
    # A dead target is not checked; the failure surfaces as an attempt error.
    result = run(
        campaign(attacks=[{"name": "baseline"}], execution={"preflight": False}),
        models=models_for(target=lambda _m: failure("down")),
    )
    assert result.attacks  # the run proceeded rather than raising


# --- target and judges ------------------------------------------------------------


def test_reachable_models_pass_preflight():
    result = run(with_preflight(), models=models_for())
    assert result.attacks


def test_an_unreachable_target_stops_the_run():
    models = models_for(target=lambda _m: failure("connection refused"))
    with pytest.raises(
        PreflightError, match=r"target \(target\): .*connection refused"
    ):
        run(with_preflight(), models=models)


def test_the_target_is_not_attacked_when_preflight_fails():
    target = down()
    with pytest.raises(PreflightError):
        run(with_preflight(), models={**models_for(), "target": target})
    # Only the preflight check reached the target; no attack request followed.
    assert len(target.requests) == 1


def test_an_unreachable_judge_stops_the_run():
    models = {**models_for(), "judge": down("judge down")}
    with pytest.raises(PreflightError, match=r"evaluation\.judges\[0\]"):
        run(with_preflight(), models=models)


def test_the_error_names_every_unreachable_model():
    models = {"target": down("t down"), "judge": down("j down")}
    with pytest.raises(PreflightError) as raised:
        run(with_preflight(), models=models)
    assert len(raised.value.failures) == 2


# --- roles and guardrails -------------------------------------------------------


def test_an_unreachable_attack_role_stops_the_run():
    models = {**models_for(), "attacker": down("attacker down")}
    with pytest.raises(PreflightError, match=r"attacks\[0\]\.pair\.attacker"):
        run(with_preflight(attacks=with_attacker("pair")), models=models)


def test_a_model_used_in_several_places_is_checked_once():
    attacker = down("attacker down")
    with pytest.raises(PreflightError) as raised:
        run(
            with_preflight(attacks=with_attacker("pair", "tap")),
            models={**models_for(), "attacker": attacker},
        )
    [message] = raised.value.failures
    assert "attacks[0].pair.attacker" in message
    assert "attacks[1].tap.attacker" in message
    assert len(attacker.requests) == 1


def test_an_unreachable_guardrail_stops_the_run():
    values = with_preflight(guardrails={"before": model("guard")})
    with pytest.raises(PreflightError, match=r"guardrails\.before"):
        run(values, models={**models_for(), "guard": down()})


# --- embedders --------------------------------------------------------------------


def test_an_embedder_is_reachable_when_it_returns_a_vector():
    async def embed(texts):
        return [[0.1, 0.2] for _ in texts]

    assert asyncio.run(embedder_is_reachable(embed))


def test_an_embedder_that_raises_or_returns_nothing_is_not_reachable():
    async def broken(_texts):
        raise ConnectionError("refused")

    async def empty(_texts):
        return []

    assert "refused" in asyncio.run(embedder_is_reachable(broken)).detail
    assert not asyncio.run(embedder_is_reachable(empty))


# --- dry run ------------------------------------------------------------------


def test_a_dry_run_skips_preflight():
    # dry_run returns before preflight, so a dead target does not raise.
    result = run(
        with_preflight(execution={"dry_run": True}),
        models={**models_for(), "target": down()},
    )
    assert result.dry_run is True
