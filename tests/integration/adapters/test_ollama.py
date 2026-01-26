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
Integration tests for Ollama adapter.

These tests verify end-to-end functionality with a real Ollama instance:
- Adapter initialization and configuration
- Text generation via the generate endpoint
- Chat completions via the chat endpoint
- Model information retrieval
- Error handling for unavailable models
- Full HackAgent integration with Ollama

Prerequisites:
    - Ollama must be running (default: http://localhost:11434)
    - At least one model must be available (default: tinyllama)

Run with:
    pytest tests/integration/test_ollama_integration.py --run-integration --run-ollama

Environment Variables:
    OLLAMA_BASE_URL: Ollama API base URL (default: http://localhost:11434)
    OLLAMA_MODEL: Model to use for tests (default: tinyllama)
"""

import logging
from typing import Any, Dict

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.ollama
class TestOllamaAdapterIntegration:
    """Integration tests for OllamaAgent adapter."""

    def test_adapter_initialization(
        self,
        skip_if_ollama_unavailable,
        ollama_config: Dict[str, Any],
    ):
        """Test that OllamaAgent initializes correctly with real endpoint."""
        from hackagent.router.adapters.ollama import OllamaAgent

        adapter = OllamaAgent(id="test_ollama_init", config=ollama_config)

        assert adapter.id == "test_ollama_init"
        assert adapter.model_name == ollama_config["name"]
        assert adapter.api_base_url is not None
        logger.info(f"Ollama adapter initialized: model={adapter.model_name}")

    def test_list_available_models(
        self,
        skip_if_ollama_unavailable,
        ollama_config: Dict[str, Any],
    ):
        """Test listing available models from Ollama."""
        from hackagent.router.adapters.ollama import OllamaAgent

        adapter = OllamaAgent(id="test_ollama_models", config=ollama_config)
        models = adapter.list_models()

        assert models is not None
        assert isinstance(models, list)
        logger.info(f"Available Ollama models: {[m.get('name') for m in models]}")

    def test_generate_completion(
        self,
        skip_if_ollama_unavailable,
        ollama_config: Dict[str, Any],
    ):
        """Test generating text completion with Ollama."""
        from hackagent.router.adapters.ollama import OllamaAgent

        adapter = OllamaAgent(id="test_ollama_generate", config=ollama_config)

        request = {
            "prompt": "What is 2 + 2? Answer briefly.",
            "max_new_tokens": 15,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        assert len(response["processed_response"]) > 0
        logger.info(f"Ollama generate response: {response['processed_response'][:100]}")

    def test_chat_completion(
        self,
        skip_if_ollama_unavailable,
        ollama_config: Dict[str, Any],
    ):
        """Test chat completion with Ollama."""
        from hackagent.router.adapters.ollama import OllamaAgent

        adapter = OllamaAgent(id="test_ollama_chat", config=ollama_config)

        request = {
            "messages": [
                {"role": "user", "content": "Hello, how are you? Answer briefly."}
            ],
            "max_new_tokens": 15,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        assert len(response["processed_response"]) > 0
        logger.info(f"Ollama chat response: {response['processed_response'][:100]}")

    def test_generation_with_custom_parameters(
        self,
        skip_if_ollama_unavailable,
        ollama_config: Dict[str, Any],
    ):
        """Test generation with custom temperature and other parameters."""
        from hackagent.router.adapters.ollama import OllamaAgent

        adapter = OllamaAgent(id="test_ollama_params", config=ollama_config)

        request = {
            "prompt": "Generate a random word.",
            "max_new_tokens": 20,
            "temperature": 1.5,  # Higher temperature for more randomness
            "top_p": 0.9,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        logger.info(
            f"Ollama response with custom params: {response['processed_response']}"
        )

    def test_get_model_info(
        self,
        skip_if_ollama_unavailable,
        ollama_config: Dict[str, Any],
    ):
        """Test retrieving model information from Ollama."""
        from hackagent.router.adapters.ollama import OllamaAgent

        adapter = OllamaAgent(id="test_ollama_info", config=ollama_config)

        try:
            model_info = adapter.get_model_info()
            assert model_info is not None
            logger.info(f"Model info: {model_info}")
        except Exception as e:
            # Model info may not be available for all models
            logger.warning(f"Could not get model info: {e}")

    def test_invalid_model_error_handling(
        self,
        skip_if_ollama_unavailable,
        ollama_base_url: str,
    ):
        """Test error handling when using a non-existent model."""
        from hackagent.router.adapters.ollama import OllamaAgent

        config = {
            "name": "nonexistent_model_xyz_12345",
            "endpoint": ollama_base_url,
        }

        adapter = OllamaAgent(id="test_ollama_invalid", config=config)

        # The adapter returns an error response instead of raising an exception
        response = adapter.handle_request({"prompt": "test"})
        assert response is not None
        assert (
            response.get("error_message") is not None
            or response.get("status_code", 200) >= 400
        )
        logger.info(f"Error response as expected: {response.get('error_message')}")


@pytest.mark.integration
@pytest.mark.ollama
class TestOllamaHackAgentIntegration:
    """End-to-end tests for HackAgent with Ollama backend."""

    def test_hackagent_with_ollama_initialization(
        self,
        skip_if_ollama_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        ollama_base_url: str,
        ollama_model: str,
    ):
        """Test HackAgent initialization with Ollama agent type."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name=ollama_model,
            endpoint=ollama_base_url,
            agent_type=AgentTypeEnum.OLLAMA,
        )

        assert agent is not None
        assert agent.router is not None
        logger.info(f"HackAgent initialized with Ollama: {agent.router.backend_agent}")

    def test_hackagent_ollama_baseline_attack(
        self,
        skip_if_ollama_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        ollama_base_url: str,
        ollama_model: str,
        basic_attack_config: Dict[str, Any],
    ):
        """Test running a baseline attack against Ollama agent."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name=ollama_model,
            endpoint=ollama_base_url,
            agent_type=AgentTypeEnum.OLLAMA,
        )

        logger.info("Starting baseline attack against Ollama agent...")
        results = agent.hack(attack_config=basic_attack_config)

        assert results is not None
        logger.info(f"Baseline attack completed: {results}")

    @pytest.mark.slow
    def test_hackagent_ollama_advprefix_attack(
        self,
        skip_if_ollama_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        ollama_base_url: str,
        ollama_model: str,
        advprefix_attack_config: Dict[str, Any],
    ):
        """Test running an advprefix attack against Ollama agent."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name=ollama_model,
            endpoint=ollama_base_url,
            agent_type=AgentTypeEnum.OLLAMA,
        )

        logger.info("Starting advprefix attack against Ollama agent...")
        results = agent.hack(attack_config=advprefix_attack_config)

        assert results is not None
        logger.info(f"Advprefix attack completed: {results}")


@pytest.mark.integration
@pytest.mark.ollama
class TestOllamaRouterIntegration:
    """Integration tests for AgentRouter with Ollama."""

    def test_router_creates_ollama_adapter(
        self,
        skip_if_ollama_unavailable,
        skip_if_no_hackagent_key,
        hackagent_api_base_url: str,
        hackagent_api_key: str,
        ollama_base_url: str,
        ollama_model: str,
    ):
        """Test that AgentRouter correctly creates OllamaAgent adapter."""
        from hackagent.client import AuthenticatedClient
        from hackagent.router.router import AgentRouter
        from hackagent.router.types import AgentTypeEnum
        from hackagent.router.adapters.ollama import OllamaAgent

        client = AuthenticatedClient(
            base_url=hackagent_api_base_url,
            token=hackagent_api_key,
            prefix="Bearer",
        )

        router = AgentRouter(
            client=client,
            name=ollama_model,
            agent_type=AgentTypeEnum.OLLAMA,
            endpoint=ollama_base_url,
        )

        # Verify adapter was created
        agent_id = str(router.backend_agent.id)
        adapter = router.get_agent_instance(registration_key=agent_id)

        assert isinstance(adapter, OllamaAgent)
        logger.info(f"Router created Ollama adapter: {adapter.id}")

    def test_router_handles_ollama_request(
        self,
        skip_if_ollama_unavailable,
        skip_if_no_hackagent_key,
        hackagent_api_base_url: str,
        hackagent_api_key: str,
        ollama_base_url: str,
        ollama_model: str,
    ):
        """Test that router can handle requests through Ollama adapter."""
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
            name=ollama_model,
            agent_type=AgentTypeEnum.OLLAMA,
            endpoint=ollama_base_url,
        )

        # Route a request
        agent_id = str(router.backend_agent.id)
        request_data = {
            "prompt": "Say hello!",
            "max_new_tokens": 20,
        }

        response = router.route_request(
            registration_key=agent_id, request_data=request_data
        )

        assert response is not None
        assert "processed_response" in response
        logger.info(f"Router Ollama response: {response['processed_response'][:50]}")
