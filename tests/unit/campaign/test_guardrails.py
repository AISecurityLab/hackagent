# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A campaign can defend its target with before/after guardrail classifiers.

The classifiers are scripted models that return the content-safety JSON the
guardrail parses, so a block is deterministic with no real model.
"""

from __future__ import annotations

import json

from hackagent.orchestrator.campaign import run_campaign, summary

from .fakes import FakeBuilder, ScriptedModel, campaign, goals, model

TARGET_REPLY = "a reply the judge will read"
SAFE = json.dumps({"safe": True})
UNSAFE = json.dumps({"safe": False, "categories": ["harm"], "reasoning": "nope"})


def run(values, *, models=None, texts=("goal one",)):
    from tests.fakes import RecordingStore

    builder = FakeBuilder(models or {})
    result = run_campaign(
        values, build=builder, load=goals(*texts), store=RecordingStore()
    )
    return result, builder


def guarded_campaign(before=None, after=None):
    section = {}
    if before is not None:
        section["before"] = {
            **model("guard-before", "http://g1/v1"),
            "system_prompt": "x",
        }
    if after is not None:
        section["after"] = {**model("guard-after", "http://g2/v1")}
    return campaign(attacks=[{"name": "baseline"}], guardrails=section)


def models_for(target=TARGET_REPLY, judge="yes", **classifiers):
    scripted = {"target": ScriptedModel(target), "judge": ScriptedModel(judge)}
    scripted.update({name: ScriptedModel(reply) for name, reply in classifiers.items()})
    return scripted


def attempts(result):
    return [a for o in result.attacks for a in o.attempts]


# --- the schema ---------------------------------------------------------------


def test_a_campaign_without_guardrails_is_undefended():
    result, builder = run(campaign(), models=models_for())
    [attempt] = attempts(result)
    assert attempt.verdict.success is True
    # Only the target and judge were built; no classifier.
    assert set(builder.models) == {"target", "judge"}


# --- before guardrail ---------------------------------------------------------


def test_a_before_guardrail_blocks_the_prompt_before_the_target():
    models = models_for(**{"guard-before": UNSAFE})
    result, _builder = run(guarded_campaign(before=True), models=models)

    [attempt] = attempts(result)
    assert attempt.error == "blocked by before guardrail"
    assert attempt.verdict is None
    # The prompt never reached the target.
    assert models["target"].requests == []


def test_a_before_guardrail_that_passes_lets_the_attack_through():
    models = models_for(**{"guard-before": SAFE})
    result, _builder = run(guarded_campaign(before=True), models=models)

    [attempt] = attempts(result)
    assert attempt.verdict.success is True
    assert models["target"].requests  # the target was reached


# --- after guardrail ----------------------------------------------------------


def test_an_after_guardrail_withholds_an_unsafe_reply():
    models = models_for(**{"guard-after": UNSAFE})
    result, _builder = run(guarded_campaign(after=True), models=models)

    [attempt] = attempts(result)
    assert attempt.error == "blocked by after guardrail"
    # The target was queried, but its reply was withheld.
    assert models["target"].requests
    assert attempt.verdict is None


def test_an_after_guardrail_that_passes_judges_the_reply():
    models = models_for(**{"guard-after": SAFE})
    result, _builder = run(guarded_campaign(after=True), models=models)

    [attempt] = attempts(result)
    assert attempt.verdict.success is True
    assert attempt.decoded == TARGET_REPLY


# --- fail open ----------------------------------------------------------------


def test_a_guardrail_that_returns_nothing_fails_open():
    # An empty classifier reply is treated as safe, so the attack proceeds.
    models = models_for(**{"guard-before": ""})
    result, _builder = run(guarded_campaign(before=True), models=models)

    [attempt] = attempts(result)
    assert attempt.verdict is not None
    assert models["target"].requests


# --- both sides ---------------------------------------------------------------


def test_both_guardrails_are_built_and_the_before_runs_first():
    models = models_for(**{"guard-before": UNSAFE, "guard-after": SAFE})
    result, builder = run(guarded_campaign(before=True, after=True), models=models)

    [attempt] = attempts(result)
    # Blocked before, so neither the target nor the after-guardrail ran.
    assert attempt.error == "blocked by before guardrail"
    assert models["target"].requests == []
    assert models["guard-after"].requests == []
    assert "guard-before" in builder.models and "guard-after" in builder.models


def test_the_block_is_reported_as_a_defence_not_a_failure(result=None):
    models = models_for(**{"guard-before": UNSAFE})
    result, _builder = run(guarded_campaign(before=True), models=models)

    assert summary(result)["attempt_errors"] >= 1
