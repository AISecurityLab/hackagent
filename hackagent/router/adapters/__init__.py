# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Adapter exception classes + ADKAgent re-export.

Issue #379 completed:
  - Phases A–D moved the chat-completion call path off the adapter
    classes and onto ``AgentRouter._dispatch_via_litellm`` + ``litellm``.
  - Phase E.2 deleted ``LiteLLMAgent`` / ``OpenAIAgent`` / ``OllamaAgent``
    entirely; chat AgentTypes now use ``_ChatRegistration``.
  - ADK lives at ``hackagent.router.providers.adk`` and is re-exported
    here so old imports keep working.

If you were importing ``LiteLLMAgent``, ``OpenAIAgent``, or
``OllamaAgent`` from this package, switch to driving requests through
``AgentRouter.route_request(...)`` instead.
"""

from .base import (
    Agent,
    ChatCompletionsAgent,
    AdapterConfigurationError,
    AdapterInteractionError,
    AdapterResponseParsingError,
)


def __getattr__(name):
    """Lazy load for the surviving adapter class."""
    if name == "ADKAgent":
        from hackagent.router.providers.adk import ADKAgent

        return ADKAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ADKAgent",
    "Agent",
    "ChatCompletionsAgent",
    "AdapterConfigurationError",
    "AdapterInteractionError",
    "AdapterResponseParsingError",
]
