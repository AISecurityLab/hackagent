# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Legacy adapter package.

Issue #379 routed every chat-completion AgentType through LiteLLM
(Phase A–B), hoisted the call path into ``AgentRouter`` (Phase C), and
wired a ``litellm.CustomLogger`` for I/O capture (Phase D). The
adapter classes ``LiteLLMAgent`` / ``OpenAIAgent`` / ``OllamaAgent``
are no longer on the hot path — ``AgentRouter._dispatch_via_litellm``
calls ``litellm.completion`` directly, reading the resolved config off
the instance only for its model name, endpoint, API key, and
generation defaults.

The classes remain available for backwards compatibility with external
callers that import them. ADK has moved to
``hackagent.router.providers.adk``; this package re-exports
``ADKAgent`` from there so old imports keep working.
"""

# Lazy imports for adapters to improve startup time
# These adapters import heavy dependencies (litellm ~2s, google-adk ~0.1s)
from .base import (
    Agent,
    ChatCompletionsAgent,
    AdapterConfigurationError,
    AdapterInteractionError,
    AdapterResponseParsingError,
)


def __getattr__(name):
    """Lazy load adapter classes on first access."""
    if name == "ADKAgent":
        from hackagent.router.providers.adk import ADKAgent

        return ADKAgent
    elif name == "LiteLLMAgent":
        from .litellm import LiteLLMAgent

        return LiteLLMAgent
    elif name == "OpenAIAgent":
        from .openai import OpenAIAgent

        return OpenAIAgent
    elif name == "OllamaAgent":
        from .ollama import OllamaAgent

        return OllamaAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ADKAgent",
    "LiteLLMAgent",
    "OpenAIAgent",
    "OllamaAgent",
    "Agent",
    "ChatCompletionsAgent",
    "AdapterConfigurationError",
    "AdapterInteractionError",
    "AdapterResponseParsingError",
]
