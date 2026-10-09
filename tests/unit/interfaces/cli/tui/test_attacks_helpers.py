# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Attacks tab helpers (model + guardrail spec builders)."""

from hackagent.interfaces.tui.views.attacks.helpers import (
    build_guardrail_config,
    model_config_from_fields,
)


def test_empty_name_means_no_guardrail():
    assert build_guardrail_config("", "OLLAMA", "http://localhost:11434") is None
    assert build_guardrail_config("   ", "OLLAMA", "http://localhost:11434") is None


def test_guardrail_is_a_named_model_config():
    config = build_guardrail_config(
        " llama-guard3:8b ", "OLLAMA", " http://localhost:11434 "
    )

    assert config == {
        "name": "llama-guard3:8b",
        "connection": {
            "provider": "litellm",
            "type": "OLLAMA",
            "endpoint": "http://localhost:11434",
        },
    }


def test_name_is_a_string_not_a_bound_method():
    config = build_guardrail_config("Model", "OPENAI_SDK", "")

    assert isinstance(config["name"], str)
    assert config["name"] == "Model"
    # An empty endpoint is omitted, not stored as "".
    assert "endpoint" not in config["connection"]


def test_native_agent_type_carries_the_local_provider():
    config = model_config_from_fields("claude", "claude-code", "")

    assert config == {
        "name": "claude",
        "connection": {"provider": "local", "type": "CLAUDE_CODE"},
    }


def test_options_and_extra_ride_along():
    config = model_config_from_fields(
        "judge-m",
        "ollama",
        "",
        options={"binary": "x"},
        extra={"scoring": {"type": "harmbench"}},
    )

    assert config["options"] == {"binary": "x"}
    assert config["scoring"] == {"type": "harmbench"}
