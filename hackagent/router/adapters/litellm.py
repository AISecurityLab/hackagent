# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


from hackagent.logger import get_logger
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


logger = get_logger(__name__)  # Module-level logger


# Provider prefixes that LiteLLM recognises natively. When a model string
# already starts with one of these, we leave it alone instead of prepending
# our own provider prefix.
_KNOWN_LITELLM_PROVIDER_PREFIXES = (
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
    "ollama_chat/",
    "groq/",
    "mistral/",
    "cohere/",
    "gemini/",
    "deepseek/",
)


class LiteLLMAgent(ChatCompletionsAgent):
    """
    Unified adapter that routes every chat-completion request through LiteLLM.

    All chat-style adapters (OpenAI-SDK, Ollama, LangChain, plain LiteLLM)
    subclass this class. Each subclass sets ``PROVIDER_PREFIX`` to declare
    which LiteLLM provider the AgentType maps to (e.g. ``"openai"`` for an
    OpenAI-compatible endpoint, ``"ollama_chat"`` for Ollama). The base class
    handles model-string normalisation, endpoint plumbing, generation
    parameters, tool calls, and the unified ``thinking`` knob.

    Thinking knob:
        Any subclass can be asked to enable or disable provider reasoning by
        setting ``thinking`` in the adapter config or per-request payload.
        Accepted values:
            - bool: ``True`` enables thinking with provider defaults,
              ``False`` disables it explicitly.
            - dict: passed through verbatim (e.g.
              ``{"type": "enabled", "budget_tokens": 1024}`` for Anthropic).
            - str: a reasoning effort level (``"low"``, ``"medium"``,
              ``"high"``) — translated by the subclass as appropriate.
            - int: budget tokens for providers that accept a budget.
        Subclasses override ``_apply_thinking`` to translate the value into
        the provider-specific request fields.
    """

    ADAPTER_TYPE = "LiteLLMAgent"
    # When set, the model string passed to LiteLLM is prefixed with
    # ``"{PROVIDER_PREFIX}/"`` unless it already starts with a known
    # LiteLLM provider prefix. ``None`` means "let LiteLLM auto-detect".
    PROVIDER_PREFIX: Optional[str] = None

    def __init__(self, id: str, config: Dict[str, Any]):
        """
        Initialise the adapter from configuration.

        Args:
            id: Unique identifier for this adapter instance.
            config: Configuration dict. Supported keys:
                - ``name``: model string (e.g. ``"llama3"`` or
                  ``"gpt-4"``). Required.
                - ``endpoint`` (optional): API base URL.
                - ``api_key`` (optional): API key or environment variable name.
                - ``max_tokens`` / ``temperature`` / ``top_p`` (optional).
                - ``tools`` / ``tool_choice`` (optional): function-calling
                  definitions, passed through to LiteLLM.
                - ``thinking`` (optional): see class docstring.
                - ``extra_body`` (optional): provider-specific request body.
        """
        super().__init__(id, config)

        # Require model name
        self.model_name = self._require_config_key("name", LiteLLMConfigurationError)
        self.api_base_url: Optional[str] = self._get_config_key("endpoint")

        # Determine the effective LiteLLM model string (with provider prefix).
        self.litellm_model = self._resolve_litellm_model(self.model_name)

        # Handle API key configuration using base class helper
        env_var_fallback = self._default_api_key_env_var()
        self.actual_api_key = self._resolve_api_key(
            config_key="api_key", env_var_fallback=env_var_fallback
        )

        # When using a custom endpoint without credentials, rely on
        # endpoint-side auth (common for local model servers).
        if self.api_base_url and not self.actual_api_key:
            self.logger.debug(
                f"Using custom endpoint '{self.api_base_url}' without api_key - "
                "endpoint handles its own auth"
            )

        self.logger.info(
            f"{self.ADAPTER_TYPE} '{self.id}' initialised for LiteLLM model: "
            f"'{self.litellm_model}'"
            + (f" API Base: '{self.api_base_url}'" if self.api_base_url else "")
        )

        # Default generation parameters (max_tokens, temperature, top_p).
        self._init_generation_params()

        # Pass-through fields commonly supplied via config.
        self.default_tools = self._get_config_key("tools")
        self.default_tool_choice = self._get_config_key("tool_choice")
        self.default_extra_body = self._get_config_key("extra_body")
        self.default_thinking = self._get_config_key("thinking")

    # ---- subclass extension points ---------------------------------------

    def _resolve_litellm_model(self, raw_model: str) -> str:
        """Return the model string to pass to ``litellm.completion``.

        Honors the subclass ``PROVIDER_PREFIX`` while leaving names that
        already carry an explicit LiteLLM provider prefix untouched.
        """
        if self.PROVIDER_PREFIX is None:
            return raw_model
        if raw_model.startswith(_KNOWN_LITELLM_PROVIDER_PREFIXES):
            return raw_model
        return f"{self.PROVIDER_PREFIX}/{raw_model}"

    def _default_api_key_env_var(self) -> Optional[str]:
        """Return the env var used as a fallback when no API key is configured."""
        if self.api_base_url:
            return None
        if self.litellm_model.startswith(("openai/", "gpt-")):
            return "OPENAI_API_KEY"
        if self.litellm_model.startswith(("anthropic/", "claude-")):
            return "ANTHROPIC_API_KEY"
        return None

    def _apply_thinking(self, litellm_params: Dict[str, Any], thinking: Any) -> None:
        """Translate the unified ``thinking`` value into LiteLLM params.

        The default implementation mirrors LiteLLM's own conventions:
            - dict: forwarded verbatim as ``thinking=...``
            - str: forwarded as ``reasoning_effort=...``
            - int: forwarded as ``thinking={"type": "enabled",
              "budget_tokens": int}``
            - True/False: forwarded as
              ``thinking={"type": "enabled" | "disabled"}``
        Subclasses override this method when their provider needs different
        field names (e.g. Ollama's ``think``).
        """
        if thinking is None:
            return
        if isinstance(thinking, dict):
            litellm_params["thinking"] = dict(thinking)
        elif isinstance(thinking, str):
            litellm_params["reasoning_effort"] = thinking
        elif isinstance(thinking, bool):
            litellm_params["thinking"] = {"type": "enabled" if thinking else "disabled"}
        elif isinstance(thinking, int):
            litellm_params["thinking"] = {
                "type": "enabled",
                "budget_tokens": int(thinking),
            }
        else:
            # Best-effort passthrough for unknown shapes.
            litellm_params["thinking"] = thinking

    # ---- request preparation --------------------------------------------

    def _prepare_litellm_params(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        top_p: float,
        **kwargs,
    ) -> Dict[str, Any]:
        """Build the kwargs dict for ``litellm.completion``."""
        litellm_params: Dict[str, Any] = {
            "model": self.litellm_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }

        if self.api_base_url:
            litellm_params["api_base"] = self.api_base_url
        if self.actual_api_key:
            litellm_params["api_key"] = self.actual_api_key

        # When the caller provides a custom endpoint without a recognised
        # LiteLLM provider prefix, treat it as OpenAI-compatible. This
        # preserves the previous behaviour for plain LiteLLM users and gives
        # us a sensible default for LangChain-style endpoints.
        if self.api_base_url and not self.litellm_model.startswith(
            _KNOWN_LITELLM_PROVIDER_PREFIXES
        ):
            litellm_params["custom_llm_provider"] = "openai"
            litellm_params["extra_headers"] = {"User-Agent": "HackAgent/0.1.0"}
        elif self.api_base_url:
            # Keep the User-Agent for outbound requests even when a provider
            # prefix is supplied — useful for self-hosted proxies.
            litellm_params["extra_headers"] = {"User-Agent": "HackAgent/0.1.0"}

        # Thinking handling — config default merged with per-request override.
        thinking = kwargs.pop("thinking", self.default_thinking)
        self._apply_thinking(litellm_params, thinking)

        # Tool calls.
        tools = kwargs.pop("tools", self.default_tools)
        tool_choice = kwargs.pop("tool_choice", self.default_tool_choice)
        if tools:
            litellm_params["tools"] = tools
            if tool_choice is not None:
                litellm_params["tool_choice"] = tool_choice

        # Provider-specific extra body (e.g. OpenRouter ``reasoning``).
        extra_body = kwargs.pop("extra_body", self.default_extra_body)
        if extra_body is not None:
            litellm_params["extra_body"] = (
                dict(extra_body) if isinstance(extra_body, dict) else extra_body
            )

        litellm_params.update(kwargs)
        return litellm_params

    def _extract_raw_response_content(self, response: Any, context: str = "") -> str:
        """Extract content from a litellm response object."""
        if not (response and response.choices and response.choices[0].message):
            self.logger.warning(
                f"LiteLLM received unexpected response structure for model "
                f"'{self.litellm_model}'{context}. Response: {response}"
            )
            return "[GENERATION_ERROR: UNEXPECTED_RESPONSE]"

        message = response.choices[0].message
        content = message.content if message.content else ""

        # Reasoning models surface their output in a dedicated field; fall
        # back to it when the regular content is empty.
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

        if content:
            return content
        if reasoning_content:
            self.logger.debug(
                f"LiteLLM using reasoning content for model "
                f"'{self.litellm_model}' (content field was empty)"
            )
            return reasoning_content

        self.logger.warning(
            f"LiteLLM received empty content and no reasoning field for model "
            f"'{self.litellm_model}'{context}. Message: {message}"
        )
        return "[GENERATION_ERROR: EMPTY_RESPONSE]"

    def _extract_tool_calls(self, response: Any) -> Optional[List[Dict[str, Any]]]:
        """Extract OpenAI-style tool_calls from a LiteLLM response, if any."""
        try:
            message = response.choices[0].message
        except (AttributeError, IndexError, TypeError):
            return None
        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            return None
        result = []
        for tc in tool_calls:
            try:
                result.append(
                    {
                        "id": getattr(tc, "id", None),
                        "type": getattr(tc, "type", "function"),
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )
            except AttributeError:
                continue
        return result or None

    def _get_excluded_request_keys(self) -> set:
        """Return keys handled explicitly so they aren't re-passed as kwargs."""
        return {
            "prompt",
            "messages",
            "max_tokens",
            "temperature",
            "top_p",
            "tools",
            "tool_choice",
            "thinking",
            "extra_body",
        }

    def _get_completion_parameters(
        self, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract completion parameters with provider-agnostic passthroughs."""
        params = super()._get_completion_parameters(request_data)
        # Carry passthrough fields when present in the request.
        for key in ("tools", "tool_choice", "thinking", "extra_body"):
            if key in request_data:
                params[key] = request_data[key]
        return params

    # ---- execution -------------------------------------------------------

    def _execute_completion(
        self, messages: List[Dict[str, str]], **parameters
    ) -> Dict[str, Any]:
        """Execute a completion via ``litellm.completion``."""
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
            if messages:
                msg_preview = str(messages[-1].get("content", ""))[:100]
                self.logger.info(f"🌐 Querying model {self.litellm_model}")
                self.logger.debug(f"   Message preview: {msg_preview}...")

            max_tokens = parameters.pop("max_tokens", self.default_max_tokens)
            temperature = parameters.pop("temperature", self.default_temperature)
            top_p = parameters.pop("top_p", self.default_top_p)

            litellm_params = self._prepare_litellm_params(
                messages, max_tokens, temperature, top_p, **parameters
            )
            response = litellm.completion(**litellm_params)

            content = self._extract_raw_response_content(response)
            tool_calls = self._extract_tool_calls(response)

            self.logger.info(f"✅ Model responded ({len(content)} chars)")

            result: Dict[str, Any] = {
                "success": True,
                "content": content,
                "raw_response": response,
            }
            if tool_calls is not None:
                result["tool_calls"] = tool_calls
            # Surface useful diagnostics when available.
            try:
                result["finish_reason"] = response.choices[0].finish_reason
            except (AttributeError, IndexError, TypeError):
                pass
            try:
                if response.usage is not None:
                    result["usage"] = response.usage.model_dump()
            except AttributeError:
                pass
            try:
                result["provider_model"] = response.model
            except AttributeError:
                pass

            return result

        except AuthenticationError as e:
            error_msg = f"Authentication failed for model '{self.litellm_model}': {e}"
            self.logger.error(error_msg)
            llm_provider = e.llm_provider if hasattr(e, "llm_provider") else "unknown"
            raise AuthenticationError(
                error_msg, llm_provider, self.litellm_model
            ) from e
        except Exception as e:
            self.logger.error(
                f"LiteLLM completion call failed for model '{self.litellm_model}': {e}",
                exc_info=True,
            )
            return {
                "success": False,
                "error_type": type(e).__name__,
                "error_message": str(e),
            }

    # ---- response shaping ------------------------------------------------

    def _build_agent_specific_data(
        self,
        completion_result: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Include common LiteLLM metadata (finish_reason, usage, tools)."""
        data = super()._build_agent_specific_data(completion_result, parameters)
        for key in ("finish_reason", "usage", "provider_model"):
            value = completion_result.get(key)
            if value is not None and key not in data:
                data[key] = value
        if completion_result.get("tool_calls"):
            data["tool_calls"] = completion_result["tool_calls"]
        return data

    # ---- legacy convenience helpers -------------------------------------

    def _execute_litellm_completion_with_messages(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        top_p: float,
        **kwargs,
    ) -> str:
        """Single completion call returning the generated text only."""
        result = self._execute_completion(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            **kwargs,
        )
        if result.get("success"):
            return result.get("content", "")
        return f"[GENERATION_ERROR: {result.get('error_type', 'UNKNOWN')}]"

    def _execute_litellm_completion(
        self,
        texts: List[str],
        max_tokens: int,
        temperature: float,
        top_p: float,
        **kwargs,
    ) -> List[str]:
        """Generate completions for a batch of prompt strings."""
        if not texts:
            return []

        litellm, is_available = _get_litellm()
        if not is_available:
            raise LiteLLMConfigurationError("litellm is not installed")

        exceptions = _get_litellm_exceptions()
        AuthenticationError = exceptions["AuthenticationError"]

        completions: List[str] = []
        self.logger.info(
            f"Sending {len(texts)} requests via LiteLLM to model "
            f"'{self.litellm_model}'..."
        )

        for text_prompt in texts:
            messages = [{"role": "user", "content": text_prompt}]
            try:
                litellm_params = self._prepare_litellm_params(
                    messages, max_tokens, temperature, top_p, **kwargs
                )
                response = litellm.completion(**litellm_params)
                completion_text = self._extract_raw_response_content(
                    response, context=f" for prompt '{text_prompt[:50]}...'"
                )
            except AuthenticationError as e:
                error_msg = (
                    f"Authentication failed for model '{self.litellm_model}': {e}"
                )
                self.logger.error(error_msg)
                llm_provider = (
                    e.llm_provider if hasattr(e, "llm_provider") else "unknown"
                )
                raise AuthenticationError(
                    error_msg, llm_provider, self.litellm_model
                ) from e
            except Exception as e:
                self.logger.error(
                    f"LiteLLM completion call failed for model "
                    f"'{self.litellm_model}' for prompt "
                    f"'{text_prompt[:50]}...': {e}",
                    exc_info=True,
                )
                completion_text = f" [GENERATION_ERROR: {type(e).__name__}]"

            completions.append(text_prompt + completion_text)

        self.logger.info(
            f"Finished LiteLLM requests for model '{self.litellm_model}'. "
            f"Generated {len(completions)} responses."
        )
        return completions
