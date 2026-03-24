# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for shared router_factory module."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from hackagent.attacks.shared.router_factory import create_router


@pytest.fixture
def logger():
    return logging.getLogger("test.router_factory")


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.token = "test-token-123"
    client.get_api_key.return_value = "test-token-123"
    return client


@pytest.fixture
def basic_config():
    return {
        "identifier": "test-model",
        "endpoint": "https://api.example.com/v1",
        "agent_type": "OPENAI_SDK",
        "max_tokens": 500,
        "temperature": 0.7,
        "agent_metadata": {},
    }


class TestCreateRouter:
    """Tests for the create_router factory function."""

    @patch("hackagent.attacks.shared.router_factory.AgentRouter")
    def test_creates_router_successfully(
        self, MockRouter, mock_client, basic_config, logger
    ):
        """Router is created and registration key is returned."""
        # Mock agent_registry
        mock_instance = MagicMock()
        mock_instance._agent_registry = {"key-1": MagicMock()}
        MockRouter.return_value = mock_instance

        router, reg_key = create_router(
            mock_client, basic_config, logger, "test-router"
        )

        assert router is mock_instance
        assert reg_key == "key-1"
        MockRouter.assert_called_once()

    @patch("hackagent.attacks.shared.router_factory.AgentRouter")
    def test_raises_on_empty_registry(
        self, MockRouter, mock_client, basic_config, logger
    ):
        """Raises RuntimeError if no agent is registered."""
        mock_instance = MagicMock()
        mock_instance._agent_registry = {}
        MockRouter.return_value = mock_instance

        with pytest.raises(RuntimeError, match="no agent was registered"):
            create_router(mock_client, basic_config, logger, "test-router")

    @patch("hackagent.attacks.shared.router_factory.AgentRouter")
    def test_uses_client_token_as_default_api_key(
        self, MockRouter, mock_client, basic_config, logger
    ):
        """Client token is used as API key when not overridden."""
        mock_instance = MagicMock()
        mock_instance._agent_registry = {"key-1": MagicMock()}
        MockRouter.return_value = mock_instance

        create_router(mock_client, basic_config, logger, "test-router")

        call_kwargs = MockRouter.call_args[1]
        assert call_kwargs["adapter_operational_config"]["api_key"] == "test-token-123"

    @patch("hackagent.attacks.shared.router_factory.AgentRouter")
    def test_api_key_override_from_metadata(
        self, MockRouter, mock_client, basic_config, logger
    ):
        """API key from agent_metadata overrides client token."""
        basic_config["agent_metadata"] = {"api_key": "override-key"}
        mock_instance = MagicMock()
        mock_instance._agent_registry = {"key-1": MagicMock()}
        MockRouter.return_value = mock_instance

        create_router(mock_client, basic_config, logger, "test-router")

        call_kwargs = MockRouter.call_args[1]
        assert call_kwargs["adapter_operational_config"]["api_key"] == "override-key"

    @patch("hackagent.attacks.shared.router_factory.AgentRouter")
    def test_env_var_api_key(self, MockRouter, mock_client, basic_config, logger):
        """API key env var name is resolved from environment."""
        basic_config["agent_metadata"] = {"api_key": "MY_API_KEY_VAR"}
        mock_instance = MagicMock()
        mock_instance._agent_registry = {"key-1": MagicMock()}
        MockRouter.return_value = mock_instance

        with patch.dict("os.environ", {"MY_API_KEY_VAR": "env-value-123"}):
            create_router(mock_client, basic_config, logger, "test-router")

        call_kwargs = MockRouter.call_args[1]
        assert call_kwargs["adapter_operational_config"]["api_key"] == "env-value-123"

    @patch("hackagent.attacks.shared.router_factory.AgentRouter")
    def test_invalid_agent_type_defaults_to_openai_sdk(
        self, MockRouter, mock_client, basic_config, logger
    ):
        """Invalid agent_type falls back to OPENAI_SDK."""
        basic_config["agent_type"] = "INVALID_TYPE"
        mock_instance = MagicMock()
        mock_instance._agent_registry = {"key-1": MagicMock()}
        MockRouter.return_value = mock_instance

        create_router(mock_client, basic_config, logger, "test-router")

        # Should have been called without error
        assert MockRouter.called

    @patch("hackagent.attacks.shared.router_factory.AgentRouter")
    def test_metadata_merged_into_operational_config(
        self, MockRouter, mock_client, basic_config, logger
    ):
        """Extra metadata fields are merged into operational config."""
        basic_config["agent_metadata"] = {"custom_param": "value123"}
        mock_instance = MagicMock()
        mock_instance._agent_registry = {"key-1": MagicMock()}
        MockRouter.return_value = mock_instance

        create_router(mock_client, basic_config, logger, "test-router")

        call_kwargs = MockRouter.call_args[1]
        assert call_kwargs["adapter_operational_config"]["custom_param"] == "value123"

    @patch("hackagent.attacks.shared.router_factory.AgentRouter")
    def test_hackagent_endpoints_do_not_disable_reasoning_by_default(
        self, MockRouter, mock_client, logger
    ):
        """HackAgent-style routers do not inject provider-specific reasoning overrides."""
        mock_instance = MagicMock()
        mock_instance._agent_registry = {"key-1": MagicMock()}
        MockRouter.return_value = mock_instance

        create_router(
            mock_client,
            {
                "identifier": "hackagent-judge",
                "endpoint": "https://api.hackagent.dev/v1",
                "agent_type": "OPENAI_SDK",
            },
            logger,
            "test-router",
        )

        call_kwargs = MockRouter.call_args[1]
        assert "extra_body" not in call_kwargs["adapter_operational_config"]

    @patch("hackagent.attacks.shared.router_factory.AgentRouter")
    def test_openrouter_endpoint_does_not_trigger_reasoning_default(
        self, MockRouter, mock_client, logger
    ):
        """OpenRouter endpoints alone should not opt into the shared default."""
        mock_instance = MagicMock()
        mock_instance._agent_registry = {"key-1": MagicMock()}
        MockRouter.return_value = mock_instance

        create_router(
            mock_client,
            {
                "identifier": "gpt-4-judge",
                "endpoint": "https://openrouter.ai/api/v1",
                "agent_type": "OPENAI_SDK",
            },
            logger,
            "test-router",
        )

        call_kwargs = MockRouter.call_args[1]
        assert "extra_body" not in call_kwargs["adapter_operational_config"]

    @patch("hackagent.attacks.shared.router_factory.AgentRouter")
    def test_top_level_extra_body_is_preserved(
        self, MockRouter, mock_client, basic_config, logger
    ):
        """Explicit extra_body config is forwarded unchanged."""
        mock_instance = MagicMock()
        mock_instance._agent_registry = {"key-1": MagicMock()}
        MockRouter.return_value = mock_instance
        basic_config["identifier"] = "hackagent-attacker"
        basic_config["endpoint"] = "https://api.hackagent.dev/v1"
        basic_config["extra_body"] = {"reasoning": {"enabled": True}}

        create_router(mock_client, basic_config, logger, "test-router")

        call_kwargs = MockRouter.call_args[1]
        assert call_kwargs["adapter_operational_config"]["extra_body"] == {
            "reasoning": {"enabled": True}
        }

    @patch("hackagent.attacks.shared.router_factory.AgentRouter")
    def test_openai_request_options_are_passed_through(
        self, MockRouter, mock_client, basic_config, logger
    ):
        """Supported OpenAI-style request fields are forwarded to the adapter."""
        mock_instance = MagicMock()
        mock_instance._agent_registry = {"key-1": MagicMock()}
        MockRouter.return_value = mock_instance
        basic_config.update(
            {
                "reasoning_effort": "minimal",
                "frequency_penalty": 0.2,
                "presence_penalty": 0.1,
                "seed": 42,
                "stop": ["END"],
                "response_format": {"type": "json_object"},
                "logit_bias": {"123": -100},
            }
        )

        create_router(mock_client, basic_config, logger, "test-router")

        call_kwargs = MockRouter.call_args[1]
        operational_config = call_kwargs["adapter_operational_config"]
        assert operational_config["reasoning_effort"] == "minimal"
        assert operational_config["frequency_penalty"] == 0.2
        assert operational_config["presence_penalty"] == 0.1
        assert operational_config["seed"] == 42
        assert operational_config["stop"] == ["END"]
        assert operational_config["response_format"] == {"type": "json_object"}
        assert operational_config["logit_bias"] == {"123": -100}
