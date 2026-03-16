# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
SDK-specific types for HackAgent router.

These types are used internally by the SDK and are not part of the API models.
The API uses plain strings for agent_type, but the SDK provides enums for type safety.
"""

from enum import Enum


class AgentTypeEnum(str, Enum):
    """
    Enumeration of supported agent types in the HackAgent SDK.

    These values correspond to the string values used in the API's agent_type field.

    Endpoint Requirements by Type:
    - GOOGLE_ADK: Google Agent Development Kit endpoint (custom protocol)
    - LITELLM: Any LLM endpoint via LiteLLM (multi-provider support)
    - OPENAI_SDK: OpenAI-compatible endpoint (should end with /v1 base path)
    - OLLAMA: Ollama local LLM endpoint (default: http://localhost:11434)
    - LANGCHAIN: LangServe endpoint (typically /invoke or /stream)
    - MCP: Model Context Protocol endpoint (MCP-specific protocol)
    - A2A: Agent-to-Agent protocol endpoint (A2A-specific protocol)
    - UNKNOWN: Unknown agent type (fallback)

    Note: For OpenAI-compatible endpoints (OPENAI_SDK, LITELLM with custom endpoints),
    provide the base URL ending in /v1 (e.g., http://localhost:8000/v1).
    The OpenAI client will automatically append /chat/completions.

    For Ollama endpoints, provide the base URL (e.g., http://localhost:11434).
    The adapter will automatically use /api/generate or /api/chat as appropriate.
    """

    GOOGLE_ADK = "GOOGLE_ADK"
    LITELLM = "LITELLM"
    OPENAI_SDK = "OPENAI_SDK"
    OLLAMA = "OLLAMA"
    LANGCHAIN = "LANGCHAIN"
    MCP = "MCP"
    A2A = "A2A"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value: object) -> "AgentTypeEnum":
        """Allow case-insensitive lookup and common shorthand aliases.

        For example ``AgentTypeEnum("openai")`` resolves to
        ``AgentTypeEnum.OPENAI_SDK``.
        """
        if not isinstance(value, str):
            return None
        normalised = value.strip().upper()
        # Direct case-insensitive match against member values
        for member in cls:
            if member.value == normalised:
                return member
        # Shorthand alias map
        alias_target = _AGENT_TYPE_ALIASES.get(normalised)
        if alias_target:
            return cls(alias_target)
        return None

    def __str__(self) -> str:
        return str(self.value)


# Shorthand aliases accepted in config files and test scripts.
# Keys are the normalised (upper-cased, stripped) input strings.
_AGENT_TYPE_ALIASES: dict = {
    "OPENAI": "OPENAI_SDK",
    "OPENAI-SDK": "OPENAI_SDK",
    "GOOGLE": "GOOGLE_ADK",
    "ADK": "GOOGLE_ADK",
    "LITE_LLM": "LITELLM",
    "LITE-LLM": "LITELLM",
}
