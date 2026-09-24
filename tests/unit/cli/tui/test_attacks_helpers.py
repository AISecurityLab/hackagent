# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Attacks tab helpers (guardrail config)."""

from hackagent.interfaces.tui.views.attacks.helpers import build_guardrail_config


def test_empty_name_means_no_guardrail():
    assert build_guardrail_config("", "OLLAMA", "http://localhost:11434") is None
    assert build_guardrail_config("   ", "OLLAMA", "http://localhost:11434") is None


def test_identifier_is_the_name_verbatim():
    config = build_guardrail_config(
        " llama-guard3:8b ", "OLLAMA", " http://localhost:11434 "
    )

    assert config == {
        "identifier": "llama-guard3:8b",
        "agent_type": "OLLAMA",
        "endpoint": "http://localhost:11434",
    }


def test_identifier_is_a_string_not_a_bound_method():
    config = build_guardrail_config("Model", "OPENAI_SDK", "")

    assert isinstance(config["identifier"], str)
    assert config["identifier"] == "Model"

