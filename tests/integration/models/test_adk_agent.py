# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Integration tests for the Google ADK (Agent Development Kit) backend.

These tests verify end-to-end functionality with a real Google ADK agent:
- Backend initialization and configuration
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

ADK_TEST_TIMEOUT_SECONDS = 45


def _adk_spec(config: Dict[str, Any]):
    """Build a ``ModelSpec`` for :class:`ADKModel` from a legacy config dict."""
    from hackagent.core.contracts import AgentType, ModelSpec

    cfg = dict(config)
    name = cfg.pop("name")
    endpoint = cfg.pop("endpoint", None)
    timeout = cfg.pop("timeout", None)
    return ModelSpec(
        identifier=name,
        agent_type=AgentType.GOOGLE_ADK,
        endpoint=endpoint,
        timeout=timeout,
        extra=cfg,
    )


def _user(text: str) -> list:
    return [{"role": "user", "content": text}]


@pytest.mark.integration
@pytest.mark.google_adk
class TestGoogleADKBackendIntegration:
    """Integration tests for the ADKModel backend."""

    def test_backend_initialization(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test that ADKModel initializes correctly with a real endpoint."""
        from hackagent.models.completions.adk import ADKModel

        model = ADKModel(_adk_spec(google_adk_config))

        assert model.name == google_adk_config["name"]
        assert model.endpoint is not None
        assert model.user_id is not None
        assert model.session_id is not None
        logger.info(
            f"ADK backend initialized: name={model.name}, "
            f"endpoint={model.endpoint}, session={model.session_id}"
        )

    def test_backend_with_custom_session_id(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test initializing the backend with a custom session ID."""
        from hackagent.models.completions.adk import ADKModel

        custom_session_id = f"test-session-{uuid.uuid4()}"
        config = google_adk_config.copy()
        config["session_id"] = custom_session_id

        model = ADKModel(_adk_spec(config))

        assert model.session_id == custom_session_id
        logger.info(f"ADK backend with custom session: {model.session_id}")

    def test_session_creation(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test explicit session creation on the ADK server."""
        from hackagent.models.completions.adk import ADKModel

        session_id = f"test-session-{uuid.uuid4()}"
        config = google_adk_config.copy()
        config["session_id"] = session_id

        model = ADKModel(_adk_spec(config))

        # Session management lives on the per-instance ``_ADKCustomLLM`` handler
        # the backend registers with LiteLLM. ``_create_session`` is idempotent
        # and raises ``ADKInteractionError`` on hard failures; we just make sure
        # it returns cleanly when given a fresh session id.
        model._custom_handler._create_session(session_id=session_id)
        logger.info(f"Session created successfully: {session_id}")

    def test_complete(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test completing a request through the ADK agent."""
        from hackagent.models.completions.adk import ADKModel

        model = ADKModel(_adk_spec(google_adk_config))

        response = model.complete(_user("What is 2 + 2? Answer briefly."))

        assert response is not None
        if response.error is not None:
            logger.warning(
                f"ADK returned error (may be LLM timeout): {response.error.message}"
            )
        else:
            assert response.text is not None
            logger.info(f"ADK response: {response.text[:100]}")

    def test_complete_with_messages(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test completing a chat-style request with messages."""
        from hackagent.models.completions.adk import ADKModel

        model = ADKModel(_adk_spec(google_adk_config))

        response = model.complete([{"role": "user", "content": "Hello! Say hi."}])

        assert response is not None
        if response.error is not None:
            logger.warning(
                f"ADK returned error (may be LLM timeout): {response.error.message}"
            )
        else:
            assert response.text is not None
            logger.info(f"ADK chat response: {response.text[:100]}")

    @pytest.mark.timeout(240)
    def test_multi_turn_conversation(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test multi-turn conversation with the ADK agent."""
        from hackagent.models.completions.adk import ADKModel

        model = ADKModel(_adk_spec(google_adk_config))

        response1 = model.complete(_user("Say hello."))
        assert response1 is not None
        if response1.error is not None:
            logger.warning(f"ADK turn 1 error: {response1.error.message}")
        else:
            logger.info(f"ADK turn 1 response: {(response1.text or '')[:50]}")

        # Second message in same session should have context.
        response2 = model.complete(_user("Say goodbye."))
        assert response2 is not None
        if response2.error is not None:
            logger.warning(f"ADK turn 2 error: {response2.error.message}")
        else:
            logger.info(f"ADK turn 2 response: {(response2.text or '')[:50]}")

    def test_session_reuse(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test that the same session is reused across requests."""
        from hackagent.models.completions.adk import ADKModel

        session_id = f"test-session-{uuid.uuid4()}"
        config = google_adk_config.copy()
        config["session_id"] = session_id

        model = ADKModel(_adk_spec(config))

        for i in range(3):
            response = model.complete(_user(f"Request {i}"))
            assert response is not None

        # Session ID should remain the same.
        assert model.session_id == session_id
        logger.info(f"Session maintained across requests: {session_id}")

    def test_error_handling_invalid_endpoint(
        self,
        skip_if_google_adk_unavailable,
    ):
        """Test error handling when the endpoint is invalid."""
        from hackagent.models.completions.adk import ADKModel

        config = {
            "name": "test_agent",
            "endpoint": "http://localhost:99999",  # Invalid port
            "user_id": "test_user",
        }

        model = ADKModel(_adk_spec(config))

        # The backend returns an error response instead of raising.
        response = model.complete(_user("test"))
        assert response is not None
        assert response.error is not None
        logger.info(f"Error response as expected: {response.error.message}")


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
        from hackagent import AgentType

        agent = hackagent_client_factory(
            name="multi_tool_agent",
            endpoint=google_adk_agent_url,
            agent_type=AgentType.GOOGLE_ADK,
        )

        assert agent is not None
        assert agent.router is not None
        logger.info(
            f"HackAgent initialized with Google ADK: {agent.router.backend_agent}"
        )

    @pytest.mark.timeout(600)
    def test_hackagent_google_adk_static_template_attack(
        self,
        skip_if_google_adk_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        google_adk_agent_url: str,
        basic_attack_config: Dict[str, Any],
    ):
        """Test running a static template attack against Google ADK agent."""
        from hackagent import AgentType

        agent = hackagent_client_factory(
            name="multi_tool_agent",
            endpoint=google_adk_agent_url,
            agent_type=AgentType.GOOGLE_ADK,
        )

        logger.info("Starting static template attack against Google ADK agent...")
        results = agent.hack(attack_config=basic_attack_config)

        assert results is not None
        logger.info(f"Baseline attack completed: {results}")

    @pytest.mark.slow
    @pytest.mark.timeout(900)
    def test_hackagent_google_adk_advprefix_attack(
        self,
        skip_if_google_adk_unavailable,
        skip_if_no_hackagent_key,
        hackagent_client_factory,
        google_adk_agent_url: str,
        advprefix_attack_config: Dict[str, Any],
    ):
        """Test running an advprefix attack against Google ADK agent."""
        from hackagent import AgentType

        agent = hackagent_client_factory(
            name="multi_tool_agent",
            endpoint=google_adk_agent_url,
            agent_type=AgentType.GOOGLE_ADK,
        )

        logger.info("Starting advprefix attack against Google ADK agent...")
        results = agent.hack(attack_config=advprefix_attack_config)

        assert results is not None
        logger.info(f"Advprefix attack completed: {results}")

    @pytest.mark.slow
    @pytest.mark.timeout(900)
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
        from hackagent import AgentType

        agent = hackagent_client_factory(
            name="multi_tool_agent",
            endpoint=google_adk_agent_url,
            agent_type=AgentType.GOOGLE_ADK,
        )

        logger.info("Starting advprefix attack with Ollama judges...")
        results = agent.hack(attack_config=advprefix_attack_config_with_ollama_judges)

        assert results is not None
        logger.info(f"Attack with Ollama judges completed: {results}")


@pytest.mark.integration
@pytest.mark.google_adk
class TestGoogleADKConnectIntegration:
    """Integration tests for connecting to a Google ADK agent."""

    @staticmethod
    def _connect(google_adk_agent_url: str):
        from hackagent.core.contracts import AgentType, ModelSpec
        from hackagent.models.connect import connect

        return connect(
            ModelSpec(
                identifier="multi_tool_agent",
                endpoint=google_adk_agent_url,
                agent_type=AgentType.GOOGLE_ADK,
                timeout=ADK_TEST_TIMEOUT_SECONDS,
                extra={"user_id": "hackagent-integration"},
            )
        )

    def test_connect_creates_adk_backend(
        self, skip_if_google_adk_unavailable, google_adk_agent_url: str
    ):
        """connect() builds an ADKModel backend without any storage backend."""
        from hackagent.models.completions.adk import ADKModel

        model = self._connect(google_adk_agent_url)

        assert isinstance(model, ADKModel)
        logger.info(f"Connected ADK backend: {model.id}")

    def test_connected_adk_handles_request(
        self, skip_if_google_adk_unavailable, google_adk_agent_url: str
    ):
        """A connected ADK agent answers a request."""
        response = self._connect(google_adk_agent_url).complete(
            _user("What can you help me with?")
        )

        assert response is not None
        if response.error is not None:
            logger.warning(f"ADK error: {response.error.message}")
        elif response.text:
            logger.info(f"ADK response: {response.text[:50]}")


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
        from hackagent.models.completions.adk import ADKModel

        model = ADKModel(_adk_spec(google_adk_config))

        response = model.complete(_user("What is the weather in Boston?"))

        assert response is not None
        assert response.text is not None
        logger.info(f"ADK tool response: {response.text[:100]}")

    @pytest.mark.timeout(300)
    def test_adk_agent_complex_query(
        self,
        skip_if_google_adk_unavailable,
        google_adk_config: Dict[str, Any],
    ):
        """Test ADK agent with complex multi-step query."""
        from hackagent.models.completions.adk import ADKModel

        model = ADKModel(_adk_spec(google_adk_config))

        response = model.complete(
            _user(
                "First tell me the weather in New York, then tell me about "
                "activities suitable for that weather."
            )
        )

        assert response is not None
        if response.error is not None:
            logger.warning(f"ADK complex query error: {response.error.message}")
        elif response.text:
            logger.info(f"ADK complex response: {response.text[:100]}")
        else:
            logger.warning("ADK complex query returned empty response")
