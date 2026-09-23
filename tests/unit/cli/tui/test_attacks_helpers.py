# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the Attacks tab helpers (guardrail config, env overrides)."""

import os

from hackagent.cli.tui.views.attacks.helpers import build_guardrail_config


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


def test_env_overrides_restore_user_values(monkeypatch):
    from hackagent.cli.tui.views.attacks.helpers import (
        apply_env_overrides,
        restore_env,
    )

    monkeypatch.setenv("NO_COLOR", "yes-please")
    monkeypatch.delenv("FORCE_COLOR", raising=False)

    saved = apply_env_overrides({"NO_COLOR": "1", "FORCE_COLOR": "0"})
    assert os.environ["NO_COLOR"] == "1"
    assert os.environ["FORCE_COLOR"] == "0"

    restore_env(saved)
    restore_env(saved)  # idempotent: both finally blocks restore

    assert os.environ["NO_COLOR"] == "yes-please"
    assert "FORCE_COLOR" not in os.environ
