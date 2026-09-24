# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Enums. Wire values are persisted and must not change."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Dict, Optional, Union

logger = logging.getLogger(__name__)


class AgentType(str, Enum):
    """How HackAgent talks to a model or agent.

    Chat-completion types (``LITELLM``, ``OPENAI_SDK``, ``OLLAMA``,
    ``LANGCHAIN``) are driven through LiteLLM. ``GOOGLE_ADK``,
    ``CLAUDE_CODE``, ``CODEX``, ``HERMES`` and ``WEB`` use dedicated adapters.
    ``MCP`` and ``A2A`` are placeholders. ``UNKNOWN`` is the fallback when a
    type cannot be inferred.
    """

    GOOGLE_ADK = "GOOGLE_ADK"
    CLAUDE_CODE = "CLAUDE_CODE"
    CODEX = "CODEX"
    HERMES = "HERMES"
    WEB = "WEB"
    LITELLM = "LITELLM"
    OPENAI_SDK = "OPENAI_SDK"
    OLLAMA = "OLLAMA"
    LANGCHAIN = "LANGCHAIN"
    MCP = "MCP"
    A2A = "A2A"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def _missing_(cls, value: object) -> Optional["AgentType"]:
        """Accept any case and the aliases in ``_AGENT_TYPE_ALIASES``."""
        if not isinstance(value, str):
            return None
        key = _normalize_agent_type(value)
        for member in cls:
            if member.value == key:
                return member
        alias = _AGENT_TYPE_ALIASES.get(key)
        return cls(alias) if alias else None

    @classmethod
    def parse(cls, value: Union["AgentType", str, None]) -> "AgentType":
        """Parse leniently: an unrecognised value becomes ``UNKNOWN``."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            try:
                return cls(value)
            except ValueError:
                pass
        logger.warning(
            "Unrecognised agent_type %r; using UNKNOWN. Valid types: %s",
            value,
            [member.value for member in cls],
        )
        return cls.UNKNOWN

    def __str__(self) -> str:
        return str(self.value)


def _normalize_agent_type(value: str) -> str:
    return value.strip().upper().replace("-", "_").replace(" ", "_")


#: Shorthands accepted for :class:`AgentType`, keyed by normalised spelling.
_AGENT_TYPE_ALIASES: Dict[str, str] = {
    "OPENAI": "OPENAI_SDK",
    "GOOGLE": "GOOGLE_ADK",
    "ADK": "GOOGLE_ADK",
    "CLAUDE": "CLAUDE_CODE",
    "CLAUDECODE": "CLAUDE_CODE",
    "CLAUDE_CLI": "CLAUDE_CODE",
    "HERMES_AGENT": "HERMES",
    "HERMESAGENT": "HERMES",
    "HERMES_CLI": "HERMES",
    "NOUS": "HERMES",
    "WEB_AGENT": "WEB",
    "WEBAGENT": "WEB",
    "BROWSER": "WEB",
    "BROWSER_AGENT": "WEB",
    "WEB_CHATBOT": "WEB",
    "WEBCHATBOT": "WEB",
    "WEBCHAT": "WEB",
    "CHATBOT": "WEB",
    "WEBSITE": "WEB",
    "LITE_LLM": "LITELLM",
    "LANG_CHAIN": "LANGCHAIN",
    "OTHER": "UNKNOWN",
}


class RunStatus(str, Enum):
    """Lifecycle of a run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepKind(str, Enum):
    """Kind of a recorded trace step."""

    TOOL_CALL = "TOOL_CALL"
    TOOL_RESPONSE = "TOOL_RESPONSE"
    AGENT_THOUGHT = "AGENT_THOUGHT"
    AGENT_RESPONSE_CHUNK = "AGENT_RESPONSE_CHUNK"
    OTHER = "OTHER"
    MCP_STEP = "MCP_STEP"
    A2_A_COMM = "A2A_COMM"


class EvalStatus(str, Enum):
    """Evaluation outcome of a result."""

    NOT_EVALUATED = "NOT_EVALUATED"
    SUCCESSFUL_JAILBREAK = "SUCCESSFUL_JAILBREAK"
    FAILED_JAILBREAK = "FAILED_JAILBREAK"
    ERROR_AGENT_RESPONSE = "ERROR_AGENT_RESPONSE"
    ERROR_TEST_FRAMEWORK = "ERROR_TEST_FRAMEWORK"
    PASSED_CRITERIA = "PASSED_CRITERIA"
    FAILED_CRITERIA = "FAILED_CRITERIA"


__all__ = [
    "AgentType",
    "EvalStatus",
    "RunStatus",
    "StepKind",
]
