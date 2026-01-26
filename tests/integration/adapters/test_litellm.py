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
Integration tests for LiteLLM adapter.

These tests verify end-to-end functionality with LiteLLM's multi-provider support:
- Adapter initialization with various providers
- Chat completions through different backends (Ollama, OpenAI, etc.)
- Model identifier parsing and routing
- Error handling for unavailable providers
- Full HackAgent integration with LiteLLM

LiteLLM supports 100+ LLMs via a unified interface:
- ollama/tinyllama - Ollama local models
- openai/gpt-4 - OpenAI models
- anthropic/claude-3 - Anthropic models
- And many more...

Prerequisites:
    - At least one supported backend must be available
    - For Ollama: Ollama must be running
    - For OpenAI: OPENAI_API_KEY must be set

Run with:
    pytest tests/integration/test_litellm_integration.py --run-integration --run-litellm

Environment Variables:
    LITELLM_MODEL: Model identifier (default: ollama/tinyllama)
    OLLAMA_BASE_URL: For Ollama-backed models
    OPENAI_API_KEY: For OpenAI-backed models
"""

import logging
from typing import Any, Dict

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.litellm
class TestLiteLLMAdapterIntegration:
    """Integration tests for LiteLLMAgent adapter."""

    def test_adapter_initialization_with_ollama_model(
        self,
        skip_if_ollama_unavailable,
        ollama_base_url: str,
    ):
        """Test LiteLLM adapter initialization with Ollama model."""
        from hackagent.router.adapters.litellm import LiteLLMAgent

        config = {
            "name": "ollama/tinyllama",
            "endpoint": ollama_base_url,
            "max_new_tokens": 20,
        }

        adapter = LiteLLMAgent(id="test_litellm_ollama", config=config)

        assert adapter.id == "test_litellm_ollama"
        assert adapter.model_name == "ollama/tinyllama"
        logger.info(f"LiteLLM adapter initialized with Ollama: {adapter.model_name}")

    def test_adapter_initialization_with_openai_model(
        self,
        skip_if_openai_unavailable,
        openai_api_key: str,
    ):
        """Test LiteLLM adapter initialization with OpenAI model."""
        from hackagent.router.adapters.litellm import LiteLLMAgent

        config = {
            "name": "gpt-4o-mini",
            "api_key": openai_api_key,
            "max_new_tokens": 20,
        }

        adapter = LiteLLMAgent(id="test_litellm_openai", config=config)

        assert adapter.id == "test_litellm_openai"
        assert adapter.model_name == "gpt-4o-mini"
        logger.info(f"LiteLLM adapter initialized with OpenAI: {adapter.model_name}")

    def test_chat_completion_with_ollama(
        self,
        skip_if_ollama_unavailable,
        ollama_base_url: str,
    ):
        """Test chat completion through LiteLLM with Ollama backend."""
        from hackagent.router.adapters.litellm import LiteLLMAgent

        config = {
            "name": "ollama/tinyllama",
            "endpoint": ollama_base_url,
            "max_new_tokens": 15,
        }

        adapter = LiteLLMAgent(id="test_litellm_chat_ollama", config=config)

        request = {
            "messages": [
                {"role": "user", "content": "What is 2 + 2? Answer in one word."}
            ],
            "max_new_tokens": 20,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        logger.info(f"LiteLLM/Ollama response: {response['processed_response']}")

    def test_chat_completion_with_openai(
        self,
        skip_if_openai_unavailable,
        openai_api_key: str,
    ):
        """Test chat completion through LiteLLM with OpenAI backend."""
        from hackagent.router.adapters.litellm import LiteLLMAgent

        config = {
            "name": "gpt-4o-mini",
            "api_key": openai_api_key,
            "max_new_tokens": 15,
        }

        adapter = LiteLLMAgent(id="test_litellm_chat_openai", config=config)

        request = {
            "messages": [
                {"role": "user", "content": "What is 2 + 2? Answer in one word."}
            ],
            "max_new_tokens": 20,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        logger.info(f"LiteLLM/OpenAI response: {response['processed_response']}")

    def test_generation_with_custom_parameters(
        self,
        skip_if_litellm_unavailable,
        litellm_config: Dict[str, Any],
    ):
        """Test generation with custom temperature and parameters."""
        from hackagent.router.adapters.litellm import LiteLLMAgent

        adapter = LiteLLMAgent(id="test_litellm_params", config=litellm_config)

        request = {
            "messages": [
                {"role": "user", "content": "Generate a creative one-word response."}
            ],
            "max_new_tokens": 20,
            "temperature": 1.2,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        logger.info(
            f"LiteLLM response with custom temp: {response['processed_response']}"
        )

    def test_multi_turn_conversation(
        self,
        skip_if_litellm_unavailable,
        litellm_config: Dict[str, Any],
    ):
        """Test multi-turn conversation handling."""
        from hackagent.router.adapters.litellm import LiteLLMAgent

        adapter = LiteLLMAgent(id="test_litellm_multi", config=litellm_config)

        request = {
            "messages": [
                {"role": "user", "content": "My name is Bob."},
                {"role": "assistant", "content": "Nice to meet you, Bob!"},
                {"role": "user", "content": "What is my name?"},
            ],
            "max_new_tokens": 30,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        # Should remember context
        assert (
            "Bob" in response["processed_response"]
            or "bob" in response["processed_response"].lower()
        )
        logger.info(f"LiteLLM multi-turn response: {response['processed_response']}")

    def test_system_message_handling(
        self,
        skip_if_litellm_unavailable,
        litellm_config: Dict[str, Any],
    ):
        """Test system message handling with LiteLLM."""
        from hackagent.router.adapters.litellm import LiteLLMAgent

        adapter = LiteLLMAgent(id="test_litellm_system", config=litellm_config)

        request = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful math tutor. Be brief.",
                },
                {"role": "user", "content": "What is the square root of 16?"},
            ],
            "max_new_tokens": 30,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        logger.info(f"LiteLLM system msg response: {response['processed_response']}")


@pytest.mark.integration
@pytest.mark.litellm
class TestLiteLLMHackAgentIntegration:
    """End-to-end tests for HackAgent with LiteLLM backend."""

    def test_hackagent_with_litellm_initialization(
        self,
        skip_if_litellm_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        litellm_model: str,
        ollama_base_url: str,
    ):
        """Test HackAgent initialization with LiteLLM agent type."""
        from hackagent import AgentTypeEnum

        # Determine endpoint based on model
        endpoint = (
            ollama_base_url
            if litellm_model.startswith("ollama/")
            else "https://api.openai.com/v1"
        )

        agent = hackagent_client_factory(
            name=litellm_model,
            endpoint=endpoint,
            agent_type=AgentTypeEnum.LITELLM,
        )

        assert agent is not None
        assert agent.router is not None
        logger.info(f"HackAgent initialized with LiteLLM: {agent.router.backend_agent}")

    def test_hackagent_litellm_baseline_attack(
        self,
        skip_if_litellm_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        litellm_model: str,
        ollama_base_url: str,
        basic_attack_config: Dict[str, Any],
    ):
        """Test running a baseline attack against LiteLLM agent."""
        from hackagent import AgentTypeEnum

        endpoint = (
            ollama_base_url
            if litellm_model.startswith("ollama/")
            else "https://api.openai.com/v1"
        )

        agent = hackagent_client_factory(
            name=litellm_model,
            endpoint=endpoint,
            agent_type=AgentTypeEnum.LITELLM,
        )

        logger.info("Starting baseline attack against LiteLLM agent...")
        results = agent.hack(attack_config=basic_attack_config)

        assert results is not None
        logger.info(f"Baseline attack completed: {results}")

    @pytest.mark.slow
    def test_hackagent_litellm_advprefix_attack(
        self,
        skip_if_litellm_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        litellm_model: str,
        ollama_base_url: str,
        advprefix_attack_config: Dict[str, Any],
    ):
        """Test running an advprefix attack against LiteLLM agent."""
        from hackagent import AgentTypeEnum

        endpoint = (
            ollama_base_url
            if litellm_model.startswith("ollama/")
            else "https://api.openai.com/v1"
        )

        agent = hackagent_client_factory(
            name=litellm_model,
            endpoint=endpoint,
            agent_type=AgentTypeEnum.LITELLM,
        )

        logger.info("Starting advprefix attack against LiteLLM agent...")
        results = agent.hack(attack_config=advprefix_attack_config)

        assert results is not None
        logger.info(f"Advprefix attack completed: {results}")


@pytest.mark.integration
@pytest.mark.litellm
class TestLiteLLMRouterIntegration:
    """Integration tests for AgentRouter with LiteLLM."""

    def test_router_creates_litellm_adapter(
        self,
        skip_if_litellm_unavailable,
        skip_if_no_hackagent_key,
        hackagent_api_base_url: str,
        hackagent_api_key: str,
        litellm_model: str,
        ollama_base_url: str,
    ):
        """Test that AgentRouter correctly creates LiteLLMAgent adapter."""
        from hackagent.client import AuthenticatedClient
        from hackagent.router.router import AgentRouter
        from hackagent.router.types import AgentTypeEnum
        from hackagent.router.adapters.litellm import LiteLLMAgent

        client = AuthenticatedClient(
            base_url=hackagent_api_base_url,
            token=hackagent_api_key,
            prefix="Bearer",
        )

        endpoint = (
            ollama_base_url
            if litellm_model.startswith("ollama/")
            else "https://api.openai.com/v1"
        )

        router = AgentRouter(
            client=client,
            name=litellm_model,
            agent_type=AgentTypeEnum.LITELLM,
            endpoint=endpoint,
        )

        # Verify adapter was created
        agent_id = str(router.backend_agent.id)
        adapter = router.get_agent_instance(registration_key=agent_id)

        assert isinstance(adapter, LiteLLMAgent)
        logger.info(f"Router created LiteLLM adapter: {adapter.id}")

    def test_router_handles_litellm_request(
        self,
        skip_if_litellm_unavailable,
        skip_if_no_hackagent_key,
        hackagent_api_base_url: str,
        hackagent_api_key: str,
        litellm_model: str,
        ollama_base_url: str,
    ):
        """Test that router can handle requests through LiteLLM adapter."""
        from hackagent.client import AuthenticatedClient
        from hackagent.router.router import AgentRouter
        from hackagent.router.types import AgentTypeEnum

        client = AuthenticatedClient(
            base_url=hackagent_api_base_url,
            token=hackagent_api_key,
            prefix="Bearer",
        )

        endpoint = (
            ollama_base_url
            if litellm_model.startswith("ollama/")
            else "https://api.openai.com/v1"
        )

        router = AgentRouter(
            client=client,
            name=litellm_model,
            agent_type=AgentTypeEnum.LITELLM,
            endpoint=endpoint,
        )

        # Route a request
        agent_id = str(router.backend_agent.id)
        request_data = {
            "messages": [{"role": "user", "content": "Say hello in one word!"}],
            "max_new_tokens": 10,
        }

        response = router.route_request(
            registration_key=agent_id, request_data=request_data
        )

        assert response is not None
        assert "processed_response" in response
        logger.info(f"Router LiteLLM response: {response['processed_response']}")


@pytest.mark.integration
@pytest.mark.litellm
class TestLiteLLMProviderSwitching:
    """Test LiteLLM's ability to switch between different providers."""

    def test_switch_between_ollama_and_openai(
        self,
        skip_if_ollama_unavailable,
        skip_if_openai_unavailable,
        ollama_base_url: str,
        openai_api_key: str,
    ):
        """Test using LiteLLM to switch between Ollama and OpenAI."""
        from hackagent.router.adapters.litellm import LiteLLMAgent

        # First with Ollama
        ollama_config = {
            "name": "ollama/tinyllama",
            "endpoint": ollama_base_url,
            "max_new_tokens": 30,
        }
        ollama_adapter = LiteLLMAgent(id="test_switch_ollama", config=ollama_config)

        ollama_response = ollama_adapter.handle_request(
            {
                "messages": [{"role": "user", "content": "Say 'Ollama here' briefly."}],
            }
        )

        assert ollama_response is not None
        logger.info(f"Ollama via LiteLLM: {ollama_response['processed_response']}")

        # Then with OpenAI
        openai_config = {
            "name": "gpt-4o-mini",
            "api_key": openai_api_key,
            "max_new_tokens": 30,
        }
        openai_adapter = LiteLLMAgent(id="test_switch_openai", config=openai_config)

        openai_response = openai_adapter.handle_request(
            {
                "messages": [{"role": "user", "content": "Say 'OpenAI here' briefly."}],
            }
        )

        assert openai_response is not None
        logger.info(f"OpenAI via LiteLLM: {openai_response['processed_response']}")

    def test_model_identifier_formats(
        self,
        skip_if_ollama_unavailable,
        ollama_base_url: str,
    ):
        """Test various model identifier formats supported by LiteLLM."""
        from hackagent.router.adapters.litellm import LiteLLMAgent

        # Test different Ollama model identifier formats
        model_formats = [
            "ollama/tinyllama",
            "ollama_chat/tinyllama",  # Chat-specific endpoint
        ]

        for model_name in model_formats:
            try:
                config = {
                    "name": model_name,
                    "endpoint": ollama_base_url,
                    "max_new_tokens": 20,
                }
                adapter = LiteLLMAgent(id=f"test_format_{model_name}", config=config)

                response = adapter.handle_request(
                    {
                        "messages": [{"role": "user", "content": "Hi"}],
                    }
                )

                logger.info(
                    f"Model {model_name}: {response.get('response', 'OK')[:30]}"
                )
            except Exception as e:
                logger.warning(f"Model {model_name} failed: {e}")
