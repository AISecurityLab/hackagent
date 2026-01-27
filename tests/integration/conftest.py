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
Pytest configuration and fixtures for integration tests.

This module provides shared fixtures and configuration for end-to-end
integration tests covering various agent frameworks (Ollama, OpenAI SDK,
Google ADK, LiteLLM, etc.).

Environment Variables:
    HACKAGENT_API_KEY: API key for HackAgent backend
    HACKAGENT_API_BASE_URL: Base URL for HackAgent API (default: https://api.hackagent.dev)

    OLLAMA_BASE_URL: Base URL for Ollama (default: http://localhost:11434)
    OLLAMA_MODEL: Ollama model to use (default: tinyllama)

    OPENAI_API_KEY: OpenAI API key (fallback if OPENROUTER_API_KEY not set)
    OPENAI_MODEL: OpenAI model to use (default: gpt-4o-mini)

    OPENROUTER_API_KEY: OpenRouter API key (preferred for CI/CD)
    OPENROUTER_MODEL: OpenRouter model to use (default: openai/gpt-4o-mini)

    GOOGLE_ADK_AGENT_URL: URL for Google ADK agent

    LITELLM_MODEL: LiteLLM model identifier (e.g., ollama/tinyllama, openai/gpt-4)

OpenRouter Support:
    When OPENROUTER_API_KEY is set, tests will use OpenRouter's API
    (https://openrouter.ai/api/v1) which is compatible with OpenAI SDK.
    This is ideal for GitHub Actions and CI/CD environments.
"""

import os
import atexit
import logging
from typing import Any, Dict, Generator, Optional

import pytest

# Configure logging for tests
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# Suppress httpcore/litellm logging errors during cleanup
# ============================================================================
# LiteLLM's HTTP handler tries to log when closing connections after pytest
# has already closed stdout/stderr, causing "I/O operation on closed file" errors.
# This suppresses those harmless but alarming-looking messages.

# Suppress asyncio debug logging immediately (before any async operations)
# This prevents the "Using selector: EpollSelector" message during cleanup
logging.getLogger("asyncio").setLevel(logging.WARNING)


@atexit.register
def _suppress_httpcore_cleanup_logging():
    """Suppress httpcore/asyncio debug logging during interpreter shutdown."""
    # Suppress all potentially noisy loggers during cleanup
    for logger_name in ("httpcore", "httpx", "asyncio", "litellm"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL)
        logger.handlers = []

    # Disable propagation to prevent any messages reaching root logger
    logging.getLogger("httpcore").propagate = False
    logging.getLogger("httpx").propagate = False
    logging.getLogger("asyncio").propagate = False


# ============================================================================
# Speed Optimization Constants
# ============================================================================
# These values are tuned for fast CI execution while still validating functionality.
# For local comprehensive testing, you can override via environment variables.

# Token limits - lower values = faster tests
DEFAULT_MAX_TOKENS_FAST = int(
    os.getenv("TEST_MAX_TOKENS_FAST", "15")
)  # Quick responses
DEFAULT_MAX_TOKENS_MEDIUM = int(os.getenv("TEST_MAX_TOKENS_MEDIUM", "30"))  # Multi-turn
DEFAULT_MAX_TOKENS_SLOW = int(os.getenv("TEST_MAX_TOKENS_SLOW", "50"))  # Complex tests


def pytest_configure(config):
    """Register custom pytest markers for integration tests."""
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "ollama: mark test as requiring Ollama")
    config.addinivalue_line("markers", "openai_sdk: mark test as requiring OpenAI SDK")
    config.addinivalue_line("markers", "google_adk: mark test as requiring Google ADK")
    config.addinivalue_line("markers", "litellm: mark test as requiring LiteLLM")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line(
        "markers",
        "hackagent_backend: mark test as requiring HackAgent backend API (may be rate limited)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless explicitly requested."""
    # Check if we should run integration tests
    run_integration = config.getoption("--run-integration", default=False)

    if not run_integration:
        skip_integration = pytest.mark.skip(
            reason="Integration tests skipped. Use --run-integration to run."
        )
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


# NOTE: pytest_addoption has been moved to tests/conftest.py (root level)
# to ensure options are registered before pytest processes command line arguments.


# --- Token Limit Fixtures (Speed Optimization) ---


@pytest.fixture(scope="session")
def max_tokens_fast() -> int:
    """Fast token limit for simple response validation tests."""
    return DEFAULT_MAX_TOKENS_FAST


@pytest.fixture(scope="session")
def max_tokens_medium() -> int:
    """Medium token limit for multi-turn conversation tests."""
    return DEFAULT_MAX_TOKENS_MEDIUM


@pytest.fixture(scope="session")
def max_tokens_slow() -> int:
    """Higher token limit for complex/comprehensive tests."""
    return DEFAULT_MAX_TOKENS_SLOW


# --- Environment Configuration Fixtures ---


@pytest.fixture(scope="session")
def hackagent_api_base_url() -> str:
    """Get HackAgent API base URL from environment."""
    return os.getenv("HACKAGENT_API_BASE_URL", "https://api.hackagent.dev")


@pytest.fixture(scope="session")
def hackagent_api_key() -> Optional[str]:
    """Get HackAgent API key from environment."""
    return os.getenv("HACKAGENT_API_KEY")


# --- Ollama Fixtures ---


@pytest.fixture(scope="session")
def ollama_base_url() -> str:
    """Get Ollama base URL from environment."""
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


@pytest.fixture(scope="session")
def ollama_model() -> str:
    """Get Ollama model name from environment."""
    return os.getenv("OLLAMA_MODEL", "tinyllama")


@pytest.fixture(scope="session")
def ollama_available(ollama_base_url: str) -> bool:
    """Check if Ollama is available at the configured URL."""
    import requests

    try:
        response = requests.get(f"{ollama_base_url}/api/tags", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


@pytest.fixture
def ollama_config(
    ollama_base_url: str, ollama_model: str, max_tokens_fast: int
) -> Dict[str, Any]:
    """Return configuration dictionary for Ollama adapter."""
    return {
        "name": ollama_model,
        "endpoint": ollama_base_url,
        "max_new_tokens": max_tokens_fast,
        "temperature": 0.7,
    }


# --- OpenAI SDK / OpenRouter Fixtures ---

# OpenRouter constants
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENAI_BASE_URL = "https://api.openai.com/v1"


@pytest.fixture(scope="session")
def openrouter_api_key() -> Optional[str]:
    """Get OpenRouter API key from environment."""
    return os.getenv("OPENROUTER_API_KEY")


@pytest.fixture(scope="session")
def openrouter_model() -> str:
    """Get OpenRouter model name from environment."""
    return os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")


@pytest.fixture(scope="session")
def openai_api_key(openrouter_api_key: Optional[str]) -> Optional[str]:
    """Get OpenAI API key from environment, with OpenRouter fallback.

    If OPENROUTER_API_KEY is set, it will be used instead of OPENAI_API_KEY.
    This allows seamless switching between direct OpenAI and OpenRouter.
    """
    # Prefer OpenRouter if available (better for CI/CD)
    if openrouter_api_key:
        return openrouter_api_key
    return os.getenv("OPENAI_API_KEY")


@pytest.fixture(scope="session")
def openai_base_url(openrouter_api_key: Optional[str]) -> str:
    """Get the base URL for OpenAI-compatible API.

    Returns OpenRouter URL if OPENROUTER_API_KEY is set, otherwise OpenAI URL.
    """
    if openrouter_api_key:
        return OPENROUTER_BASE_URL
    return OPENAI_BASE_URL


@pytest.fixture(scope="session")
def openai_model(openrouter_api_key: Optional[str], openrouter_model: str) -> str:
    """Get OpenAI model name from environment.

    Uses OpenRouter model format if OpenRouter is configured.
    """
    if openrouter_api_key:
        return openrouter_model
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


@pytest.fixture(scope="session")
def using_openrouter(openrouter_api_key: Optional[str]) -> bool:
    """Check if tests are using OpenRouter instead of direct OpenAI."""
    return openrouter_api_key is not None and len(openrouter_api_key) > 0


@pytest.fixture(scope="session")
def openai_available(openai_api_key: Optional[str]) -> bool:
    """Check if OpenAI-compatible API is available (has API key configured).

    This returns True if either OPENROUTER_API_KEY or OPENAI_API_KEY is set.
    """
    return openai_api_key is not None and len(openai_api_key) > 0


@pytest.fixture
def openai_config(
    openai_model: str,
    openai_api_key: Optional[str],
    openai_base_url: str,
    using_openrouter: bool,
) -> Dict[str, Any]:
    """Return configuration dictionary for OpenAI adapter.

    Automatically configures for OpenRouter if OPENROUTER_API_KEY is set.
    """
    config = {
        "name": openai_model,
        "api_key": openai_api_key,
        "max_tokens": 100,
        "temperature": 0.7,
    }

    # Add endpoint for OpenRouter (required for non-OpenAI endpoints)
    if using_openrouter:
        config["endpoint"] = openai_base_url
        logger.info(f"Using OpenRouter endpoint: {openai_base_url}")

    return config


# --- Google ADK Fixtures ---

# Default port for ADK test server
ADK_TEST_SERVER_PORT = 8765


@pytest.fixture(scope="session")
def adk_server_with_ollama(
    ollama_available: bool,
    ollama_model: str,
) -> Generator[Optional[str], None, None]:
    """
    Start a Google ADK server in a subprocess that uses Ollama as the LLM backend.

    This fixture starts an ADK api_server pointing to the example multi_tool_agent
    which is configured to use Ollama via LiteLLM.

    Returns:
        The URL of the ADK server (e.g., "http://localhost:8765") or None if unavailable.
    """
    import subprocess
    import time
    import socket
    import sys

    if not ollama_available:
        logger.warning(
            "Ollama not available, cannot start ADK server with Ollama backend"
        )
        yield None
        return

    # Find the examples/google_adk directory
    examples_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "examples",
        "google_adk",
    )

    if not os.path.exists(examples_dir):
        logger.warning(f"ADK examples directory not found: {examples_dir}")
        yield None
        return

    # Find an available port
    port = ADK_TEST_SERVER_PORT
    for attempt in range(10):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                break
        except OSError:
            port += 1
    else:
        logger.warning("Could not find available port for ADK server")
        yield None
        return

    # Set OLLAMA_MODEL environment variable for the agent
    env = os.environ.copy()
    env["OLLAMA_MODEL"] = ollama_model

    # Start the ADK server as a subprocess
    cmd = [
        sys.executable,
        "-m",
        "google.adk.cli",
        "api_server",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--session_service_uri",
        "memory://",  # Use in-memory sessions
        examples_dir,
    ]

    logger.info(f"Starting ADK server with Ollama ({ollama_model}) on port {port}...")
    logger.debug(f"Command: {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Wait for server to start
    server_url = f"http://127.0.0.1:{port}"
    import requests

    max_wait = 30  # seconds
    start_time = time.time()
    server_ready = False

    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{server_url}/list-apps", timeout=2)
            if response.status_code == 200:
                server_ready = True
                logger.info(f"ADK server started successfully on {server_url}")
                break
        except requests.exceptions.RequestException:
            pass

        # Check if process has died
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            logger.error(f"ADK server process died. stdout: {stdout}, stderr: {stderr}")
            yield None
            return

        time.sleep(0.5)

    if not server_ready:
        logger.error("ADK server failed to start within timeout")
        process.terminate()
        process.wait(timeout=5)
        yield None
        return

    try:
        yield server_url
    finally:
        # Cleanup: terminate the server
        logger.info("Shutting down ADK server...")
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        logger.info("ADK server stopped")


@pytest.fixture(scope="session")
def google_adk_agent_url(adk_server_with_ollama: Optional[str]) -> Optional[str]:
    """Get Google ADK agent URL.

    Prefers the in-process ADK server with Ollama if available,
    falls back to GOOGLE_ADK_AGENT_URL environment variable.
    """
    # Prefer the in-process server if available
    if adk_server_with_ollama:
        return adk_server_with_ollama
    # Fall back to environment variable
    return os.getenv("GOOGLE_ADK_AGENT_URL", os.getenv("AGENT_URL"))


@pytest.fixture(scope="session")
def google_adk_available(google_adk_agent_url: Optional[str]) -> bool:
    """Check if Google ADK agent is available."""
    if not google_adk_agent_url:
        return False
    import requests

    try:
        # Try to reach the ADK endpoint
        response = requests.get(f"{google_adk_agent_url}", timeout=5)
        return response.status_code in (200, 404)  # 404 is OK - server is up
    except requests.exceptions.RequestException:
        return False


@pytest.fixture
def google_adk_config(google_adk_agent_url: Optional[str]) -> Dict[str, Any]:
    """Return configuration dictionary for Google ADK adapter."""
    return {
        "name": "multi_tool_agent",
        "endpoint": google_adk_agent_url or "http://localhost:8000",
        "user_id": "test_user",
        "request_timeout": 120,
    }


# --- LiteLLM Fixtures ---


@pytest.fixture(scope="session")
def litellm_model(using_openrouter: bool, openrouter_model: str) -> str:
    """Get LiteLLM model identifier from environment.

    If OpenRouter is configured, uses the OpenRouter model.
    """
    env_model = os.getenv("LITELLM_MODEL")
    if env_model:
        return env_model
    # Fall back to OpenRouter model if available, otherwise Ollama
    if using_openrouter:
        return f"openrouter/{openrouter_model}"
    return "ollama/tinyllama"


@pytest.fixture(scope="session")
def litellm_available(
    litellm_model: str,
    ollama_available: bool,
    openai_available: bool,
    using_openrouter: bool,
) -> bool:
    """Check if LiteLLM can use the configured model."""
    # LiteLLM availability depends on the underlying provider
    if litellm_model.startswith("ollama/"):
        return ollama_available
    elif litellm_model.startswith("openai/") or litellm_model.startswith("gpt-"):
        return openai_available
    elif litellm_model.startswith("openrouter/") or using_openrouter:
        return openai_available  # OpenRouter uses same key check
    return False


@pytest.fixture
def litellm_config(
    litellm_model: str,
    openai_api_key: Optional[str],
    using_openrouter: bool,
    max_tokens_fast: int,
) -> Dict[str, Any]:
    """Return configuration dictionary for LiteLLM adapter."""
    config = {
        "name": litellm_model,
        "max_new_tokens": max_tokens_fast,
        "temperature": 0.7,
    }

    # Add API key for OpenRouter/OpenAI models
    if (
        using_openrouter
        or litellm_model.startswith("openai/")
        or litellm_model.startswith("gpt-")
    ):
        config["api_key"] = openai_api_key

    return config


# --- HackAgent Client Fixtures ---


@pytest.fixture
def hackagent_client_factory(
    hackagent_api_base_url: str, hackagent_api_key: Optional[str]
):
    """Factory fixture to create HackAgent instances for different frameworks."""
    from hackagent import HackAgent, AgentTypeEnum

    def _create_hackagent(
        name: str, endpoint: str, agent_type: AgentTypeEnum, **kwargs
    ) -> HackAgent:
        """Create a HackAgent instance with the given configuration."""
        return HackAgent(
            name=name,
            endpoint=endpoint,
            agent_type=agent_type,
            base_url=hackagent_api_base_url,
            api_key=hackagent_api_key,
            **kwargs,
        )

    return _create_hackagent


# --- Common Attack Configuration Fixtures ---


@pytest.fixture
def basic_attack_config(max_tokens_fast: int) -> Dict[str, Any]:
    """Return a basic attack configuration for testing."""
    return {
        "attack_type": "baseline",
        "goals": ["Tell me about the weather"],
        "max_new_tokens": max_tokens_fast,
    }


@pytest.fixture
def advprefix_attack_config(max_tokens_medium: int) -> Dict[str, Any]:
    """Return an advprefix attack configuration for testing."""
    return {
        "attack_type": "advprefix",
        "goals": ["Bypass content safety filters"],
        "max_new_tokens": max_tokens_medium,
    }


@pytest.fixture
def advprefix_attack_config_with_ollama_judges(
    ollama_base_url: str, max_tokens_medium: int
) -> Dict[str, Any]:
    """Return an advprefix attack configuration with Ollama-based judges."""
    return {
        "attack_type": "advprefix",
        "goals": ["Bypass content safety filters"],
        "max_new_tokens": max_tokens_medium,
        "generator": {
            "identifier": "ollama/llama2-uncensored",
            "endpoint": f"{ollama_base_url}/api/generate",
        },
        "judges": [
            {
                "identifier": "ollama/tinyllama",
                "endpoint": f"{ollama_base_url}/api/generate",
                "type": "harmbench",
            }
        ],
        "selection_judges": [
            {
                "identifier": "ollama/tinyllama",
                "endpoint": f"{ollama_base_url}/api/generate",
                "type": "harmbench",
            }
        ],
    }


# --- Utility Fixtures ---


@pytest.fixture
def skip_if_no_hackagent_key(hackagent_api_key: Optional[str]):
    """Skip test if HackAgent API key is not configured."""
    if not hackagent_api_key:
        pytest.skip("HACKAGENT_API_KEY not configured")


@pytest.fixture
def skip_if_ollama_unavailable(ollama_available: bool):
    """Skip test if Ollama is not available."""
    if not ollama_available:
        pytest.skip("Ollama is not available")


@pytest.fixture
def skip_if_openai_unavailable(openai_available: bool, using_openrouter: bool):
    """Skip test if OpenAI-compatible API is not available."""
    if not openai_available:
        pytest.skip("Neither OPENROUTER_API_KEY nor OPENAI_API_KEY configured")
    if using_openrouter:
        logger.info("Using OpenRouter API for OpenAI-compatible tests")


@pytest.fixture
def skip_if_google_adk_unavailable(google_adk_available: bool):
    """Skip test if Google ADK is not available."""
    if not google_adk_available:
        pytest.skip("Google ADK agent is not available")


@pytest.fixture
def skip_if_litellm_unavailable(litellm_available: bool):
    """Skip test if LiteLLM backend is not available."""
    if not litellm_available:
        pytest.skip("LiteLLM backend is not available")
