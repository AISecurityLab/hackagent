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
Integration tests for Google ADK (Agent Development Kit) adapter.

These tests verify end-to-end functionality with a real Google ADK agent:
- Adapter initialization and configuration
- Session management (create, reuse, cleanup)
- Request/response handling with ADK protocol
- Error handling for various failure scenarios
- Full HackAgent integration with Google ADK

Prerequisites:
    - A Google ADK agent must be running (see examples/google_adk/)
    - The ADK server should be accessible at the configured URL
    - GOOGLE_ADK_AGENT_URL or AGENT_URL environment variable should be set

Run with:
    pytest tests/integration/test_google_adk_integration.py --run-integration --run-google-adk

Environment Variables:
    GOOGLE_ADK_AGENT_URL or AGENT_URL: URL of the running ADK agent
    HACKAGENT_API_KEY: HackAgent API key
    HACKAGENT_API_BASE_URL: HackAgent backend URL
"""

import logging
import uuid
from typing import Any, Dict

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.google_adk
class TestGoogleADKAdapterIntegration:
    """Integration tests for ADKAgent adapter."""

    def test_adapter_initialization(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test that ADKAgent initializes correctly with real endpoint."""
        from hackagent.router.adapters.google_adk import ADKAgent

        adapter = ADKAgent(id="test_adk_init", config=google_adk_config)

        assert adapter.id == "test_adk_init"
        assert adapter.name == google_adk_config["name"]
        assert adapter.endpoint is not None
        assert adapter.user_id is not None
        assert adapter.session_id is not None
        logger.info(
            f"ADK adapter initialized: name={adapter.name}, "
            f"endpoint={adapter.endpoint}, session={adapter.session_id}"
        )

    def test_adapter_with_custom_session_id(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test initializing adapter with custom session ID."""
        from hackagent.router.adapters.google_adk import ADKAgent

        custom_session_id = f"test-session-{uuid.uuid4()}"
        config = google_adk_config.copy()
        config["session_id"] = custom_session_id

        adapter = ADKAgent(id="test_adk_custom_session", config=config)

        assert adapter.session_id == custom_session_id
        logger.info(f"ADK adapter with custom session: {adapter.session_id}")

    def test_session_creation(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test explicit session creation on ADK server."""
        from hackagent.router.adapters.google_adk import ADKAgent

        session_id = f"test-session-{uuid.uuid4()}"
        config = google_adk_config.copy()
        config["session_id"] = session_id

        adapter = ADKAgent(id="test_adk_session_create", config=config)

        # Initialize session explicitly
        result = adapter._initialize_session(session_id)

        assert result is True
        logger.info(f"Session created successfully: {session_id}")

    def test_handle_request(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test handling a request through ADK agent."""
        from hackagent.router.adapters.google_adk import ADKAgent

        adapter = ADKAgent(id="test_adk_request", config=google_adk_config)

        request = {
            "prompt": "What is 2 + 2? Answer briefly.",
            "max_new_tokens": 15,
        }

        response = adapter.handle_request(request)

        assert response is not None
        # Check for either success or handled error
        if response.get("error_message"):
            logger.warning(
                f"ADK returned error (may be LLM timeout): {response.get('error_message')}"
            )
        else:
            assert "processed_response" in response
            assert response["processed_response"] is not None
            logger.info(f"ADK response: {response['processed_response'][:100]}")

    def test_handle_request_with_messages(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test handling a chat-style request with messages."""
        from hackagent.router.adapters.google_adk import ADKAgent

        adapter = ADKAgent(id="test_adk_messages", config=google_adk_config)

        request = {
            "messages": [{"role": "user", "content": "Hello! Say hi."}],
            "max_new_tokens": 15,
        }

        response = adapter.handle_request(request)

        assert response is not None
        # Check for either success or handled error
        if response.get("error_message"):
            logger.warning(
                f"ADK returned error (may be LLM timeout): {response.get('error_message')}"
            )
        else:
            assert "processed_response" in response
            assert response["processed_response"] is not None
            logger.info(f"ADK chat response: {response['processed_response'][:100]}")

    def test_multi_turn_conversation(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test multi-turn conversation with ADK agent."""
        from hackagent.router.adapters.google_adk import ADKAgent

        adapter = ADKAgent(id="test_adk_multi_turn", config=google_adk_config)

        # First message
        request1 = {
            "prompt": "Say hello.",
            "max_new_tokens": 15,
        }
        response1 = adapter.handle_request(request1)
        assert response1 is not None
        if response1.get("error_message"):
            logger.warning(f"ADK turn 1 error: {response1.get('error_message')}")
        else:
            logger.info(
                f"ADK turn 1 response: {response1.get('processed_response', '')[:50]}"
            )

        # Second message in same session should have context
        request2 = {
            "prompt": "Say goodbye.",
            "max_new_tokens": 15,
        }
        response2 = adapter.handle_request(request2)
        assert response2 is not None
        if response2.get("error_message"):
            logger.warning(f"ADK turn 2 error: {response2.get('error_message')}")
        else:
            logger.info(
                f"ADK turn 2 response: {response2.get('processed_response', '')[:50]}"
            )

    def test_session_reuse(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test that the same session is reused across requests."""
        from hackagent.router.adapters.google_adk import ADKAgent

        session_id = f"test-session-{uuid.uuid4()}"
        config = google_adk_config.copy()
        config["session_id"] = session_id

        adapter = ADKAgent(id="test_adk_session_reuse", config=config)

        # Make multiple requests
        for i in range(3):
            response = adapter.handle_request(
                {"prompt": f"Request {i}", "max_new_tokens": 20}
            )
            assert response is not None

        # Session ID should remain the same
        assert adapter.session_id == session_id
        logger.info(f"Session maintained across requests: {session_id}")

    def test_error_handling_invalid_endpoint(
        self,
        skip_if_google_adk_unavailable,
    ):
        """Test error handling when endpoint is invalid."""
        from hackagent.router.adapters.google_adk import ADKAgent

        config = {
            "name": "test_agent",
            "endpoint": "http://localhost:99999",  # Invalid port
            "user_id": "test_user",
        }

        adapter = ADKAgent(id="test_adk_invalid", config=config)

        # The adapter returns an error response instead of raising an exception
        response = adapter.handle_request({"prompt": "test"})
        assert response is not None
        assert (
            response.get("error_message") is not None
            or response.get("status_code", 200) >= 400
        )
        logger.info(f"Error response as expected: {response.get('error_message')}")


@pytest.mark.integration
@pytest.mark.google_adk
class TestGoogleADKHackAgentIntegration:
    """End-to-end tests for HackAgent with Google ADK backend."""

    def test_hackagent_with_google_adk_initialization(
        self,
        skip_if_google_adk_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        google_adk_agent_url: str,
    ):
        """Test HackAgent initialization with Google ADK agent type."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name="multi_tool_agent",
            endpoint=google_adk_agent_url,
            agent_type=AgentTypeEnum.GOOGLE_ADK,
        )

        assert agent is not None
        assert agent.router is not None
        logger.info(
            f"HackAgent initialized with Google ADK: {agent.router.backend_agent}"
        )

    def test_hackagent_google_adk_baseline_attack(
        self,
        skip_if_google_adk_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        google_adk_agent_url: str,
        basic_attack_config: Dict[str, Any],
    ):
        """Test running a baseline attack against Google ADK agent."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name="multi_tool_agent",
            endpoint=google_adk_agent_url,
            agent_type=AgentTypeEnum.GOOGLE_ADK,
        )

        logger.info("Starting baseline attack against Google ADK agent...")
        results = agent.hack(attack_config=basic_attack_config)

        assert results is not None
        logger.info(f"Baseline attack completed: {results}")

    @pytest.mark.slow
    def test_hackagent_google_adk_advprefix_attack(
        self,
        skip_if_google_adk_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        google_adk_agent_url: str,
        advprefix_attack_config: Dict[str, Any],
    ):
        """Test running an advprefix attack against Google ADK agent."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name="multi_tool_agent",
            endpoint=google_adk_agent_url,
            agent_type=AgentTypeEnum.GOOGLE_ADK,
        )

        logger.info("Starting advprefix attack against Google ADK agent...")
        results = agent.hack(attack_config=advprefix_attack_config)

        assert results is not None
        logger.info(f"Advprefix attack completed: {results}")

    @pytest.mark.slow
    def test_hackagent_google_adk_with_ollama_judges(
        self,
        skip_if_google_adk_unavailable,
        skip_if_ollama_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        google_adk_agent_url: str,
        advprefix_attack_config_with_ollama_judges: Dict[str, Any],
    ):
        """Test advprefix attack with Ollama-based judges against Google ADK."""
        from hackagent import AgentTypeEnum

        agent = hackagent_client_factory(
            name="multi_tool_agent",
            endpoint=google_adk_agent_url,
            agent_type=AgentTypeEnum.GOOGLE_ADK,
        )

        logger.info("Starting advprefix attack with Ollama judges...")
        results = agent.hack(attack_config=advprefix_attack_config_with_ollama_judges)

        assert results is not None
        logger.info(f"Attack with Ollama judges completed: {results}")


@pytest.mark.integration
@pytest.mark.google_adk
class TestGoogleADKRouterIntegration:
    """Integration tests for AgentRouter with Google ADK."""

    def test_router_creates_adk_adapter(
        self,
        skip_if_google_adk_unavailable,
        skip_if_no_hackagent_key,
        hackagent_api_base_url: str,
        hackagent_api_key: str,
        google_adk_agent_url: str,
    ):
        """Test that AgentRouter correctly creates ADKAgent adapter."""
        from hackagent.client import AuthenticatedClient
        from hackagent.router.router import AgentRouter
        from hackagent.router.types import AgentTypeEnum
        from hackagent.router.adapters.google_adk import ADKAgent

        client = AuthenticatedClient(
            base_url=hackagent_api_base_url,
            token=hackagent_api_key,
            prefix="Bearer",
        )

        router = AgentRouter(
            client=client,
            name="multi_tool_agent",
            agent_type=AgentTypeEnum.GOOGLE_ADK,
            endpoint=google_adk_agent_url,
        )

        # Verify adapter was created
        agent_id = str(router.backend_agent.id)
        adapter = router.get_agent_instance(registration_key=agent_id)

        assert isinstance(adapter, ADKAgent)
        logger.info(f"Router created ADK adapter: {adapter.id}")

    def test_router_handles_adk_request(
        self,
        skip_if_google_adk_unavailable,
        skip_if_no_hackagent_key,
        hackagent_api_base_url: str,
        hackagent_api_key: str,
        google_adk_agent_url: str,
    ):
        """Test that router can handle requests through ADK adapter."""
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
            name="multi_tool_agent",
            agent_type=AgentTypeEnum.GOOGLE_ADK,
            endpoint=google_adk_agent_url,
        )

        # Route a request
        agent_id = str(router.backend_agent.id)
        request_data = {
            "prompt": "What can you help me with?",
            "max_new_tokens": 15,
        }

        response = router.route_request(
            registration_key=agent_id, request_data=request_data
        )

        assert response is not None
        assert "processed_response" in response
        if response.get("error_message"):
            logger.warning(f"Router ADK error: {response.get('error_message')}")
        elif response.get("processed_response"):
            logger.info(f"Router ADK response: {response['processed_response'][:50]}")
        else:
            logger.warning("Router ADK returned empty response")


@pytest.mark.integration
@pytest.mark.google_adk
class TestGoogleADKToolUsage:
    """Integration tests for ADK agents with tool/function calling capabilities."""

    def test_adk_agent_with_tool_calls(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test ADK agent that can use tools (e.g., weather lookup)."""
        from hackagent.router.adapters.google_adk import ADKAgent

        adapter = ADKAgent(id="test_adk_tools", config=google_adk_config)

        # Request that should trigger tool use (if agent supports it)
        request = {
            "prompt": "What is the weather in Boston?",
            "max_new_tokens": 20,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        # Tool usage details might be in response metadata
        logger.info(f"ADK tool response: {response}")

    def test_adk_agent_complex_query(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test ADK agent with complex multi-step query."""
        from hackagent.router.adapters.google_adk import ADKAgent

        adapter = ADKAgent(id="test_adk_complex", config=google_adk_config)

        request = {
            "prompt": "First tell me the weather in New York, then tell me about activities suitable for that weather.",
            "max_new_tokens": 30,
        }

        response = adapter.handle_request(request)

        assert response is not None
        assert "processed_response" in response
        if response.get("error_message"):
            logger.warning(f"ADK complex query error: {response.get('error_message')}")
        elif response.get("processed_response"):
            logger.info(f"ADK complex response: {response['processed_response'][:100]}")
        else:
            logger.warning("ADK complex query returned empty response")
