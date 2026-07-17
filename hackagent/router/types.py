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

    These values correspond to the string values used in the API's
    agent_type field.

    Recommended choice for chat-completion targets:
        - **LITELLM** is the general-purpose path. It speaks
          OpenAI, Anthropic, Google Gemini, AWS Bedrock, Azure, Cohere,
          Mistral, Groq, OpenRouter, Together, vLLM, LM Studio,
          Hugging Face Inference, NVIDIA NIM, and ~140 other providers
          out of the box. Pass the model with a provider prefix in
          ``adapter_operational_config["name"]`` — e.g.
          ``"anthropic/claude-3-5-sonnet-20241022"``,
          ``"gemini/gemini-2.0-flash"``,
          ``"bedrock/anthropic.claude-3-sonnet-20240229-v1:0"``,
          ``"groq/llama-3.1-70b-versatile"``.

    Convenience aliases (same behaviour as ``LITELLM`` with the right
    provider prefix; kept for ergonomics and back-compat):
        - **OPENAI_SDK**: OpenAI-compatible endpoint (the official API
          or a local server exposing ``/v1/chat/completions``).
        - **OLLAMA**: targets ``ollama_chat/<model>`` via LiteLLM
          (default endpoint ``http://localhost:11434``).
        - **LANGCHAIN**: LangServe endpoints (treated as OpenAI-compat).

    Custom protocols (gap-fillers that LiteLLM doesn't speak natively):
        - **GOOGLE_ADK**: deployed Google ADK agent server
          (POST /run with session + event protocol). Implemented as a
          per-instance ``litellm.CustomLLM`` provider.
        - **CLAUDE_CODE**: a locally-installed Claude Code CLI, driven in
          headless mode (``claude -p``). Like ADK, implemented as a
          per-instance ``litellm.CustomLLM`` provider that shells out to the
          ``claude`` binary instead of making an HTTP call — no endpoint.
        - **WEB**: a chatbot on a public website, driven through a real browser
          (Playwright). Point it at the site URL and it types each prompt into
          the live chat widget and reads the reply from the page — works on any
          chat UI regardless of transport (WebSocket/SSE/HTTP). Implemented as a
          per-instance ``litellm.CustomLLM`` provider.
        - **MCP**: Model Context Protocol endpoint (placeholder).
        - **A2A**: Agent-to-Agent protocol endpoint (placeholder).

    - **UNKNOWN**: fallback used when the agent type can't be inferred.

    See ``hackagent/examples/litellm_multi_provider/`` for a working
    demo that runs the same attack against several providers by only
    changing the model string.
    """

    GOOGLE_ADK = "GOOGLE_ADK"
    CLAUDE_CODE = "CLAUDE_CODE"
    CODEX = "CODEX"
    WEB = "WEB"
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
    "CLAUDE": "CLAUDE_CODE",
    "CLAUDE-CODE": "CLAUDE_CODE",
    "CLAUDECODE": "CLAUDE_CODE",
    "CODEX": "CODEX",
    "CLAUDE_CLI": "CLAUDE_CODE",
    # The live-browser web agent is now the single web target; accept the old
    # and adjacent names so existing configs keep resolving.
    "WEB-AGENT": "WEB",
    "WEBAGENT": "WEB",
    "BROWSER": "WEB",
    "BROWSER-AGENT": "WEB",
    "WEB-CHATBOT": "WEB",
    "WEBCHATBOT": "WEB",
    "WEBCHAT": "WEB",
    "CHATBOT": "WEB",
    "WEBSITE": "WEB",
    "LITE_LLM": "LITELLM",
    "LITE-LLM": "LITELLM",
}
