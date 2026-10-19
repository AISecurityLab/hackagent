# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the shared CLI backend base (``models/completions/cli.py``)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.models.completions.cli import (
    CLIConfigurationError,
    SubprocessCLIModel,
    last_user_text,
)


def _response(text):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
    )


class _FakeLiteLLM:
    def __init__(self, completion=None):
        self.custom_provider_map = []
        self._custom_providers = []
        self.completion = completion or MagicMock(return_value=_response("hello"))


class _EchoCLI(SubprocessCLIModel):
    LABEL = "Echo"
    PROVIDER_PREFIX = "hackagent_echo"
    DEFAULT_BINARY = "echo-cli"
    INSTALL_HINT = "Install echo-cli"

    def _configure(self, config):
        self.flavour = config.get("flavour", "plain")

    def _build_handler(self):
        return SimpleNamespace(flavour=self.flavour, timeout=self.timeout)


def _spec(**config):
    timeout = config.pop("timeout", None)
    name = config.pop("name", "m")
    return ModelSpec(
        identifier=name,
        agent_type=AgentType.CLAUDE_CODE,
        timeout=timeout,
        extra=dict(config),
    )


def _make(config=None, litellm=None, binary="/usr/bin/echo-cli"):
    litellm = litellm or _FakeLiteLLM()
    with (
        patch("hackagent.models.completions.cli._litellm", return_value=litellm),
        patch("hackagent.models.completions.cli.shutil.which", return_value=binary),
    ):
        model = _EchoCLI(_spec(**(config or {})))
    return model, litellm


def test_requires_model_name():
    with pytest.raises(CLIConfigurationError, match="'name'"):
        _EchoCLI(ModelSpec(identifier="", agent_type=AgentType.CLAUDE_CODE))


def test_missing_binary_names_the_install_hint():
    with pytest.raises(CLIConfigurationError, match="Install echo-cli"):
        _make(binary=None)


def test_registers_one_custom_provider_per_instance():
    model, litellm = _make({"flavour": "spicy", "timeout": 5})

    provider = model._provider_name
    assert model.litellm_model == f"{provider}/m"
    assert provider.startswith("hackagent_echo_")
    assert litellm._custom_providers == [provider]
    [entry] = litellm.custom_provider_map
    assert entry["provider"] == provider
    assert entry["custom_handler"].flavour == "spicy"
    assert entry["custom_handler"].timeout == 5


def test_complete_wraps_the_cli_reply():
    model, litellm = _make()

    with patch("hackagent.models.completions.cli._litellm", return_value=litellm):
        response = model.complete([{"role": "user", "content": "hi"}])

    assert response.text == "hello"
    assert response.error is None
    litellm.completion.assert_called_once_with(
        model=model.litellm_model, messages=[{"role": "user", "content": "hi"}]
    )


def test_complete_turns_failures_into_error_responses():
    model, litellm = _make(
        litellm=_FakeLiteLLM(completion=MagicMock(side_effect=RuntimeError("boom")))
    )

    with patch("hackagent.models.completions.cli._litellm", return_value=litellm):
        response = model.complete([{"role": "user", "content": "hi"}])

    assert response.error is not None
    assert "boom" in response.error.message
    assert response.text == ""


def test_last_user_text_picks_the_last_user_turn():
    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "ack"},
        {"role": "user", "content": [{"type": "text", "text": "second"}]},
    ]
    assert last_user_text(messages) == "second"
    assert last_user_text([{"role": "system", "content": "x"}]) is None


def test_codex_falls_back_to_the_direct_handler():
    from hackagent.models.completions.codex import CodexModel

    model = CodexModel.__new__(CodexModel)
    model.id = "c1"
    model.litellm_model = "hackagent_codex_c1/m"
    model.actual_api_key = "not-required"
    model.logger = MagicMock()
    model._custom_handler = MagicMock()
    model._custom_handler.completion.return_value = _response("direct")
    litellm = SimpleNamespace(completion=MagicMock(side_effect=ValueError("routed")))

    result = model._call(litellm, [{"role": "user", "content": "hi"}])

    assert result.choices[0].message.content == "direct"
    litellm.completion.assert_called_once()
    model._custom_handler.completion.assert_called_once_with(
        model="hackagent_codex_c1/m", messages=[{"role": "user", "content": "hi"}]
    )
