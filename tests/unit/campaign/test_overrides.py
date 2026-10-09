# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Endpoint overrides and server readiness for campaign files."""

from __future__ import annotations

import copy
from unittest.mock import patch

import pytest

from hackagent.orchestrator.campaign.overrides import (
    EndpointOverrides,
    ServerReadiness,
    apply_endpoint_overrides,
    campaign_models,
    wait_for_servers,
)


def _conn(endpoint, wire="OPENAI_SDK", provider="vllm"):
    return {"provider": provider, "type": wire, "endpoint": endpoint}


def _values():
    return {
        "target": {"name": "target", "connection": _conn("http://host/v1")},
        "attacks": [
            {
                "name": "pair",
                "roles": {
                    "attacker": {"name": "atk", "connection": _conn("http://atk/v1")}
                },
            }
        ],
        "evaluation": {
            "judges": [
                {"name": "shared", "connection": _conn("http://host/v1")},
                {"name": "other", "connection": _conn("http://other/v1")},
            ]
        },
        "dataset": {},
    }


def test_campaign_models_yields_target_roles_judges_and_classifier():
    values = _values()
    values["dataset"] = {
        "classifier": {"name": "cls", "connection": _conn("http://host/v1")}
    }
    kinds = [kind for kind, _ in campaign_models(values)]
    assert kinds == ["target", "role", "judge", "judge", "judge"]


def test_ollama_override_repoints_every_model():
    values = _values()
    for _, model in campaign_models(values):
        model["connection"]["type"] = "OLLAMA"
    apply_endpoint_overrides(values, EndpointOverrides(ollama="http://ollama:11434"))
    assert all(
        model["connection"]["endpoint"] == "http://ollama:11434"
        for _, model in campaign_models(values)
    )


def test_ollama_override_requires_ollama_connections():
    with pytest.raises(ValueError, match="Ollama"):
        apply_endpoint_overrides(_values(), EndpointOverrides(ollama="http://x"))


def test_openai_override_splits_target_judge_and_attacker():
    values = _values()
    apply_endpoint_overrides(
        values,
        EndpointOverrides(
            openai="http://new-target/v1",
            judge="http://new-judge/v1",
            attacker="http://new-atk/v1",
        ),
    )
    by_name = {
        m["name"]: m["connection"]["endpoint"] for _, m in campaign_models(values)
    }
    assert by_name["target"] == "http://new-target/v1"
    assert by_name["shared"] == "http://new-target/v1"  # follows the target
    assert by_name["other"] == "http://new-judge/v1"
    assert by_name["atk"] == "http://new-atk/v1"


def test_attacker_override_requires_a_role_model():
    values = _values()
    values["attacks"][0]["roles"] = {}
    with pytest.raises(ValueError, match="role model"):
        apply_endpoint_overrides(values, EndpointOverrides(attacker="http://x/v1"))


def test_ollama_and_openai_overrides_cannot_combine():
    with pytest.raises(ValueError, match="cannot be combined"):
        apply_endpoint_overrides(
            _values(), EndpointOverrides(ollama="http://o", openai="http://p")
        )


def test_wait_for_servers_requires_an_endpoint_for_local_models():
    values = _values()
    values["target"]["connection"]["endpoint"] = None
    with pytest.raises(ValueError, match="explicit endpoint"):
        wait_for_servers(values, ServerReadiness())


def test_wait_for_servers_passes_when_every_model_is_served():
    served = {"target", "atk", "shared", "other"}
    with patch(
        "hackagent.orchestrator.campaign.overrides.installed_models",
        return_value=served,
    ):
        wait_for_servers(_values(), ServerReadiness())  # no raise


def test_wait_for_servers_reports_a_missing_model():
    with patch(
        "hackagent.orchestrator.campaign.overrides.installed_models",
        return_value={"target"},
    ):
        with pytest.raises(RuntimeError, match="Missing"):
            wait_for_servers(_values(), ServerReadiness())


def test_apply_does_not_mutate_when_no_override_is_given():
    values = _values()
    before = copy.deepcopy(values)
    apply_endpoint_overrides(values, EndpointOverrides())
    assert values == before
