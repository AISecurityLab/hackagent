# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Base classes and common utilities for all agent adapters.

This module provides:
- Common exception classes for adapter errors
- Abstract base class `Agent` with shared functionality
- Utility methods for request validation, response building, and API key resolution
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


# --- Common Exception Classes ---
class AdapterConfigurationError(Exception):
    """Base exception for adapter configuration issues."""

    pass


class AdapterInteractionError(Exception):
    """Base exception for errors during interaction with an agent API."""

    pass


class AdapterResponseParsingError(Exception):
    """Base exception for errors parsing an agent's response."""

    pass


class Agent(ABC):
    """
    Abstract Base Class for all agent implementations.

    It defines a common interface for the router to interact with various agents,
    and provides shared functionality for logging, request validation, response
    building, and configuration handling.

    Attributes:
        id (str): Unique identifier for this agent instance.
        config (Dict[str, Any]): Configuration dictionary for this agent.
        logger (logging.Logger): Hierarchical logger instance.
        model_name (str): Name of the model (if applicable).
        adapter_type (str): Type identifier for the adapter (e.g., "OpenAIAgent").

    Default Generation Parameters (optional, set by subclasses):
        default_max_new_tokens (int): Default maximum tokens to generate.
        default_temperature (float): Default sampling temperature.
        default_top_p (float): Default top-p sampling parameter.
    """

    # Default values for generation parameters (can be overridden by subclasses)
    DEFAULT_MAX_NEW_TOKENS: int = 100
    DEFAULT_TEMPERATURE: float = 0.8
    DEFAULT_TOP_P: float = 0.95

    # Subclasses should set this to their adapter type name
    ADAPTER_TYPE: str = "Agent"

    @abstractmethod
    def __init__(self, id: str, config: Dict[str, Any]):
        """
        Initializes the agent with common setup.

        Args:
            id: A unique identifier for this specific agent instance or type.
            config: Configuration specific to this agent (e.g., API keys, model names).
        """
        self.id = id
        self.config = config

        # Set up hierarchical logger - subclasses can override adapter_type
        self._setup_logger()

        # Initialize optional attributes that subclasses may set
        self.model_name: Optional[str] = None
        self.default_max_new_tokens: int = self.DEFAULT_MAX_NEW_TOKENS
        self.default_temperature: float = self.DEFAULT_TEMPERATURE
        self.default_top_p: float = self.DEFAULT_TOP_P

    def _setup_logger(self) -> None:
        """Set up the hierarchical logger for this adapter instance."""
        self.logger = logging.getLogger(
            f"hackagent.router.adapters.{self.ADAPTER_TYPE}.{self.id}"
        )

    @property
    def adapter_type(self) -> str:
        """Returns the adapter type name."""
        return self.ADAPTER_TYPE

    def _require_config_key(
        self, key: str, error_class: type = AdapterConfigurationError
    ) -> Any:
        """
        Retrieves a required configuration key, raising an error if missing.

        Args:
            key: The configuration key to retrieve.
            error_class: The exception class to raise if key is missing.

        Returns:
            The value of the configuration key.

        Raises:
            error_class: If the key is not present in the config.
        """
        if key not in self.config:
            msg = f"Missing required configuration key '{key}' for {self.ADAPTER_TYPE}: {self.id}"
            self.logger.error(msg)
            raise error_class(msg)
        return self.config[key]

    def _get_config_key(self, key: str, default: Any = None) -> Any:
        """
        Retrieves an optional configuration key with a default value.

        Args:
            key: The configuration key to retrieve.
            default: The default value if key is not present.

        Returns:
            The value of the configuration key or the default.
        """
        return self.config.get(key, default)

    def _init_generation_params(self) -> None:
        """
        Initialize default generation parameters from config.

        This method should be called by subclasses after setting up the basic
        configuration. It reads max_new_tokens, temperature, and top_p from
        the config with fallback to class defaults.
        """
        self.default_max_new_tokens = self._get_config_key(
            "max_new_tokens", self.DEFAULT_MAX_NEW_TOKENS
        )
        self.default_temperature = self._get_config_key(
            "temperature", self.DEFAULT_TEMPERATURE
        )
        self.default_top_p = self._get_config_key("top_p", self.DEFAULT_TOP_P)

    def _resolve_api_key(
        self,
        config_key: str = "api_key",
        env_var_fallback: Optional[str] = None,
    ) -> Optional[str]:
        """
        Resolves an API key from config or environment variables.

        The resolution order is:
        1. If config[config_key] is set, try it as an env var name first
        2. If not found as env var, use the config value directly
        3. If config key not set but env_var_fallback provided, try that env var

        Args:
            config_key: The key in self.config that may contain the API key
                        or the name of an environment variable.
            env_var_fallback: Optional environment variable name to try if
                              config_key is not set.

        Returns:
            The resolved API key, or None if not found.
        """
        api_key_config: Optional[str] = self.config.get(config_key)

        if api_key_config:
            # Try as environment variable first, then use value directly
            resolved = os.environ.get(api_key_config)
            if resolved:
                self.logger.debug(
                    f"Resolved API key from environment variable '{api_key_config}'"
                )
                return resolved
            # Use the config value directly (it might be the actual key)
            return api_key_config

        # Try fallback environment variable
        if env_var_fallback:
            resolved = os.environ.get(env_var_fallback)
            if resolved:
                self.logger.debug(
                    f"Using API key from fallback environment variable '{env_var_fallback}'"
                )
                return resolved

        return None

    def _validate_request(
        self, request_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[List[Dict[str, str]]]]:
        """
        Validates that request_data contains either 'messages' or 'prompt'.

        Args:
            request_data: The incoming request data dictionary.

        Returns:
            A tuple of (is_valid, prompt_text, messages):
            - is_valid: True if request contains valid input
            - prompt_text: The prompt string if provided, else None
            - messages: The messages list if provided, else None
        """
        messages = request_data.get("messages")
        prompt_text = request_data.get("prompt")

        if not messages and not prompt_text:
            return False, None, None

        return True, prompt_text, messages

    def _prompt_to_messages(
        self, prompt: str, role: str = "user"
    ) -> List[Dict[str, str]]:
        """
        Converts a simple prompt string to a messages list format.

        Args:
            prompt: The prompt text to convert.
            role: The role for the message (default: "user").

        Returns:
            A list with a single message dictionary.
        """
        return [{"role": role, "content": prompt}]

    def _get_messages_from_request(
        self, request_data: Dict[str, Any]
    ) -> Optional[List[Dict[str, str]]]:
        """
        Extracts or converts messages from request data.

        If 'messages' is provided, returns it directly.
        If only 'prompt' is provided, converts it to messages format.
        If neither is provided, returns None.

        Args:
            request_data: The incoming request data dictionary.

        Returns:
            A list of message dictionaries, or None if no valid input.
        """
        messages = request_data.get("messages")
        if messages:
            return messages

        prompt = request_data.get("prompt")
        if prompt:
            return self._prompt_to_messages(prompt)

        return None

    def _build_error_response(
        self,
        error_message: str,
        status_code: Optional[int] = None,
        raw_request: Optional[Dict[str, Any]] = None,
        raw_response_body: Optional[str] = None,
        raw_response_headers: Optional[Dict[str, str]] = None,
        agent_specific_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Constructs a standardized error response dictionary.

        Args:
            error_message: The primary error message string.
            status_code: The HTTP status code associated with the error.
            raw_request: The original request data that led to the error.
            raw_response_body: Raw response body if available.
            raw_response_headers: Response headers if available.
            agent_specific_data: Additional adapter-specific data.

        Returns:
            A dictionary representing a standardized error response.
        """
        if agent_specific_data is None:
            agent_specific_data = {}

        # Include model_name in agent_specific_data if available
        if self.model_name and "model_name" not in agent_specific_data:
            agent_specific_data["model_name"] = self.model_name

        return {
            "raw_request": raw_request,
            "processed_response": None,
            "generated_text": None,
            "status_code": status_code if status_code is not None else 500,
            "raw_response_headers": raw_response_headers,
            "raw_response_body": raw_response_body,
            "agent_specific_data": agent_specific_data,
            "error_message": error_message,
            "agent_id": self.id,
            "adapter_type": self.ADAPTER_TYPE,
        }

    def _build_success_response(
        self,
        processed_response: Optional[str],
        raw_request: Optional[Dict[str, Any]] = None,
        raw_response_body: Optional[Any] = None,
        raw_response_headers: Optional[Dict[str, str]] = None,
        agent_specific_data: Optional[Dict[str, Any]] = None,
        status_code: int = 200,
    ) -> Dict[str, Any]:
        """
        Constructs a standardized success response dictionary.

        Args:
            processed_response: The processed/generated text response.
            raw_request: The original request data.
            raw_response_body: Raw response body if available.
            raw_response_headers: Response headers if available.
            agent_specific_data: Additional adapter-specific data.
            status_code: HTTP status code (default: 200).

        Returns:
            A dictionary representing a standardized success response.
        """
        if agent_specific_data is None:
            agent_specific_data = {}

        # Include model_name in agent_specific_data if available
        if self.model_name and "model_name" not in agent_specific_data:
            agent_specific_data["model_name"] = self.model_name

        return {
            "raw_request": raw_request,
            "processed_response": processed_response,
            "generated_text": processed_response,
            "status_code": status_code,
            "raw_response_headers": raw_response_headers,
            "raw_response_body": raw_response_body,
            "agent_specific_data": agent_specific_data,
            "error_message": None,
            "agent_id": self.id,
            "adapter_type": self.ADAPTER_TYPE,
        }

    @abstractmethod
    def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes an incoming request and returns a standardized response.

        The response should be suitable for storage via the API and should ideally
        include enough information to reconstruct the interaction.

        Args:
            request_data: The data for the agent to process. This might include
                          the prompt, session information, user details, etc.
                          Common keys:
                          - 'prompt': Simple text prompt
                          - 'messages': List of message dicts with 'role' and 'content'
                          - 'max_new_tokens': Override default max tokens
                          - 'temperature': Override default temperature
                          - 'top_p': Override default top_p

        Returns:
            A dictionary containing the standardized response with keys:
            - 'raw_request': The original request sent to the underlying agent.
            - 'raw_response_body': The raw response received from the underlying agent.
            - 'raw_response_headers': HTTP headers from the response if applicable.
            - 'processed_response': The key information extracted/processed.
            - 'generated_text': Alias for processed_response (for compatibility).
            - 'status_code': HTTP-like status code of the interaction.
            - 'error_message': Any error message encountered (None on success).
            - 'agent_specific_data': Adapter-specific metadata.
            - 'agent_id': The identifier of this agent.
            - 'adapter_type': The type of this adapter.
        """
        pass

    def get_identifier(self) -> str:
        """Returns the unique identifier for this agent instance or type."""
        return self.id


class ChatCompletionsAgent(Agent):
    """
    Abstract base class for chat completion-based agents.

    This class provides a common implementation for agents that follow the
    chat completions pattern (OpenAI, LiteLLM, Ollama, etc.). It handles:
    - Request validation (prompt or messages)
    - Prompt to messages conversion
    - Parameter extraction with defaults
    - Common handle_request flow with template method pattern

    Subclasses must implement:
    - _execute_completion(): The actual API call to generate completions

    Subclasses may override:
    - _get_completion_parameters(): To add adapter-specific parameters
    - _extract_response_content(): To handle adapter-specific response formats
    - _get_excluded_request_keys(): To exclude additional keys from kwargs
    """

    ADAPTER_TYPE = "ChatCompletionsAgent"

    def __init__(self, id: str, config: Dict[str, Any]):
        """
        Initializes the ChatCompletionsAgent.

        Args:
            id: A unique identifier for this agent instance.
            config: Configuration dictionary for this agent.
        """
        super().__init__(id, config)

    @abstractmethod
    def _execute_completion(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute the completion request to the underlying API.

        This is the core method that subclasses must implement. It should:
        1. Make the API call with the provided messages and parameters
        2. Return a dictionary with the result

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            A dictionary containing:
            - 'success': bool - Whether the call succeeded
            - 'content': str - The generated text (on success)
            - 'error_message': str - Error description (on failure)
            - 'error_type': str - Error category (on failure)
            - 'raw_response': Any - The raw API response (optional)
            - Any additional adapter-specific data
        """
        pass

    def _get_excluded_request_keys(self) -> set:
        """
        Returns the set of keys to exclude when extracting additional kwargs.

        Override this method to add adapter-specific keys that should not
        be passed through to the completion call.

        Returns:
            Set of key names to exclude from additional kwargs.
        """
        return {
            "prompt",
            "messages",
            "max_new_tokens",
            "max_tokens",
            "temperature",
            "top_p",
        }

    def _get_completion_parameters(
        self, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract and prepare parameters for the completion call.

        Override this method to add adapter-specific parameter handling.

        Args:
            request_data: The incoming request data dictionary.

        Returns:
            Dictionary of parameters to pass to _execute_completion.
        """
        # Support both max_tokens (OpenAI style) and max_new_tokens (HuggingFace style)
        max_tokens = request_data.get("max_tokens") or request_data.get(
            "max_new_tokens", self.default_max_new_tokens
        )

        params = {
            "max_tokens": max_tokens,
            "temperature": request_data.get("temperature", self.default_temperature),
            "top_p": request_data.get("top_p", self.default_top_p),
        }

        # Add any additional kwargs not in excluded keys
        excluded_keys = self._get_excluded_request_keys()
        additional_kwargs = {
            k: v for k, v in request_data.items() if k not in excluded_keys
        }
        params.update(additional_kwargs)

        return params

    def _extract_response_content(
        self, completion_result: Dict[str, Any]
    ) -> Optional[str]:
        """
        Extract the generated text content from the completion result.

        Override this method to handle adapter-specific response formats.

        Args:
            completion_result: The result dictionary from _execute_completion.

        Returns:
            The extracted text content, or None if extraction failed.
        """
        return completion_result.get("content")

    def _build_agent_specific_data(
        self,
        completion_result: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build the agent_specific_data dictionary for the response.

        Override this method to add adapter-specific metadata.

        Args:
            completion_result: The result dictionary from _execute_completion.
            parameters: The parameters used for the completion call.

        Returns:
            Dictionary of adapter-specific data to include in response.
        """
        data = {
            "model_name": self.model_name,
            "invoked_parameters": parameters,
        }

        # Include any additional data from the completion result
        for key in ["usage", "finish_reason", "raw_response"]:
            if key in completion_result:
                data[key] = completion_result[key]

        return data

    def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles an incoming request using the chat completions pattern.

        This method implements the common flow for chat completion agents:
        1. Validate request (requires 'prompt' or 'messages')
        2. Convert prompt to messages if needed
        3. Extract completion parameters
        4. Execute the completion via _execute_completion()
        5. Build and return standardized response

        Args:
            request_data: A dictionary containing the request data.
                          Expected keys:
                          - 'prompt': Text prompt (converted to messages)
                          - 'messages': Pre-formatted messages list (takes precedence)
                          - 'max_tokens'/'max_new_tokens': Override default max tokens
                          - 'temperature': Override default temperature
                          - 'top_p': Override default top_p
                          - Additional adapter-specific parameters

        Returns:
            A dictionary representing the agent's response or an error.
        """
        # Step 1: Validate request
        is_valid, prompt_text, messages = self._validate_request(request_data)

        if not is_valid:
            self.logger.warning("No 'messages' or 'prompt' found in request_data.")
            return self._build_error_response(
                error_message="Request data must include either 'messages' or 'prompt' field.",
                status_code=400,
                raw_request=request_data,
            )

        # Step 2: Convert prompt to messages if needed
        if not messages:
            messages = self._prompt_to_messages(prompt_text)

        # Log the request
        log_preview = str(messages[-1].get("content", ""))[:75] if messages else ""
        self.logger.info(
            f"Handling request for {self.ADAPTER_TYPE} adapter {self.id} "
            f"with {len(messages)} messages: '{log_preview}...'"
        )

        # Step 3: Extract completion parameters
        parameters = self._get_completion_parameters(request_data)

        try:
            # Step 4: Execute the completion
            completion_result = self._execute_completion(messages, **parameters)

            # Check for errors
            if not completion_result.get("success", False):
                error_type = completion_result.get("error_type", "unknown")
                error_message = completion_result.get(
                    "error_message", "Unknown error during completion"
                )
                self.logger.error(f"Completion failed ({error_type}): {error_message}")
                return self._build_error_response(
                    error_message=f"{self.ADAPTER_TYPE} error ({error_type}): {error_message}",
                    status_code=500,
                    raw_request=request_data,
                )

            # Step 5: Extract content and build response
            generated_text = self._extract_response_content(completion_result)

            if generated_text is None:
                self.logger.warning("Completion returned no content")
                return self._build_error_response(
                    error_message=f"{self.ADAPTER_TYPE} returned empty result.",
                    status_code=500,
                    raw_request=request_data,
                )

            # Check for generation error markers
            if (
                isinstance(generated_text, str)
                and "[GENERATION_ERROR:" in generated_text
            ):
                return self._build_error_response(
                    error_message=f"{self.ADAPTER_TYPE} generation error: {generated_text}",
                    status_code=500,
                    raw_request=request_data,
                )

            self.logger.info(
                f"Successfully processed request for {self.ADAPTER_TYPE} adapter {self.id}."
            )

            return self._build_success_response(
                processed_response=generated_text,
                raw_request=request_data,
                raw_response_body=completion_result.get("raw_response"),
                agent_specific_data=self._build_agent_specific_data(
                    completion_result, parameters
                ),
            )

        except Exception as e:
            self.logger.exception(
                f"Unexpected error in {self.ADAPTER_TYPE} handle_request for agent {self.id}: {e}"
            )
            return self._build_error_response(
                error_message=f"Unexpected adapter error: {type(e).__name__} - {str(e)}",
                status_code=500,
                raw_request=request_data,
            )
