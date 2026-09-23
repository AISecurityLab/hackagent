# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the shared CLI-agent base (``models/adapters/cli_agent.py``)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from hackagent.models.adapters.base import AdapterConfigurationError
from hackagent.models.adapters.cli_agent import SubprocessCLIAgent, last_user_text


def _response(text):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
    )


class _FakeLiteLLM:
    def __init__(self, completion=None):
        self.custom_provider_map = []
        self._custom_providers = []
        self.completion = completion or MagicMock(return_value=_response("hello"))


class _EchoCLI(SubprocessCLIAgent):
    ADAPTER_TYPE = "EchoCLIAgent"
    LABEL = "Echo"
    PROVIDER_PREFIX = "hackagent_echo"
    DEFAULT_BINARY = "echo-cli"
    INSTALL_HINT = "Install echo-cli"

    def _configure(self, config):
        self.flavour = config.get("flavour", "plain")

    def _build_handler(self):
        return SimpleNamespace(flavour=self.flavour, timeout=self.timeout)


def _make(config=None, litellm=None, binary="/usr/bin/echo-cli"):
    litellm = litellm or _FakeLiteLLM()
    with (
        patch(
            "hackagent.models.adapters.cli_agent.get_litellm",
            return_value=(litellm, True),
        ),
        patch("hackagent.models.adapters.cli_agent.shutil.which", return_value=binary),
    ):
        agent = _EchoCLI("a1", {"name": "m", **(config or {})})
    return agent, litellm


def test_requires_model_name():
    with pytest.raises(AdapterConfigurationError, match="'name'"):
        _EchoCLI("a1", {})


def test_missing_binary_names_the_install_hint():
    with pytest.raises(AdapterConfigurationError, match="Install echo-cli"):
        _make(binary=None)


def test_registers_one_custom_provider_per_instance():
    agent, litellm = _make({"flavour": "spicy", "timeout": 5})

    assert agent.litellm_model == "hackagent_echo_a1/m"
    assert litellm._custom_providers == ["hackagent_echo_a1"]
    [entry] = litellm.custom_provider_map
    assert entry["provider"] == "hackagent_echo_a1"
    assert entry["custom_handler"].flavour == "spicy"
    assert entry["custom_handler"].timeout == 5


def test_handle_request_wraps_the_cli_reply():
    agent, litellm = _make()

    with patch(
        "hackagent.models.adapters.cli_agent.get_litellm", return_value=(litellm, True)
    ):
        envelope = agent.handle_request({"prompt": "hi"})

    assert envelope["processed_response"] == "hello"
    assert envelope["error_message"] is None
    litellm.completion.assert_called_once_with(
        model="hackagent_echo_a1/m", messages=[{"role": "user", "content": "hi"}]
    )


def test_handle_request_turns_failures_into_error_envelopes():
    agent, litellm = _make(
        litellm=_FakeLiteLLM(completion=MagicMock(side_effect=RuntimeError("boom")))
    )

    with patch(
        "hackagent.models.adapters.cli_agent.get_litellm", return_value=(litellm, True)
    ):
        envelope = agent.handle_request({"prompt": "hi"})

    assert "boom" in envelope["error_message"]
    assert envelope["processed_response"] is None


def test_last_user_text_picks_the_last_user_turn():
    messages = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "ack"},
        {"role": "user", "content": [{"type": "text", "text": "second"}]},
    ]
    assert last_user_text(messages) == "second"
    assert last_user_text([{"role": "system", "content": "x"}]) is None


def test_codex_falls_back_to_the_direct_handler():
    from hackagent.models.adapters.codex import CodexAgent

    agent = CodexAgent.__new__(CodexAgent)
    agent.id = "c1"
    agent.litellm_model = "hackagent_codex_c1/m"
    agent.actual_api_key = "not-required"
    agent.logger = MagicMock()
    agent._custom_handler = MagicMock()
    agent._custom_handler.completion.return_value = _response("direct")
    litellm = SimpleNamespace(completion=MagicMock(side_effect=ValueError("routed")))

    result = agent._complete(litellm, [{"role": "user", "content": "hi"}])

    assert result.choices[0].message.content == "direct"
    litellm.completion.assert_called_once()
    agent._custom_handler.completion.assert_called_once_with(
        model="hackagent_codex_c1/m", messages=[{"role": "user", "content": "hi"}]
    )
