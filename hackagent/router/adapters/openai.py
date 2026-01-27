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


import logging
from typing import Any, Dict, List, Optional

from .base import ChatCompletionsAgent, AdapterConfigurationError

# Lazy-load openai to improve startup time
_openai_module = None
_openai_available = None

# Module-level names for test patching compatibility
# These will be populated when _get_openai() is first called,
# but tests can patch them directly
OpenAI = None
OPENAI_AVAILABLE = None


def _get_openai():
    """Lazily import and return the openai module."""
    global _openai_module, _openai_available, OpenAI, OPENAI_AVAILABLE
    if _openai_module is None:
        try:
            import openai as _openai

            _openai_module = _openai
            _openai_available = True
            # Also set module-level names for compatibility
            OpenAI = _openai.OpenAI
            OPENAI_AVAILABLE = True
        except ImportError:
            _openai_module = False
            _openai_available = False
            OPENAI_AVAILABLE = False
    return _openai_module if _openai_module else None


def _get_openai_exceptions():
    """Get OpenAI exception classes, or dummy classes if not available."""
    openai = _get_openai()
    if openai:
        return (
            openai.OpenAIError,
            openai.APIConnectionError,
            openai.RateLimitError,
            openai.APITimeoutError,
        )
    else:
        # Return dummy exceptions
        return (Exception, Exception, Exception, Exception)


def _is_openai_available():
    """Check if openai is available."""
    global _openai_available, OPENAI_AVAILABLE
    # Allow test patches to override OPENAI_AVAILABLE
    if OPENAI_AVAILABLE is not None:
        return OPENAI_AVAILABLE
    if _openai_available is None:
        _get_openai()
    return _openai_available


def _check_openai_available():
    global OPENAI_AVAILABLE
    if OPENAI_AVAILABLE is None:
        OPENAI_AVAILABLE = _is_openai_available()
    return OPENAI_AVAILABLE


# --- Custom Exceptions (subclass from base) ---
class OpenAIConfigurationError(AdapterConfigurationError):
    """Custom exception for OpenAI adapter configuration issues."""

    pass


logger = logging.getLogger(__name__)  # Module-level logger


class OpenAIAgent(ChatCompletionsAgent):
    """
    Adapter for interacting with AI agents built using the OpenAI SDK.

    This adapter supports OpenAI's chat completions API, including support for
    function calling and tool use, which are common patterns in agent implementations.
    """

    ADAPTER_TYPE = "OpenAIAgent"
    DEFAULT_TEMPERATURE = 1.0  # OpenAI default

    def __init__(self, id: str, config: Dict[str, Any]):
        """
        Initializes the OpenAIAgent.

        Args:
            id: The unique identifier for this OpenAI agent instance.
            config: Configuration dictionary for the OpenAI agent.
                          Expected keys:
                          - 'name': Model name (e.g., "gpt-4", "gpt-3.5-turbo").
                          - 'endpoint' (optional): Base URL for the API (for custom endpoints).
                          - 'api_key' (optional): Name of the environment variable holding the API key,
                            or the API key itself. Defaults to OPENAI_API_KEY env var.
                          - 'max_tokens' (optional): Default max tokens for generation.
                          - 'temperature' (optional): Default temperature (defaults to 1.0).
                          - 'tools' (optional): List of tool/function definitions for function calling.
                          - 'tool_choice' (optional): Controls which tools the model can call.
        """
        super().__init__(id, config)

        if not _is_openai_available():
            msg = (
                f"OpenAI SDK is not installed. Please install it with: pip install openai. "
                f"OpenAIAgent: {self.id}"
            )
            self.logger.error(msg)
            raise OpenAIConfigurationError(msg)

        self.api_base_url: Optional[str] = self._get_config_key("endpoint")

        # Model name defaults to "default" for custom endpoints (server decides the model)
        if "name" not in self.config:
            if self.api_base_url:
                # Custom endpoint - use a default model name, server will handle it
                self.model_name = self._get_config_key("name", "default")
                self.logger.info(
                    "No model name specified for custom endpoint, using 'default'"
                )
            else:
                self.model_name = self._require_config_key(
                    "name", OpenAIConfigurationError
                )
        else:
            self.model_name: str = self.config["name"]

        # Handle API key resolution
        self.actual_api_key = self._resolve_api_key(
            config_key="api_key", env_var_fallback="OPENAI_API_KEY"
        )

        # For custom endpoints without API key, use a placeholder
        # (some local servers don't require authentication)
        if not self.actual_api_key and self.api_base_url:
            self.actual_api_key = "not-required"
            self.logger.info(
                f"No API key configured for custom endpoint '{self.api_base_url}', using placeholder"
            )

        # Initialize OpenAI client
        # Check for test-patched OpenAI first, then fall back to lazy-loaded module
        global OpenAI
        if OpenAI is not None:
            # Use patched or pre-loaded OpenAI class
            openai_client_class = OpenAI
        else:
            # Lazy load the module
            openai = _get_openai()
            openai_client_class = openai.OpenAI

        client_kwargs = {}
        if self.actual_api_key:
            client_kwargs["api_key"] = self.actual_api_key
        if self.api_base_url:
            client_kwargs["base_url"] = self.api_base_url

        self.client = openai_client_class(**client_kwargs)

        self.logger.info(
            f"OpenAIAgent '{self.id}' initialized for model: '{self.model_name}'"
            + (f" API Base: '{self.api_base_url}'" if self.api_base_url else "")
        )

        # Store default generation parameters
        self.default_max_tokens = self._get_config_key("max_tokens")
        self.default_max_new_tokens = self.default_max_tokens  # Alias for base class
        self.default_temperature = self._get_config_key(
            "temperature", self.DEFAULT_TEMPERATURE
        )
        self.default_tools = self._get_config_key("tools")
        self.default_tool_choice = self._get_config_key("tool_choice")

    def _get_excluded_request_keys(self) -> set:
        """Returns keys to exclude when extracting additional kwargs."""
        base_keys = super()._get_excluded_request_keys()
        return base_keys | {"tools", "tool_choice"}

    def _get_completion_parameters(
        self, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters including OpenAI-specific tools."""
        params = super()._get_completion_parameters(request_data)

        # Add OpenAI-specific parameters
        params["tools"] = request_data.get("tools", self.default_tools)
        params["tool_choice"] = request_data.get(
            "tool_choice", self.default_tool_choice
        )

        return params

    def _execute_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute the completion request using OpenAI's chat completions API.

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            **kwargs: Additional parameters (temperature, max_tokens, tools, etc.)

        Returns:
            A dictionary containing the result with 'success', 'content', etc.
        """
        max_tokens = kwargs.pop("max_tokens", None)
        temperature = kwargs.pop("temperature", self.default_temperature)
        tools = kwargs.pop("tools", None)
        tool_choice = kwargs.pop("tool_choice", None)

        self.logger.info(
            f"Sending request to OpenAI model '{self.model_name}' with {len(messages)} messages..."
        )

        try:
            openai_params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
            }

            if max_tokens is not None:
                openai_params["max_tokens"] = max_tokens

            if tools:
                openai_params["tools"] = tools
                if tool_choice:
                    openai_params["tool_choice"] = tool_choice

            # Add any additional kwargs
            openai_params.update(kwargs)

            # Log request parameters at debug level
            self.logger.debug(
                f"OpenAI API request params: model={self.model_name}, "
                f"base_url={self.api_base_url}, "
                f"messages={messages[:1] if messages else []}, "
                f"temperature={temperature}, max_tokens={max_tokens}, "
                f"extra_kwargs={list(kwargs.keys())}"
            )

            # Make the API call
            response = self.client.chat.completions.create(**openai_params)

            # Extract response data
            message = response.choices[0].message
            content = message.content if message.content else ""

            # For reasoning models (e.g., o1-preview, o1-mini), check reasoning field
            if not content and hasattr(message, "reasoning") and message.reasoning:
                content = message.reasoning
                self.logger.info(
                    f"OpenAI extracted text from 'reasoning' field (reasoning model) for '{self.model_name}'"
                )

            # Check if there are tool calls
            tool_calls = None
            if hasattr(message, "tool_calls") and message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ]

            result = {
                "success": True,
                "content": content,
                "finish_reason": response.choices[0].finish_reason,
                "usage": response.usage.model_dump() if response.usage else None,
                "model": response.model,
                "tool_calls": tool_calls,
                "raw_response": response,
            }

            self.logger.info(
                f"Successfully received response from OpenAI model '{self.model_name}'. "
                f"Finish reason: {result['finish_reason']}"
            )

            return result

        except Exception as e:
            # Get OpenAI exceptions dynamically
            openai = _get_openai()
            if openai:
                OpenAIError = openai.OpenAIError
                APITimeoutError = openai.APITimeoutError
                RateLimitError = openai.RateLimitError
                APIConnectionError = openai.APIConnectionError
            else:
                # If openai not available, these will never match
                OpenAIError = APITimeoutError = RateLimitError = APIConnectionError = (
                    type(None)
                )

            if isinstance(e, APITimeoutError):
                self.logger.error(
                    f"OpenAI API timeout for model '{self.model_name}': {e}",
                    exc_info=True,
                )
                return {
                    "success": False,
                    "error_type": "timeout",
                    "error_message": str(e),
                }
            elif isinstance(e, RateLimitError):
                self.logger.error(
                    f"OpenAI rate limit exceeded for model '{self.model_name}': {e}",
                    exc_info=True,
                )
                return {
                    "success": False,
                    "error_type": "rate_limit",
                    "error_message": str(e),
                }
            elif isinstance(e, APIConnectionError):
                self.logger.error(
                    f"OpenAI API connection error for model '{self.model_name}': {e}",
                    exc_info=True,
                )
                return {
                    "success": False,
                    "error_type": "connection",
                    "error_message": str(e),
                }
            elif isinstance(e, OpenAIError):
                self.logger.error(
                    f"OpenAI API error for model '{self.model_name}': {e}",
                    exc_info=True,
                )
                return {
                    "success": False,
                    "error_type": "api_error",
                    "error_message": str(e),
                }
            else:
                self.logger.exception(
                    f"Unexpected error during OpenAI completion for model '{self.model_name}': {e}"
                )
                return {
                    "success": False,
                    "error_type": "unexpected",
                    "error_message": f"{type(e).__name__}: {str(e)}",
                }

    def _build_agent_specific_data(
        self,
        completion_result: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build OpenAI-specific response data including tool calls."""
        data = super()._build_agent_specific_data(completion_result, parameters)

        # Add tool calls if present
        if completion_result.get("tool_calls"):
            data["tool_calls"] = completion_result["tool_calls"]

        # Add tools_provided flag
        data["invoked_parameters"]["tools_provided"] = (
            parameters.get("tools") is not None
        )

        return data
