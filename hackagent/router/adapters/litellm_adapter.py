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
        self.logger = logging.getLogger(
            f"{__name__}.{self.id}"
        )  # Instance-specific logger

        if "name" not in self.config:
            msg = (
                f"Missing required configuration key 'name' (for model string) for "
                f"LiteLLMAgentAdapter: {self.id}"
            )
            self.logger.error(msg)
            raise LiteLLMConfigurationError(msg)

        self.model_name: str = self.config["name"]
        self.api_base_url: Optional[str] = self.config.get("endpoint")

        api_key: Optional[str] = self.config.get("api_key")
        self.actual_api_key: Optional[str] = (
            os.environ.get(api_key) if api_key else None
        )

        self.logger.info(
            f"LiteLLMAgentAdapter '{self.id}' initialized for model: '{self.model_name}'"
            + (f" API Base: '{self.api_base_url}'" if self.api_base_url else "")
            + (f" API Key: '{api_key}'" if api_key else "")
        )

        # Store default generation parameters
        self.default_max_new_tokens = self.config.get("max_new_tokens", 100)
        self.default_temperature = self.config.get("temperature", 0.8)
        self.default_top_p = self.config.get("top_p", 0.95)

    def _execute_litellm_completion(
        self,
        texts: List[str],
        max_new_tokens: int,
        temperature: float,
        top_p: float,
        **kwargs,
    ) -> List[str]:
        """
        Internal method to generate completions using litellm.completion.
        Relies on litellm's internal retry mechanisms if applicable.
        """
        if not texts:
            return []

        completions = []
        self.logger.info(
            f"Sending {len(texts)} requests via LiteLLM to model '{self.model_name}'..."
        )

        for text_prompt in texts:
            messages = [{"role": "user", "content": text_prompt}]
            completion_text_suffix = ""  # To store error or actual completion

            try:
                litellm_params = {
                    "model": self.model_name,
                    "messages": messages,
                    "max_tokens": max_new_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                    "api_base": self.api_base_url,
                    "api_key": self.actual_api_key,
                }
                litellm_params.update(kwargs)

                # Single call to litellm.completion
                response = litellm.completion(**litellm_params)

                if response and response.choices and response.choices[0].message:
                    message = response.choices[0].message
                    content = message.content if message.content else ""

                    # For reasoning models (e.g., moonshotai/kimi-k2-thinking, o1 models)
                    # check for reasoning field when content is empty
                    if (
                        not content
                        and hasattr(message, "reasoning")
                        and message.reasoning
                    ):
                        completion_text_suffix = message.reasoning
                        self.logger.info(
                            f"LiteLLM extracted text from 'reasoning' field (reasoning model) for '{self.model_name}'"
                        )
                    elif content:
                        completion_text_suffix = content
                    else:
                        # No content or reasoning - unexpected
                        self.logger.warning(
                            f"LiteLLM received empty content and no reasoning field for model '{self.model_name}' for prompt '{text_prompt[:50]}...'. Message: {message}"
                        )
                        completion_text_suffix = " [GENERATION_ERROR: EMPTY_RESPONSE]"
                else:
                    self.logger.warning(
                        f"LiteLLM received unexpected response structure for model '{self.model_name}' for prompt '{text_prompt[:50]}...'. Response: {response}"
                    )
                    completion_text_suffix = " [GENERATION_ERROR: UNEXPECTED_RESPONSE]"

            except Exception as e:
                self.logger.error(
                    f"LiteLLM completion call failed for model '{self.model_name}' for prompt '{text_prompt[:50]}...': {e}",
                    exc_info=True,
                )
                completion_text_suffix = f" [GENERATION_ERROR: {type(e).__name__}]"

            full_text = text_prompt + completion_text_suffix
            completions.append(full_text)

        self.logger.info(
            f"Finished LiteLLM requests for model '{self.model_name}'. Generated {len(completions)} responses."
        )
        return completions

    def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles an incoming request by processing it through LiteLLM.

        Args:
            request_data: A dictionary containing the request data.
                          Expected keys:
                          - 'prompt': The text prompt to send to the LLM.
                          - 'max_new_tokens' (optional): Override default max tokens.
                          - 'temperature' (optional): Override default temperature.
                          - 'top_p' (optional): Override default top_p.
                          - Any other kwargs to pass to litellm.completion.
        Returns:
            A dictionary representing the agent's response or an error.
        """
        prompt_text = request_data.get("prompt")
        if not prompt_text:
            self.logger.warning("No 'prompt' found in request_data.")
            return self._build_error_response(
                error_message="Request data must include a 'prompt' field.",
                status_code=400,
                raw_request=request_data,
            )

        self.logger.info(
            f"Handling request for LiteLLM adapter {self.id} with prompt: '{prompt_text[:75]}...'"
        )

        max_new_tokens = request_data.get("max_new_tokens", self.default_max_new_tokens)
        temperature = request_data.get("temperature", self.default_temperature)
        top_p = request_data.get("top_p", self.default_top_p)

        excluded_keys = {"prompt", "max_new_tokens", "temperature", "top_p"}
        additional_kwargs = {
            k: v for k, v in request_data.items() if k not in excluded_keys
        }

        try:
            # The _execute_litellm_completion method is now synchronous
            completions = self._execute_litellm_completion(
                texts=[prompt_text],
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                **additional_kwargs,
            )

            if completions and isinstance(completions, list) and len(completions) > 0:
                full_response_text = completions[0]
                processed_response = full_response_text

                if "[GENERATION_ERROR:" in processed_response:
                    self.logger.warning(
                        f"LiteLLM generation indicated an error for adapter {self.id}: {processed_response}"
                    )
                    error_detail = processed_response[
                        len(prompt_text) :
                    ].strip()  # Get the error part
                    return self._build_error_response(
                        error_message=f"LiteLLM generation error: {error_detail}",
                        status_code=500,
                        raw_request=request_data,
                    )

                self.logger.info(
                    f"Successfully processed request for LiteLLM adapter {self.id}."
                )
                return {
                    "raw_request": request_data,
                    "processed_response": processed_response,
                    "status_code": 200,
                    "raw_response_headers": None,
                    "raw_response_body": None,
                    "agent_specific_data": {
                        "model_name": self.model_name,  # Updated key
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
            else:
                self.logger.error(
                    f"LiteLLM returned empty or invalid completions for adapter {self.id}."
                )
                return self._build_error_response(
                    error_message="LiteLLM returned empty or invalid result.",
                    status_code=500,
                    raw_request=request_data,
                )
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
        return {
            "raw_request": raw_request,
            "processed_response": None,
            "status_code": status_code if status_code is not None else 500,
            "raw_response_headers": None,
            "raw_response_body": None,
            "agent_specific_data": {
                "model_name": self.model_name if hasattr(self, "model_name") else "N/A"
            },  # Updated key
            "error_message": error_message,
            "agent_id": self.id,
            "adapter_type": "LiteLLMAgentAdapter",
        }
