# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
OpenAI-compatible adapter built on top of LiteLLM.

The OpenAI agent type used to talk to the OpenAI SDK directly. As of
issue #379 every chat-completion adapter routes through LiteLLM, so this
class is now a thin specialisation of :class:`LiteLLMAgent` that pins the
provider prefix to ``openai`` and translates the unified ``thinking`` knob
into OpenAI's ``reasoning_effort`` field for the o-series models.
"""

from hackagent.logger import get_logger
from typing import Any, Dict

from .base import AdapterConfigurationError
from .litellm import LiteLLMAgent


# Keep this exception public for backwards compatibility — downstream code
# (and several tests) import OpenAIConfigurationError from this module.
class OpenAIConfigurationError(AdapterConfigurationError):
    """Custom exception for OpenAI adapter configuration issues."""

    pass


logger = get_logger(__name__)


# OpenAI reasoning models that natively understand ``reasoning_effort``.
# ``thinking=True`` defaults to "medium" for these; for other models we fall
# back to LiteLLM's generic ``thinking`` payload.
_OPENAI_REASONING_MODEL_PREFIXES = ("o1", "o3", "o4", "gpt-5", "gpt-6")


class OpenAIAgent(LiteLLMAgent):
    """
    Adapter for OpenAI-compatible chat endpoints.

    Configured via the ``OPENAI_SDK`` agent type. Internally uses LiteLLM,
    so any OpenAI-compatible server (the official API, a local model server
    exposing ``/v1/chat/completions``, OpenRouter, etc.) works as the
    endpoint.

    Reasoning / "thinking":
        Set ``thinking`` in the adapter config or per request to enable or
        disable the model's reasoning. For the o-series and newer GPT
        reasoning models the value is translated to ``reasoning_effort``
        (low/medium/high).
    """

    ADAPTER_TYPE = "OpenAIAgent"
    PROVIDER_PREFIX = "openai"
    DEFAULT_TEMPERATURE = 1.0

    def __init__(self, id: str, config: Dict[str, Any]):
        # Custom endpoints don't always require a model name; default to
        # ``"default"`` (the server then decides) when an endpoint is set
        # but no model is provided.
        if "name" not in config and config.get("endpoint"):
            config = {**config, "name": config.get("name", "default")}

        try:
            super().__init__(id, config)
        except AdapterConfigurationError as e:
            # Re-raise as the OpenAI-flavoured subclass so legacy callers
            # that catch OpenAIConfigurationError keep working.
            raise OpenAIConfigurationError(str(e)) from e

        # For custom endpoints without an API key, use a placeholder so the
        # OpenAI client (under LiteLLM's hood) doesn't error out.
        if not self.actual_api_key and self.api_base_url:
            self.actual_api_key = "not-required"
            self.logger.info(
                f"No API key configured for custom endpoint "
                f"'{self.api_base_url}', using placeholder"
            )

    # ---- thinking translation -------------------------------------------

    def _is_reasoning_model(self) -> bool:
        bare = self.model_name.split("/")[-1]
        return bare.startswith(_OPENAI_REASONING_MODEL_PREFIXES)

    def _apply_thinking(self, litellm_params: Dict[str, Any], thinking: Any) -> None:
        """Map ``thinking`` to ``reasoning_effort`` for OpenAI reasoning models.

        Non-reasoning models fall back to LiteLLM's default ``thinking``
        passthrough, so callers can still attach arbitrary provider payload
        if they need to.
        """
        if thinking is None:
            return

        if self._is_reasoning_model():
            if thinking is True:
                litellm_params["reasoning_effort"] = "medium"
            elif thinking is False:
                # Explicit disable: omit the parameter entirely so the
                # provider falls back to whatever its server-side default is.
                # (OpenAI doesn't currently accept reasoning_effort="off".)
                return
            elif isinstance(thinking, str):
                litellm_params["reasoning_effort"] = thinking
            elif isinstance(thinking, dict):
                effort = thinking.get("reasoning_effort") or thinking.get("effort")
                if effort:
                    litellm_params["reasoning_effort"] = effort
                else:
                    litellm_params["thinking"] = dict(thinking)
            else:
                super()._apply_thinking(litellm_params, thinking)
            return

        # Non-reasoning model: defer to the generic translation.
        super()._apply_thinking(litellm_params, thinking)
