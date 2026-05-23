# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
OpenAI-compatible adapter built on top of LiteLLM.

The OpenAI agent type used to talk to the OpenAI SDK directly. As of
issue #379 every chat-completion adapter routes through LiteLLM, so this
class is now a thin specialisation of :class:`LiteLLMAgent` that pulls
its provider prefix + thinking translator out of the
:class:`ProviderConfig` table.
"""

from hackagent.logger import get_logger
from typing import Any, Dict

from hackagent.router.provider_config import get_provider_config
from hackagent.router.types import AgentTypeEnum

from .base import AdapterConfigurationError
from .litellm import LiteLLMAgent


# Keep this exception public for backwards compatibility — downstream code
# (and several tests) import OpenAIConfigurationError from this module.
class OpenAIConfigurationError(AdapterConfigurationError):
    """Custom exception for OpenAI adapter configuration issues."""

    pass


logger = get_logger(__name__)


class OpenAIAgent(LiteLLMAgent):
    """
    Adapter for OpenAI-compatible chat endpoints.

    Configured via the ``OPENAI_SDK`` agent type. Internally uses
    LiteLLM, so any OpenAI-compatible server (the official API, a local
    model server exposing ``/v1/chat/completions``, OpenRouter, etc.)
    works as the endpoint.

    Reasoning / "thinking":
        Driven by the :class:`ProviderConfig` for
        ``AgentTypeEnum.OPENAI_SDK`` — for the o-series and newer GPT
        reasoning models the unified ``thinking`` value is translated
        to ``reasoning_effort``.
    """

    ADAPTER_TYPE = "OpenAIAgent"
    DEFAULT_TEMPERATURE = 1.0

    def __init__(self, id: str, config: Dict[str, Any]):
        # Custom endpoints don't always require a model name; default to
        # ``"default"`` (the server then decides) when an endpoint is set
        # but no model is provided.
        if "name" not in config and config.get("endpoint"):
            config = {**config, "name": config.get("name", "default")}

        try:
            super().__init__(
                id,
                config,
                provider_config=get_provider_config(AgentTypeEnum.OPENAI_SDK),
            )
        except AdapterConfigurationError as e:
            # Re-raise as the OpenAI-flavoured subclass so legacy callers
            # that catch OpenAIConfigurationError keep working.
            raise OpenAIConfigurationError(str(e)) from e

        # For custom endpoints without an API key, use a placeholder so
        # the OpenAI client (under LiteLLM's hood) doesn't error out.
        if not self.actual_api_key and self.api_base_url:
            self.actual_api_key = "not-required"
            self.logger.info(
                f"No API key configured for custom endpoint "
                f"'{self.api_base_url}', using placeholder"
            )
