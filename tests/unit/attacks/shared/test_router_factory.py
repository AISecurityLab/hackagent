# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
    return client


@pytest.fixture
def basic_config():
    return {
        "identifier": "test-model",
        "endpoint": "https://api.example.com/v1",
        "agent_type": "OPENAI_SDK",
        "max_new_tokens": 500,
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
