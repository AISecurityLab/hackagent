# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""With preflight on, an unreachable target or judge stops the run up front."""

from __future__ import annotations

import pytest

from hackagent.orchestrator.campaign import run_campaign
from hackagent.orchestrator.campaign.preflight import PreflightError

from .fakes import FakeBuilder, ScriptedModel, campaign, failure, goals

TARGET_REPLY = "a reply the judge will read"


def run(values, *, models=None):
    from tests.fakes import RecordingStore

    builder = FakeBuilder(models or {})
    return run_campaign(
        values, build=builder, load=goals("goal one"), store=RecordingStore()
    )


def models_for(target=TARGET_REPLY, judge="yes"):
    return {"target": ScriptedModel(target), "judge": ScriptedModel(judge)}


def with_preflight(**execution):
    return campaign(
        attacks=[{"name": "baseline"}],
        execution={"preflight": True, **execution},
    )


# --- off by default -----------------------------------------------------------


def test_preflight_is_off_by_default():
    # A dead target is not pinged; the failure surfaces as an attempt error.
    result = run(
        campaign(attacks=[{"name": "baseline"}]),
        models={
            "target": ScriptedModel(lambda _m: failure("down")),
            "judge": ScriptedModel("yes"),
        },
    )
    assert result.attacks  # the run proceeded rather than raising


# --- target -------------------------------------------------------------------


def test_a_reachable_target_and_judge_pass_preflight():
    result = run(with_preflight(), models=models_for())
    assert result.attacks


def test_an_unreachable_target_stops_the_run():
    models = {
        "target": ScriptedModel(lambda _m: failure("connection refused")),
        "judge": ScriptedModel("yes"),
    }
    with pytest.raises(PreflightError, match="target error"):
        run(with_preflight(), models=models)


def test_the_target_is_not_attacked_when_preflight_fails():
    target = ScriptedModel(lambda _m: failure("down"))
    models = {"target": target, "judge": ScriptedModel("yes")}
    with pytest.raises(PreflightError):
        run(with_preflight(), models=models)
    # Only the preflight ping reached the target; no attack request followed.
    assert len(target.requests) == 1


# --- judge --------------------------------------------------------------------


def test_an_unreachable_judge_stops_the_run():
    models = {
        "target": ScriptedModel(TARGET_REPLY),
        "judge": ScriptedModel(lambda _m: failure("judge down")),
    }
    with pytest.raises(PreflightError, match="judge .* unreachable"):
        run(with_preflight(), models=models)


def test_the_error_names_every_unreachable_model():
    models = {
        "target": ScriptedModel(lambda _m: failure("t down")),
        "judge": ScriptedModel(lambda _m: failure("j down")),
    }
    with pytest.raises(PreflightError) as raised:
        run(with_preflight(), models=models)
    assert len(raised.value.failures) == 2


# --- dry run ------------------------------------------------------------------


def test_a_dry_run_skips_preflight():
    # dry_run returns before preflight, so a dead target does not raise.
    result = run(
        with_preflight(dry_run=True),
        models={
            "target": ScriptedModel(lambda _m: failure("down")),
            "judge": ScriptedModel("yes"),
        },
    )
    assert result.dry_run is True
