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
import os
from typing import Any, Dict, List, Optional

from .base import Agent

# Lazy-load openai to improve startup time
_openai_module = None
_openai_available = None

# Module-level names for test patching compatibility
# These will be populated when _get_openai() is first called,
# but tests can patch them directly
OpenAI = None
OPENAI_AVAILABLE = None
_OpenAIError = None
_APIConnectionError = None
_RateLimitError = None
_APITimeoutError = None


def _get_openai():
    """Lazily import and return the openai module."""
    global _openai_module, _openai_available, OpenAI, OPENAI_AVAILABLE
    global _OpenAIError, _APIConnectionError, _RateLimitError, _APITimeoutError
    if _openai_module is None:
        try:
            import openai as _openai

            _openai_module = _openai
            _openai_available = True
            # Also set module-level names for compatibility
            OpenAI = _openai.OpenAI
            OPENAI_AVAILABLE = True
            _OpenAIError = _openai.OpenAIError
            _APIConnectionError = _openai.APIConnectionError
            _RateLimitError = _openai.RateLimitError
            _APITimeoutError = _openai.APITimeoutError
        except ImportError:
            _openai_module = False
            _openai_available = False
            OPENAI_AVAILABLE = False
    return _openai_module if _openai_module else None


def __getattr__(name):
    """Lazy module-level attribute access for exception classes."""
    # Map exception names to their private globals
    exception_map = {
        "OpenAIError": "_OpenAIError",
        "APIConnectionError": "_APIConnectionError",
        "RateLimitError": "_RateLimitError",
        "APITimeoutError": "_APITimeoutError",
    }
    if name in exception_map:
        # Ensure openai is loaded
        _get_openai()
        # Return the exception class (may be None if openai not available)
        return globals().get(exception_map[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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


# For backward compatibility - make it a simple function call
OPENAI_AVAILABLE = None  # Will be set lazily


def _check_openai_available():
    global OPENAI_AVAILABLE
    if OPENAI_AVAILABLE is None:
        OPENAI_AVAILABLE = _is_openai_available()
    return OPENAI_AVAILABLE


# --- Custom Exceptions ---
class OpenAIConfigurationError(Exception):
    """Custom exception for OpenAI adapter configuration issues."""

    pass


logger = logging.getLogger(__name__)  # Module-level logger


class OpenAIAgentAdapter(Agent):
    """
    Adapter for interacting with AI agents built using the OpenAI SDK.

    This adapter supports OpenAI's chat completions API, including support for
    function calling and tool use, which are common patterns in agent implementations.
    """

    def __init__(self, id: str, config: Dict[str, Any]):
        """
        Initializes the OpenAIAgentAdapter.

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
        # Use hierarchical logger name for TUI handler inheritance
        self.logger = logging.getLogger(
            f"hackagent.router.adapters.OpenAIAgentAdapter.{self.id}"
        )

        if not _is_openai_available():
            msg = (
                f"OpenAI SDK is not installed. Please install it with: pip install openai. "
                f"OpenAIAgentAdapter: {self.id}"
            )
            self.logger.error(msg)
            raise OpenAIConfigurationError(msg)

        self.api_base_url: Optional[str] = self.config.get("endpoint")

        # Model name defaults to "default" for custom endpoints (server decides the model)
        if "name" not in self.config:
            if self.api_base_url:
                # Custom endpoint - use a default model name, server will handle it
                self.model_name = self.config.get("name", "default")
                self.logger.info(
                    "No model name specified for custom endpoint, using 'default'"
                )
            else:
                msg = f"Missing required configuration key 'name' (for model string) for OpenAIAgentAdapter: {self.id}"
                self.logger.error(msg)
                raise OpenAIConfigurationError(msg)
        else:
            self.model_name: str = self.config["name"]

        # Handle API key: can be env var name or the key itself
        api_key_config: Optional[str] = self.config.get("api_key")
        if api_key_config:
            # Try as environment variable first
            self.actual_api_key: Optional[str] = os.environ.get(
                api_key_config, api_key_config
            )
        else:
            # Default to OPENAI_API_KEY environment variable
            self.actual_api_key = os.environ.get("OPENAI_API_KEY")

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
            f"OpenAIAgentAdapter '{self.id}' initialized for model: '{self.model_name}'"
            + (f" API Base: '{self.api_base_url}'" if self.api_base_url else "")
        )

        # Store default generation parameters
        self.default_max_tokens = self.config.get("max_tokens")
        self.default_temperature = self.config.get("temperature", 1.0)
        self.default_tools = self.config.get("tools")
        self.default_tool_choice = self.config.get("tool_choice")

    def _execute_openai_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int],
        temperature: float,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Internal method to generate completions using OpenAI's chat completions API.

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.
            tools: Optional list of tool/function definitions.
            tool_choice: Optional tool choice parameter.
            **kwargs: Additional parameters to pass to the API.

        Returns:
            A dictionary containing the response data and metadata.
        """
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
            result = {
                "success": True,
                "message": response.choices[0].message,
                "finish_reason": response.choices[0].finish_reason,
                "usage": response.usage.model_dump() if response.usage else None,
                "model": response.model,
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

    def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles an incoming request by processing it through the OpenAI API.

        Args:
            request_data: A dictionary containing the request data.
                          Expected keys:
                          - 'prompt': The text prompt to send to the model (will be converted to messages).
                          - 'messages' (optional): Pre-formatted messages list (takes precedence over prompt).
                          - 'max_tokens' (optional): Override default max tokens.
                          - 'temperature' (optional): Override default temperature.
                          - 'tools' (optional): Override default tools.
                          - 'tool_choice' (optional): Override default tool choice.
                          - Any other kwargs to pass to the OpenAI API.

        Returns:
            A dictionary representing the agent's response or an error.
        """
        # Get messages or convert prompt to messages
        messages = request_data.get("messages")
        prompt_text = request_data.get("prompt")

        if not messages and not prompt_text:
            self.logger.warning("No 'messages' or 'prompt' found in request_data.")
            return self._build_error_response(
                error_message="Request data must include either 'messages' or 'prompt' field.",
                status_code=400,
                raw_request=request_data,
            )

        # Convert prompt to messages if messages not provided
        if not messages:
            messages = [{"role": "user", "content": prompt_text}]

        self.logger.info(
            f"Handling request for OpenAI adapter {self.id} with {len(messages)} messages"
        )

        # Get parameters with defaults
        # Support both max_tokens (OpenAI standard) and max_new_tokens (HuggingFace style)
        max_tokens = request_data.get("max_tokens") or request_data.get(
            "max_new_tokens", self.default_max_tokens
        )
        temperature = request_data.get("temperature", self.default_temperature)
        tools = request_data.get("tools", self.default_tools)
        tool_choice = request_data.get("tool_choice", self.default_tool_choice)

        # Get additional kwargs (exclude known parameters)
        excluded_keys = {
            "prompt",
            "messages",
            "max_tokens",
            "max_new_tokens",  # HuggingFace style, converted to max_tokens above
            "temperature",
            "tools",
            "tool_choice",
        }
        additional_kwargs = {
            k: v for k, v in request_data.items() if k not in excluded_keys
        }

        try:
            # Execute the completion
            result = self._execute_openai_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=tools,
                tool_choice=tool_choice,
                **additional_kwargs,
            )

            if not result.get("success"):
                # Handle API errors
                return self._build_error_response(
                    error_message=f"OpenAI API error ({result.get('error_type')}): {result.get('error_message')}",
                    status_code=500,
                    raw_request=request_data,
                )

            # Extract the generated text
            message = result["message"]
            content = message.content if message.content else ""

            # For reasoning models (e.g., o1-preview, o1-mini), check reasoning field
            if not content and hasattr(message, "reasoning") and message.reasoning:
                generated_text = message.reasoning
                self.logger.info(
                    f"OpenAI extracted text from 'reasoning' field (reasoning model) for '{self.model_name}'"
                )
            else:
                generated_text = content

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

            self.logger.info(
                f"Successfully processed request for OpenAI adapter {self.id}."
            )

            return {
                "raw_request": request_data,
                "generated_text": generated_text,
                "processed_response": generated_text,
                "status_code": 200,
                "raw_response_headers": None,
                "raw_response_body": None,
                "agent_specific_data": {
                    "model_name": self.model_name,
                    "finish_reason": result["finish_reason"],
                    "usage": result.get("usage"),
                    "tool_calls": tool_calls,
                    "invoked_parameters": {
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "tools_provided": tools is not None,
                        **additional_kwargs,
                    },
                },
                "error_message": None,
                "agent_id": self.id,
                "adapter_type": "OpenAIAgentAdapter",
            }

        except Exception as e:
            self.logger.exception(
                f"Unexpected error in OpenAIAgentAdapter handle_request for agent {self.id}: {e}"
            )
            return self._build_error_response(
                error_message=f"Unexpected adapter error: {type(e).__name__} - {str(e)}",
                status_code=500,
                raw_request=request_data,
            )

    def _build_error_response(
        self,
        error_message: str,
        status_code: Optional[int],
        raw_request: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Constructs a standardized error response dictionary for the adapter.

        Args:
            error_message: The primary error message string.
            status_code: The HTTP status code associated with the error.
            raw_request: The original request data that led to the error.

        Returns:
            A dictionary representing a standardized error response.
        """
        return {
            "raw_request": raw_request,
            "processed_response": None,
            "generated_text": None,
            "status_code": status_code if status_code is not None else 500,
            "raw_response_headers": None,
            "raw_response_body": None,
            "agent_specific_data": {
                "model_name": self.model_name if hasattr(self, "model_name") else "N/A"
            },
            "error_message": error_message,
            "agent_id": self.id,
            "adapter_type": "OpenAIAgentAdapter",
        }
