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

# Attempt to import litellm, but catch ImportError if not installed.
try:
    import litellm
    from litellm.exceptions import (
        APIConnectionError,
        APIError,
        AuthenticationError,
        BadRequestError,
        ContextWindowExceededError,
        NotFoundError,
        PermissionDeniedError,
        RateLimitError,
        ServiceUnavailableError,
        Timeout,
    )

    LITELLM_AVAILABLE = True
except ImportError:
    litellm = None  # type: ignore

    # Define dummy exceptions if litellm is not available so the rest of the code can type hint
    class APIConnectionError(Exception):
        pass

    class RateLimitError(Exception):
        pass

    class ServiceUnavailableError(Exception):
        pass

    class Timeout(Exception):
        pass

    class APIError(Exception):
        pass

    class AuthenticationError(Exception):
        pass

    class BadRequestError(Exception):
        pass

    class NotFoundError(Exception):
        pass

    class PermissionDeniedError(Exception):
        pass

    class ContextWindowExceededError(Exception):
        pass

    LITELLM_AVAILABLE = False


from .base import Agent  # Updated import


# --- Custom Exceptions ---
class LiteLLMConfigurationError(Exception):
    """Custom exception for LiteLLM adapter configuration issues."""

    pass


logger = logging.getLogger(__name__)  # Module-level logger


class LiteLLMAgentAdapter(Agent):
    """
    Adapter for interacting with LLMs via the LiteLLM library.

    This adapter supports multiple LLM providers through LiteLLM's unified interface.
    For custom/self-hosted endpoints, the endpoint URL must be provided correctly:

    OpenAI-Compatible Endpoints:
    - Provide the base URL ending with /v1 (e.g., "http://localhost:8000/v1")
    - The OpenAI client will automatically append /chat/completions
    - Example: endpoint="http://localhost:8000/v1" → requests to http://localhost:8000/v1/chat/completions

    Non-OpenAI Protocols:
    - Use the appropriate agent type (LANGCHAIN, MCP, A2A) instead of routing through LiteLLM
    - LANGCHAIN: Use LangServe endpoints (e.g., "http://localhost:8000/invoke")
    - MCP: Use Model Context Protocol adapter (not LiteLLM)
    - A2A: Use Agent-to-Agent protocol adapter (not LiteLLM)
    """

    def __init__(self, id: str, config: Dict[str, Any]):
        """
        Initializes the LiteLLMAgentAdapter.

        Args:
            id: The unique identifier for this LiteLLM agent instance.
            config: Configuration dictionary for the LiteLLM agent.
                          Expected keys:
                          - 'name': Model string for LiteLLM (e.g., "ollama/llama3").
                          - 'endpoint' (optional): Base URL for the API.
                          - 'api_key' (optional): Name of the environment variable holding the API key.
                          - 'max_new_tokens' (optional): Default max tokens for generation (defaults to 100).
                          - 'temperature' (optional): Default temperature (defaults to 0.8).
                          - 'top_p' (optional): Default top_p (defaults to 0.95).
        """
        super().__init__(id, config)
        # Use hierarchical logger name for TUI handler inheritance
        self.logger = logging.getLogger(
            f"hackagent.router.adapters.LiteLLMAgentAdapter.{self.id}"
        )

        if "name" not in self.config:
            msg = f"Missing required configuration key 'name' (for model string) for LiteLLMAgentAdapter: {self.id}"
            self.logger.error(msg)
            raise LiteLLMConfigurationError(msg)

        self.model_name: str = self.config["name"]
        self.api_base_url: Optional[str] = self.config.get("endpoint")

        # Handle API key configuration
        # Important: When using a custom endpoint, the agent at that endpoint handles its own auth.
        # Exception: hackagent/* models are HackAgent services that need the HackAgent API key.
        api_key_config: Optional[str] = self.config.get("api_key")
        self.actual_api_key: Optional[str] = None

        if api_key_config:
            # Explicit api_key provided - try as env var name first, then use value directly
            self.actual_api_key = os.environ.get(api_key_config)
            if self.actual_api_key is None:
                self.actual_api_key = api_key_config

        elif not self.api_base_url:
            # No custom endpoint and no explicit api_key - try standard env vars for public APIs
            # This only applies when calling public APIs directly (OpenAI, Anthropic, etc.)
            if self.model_name.startswith("openai/") or self.model_name.startswith(
                "gpt-"
            ):
                self.actual_api_key = os.environ.get("OPENAI_API_KEY")
                if self.actual_api_key:
                    self.logger.debug(
                        "Using OPENAI_API_KEY from environment for public API"
                    )
            elif self.model_name.startswith("anthropic/") or self.model_name.startswith(
                "claude-"
            ):
                self.actual_api_key = os.environ.get("ANTHROPIC_API_KEY")
                if self.actual_api_key:
                    self.logger.debug(
                        "Using ANTHROPIC_API_KEY from environment for public API"
                    )

        # When using custom endpoint, determine auth strategy
        if self.api_base_url and not self.actual_api_key:
            if self.model_name.startswith("hackagent/"):
                # hackagent/* models need the HackAgent API key
                # Try to get from config first (passed by router), then environment
                hackagent_key = self.config.get("hackagent_api_key")
                if not hackagent_key:
                    hackagent_key = os.environ.get("HACKAGENT_API_KEY")

                if hackagent_key:
                    self.actual_api_key = hackagent_key
                    self.logger.debug(
                        f"Using HACKAGENT_API_KEY for {self.model_name} service"
                    )
                else:
                    self.logger.warning(
                        f"HackAgent model '{self.model_name}' requires HACKAGENT_API_KEY but none found. "
                        f"Requests will likely fail with authentication errors."
                    )
                    # Use placeholder to avoid immediate failure, let backend reject with clear error
                    self.actual_api_key = "sk-placeholder-missing-hackagent-key"
            else:
                # Other custom endpoints (LangChain, etc.) - use placeholder
                # The actual endpoint will handle its own authentication
                self.actual_api_key = "sk-placeholder-key-for-custom-endpoint"
                self.logger.debug(
                    f"Using custom endpoint '{self.api_base_url}' - agent handles its own authentication"
                )

        self.logger.info(
            f"LiteLLMAgentAdapter '{self.id}' initialized for model: '{self.model_name}'"
            + (f" API Base: '{self.api_base_url}'" if self.api_base_url else "")
        )

        # Store default generation parameters
        self.default_max_new_tokens = self.config.get("max_new_tokens", 100)
        self.default_temperature = self.config.get("temperature", 0.8)
        self.default_top_p = self.config.get("top_p", 0.95)

    def _prepare_litellm_params(
        self,
        messages: List[Dict[str, str]],
        max_new_tokens: int,
        temperature: float,
        top_p: float,
        **kwargs,
    ) -> Dict[str, Any]:
        """Prepare parameters for litellm.completion call."""
        litellm_params = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "api_base": self.api_base_url,
            "api_key": self.actual_api_key,
        }

        # Handle custom endpoint scenarios (LangChain, custom agents, etc.)
        if self.api_base_url:
            # For custom endpoints, treat as OpenAI-compatible unless model has a known provider prefix
            if not any(
                self.model_name.startswith(prefix)
                for prefix in [
                    "openai/",
                    "anthropic/",
                    "azure/",
                    "bedrock/",
                    "vertex_ai/",
                    "huggingface/",
                    "replicate/",
                    "together_ai/",
                    "anyscale/",
                    "ollama/",
                ]
            ):
                # Model name without provider prefix - treat as OpenAI-compatible custom endpoint
                litellm_params["custom_llm_provider"] = "openai"
                # Use the endpoint exactly as provided - user specifies the complete URL
                # For OpenAI-compatible endpoints, this should be the base URL (e.g., http://host:port/v1)
                # and the OpenAI client will append /chat/completions automatically
                litellm_params["api_base"] = self.api_base_url
            elif self.model_name.startswith("hackagent/"):
                # Special handling for hackagent/* models
                litellm_params["custom_llm_provider"] = "openai"
                litellm_params["api_base"] = self.api_base_url

            litellm_params["extra_headers"] = {"User-Agent": "HackAgent/0.1.0"}

        litellm_params.update(kwargs)
        return litellm_params

    def _extract_response_content(self, response: Any, context: str = "") -> str:
        """Extract content from litellm response, handling various response formats."""
        if not (response and response.choices and response.choices[0].message):
            self.logger.warning(
                f"LiteLLM received unexpected response structure for model '{self.model_name}'{context}. Response: {response}"
            )
            return "[GENERATION_ERROR: UNEXPECTED_RESPONSE]"

        message = response.choices[0].message
        content = message.content if message.content else ""

        # Try to extract reasoning content from various possible locations
        reasoning_content = None
        if hasattr(message, "reasoning_content") and message.reasoning_content:
            reasoning_content = message.reasoning_content
        elif hasattr(message, "reasoning") and message.reasoning:
            reasoning_content = message.reasoning
        elif (
            hasattr(message, "provider_specific_fields")
            and message.provider_specific_fields
        ):
            reasoning_content = message.provider_specific_fields.get(
                "reasoning_content"
            ) or message.provider_specific_fields.get("reasoning")

        # Use content if available, otherwise fall back to reasoning content
        if content:
            return content
        elif reasoning_content:
            self.logger.debug(
                f"LiteLLM using reasoning content for model '{self.model_name}' (content field was empty)"
            )
            return reasoning_content
        else:
            self.logger.warning(
                f"LiteLLM received empty content and no reasoning field for model '{self.model_name}'{context}. Message: {message}"
            )
            return "[GENERATION_ERROR: EMPTY_RESPONSE]"

    def _execute_litellm_completion_with_messages(
        self,
        messages: List[Dict[str, str]],
        max_new_tokens: int,
        temperature: float,
        top_p: float,
        **kwargs,
    ) -> str:
        """Execute a single completion using litellm.completion with messages format."""
        try:
            # Log agent interaction for TUI visibility
            if messages:
                msg_preview = str(messages[-1].get("content", ""))[:100]
                self.logger.info(f"🌐 Querying model {self.model_name}")
                self.logger.debug(f"   Message preview: {msg_preview}...")

            litellm_params = self._prepare_litellm_params(
                messages, max_new_tokens, temperature, top_p, **kwargs
            )
            response = litellm.completion(**litellm_params)

            content = self._extract_response_content(response)
            self.logger.info(f"✅ Model responded ({len(content)} chars)")
            return content

        except AuthenticationError as e:
            error_msg = f"Authentication failed for model '{self.model_name}': {str(e)}"
            self.logger.error(error_msg)
            llm_provider = e.llm_provider if hasattr(e, "llm_provider") else "unknown"
            raise AuthenticationError(error_msg, llm_provider, self.model_name) from e
        except Exception as e:
            self.logger.error(
                f"LiteLLM completion call failed for model '{self.model_name}': {e}",
                exc_info=True,
            )
            return f"[GENERATION_ERROR: {type(e).__name__}]"

    def _execute_litellm_completion(
        self,
        texts: List[str],
        max_new_tokens: int,
        temperature: float,
        top_p: float,
        **kwargs,
    ) -> List[str]:
        """Generate completions for multiple text prompts using litellm.completion."""
        if not texts:
            return []

        completions = []
        self.logger.info(
            f"Sending {len(texts)} requests via LiteLLM to model '{self.model_name}'..."
        )

        for text_prompt in texts:
            messages = [{"role": "user", "content": text_prompt}]

            try:
                litellm_params = self._prepare_litellm_params(
                    messages, max_new_tokens, temperature, top_p, **kwargs
                )
                response = litellm.completion(**litellm_params)
                completion_text = self._extract_response_content(
                    response, context=f" for prompt '{text_prompt[:50]}...'"
                )

            except AuthenticationError as e:
                error_msg = (
                    f"Authentication failed for model '{self.model_name}': {str(e)}"
                )
                self.logger.error(error_msg)
                llm_provider = (
                    e.llm_provider if hasattr(e, "llm_provider") else "unknown"
                )
                raise AuthenticationError(
                    error_msg, llm_provider, self.model_name
                ) from e
            except Exception as e:
                self.logger.error(
                    f"LiteLLM completion call failed for model '{self.model_name}' for prompt '{text_prompt[:50]}...': {e}",
                    exc_info=True,
                )
                completion_text = f" [GENERATION_ERROR: {type(e).__name__}]"

            full_text = text_prompt + completion_text
            completions.append(full_text)

        self.logger.info(
            f"Finished LiteLLM requests for model '{self.model_name}'. Generated {len(completions)} responses."
        )
        return completions

    def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an incoming request by processing it through LiteLLM.

        Args:
            request_data: Dictionary containing request data with keys:
                - 'prompt': Text prompt to send to the LLM
                - 'messages': Pre-formatted messages list (takes precedence over prompt)
                - 'max_new_tokens'/'max_tokens': Override default max tokens
                - 'temperature': Override default temperature
                - 'top_p': Override default top_p
                - Other kwargs to pass to litellm.completion

        Returns:
            Dictionary representing the agent's response or an error
        """
        messages = request_data.get("messages")
        prompt_text = request_data.get("prompt")

        if not messages and not prompt_text:
            return self._build_error_response(
                error_message="Request data must include either 'messages' or 'prompt' field.",
                status_code=400,
                raw_request=request_data,
            )

        # Convert prompt to messages if not provided
        if not messages:
            messages = [{"role": "user", "content": prompt_text}]
            log_text = str(prompt_text)[:75]
        else:
            log_text = str(messages[0].get("content", ""))[:75] if messages else ""

        self.logger.info(
            f"Handling request for LiteLLM adapter {self.id} with prompt: '{log_text}...'"
        )

        max_new_tokens = request_data.get("max_new_tokens") or request_data.get(
            "max_tokens", self.default_max_new_tokens
        )
        temperature = request_data.get("temperature", self.default_temperature)
        top_p = request_data.get("top_p", self.default_top_p)

        excluded_keys = {
            "prompt",
            "messages",
            "max_new_tokens",
            "max_tokens",
            "temperature",
            "top_p",
        }
        additional_kwargs = {
            k: v for k, v in request_data.items() if k not in excluded_keys
        }

        try:
            completion_text = self._execute_litellm_completion_with_messages(
                messages=messages,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                **additional_kwargs,
            )

            if not completion_text:
                return self._build_error_response(
                    error_message="LiteLLM returned empty result.",
                    status_code=500,
                    raw_request=request_data,
                )

            if "[GENERATION_ERROR:" in completion_text:
                return self._build_error_response(
                    error_message=f"LiteLLM generation error: {completion_text}",
                    status_code=500,
                    raw_request=request_data,
                )

            self.logger.info(
                f"Successfully processed request for LiteLLM adapter {self.id}."
            )
            return {
                "raw_request": request_data,
                "processed_response": completion_text,
                "status_code": 200,
                "raw_response_headers": None,
                "raw_response_body": None,
                "agent_specific_data": {
                    "model_name": self.model_name,
                    "invoked_parameters": {
                        "max_new_tokens": max_new_tokens,
                        "temperature": temperature,
                        "top_p": top_p,
                        **additional_kwargs,
                    },
                },
                "error_message": None,
                "agent_id": self.id,
                "adapter_type": "LiteLLMAgentAdapter",
            }

        except AuthenticationError as e:
            error_msg = f"Authentication failed for model '{self.model_name}': {str(e)}"
            self.logger.error(error_msg)
            llm_provider = e.llm_provider if hasattr(e, "llm_provider") else "unknown"
            raise AuthenticationError(error_msg, llm_provider, self.model_name) from e
        except Exception as e:
            self.logger.exception(
                f"Unexpected error in LiteLLMAgentAdapter handle_request for agent {self.id}: {e}"
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
        """Build a standardized error response dictionary."""
        return {
            "raw_request": raw_request,
            "processed_response": None,
            "status_code": status_code if status_code is not None else 500,
            "raw_response_headers": None,
            "raw_response_body": None,
            "agent_specific_data": {
                "model_name": self.model_name if hasattr(self, "model_name") else "N/A"
            },
            "error_message": error_message,
            "agent_id": self.id,
            "adapter_type": "LiteLLMAgentAdapter",
        }
