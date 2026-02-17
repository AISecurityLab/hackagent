# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Ollama Agent Adapter

This adapter provides direct integration with Ollama for running local LLMs.
It uses Ollama's native HTTP API for efficient communication.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import requests

from .base import Agent, AdapterConfigurationError, AdapterInteractionError


# --- Custom Exceptions (subclass from base) ---
class OllamaConfigurationError(AdapterConfigurationError):
    """Custom exception for Ollama adapter configuration issues."""

    pass


class OllamaConnectionError(AdapterInteractionError):
    """Custom exception for Ollama connection issues."""

    pass


logger = logging.getLogger(__name__)


class OllamaAgent(Agent):
    """
    Adapter for interacting with Ollama's native HTTP API.

    This adapter provides direct integration with Ollama for running local LLMs,
    bypassing LiteLLM for more efficient and direct communication.

    Ollama API Endpoints:
    - /api/generate: Generate completions (used for text generation)
    - /api/chat: Chat completions (used for chat-based models)
    - /api/tags: List available models
    - /api/show: Show model information

    Configuration:
    - 'name': Model name (e.g., "llama3", "mistral", "codellama")
    - 'endpoint': Ollama API base URL (default: "http://localhost:11434")
    - 'max_new_tokens': Maximum tokens to generate (default: 100)
    - 'temperature': Sampling temperature (default: 0.8)
    - 'top_p': Top-p sampling parameter (default: 0.95)
    - 'top_k': Top-k sampling parameter (optional)
    - 'num_ctx': Context window size (optional)
    - 'stream': Whether to stream responses (default: False)
    """

    ADAPTER_TYPE = "OllamaAgent"
    DEFAULT_ENDPOINT = "http://localhost:11434"

    def __init__(self, id: str, config: Dict[str, Any]):
        """
        Initializes the OllamaAgent.

        Args:
            id: The unique identifier for this Ollama agent instance.
            config: Configuration dictionary for the Ollama agent.
                Expected keys:
                - 'name': Model name (required, e.g., "llama3", "mistral")
                - 'endpoint' (optional): Ollama API base URL (default: http://localhost:11434)
                - 'max_new_tokens' (optional): Default max tokens for generation (default: 100)
                - 'temperature' (optional): Default temperature (default: 0.8)
                - 'top_p' (optional): Default top_p (default: 0.95)
                - 'top_k' (optional): Default top_k sampling
                - 'num_ctx' (optional): Context window size
                - 'stream' (optional): Enable streaming (default: False)
        """
        super().__init__(id, config)

        # Require model name using base class helper
        self.model_name = self._require_config_key("name", OllamaConfigurationError)

        # Handle endpoint configuration
        # Priority: config['endpoint'] > OLLAMA_BASE_URL env var > default
        self.api_base_url: str = self._get_config_key("endpoint")
        if not self.api_base_url:
            self.api_base_url = os.environ.get("OLLAMA_BASE_URL", self.DEFAULT_ENDPOINT)

        # Normalize endpoint: remove trailing slash and /api/* suffixes
        self.api_base_url = self._normalize_endpoint(self.api_base_url)

        # Initialize default generation parameters using base class method
        self._init_generation_params()

        # Additional Ollama-specific parameters
        self.default_top_k = self._get_config_key("top_k")
        self.default_num_ctx = self._get_config_key("num_ctx")
        self.default_stream = self._get_config_key("stream", False)

        # Request timeout
        self.timeout = self._get_config_key("timeout", 120)

        self.logger.info(
            f"OllamaAgent '{self.id}' initialized for model: '{self.model_name}' "
            f"at endpoint: '{self.api_base_url}'"
        )

    def _normalize_endpoint(self, endpoint: str) -> str:
        """
        Normalize the Ollama endpoint URL.

        Strips trailing slashes and common API path suffixes that users might
        mistakenly include (/api/generate, /api/chat, /api/tags, etc.).

        Args:
            endpoint: The raw endpoint URL from configuration

        Returns:
            Normalized base URL for Ollama API
        """
        endpoint = endpoint.rstrip("/")

        # Common suffixes users mistakenly include
        api_suffixes = ["/api/generate", "/api/chat", "/api/tags", "/api/show", "/api"]
        for suffix in api_suffixes:
            if endpoint.endswith(suffix):
                original = endpoint
                endpoint = endpoint[: -len(suffix)]
                self.logger.info(
                    f"Normalized Ollama endpoint from '{original}' to '{endpoint}' "
                    f"(removed '{suffix}' suffix)"
                )
                break

        return endpoint

    def _build_options(
        self,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        num_ctx: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Build Ollama options dictionary from parameters.

        Args:
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            top_k: Top-k sampling parameter
            num_ctx: Context window size
            **kwargs: Additional options to pass

        Returns:
            Dictionary of Ollama options
        """
        options = {}

        # Use provided values or fall back to defaults
        if max_new_tokens is not None:
            options["num_predict"] = max_new_tokens
        elif self.default_max_new_tokens is not None:
            options["num_predict"] = self.default_max_new_tokens

        if temperature is not None:
            options["temperature"] = temperature
        elif self.default_temperature is not None:
            options["temperature"] = self.default_temperature

        if top_p is not None:
            options["top_p"] = top_p
        elif self.default_top_p is not None:
            options["top_p"] = self.default_top_p

        if top_k is not None:
            options["top_k"] = top_k
        elif self.default_top_k is not None:
            options["top_k"] = self.default_top_k

        if num_ctx is not None:
            options["num_ctx"] = num_ctx
        elif self.default_num_ctx is not None:
            options["num_ctx"] = self.default_num_ctx

        # Add any additional kwargs that are valid Ollama options
        valid_ollama_options = [
            "seed",
            "repeat_penalty",
            "presence_penalty",
            "frequency_penalty",
            "mirostat",
            "mirostat_tau",
            "mirostat_eta",
            "stop",
        ]
        for key in valid_ollama_options:
            if key in kwargs and kwargs[key] is not None:
                options[key] = kwargs[key]

        return options

    def _execute_generate(
        self,
        prompt: str,
        options: Dict[str, Any],
        stream: bool = False,
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a generate request to Ollama's /api/generate endpoint.

        Args:
            prompt: The prompt text
            options: Ollama generation options
            stream: Whether to stream the response
            system: Optional system prompt

        Returns:
            Dictionary containing response data
        """
        url = f"{self.api_base_url}/api/generate"

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": stream,
            "options": options,
        }

        if system:
            payload["system"] = system

        self.logger.info(
            f"Sending generate request to Ollama model '{self.model_name}' at '{url}'"
        )
        self.logger.debug(f"Generate payload: {payload}")

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Failed to connect to Ollama at {url}: {e}")
            raise OllamaConnectionError(
                f"Failed to connect to Ollama at {url}. "
                f"Make sure Ollama is running: `ollama serve`"
            ) from e
        except requests.exceptions.Timeout as e:
            self.logger.error(f"Ollama request timed out after {self.timeout}s: {e}")
            raise OllamaConnectionError(
                f"Ollama request timed out after {self.timeout} seconds"
            ) from e
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"Ollama HTTP error: {e}")
            raise

    def _execute_chat(
        self,
        messages: List[Dict[str, str]],
        options: Dict[str, Any],
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a chat request to Ollama's /api/chat endpoint.

        Args:
            messages: List of chat messages with 'role' and 'content'
            options: Ollama generation options
            stream: Whether to stream the response

        Returns:
            Dictionary containing response data
        """
        url = f"{self.api_base_url}/api/chat"

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
            "options": options,
        }

        self.logger.info(
            f"Sending chat request to Ollama model '{self.model_name}' at '{url}' "
            f"with {len(messages)} messages"
        )
        self.logger.debug(f"Chat payload: {payload}")

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Failed to connect to Ollama at {url}: {e}")
            raise OllamaConnectionError(
                f"Failed to connect to Ollama at {url}. "
                f"Make sure Ollama is running: `ollama serve`"
            ) from e
        except requests.exceptions.Timeout as e:
            self.logger.error(f"Ollama request timed out after {self.timeout}s: {e}")
            raise OllamaConnectionError(
                f"Ollama request timed out after {self.timeout} seconds"
            ) from e
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"Ollama HTTP error: {e}")
            raise

    def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes an incoming request using Ollama's API.

        This method handles both 'prompt' (for /api/generate) and 'messages'
        (for /api/chat) formats, automatically selecting the appropriate endpoint.

        Args:
            request_data: The data for the agent to process. Expected keys:
                - 'prompt' or 'messages': The input for generation
                - 'max_new_tokens' or 'max_tokens' (optional): Override default max tokens
                - 'temperature' (optional): Override default temperature
                - 'top_p' (optional): Override default top_p
                - 'top_k' (optional): Override default top_k
                - 'system' (optional): System prompt for generate endpoint
                - 'stream' (optional): Enable streaming

        Returns:
            A dictionary containing:
            - 'status_code': HTTP-like status code
            - 'raw_request': The original request data
            - 'raw_response': The raw Ollama response
            - 'processed_response': The generated text
            - 'error_message': Error message if any
            - 'agent_specific_data': Ollama-specific metadata
        """
        self.logger.info(
            f"OllamaAgent '{self.id}' handling request for model '{self.model_name}'"
        )

        # Validate request using base class method
        is_valid, prompt, messages = self._validate_request(request_data)

        if not is_valid:
            error_msg = "Request data must include either 'messages' or 'prompt' field."
            self.logger.warning(error_msg)
            return self._build_error_response(
                error_message=error_msg,
                status_code=400,
                raw_request=request_data,
            )

        # Build options from request data
        # Support both 'max_new_tokens' and 'max_tokens' (OpenAI convention)
        max_tokens_value = request_data.get("max_new_tokens") or request_data.get(
            "max_tokens"
        )
        options = self._build_options(
            max_new_tokens=max_tokens_value,
            temperature=request_data.get("temperature"),
            top_p=request_data.get("top_p"),
            top_k=request_data.get("top_k"),
            num_ctx=request_data.get("num_ctx"),
            seed=request_data.get("seed"),
            repeat_penalty=request_data.get("repeat_penalty"),
            stop=request_data.get("stop"),
        )

        stream = request_data.get("stream", self.default_stream)
        system = request_data.get("system")

        try:
            if messages:
                # Use chat endpoint
                raw_response = self._execute_chat(messages, options, stream)
                # Chat response has message.content
                processed_response = raw_response.get("message", {}).get("content", "")
            else:
                # Use generate endpoint
                raw_response = self._execute_generate(prompt, options, stream, system)
                # Generate response has 'response' field
                processed_response = raw_response.get("response", "")

            self.logger.info(
                f"Ollama request successful. Response length: {len(processed_response)} chars"
            )

            return self._build_success_response(
                processed_response=processed_response,
                raw_request=request_data,
                raw_response_body=raw_response,
                agent_specific_data={
                    "model_name": self.model_name,
                    "endpoint": self.api_base_url,
                    "invoked_options": options,
                    "eval_count": raw_response.get("eval_count"),
                    "eval_duration": raw_response.get("eval_duration"),
                    "prompt_eval_count": raw_response.get("prompt_eval_count"),
                    "total_duration": raw_response.get("total_duration"),
                },
            )

        except OllamaConnectionError as e:
            error_msg = f"Ollama connection error: {e}"
            self.logger.error(error_msg)
            return self._build_error_response(
                error_message=error_msg,
                status_code=503,
                raw_request=request_data,
            )

        except requests.exceptions.HTTPError as e:
            error_msg = f"Ollama HTTP error: {e}"
            status_code = e.response.status_code if e.response else 500
            self.logger.error(error_msg)
            return self._build_error_response(
                error_message=error_msg,
                status_code=status_code,
                raw_request=request_data,
                raw_response_body=e.response.text if e.response else None,
            )

        except Exception as e:
            error_msg = (
                f"Ollama generation error: [GENERATION_ERROR: {type(e).__name__}] {e}"
            )
            self.logger.error(error_msg, exc_info=True)
            return self._build_error_response(
                error_message=error_msg,
                status_code=500,
                raw_request=request_data,
            )

    def list_models(self) -> List[Dict[str, Any]]:
        """
        List available models from Ollama.

        Returns:
            List of model information dictionaries
        """
        url = f"{self.api_base_url}/api/tags"
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
        except Exception as e:
            self.logger.error(f"Failed to list Ollama models: {e}")
            return []

    def model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model.

        Returns:
            Dictionary with model information
        """
        url = f"{self.api_base_url}/api/show"
        try:
            response = requests.post(
                url, json={"name": self.model_name}, timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get model info for '{self.model_name}': {e}")
            return {}

    def is_available(self) -> bool:
        """
        Check if Ollama is available and the model is loaded.

        Returns:
            True if Ollama is reachable and the model exists
        """
        try:
            models = self.list_models()
            model_names = [m.get("name", "").split(":")[0] for m in models]
            # Check if our model (without tag) exists
            base_model = self.model_name.split(":")[0]
            return base_model in model_names or self.model_name in [
                m.get("name") for m in models
            ]
        except Exception:
            return False
