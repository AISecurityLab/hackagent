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

from .base import ChatCompletionsAgent, AdapterConfigurationError

# Lazy load litellm - only import when actually needed to avoid ~2s startup delay
# The actual import happens in _get_litellm() method
_litellm_module = None
_litellm_exceptions = None


def _get_litellm():
    """Lazily import litellm module. Returns (litellm_module, is_available)."""
    global _litellm_module, _litellm_exceptions
    if _litellm_module is not None:
        return _litellm_module, True

    try:
        import litellm

        _litellm_module = litellm
        return litellm, True
    except ImportError:
        return None, False


def _get_litellm_exceptions():
    """Lazily import litellm exceptions. Returns dict of exception classes."""
    global _litellm_exceptions
    if _litellm_exceptions is not None:
        return _litellm_exceptions

    try:
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

        _litellm_exceptions = {
            "APIConnectionError": APIConnectionError,
            "APIError": APIError,
            "AuthenticationError": AuthenticationError,
            "BadRequestError": BadRequestError,
            "ContextWindowExceededError": ContextWindowExceededError,
            "NotFoundError": NotFoundError,
            "PermissionDeniedError": PermissionDeniedError,
            "RateLimitError": RateLimitError,
            "ServiceUnavailableError": ServiceUnavailableError,
            "Timeout": Timeout,
        }
    except ImportError:
        # Define dummy exceptions if litellm is not available
        _litellm_exceptions = {
            "APIConnectionError": Exception,
            "APIError": Exception,
            "AuthenticationError": Exception,
            "BadRequestError": Exception,
            "ContextWindowExceededError": Exception,
            "NotFoundError": Exception,
            "PermissionDeniedError": Exception,
            "RateLimitError": Exception,
            "ServiceUnavailableError": Exception,
            "Timeout": Exception,
        }
    return _litellm_exceptions


# --- Custom Exceptions (subclass from base) ---
class LiteLLMConfigurationError(AdapterConfigurationError):
    """Custom exception for LiteLLM adapter configuration issues."""

    pass


logger = logging.getLogger(__name__)  # Module-level logger


class LiteLLMAgent(ChatCompletionsAgent):
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

    ADAPTER_TYPE = "LiteLLMAgent"

    def __init__(self, id: str, config: Dict[str, Any]):
        """
        Initializes the LiteLLMAgent.

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

        # Require model name
        self.model_name = self._require_config_key("name", LiteLLMConfigurationError)
        self.api_base_url: Optional[str] = self._get_config_key("endpoint")

        # Handle API key configuration using base class helper
        self.actual_api_key: Optional[str] = None

        # Determine appropriate fallback env var based on model name
        env_var_fallback = None
        if not self.api_base_url:
            # No custom endpoint - try standard env vars for public APIs
            if self.model_name.startswith("openai/") or self.model_name.startswith(
                "gpt-"
            ):
                env_var_fallback = "OPENAI_API_KEY"
            elif self.model_name.startswith("anthropic/") or self.model_name.startswith(
                "claude-"
            ):
                env_var_fallback = "ANTHROPIC_API_KEY"

        self.actual_api_key = self._resolve_api_key(
            config_key="api_key", env_var_fallback=env_var_fallback
        )

        # When using custom endpoint, determine auth strategy
        if self.api_base_url and not self.actual_api_key:
            if self.model_name.startswith("hackagent/"):
                # hackagent/* models need the HackAgent API key
                # Try to get from config first (passed by router), then environment
                hackagent_key = self._get_config_key("hackagent_api_key")
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
            else:
                # Other custom endpoints (LangChain, local APIs, etc.) - no api_key needed
                self.logger.debug(
                    f"Using custom endpoint '{self.api_base_url}' without api_key - endpoint handles its own auth"
                )

        self.logger.info(
            f"LiteLLMAgent '{self.id}' initialized for model: '{self.model_name}'"
            + (f" API Base: '{self.api_base_url}'" if self.api_base_url else "")
        )

        # Initialize default generation parameters using base class method
        self._init_generation_params()

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
        }

        # Only include api_base and api_key if they are set
        if self.api_base_url:
            litellm_params["api_base"] = self.api_base_url
        if self.actual_api_key:
            litellm_params["api_key"] = self.actual_api_key

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

    def _extract_raw_response_content(self, response: Any, context: str = "") -> str:
        """Extract content from raw litellm response object, handling various response formats."""
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

    def _get_excluded_request_keys(self) -> set:
        """Return keys to exclude when passing additional kwargs."""
        return {
            "prompt",
            "messages",
            "max_new_tokens",
            "max_tokens",
            "temperature",
            "top_p",
        }

    def _execute_completion(
        self, messages: List[Dict[str, str]], **parameters
    ) -> Dict[str, Any]:
        """
        Execute a completion using litellm.completion.

        This implements the abstract method from ChatCompletionsAgent.

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            **parameters: Completion parameters including max_tokens, temperature, top_p.

        Returns:
            Dictionary with:
                - success: Boolean indicating if completion succeeded
                - content: The generated text (if successful)
                - error_type: Type of error (if failed)
                - error_message: Error description (if failed)
                - raw_response: The raw API response (if available)
        """
        litellm, is_available = _get_litellm()
        if not is_available:
            return {
                "success": False,
                "error_type": "configuration_error",
                "error_message": "litellm is not installed",
            }

        exceptions = _get_litellm_exceptions()
        AuthenticationError = exceptions["AuthenticationError"]

        try:
            # Log agent interaction for TUI visibility
            if messages:
                msg_preview = str(messages[-1].get("content", ""))[:100]
                self.logger.info(f"🌐 Querying model {self.model_name}")
                self.logger.debug(f"   Message preview: {msg_preview}...")

            # Extract parameters
            max_tokens = parameters.get("max_tokens", self.default_max_new_tokens)
            temperature = parameters.get("temperature", self.default_temperature)
            top_p = parameters.get("top_p", self.default_top_p)

            # Remove these from kwargs to avoid duplication
            kwargs = {
                k: v
                for k, v in parameters.items()
                if k not in {"max_tokens", "temperature", "top_p"}
            }

            litellm_params = self._prepare_litellm_params(
                messages, max_tokens, temperature, top_p, **kwargs
            )
            response = litellm.completion(**litellm_params)

            content = self._extract_raw_response_content(response)
            self.logger.info(f"✅ Model responded ({len(content)} chars)")

            return {
                "success": True,
                "content": content,
                "raw_response": response,
            }

        except AuthenticationError as e:
            error_msg = f"Authentication failed for model '{self.model_name}': {str(e)}"
            self.logger.error(error_msg)
            # Re-raise authentication errors so they can be handled specially
            llm_provider = e.llm_provider if hasattr(e, "llm_provider") else "unknown"
            raise AuthenticationError(error_msg, llm_provider, self.model_name) from e
        except Exception as e:
            self.logger.error(
                f"LiteLLM completion call failed for model '{self.model_name}': {e}",
                exc_info=True,
            )
            return {
                "success": False,
                "error_type": type(e).__name__,
                "error_message": str(e),
            }

    def _execute_litellm_completion_with_messages(
        self,
        messages: List[Dict[str, str]],
        max_new_tokens: int,
        temperature: float,
        top_p: float,
        **kwargs,
    ) -> str:
        """Execute a single completion using litellm.completion with messages format.

        This is a convenience method that wraps _execute_completion for backwards compatibility.
        """
        result = self._execute_completion(
            messages,
            max_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            **kwargs,
        )

        if result.get("success"):
            return result.get("content", "")
        else:
            return f"[GENERATION_ERROR: {result.get('error_type', 'UNKNOWN')}]"

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

        litellm, is_available = _get_litellm()
        if not is_available:
            raise LiteLLMConfigurationError("litellm is not installed")

        exceptions = _get_litellm_exceptions()
        AuthenticationError = exceptions["AuthenticationError"]

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
                completion_text = self._extract_raw_response_content(
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
