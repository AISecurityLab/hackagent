# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

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
        from .google_adk import ADKAgent

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
