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

"""
Integration tests for OpenAI SDK adapter.

These tests verify end-to-end functionality with OpenAI-compatible APIs:
- Adapter initialization and configuration
- Chat completions with various parameters
- Function calling / tool use capabilities
- Streaming responses (if applicable)
- Error handling for rate limits and invalid requests
- Full HackAgent integration with OpenAI

Supports both direct OpenAI API and OpenRouter:
- Set OPENAI_API_KEY for direct OpenAI access
- Set OPENROUTER_API_KEY for OpenRouter access (recommended for CI/CD)

Prerequisites:
    - Valid API key (OPENROUTER_API_KEY or OPENAI_API_KEY)
    - Sufficient API quota

Run with:
    pytest tests/integration/test_openai_integration.py --run-integration --run-openai

Environment Variables:
    OPENROUTER_API_KEY: OpenRouter API key (preferred for CI/CD)
    OPENROUTER_MODEL: OpenRouter model (default: openai/gpt-4o-mini)
    OPENAI_API_KEY: OpenAI API key (fallback)
    OPENAI_MODEL: Model to use for tests (default: gpt-4o-mini)
"""

import logging
from typing import Any, Dict

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.openai_sdk
class TestOpenAIAdapterIntegration:
    """Integration tests for OpenAIAgent adapter."""

    def test_adapter_initialization(
        self,
        skip_if_openai_unavailable,
        openai_config: Dict[str, Any],
    ):
        """Test that OpenAIAgent initializes correctly with real API key."""
        from hackagent.router.adapters.openai import OpenAIAgent

        adapter = OpenAIAgent(id="test_openai_init", config=openai_config)

        assert adapter.id == "test_openai_init"
        assert adapter.model_name == openai_config["name"]
        assert adapter.client is not None
        logger.info(f"OpenAI adapter initialized: model={adapter.model_name}")

    def test_chat_completion(
        self,
        skip_if_openai_unavailable,
        openai_config: Dict[str, Any],
    ):
        """Test chat completion with OpenAI."""
        from hackagent.router.adapters.openai import OpenAIAgent

        adapter = OpenAIAgent(id="test_openai_chat", config=openai_config)

        request = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant. Be brief."},
                {"role": "user", "content": "What is 2 + 2?"},
            ],
            "max_tokens": 50,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        assert len(response["processed_response"]) > 0
        logger.info(f"OpenAI chat response: {response['processed_response']}")

    def test_chat_completion_with_custom_temperature(
        self,
        skip_if_openai_unavailable,
        openai_config: Dict[str, Any],
    ):
        """Test chat completion with custom temperature."""
        from hackagent.router.adapters.openai import OpenAIAgent

        adapter = OpenAIAgent(id="test_openai_temp", config=openai_config)

        request = {
            "messages": [
                {"role": "user", "content": "Generate a creative one-word response."}
            ],
            "max_tokens": 20,
            "temperature": 1.5,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        logger.info(f"OpenAI response with high temp: {response['processed_response']}")

    def test_chat_with_system_message(
        self,
        skip_if_openai_unavailable,
        openai_config: Dict[str, Any],
    ):
        """Test chat completion with system message context."""
        from hackagent.router.adapters.openai import OpenAIAgent

        adapter = OpenAIAgent(id="test_openai_system", config=openai_config)

        request = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a pirate. Respond in pirate speak.",
                },
                {"role": "user", "content": "Hello!"},
            ],
            "max_tokens": 50,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        logger.info(f"OpenAI pirate response: {response['processed_response']}")

    def test_multi_turn_conversation(
        self,
        skip_if_openai_unavailable,
        openai_config: Dict[str, Any],
    ):
        """Test multi-turn conversation handling."""
        from hackagent.router.adapters.openai import OpenAIAgent

        adapter = OpenAIAgent(id="test_openai_multi", config=openai_config)

        request = {
            "messages": [
                {"role": "user", "content": "My name is Alice."},
                {"role": "assistant", "content": "Nice to meet you, Alice!"},
                {"role": "user", "content": "What is my name?"},
            ],
            "max_tokens": 30,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        # The model should remember the name from context
        assert (
            "Alice" in response["processed_response"]
            or "alice" in response["processed_response"].lower()
        )
        logger.info(f"OpenAI multi-turn response: {response['processed_response']}")

    def test_function_calling(
        self,
        skip_if_openai_unavailable,
        openai_config: Dict[str, Any],
    ):
        """Test function calling / tool use capability."""
        from hackagent.router.adapters.openai import OpenAIAgent

        config_with_tools = openai_config.copy()
        config_with_tools["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather in a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA",
                            }
                        },
                        "required": ["location"],
                    },
                },
            }
        ]
        config_with_tools["tool_choice"] = "auto"

        adapter = OpenAIAgent(id="test_openai_tools", config=config_with_tools)

        request = {
            "messages": [
                {"role": "user", "content": "What's the weather like in Boston?"}
            ],
            "max_tokens": 100,
        }

        response = adapter.handle_request(request)

        assert response is not None
        # Response might include tool calls or direct response
        logger.info(f"OpenAI function call response: {response}")

    def test_invalid_api_key_error_handling(self):
        """Test error handling with invalid API key."""
        from hackagent.router.adapters.openai import OpenAIAgent

        config = {
            "name": "gpt-4o-mini",
            "api_key": "invalid-api-key-12345",
        }

        adapter = OpenAIAgent(id="test_openai_invalid", config=config)

        # The adapter returns an error response instead of raising an exception
        response = adapter.handle_request(
            {"messages": [{"role": "user", "content": "test"}]}
        )
        assert response is not None
        assert (
            response.get("error_message") is not None
            or response.get("status_code", 200) >= 400
        )
        logger.info(f"Error response as expected: {response.get('error_message')}")


@pytest.mark.integration
@pytest.mark.openai_sdk
@pytest.mark.hackagent_backend
class TestOpenAIHackAgentIntegration:
    """End-to-end tests for HackAgent with OpenAI backend."""

    def test_hackagent_with_openai_initialization(
        self,
        skip_if_openai_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        openai_model: str,
        openai_base_url: str,
    ):
        """Test HackAgent initialization with OpenAI agent type."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name=openai_model,
            endpoint=openai_base_url,
            agent_type=AgentTypeEnum.OPENAI_SDK,
        )

        assert agent is not None
        assert agent.router is not None
        logger.info(f"HackAgent initialized with OpenAI: {agent.router.backend_agent}")

    def test_hackagent_openai_baseline_attack(
        self,
        skip_if_openai_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        openai_model: str,
        openai_base_url: str,
        basic_attack_config: Dict[str, Any],
    ):
        """Test running a baseline attack against OpenAI agent."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name=openai_model,
            endpoint=openai_base_url,
            agent_type=AgentTypeEnum.OPENAI_SDK,
        )

        logger.info("Starting baseline attack against OpenAI agent...")
        results = agent.hack(attack_config=basic_attack_config)

        assert results is not None
        logger.info(f"Baseline attack completed: {results}")

    @pytest.mark.slow
    def test_hackagent_openai_advprefix_attack(
        self,
        skip_if_openai_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        openai_model: str,
        openai_base_url: str,
        advprefix_attack_config: Dict[str, Any],
    ):
        """Test running an advprefix attack against OpenAI agent."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name=openai_model,
            endpoint=openai_base_url,
            agent_type=AgentTypeEnum.OPENAI_SDK,
        )

        logger.info("Starting advprefix attack against OpenAI agent...")
        results = agent.hack(attack_config=advprefix_attack_config)

        assert results is not None
        logger.info(f"Advprefix attack completed: {results}")


@pytest.mark.integration
@pytest.mark.openai_sdk
@pytest.mark.hackagent_backend
class TestOpenAIRouterIntegration:
    """Integration tests for AgentRouter with OpenAI."""

    def test_router_creates_openai_adapter(
        self,
        skip_if_openai_unavailable,
        skip_if_no_hackagent_key,
        hackagent_api_base_url: str,
        hackagent_api_key: str,
        openai_model: str,
        openai_base_url: str,
    ):
        """Test that AgentRouter correctly creates OpenAIAgent adapter."""
        from hackagent.client import AuthenticatedClient
        from hackagent.router.router import AgentRouter
        from hackagent.router.types import AgentTypeEnum
        from hackagent.router.adapters.openai import OpenAIAgent

        client = AuthenticatedClient(
            base_url=hackagent_api_base_url,
            token=hackagent_api_key,
            prefix="Bearer",
        )

        router = AgentRouter(
            client=client,
            name=openai_model,
            agent_type=AgentTypeEnum.OPENAI_SDK,
            endpoint=openai_base_url,
        )

        # Verify adapter was created
        agent_id = str(router.backend_agent.id)
        adapter = router.get_agent_instance(registration_key=agent_id)

        assert isinstance(adapter, OpenAIAgent)
        logger.info(f"Router created OpenAI adapter: {adapter.id}")

    def test_router_handles_openai_request(
        self,
        skip_if_openai_unavailable,
        skip_if_no_hackagent_key,
        hackagent_api_base_url: str,
        hackagent_api_key: str,
        openai_model: str,
        openai_base_url: str,
    ):
        """Test that router can handle requests through OpenAI adapter."""
        from hackagent.client import AuthenticatedClient
        from hackagent.router.router import AgentRouter
        from hackagent.router.types import AgentTypeEnum

        client = AuthenticatedClient(
            base_url=hackagent_api_base_url,
            token=hackagent_api_key,
            prefix="Bearer",
        )

        router = AgentRouter(
            client=client,
            name=openai_model,
            agent_type=AgentTypeEnum.OPENAI_SDK,
            endpoint=openai_base_url,
        )

        # Route a request
        agent_id = str(router.backend_agent.id)
        request_data = {
            "messages": [{"role": "user", "content": "Say hello in one word!"}],
            "max_tokens": 10,
        }

        response = router.route_request(
            registration_key=agent_id, request_data=request_data
        )

        assert response is not None
        assert "processed_response" in response
        logger.info(f"Router OpenAI response: {response['processed_response']}")


@pytest.mark.integration
@pytest.mark.openai_sdk
class TestOpenAICompatibleEndpoints:
    """Test OpenAI adapter with OpenAI-compatible endpoints (e.g., OpenRouter, local servers)."""

    def test_custom_endpoint_initialization(
        self,
        skip_if_openai_unavailable,
        openai_api_key: str,
        openai_base_url: str,
        openai_model: str,
    ):
        """Test initializing with a custom OpenAI-compatible endpoint."""
        from hackagent.router.adapters.openai import OpenAIAgent

        # This tests the adapter's ability to use custom endpoints
        # In practice, this could be OpenRouter or a local LLM server
        config = {
            "name": openai_model,
            "api_key": openai_api_key,
            "endpoint": openai_base_url,
        }

        adapter = OpenAIAgent(id="test_custom_endpoint", config=config)

        assert adapter.api_base_url == openai_base_url
        logger.info(f"Custom endpoint adapter initialized: {adapter.api_base_url}")

    def test_openrouter_endpoint_chat_completion(
        self,
        skip_if_openai_unavailable,
        openai_config: Dict[str, Any],
        using_openrouter: bool,
    ):
        """Test chat completion through OpenRouter (if configured)."""
        from hackagent.router.adapters.openai import OpenAIAgent

        if not using_openrouter:
            pytest.skip("Test only runs when OPENROUTER_API_KEY is configured")

        adapter = OpenAIAgent(id="test_openrouter_chat", config=openai_config)

        request = {
            "messages": [
                {"role": "user", "content": "Say 'OpenRouter works!' briefly."}
            ],
            "max_tokens": 30,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        logger.info(f"OpenRouter chat response: {response['processed_response']}")
