# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Binding the symbolic HackAgent gateway marker to a concrete endpoint."""

from __future__ import annotations

import pytest

from hackagent.core.credentials import reference_name
from hackagent.models import ModelConfig
from hackagent.orchestrator.campaign import CampaignSpec
from hackagent.orchestrator.campaign.loader import load_stored_campaign
from hackagent.orchestrator.campaign.gateway import (
    GATEWAY_KEY_ENV,
    bind_gateway,
    is_gateway,
    key_envs,
)

from .fakes import campaign, model

GW = {"name": "gateway", "connection": {"provider": "hackagent", "type": "OPENAI"}}
JUDGE_GW = {**GW, "scoring": {"type": "harmbench"}}


def _spec(**sections) -> CampaignSpec:
    return load_stored_campaign(campaign(**sections))


def test_bind_gateway_sets_endpoint_and_key_reference():
    spec = _spec(attacks=[{"name": "pair", "roles": {"attacker": GW}}])
    bound = bind_gateway(spec, "https://api.x.it/")
    c = bound.attacks[0].roles["attacker"].connection
    assert c.endpoint == "https://api.x.it/v1"
    assert reference_name(c.api_key) == GATEWAY_KEY_ENV == "HACKAGENT_GATEWAY_KEY"
    assert (
        bound.model_dump(mode="json")["attacks"][0]["roles"]["attacker"]["connection"][
            "api_key"
        ]
        == "${HACKAGENT_GATEWAY_KEY}"
    )
    assert c.provider == "hackagent"


def test_bind_gateway_keeps_path_prefix():
    spec = _spec(evaluation={"judges": [JUDGE_GW]})
    bound = bind_gateway(spec, "https://h/api")
    judge = bound.evaluation.judges[0]
    assert judge.connection.endpoint == "https://h/api/v1"
    assert judge.scoring.type == "harmbench"


def test_bind_gateway_rewrites_a_gateway_target():
    bound = bind_gateway(_spec(target=GW), "https://h")
    assert bound.target.connection.endpoint == "https://h/v1"


def test_non_gateway_models_untouched():
    target = model("target", "http://t/v1")
    target["connection"]["api_key"] = "${OPENAI_KEY}"
    spec = _spec(target=target, attacks=[{"name": "pair", "roles": {"attacker": GW}}])
    bound = bind_gateway(spec, "https://h")
    assert bound.target == spec.target
    assert bound.evaluation == spec.evaluation


def test_bind_gateway_without_gateway_returns_equal_spec():
    spec = _spec()
    assert bind_gateway(spec, "https://h") == spec


@pytest.mark.parametrize("agent_type", ["CLAUDE_CODE", "WEB", "LITELLM"])
def test_bind_gateway_refuses_a_gateway_marker_of_another_type(agent_type):
    gateway = {"name": "g", "connection": {"provider": "hackagent", "type": agent_type}}
    spec = _spec(attacks=[{"name": "pair", "roles": {"attacker": gateway}}])
    with pytest.raises(ValueError, match="OPENAI"):
        bind_gateway(spec, "https://h")


def test_is_gateway():
    assert is_gateway(ModelConfig.model_validate(GW))
    assert not is_gateway(ModelConfig.model_validate(model("m")))


def test_key_envs_excludes_gateway():
    target = model("target")
    target["connection"]["api_key"] = "${OPENAI_KEY}"
    bound = bind_gateway(
        _spec(
            target=target,
            attacks=[{"name": "pair", "roles": {"attacker": GW}}],
            evaluation={"judges": [JUDGE_GW]},
        ),
        "https://h",
    )
    assert key_envs(bound) == {"OPENAI_KEY"}
