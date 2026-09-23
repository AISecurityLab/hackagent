# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared vocabulary: the values that cross package boundaries.

Every package may import this module. It holds data definitions and
protocols only, no behaviour beyond validation and small properties.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Protocol,
    Sequence,
    Union,
    runtime_checkable,
)

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums (wire values are persisted and must not change)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Messages and completions
# ---------------------------------------------------------------------------

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class ToolCall(BaseModel):
    """A tool invocation requested by a model."""

    model_config = _FROZEN

    id: Optional[str] = None
    name: str
    arguments: str = ""


class Message(BaseModel):
    """One chat message. ``content`` is text or OpenAI-style content parts."""

    model_config = _FROZEN

    role: Literal["system", "user", "assistant", "tool"]
    content: Union[str, List[Dict[str, Any]], None] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    tool_call_id: Optional[str] = None


class Usage(BaseModel):
    model_config = _FROZEN

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class RawExchange(BaseModel):
    """The provider-level request and response, for callers that need them."""

    model_config = _FROZEN

    request: Dict[str, Any] = Field(default_factory=dict)
    status_code: Optional[int] = None
    headers: Optional[Dict[str, Any]] = None
    body: Any = None


class LLMError(BaseModel):
    """Why a call failed. Calls return errors as values."""

    model_config = _FROZEN

    message: str
    category: Optional[str] = None
    status_code: Optional[int] = None


class GuardrailInfo(BaseModel):
    """A guardrail blocked the prompt (``before``) or the response (``after``)."""

    model_config = _FROZEN

    side: Literal["before", "after"]
    message: str = ""
    categories: List[str] = Field(default_factory=list)
    reasoning: str = ""


class Completion(BaseModel):
    """The result of one model call.

    Replaces the response dict: ``generated_text`` / ``processed_response``
    become ``text``; ``error_message`` / ``error_category`` become ``error``;
    ``agent_specific_data`` usage, finish reason, model and invoked
    parameters become typed fields; ``raw_response_*`` and ``raw_request``
    become ``raw``; a guardrail envelope becomes ``guardrail``.
    """

    model_config = _FROZEN

    text: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    usage: Optional[Usage] = None
    finish_reason: Optional[str] = None
    provider_model: Optional[str] = None
    invoked_parameters: Dict[str, Any] = Field(default_factory=dict)
    raw: Optional[RawExchange] = None
    error: Optional[LLMError] = None
    guardrail: Optional[GuardrailInfo] = None
    extra: Dict[str, Any] = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True when the call produced a usable response."""
        return self.error is None and self.guardrail is None


# ---------------------------------------------------------------------------
# Model and judge specifications
# ---------------------------------------------------------------------------


class ModelSpec(BaseModel):
    """How to reach one model: the target or any role model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    identifier: str
    endpoint: Optional[str] = None
    agent_type: AgentType = AgentType.OPENAI_SDK
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    max_tokens: Optional[int] = Field(default=None, ge=1)
    temperature: Optional[float] = Field(default=None, ge=0.0)
    top_p: Optional[float] = None
    timeout: Optional[float] = Field(default=None, gt=0)
    thinking: Optional[bool] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class JudgeSpec(ModelSpec):
    """A judge model and how to read its verdicts."""

    type: str = "harmbench"
    range: Optional[Literal["binary", "decimal"]] = None
    system_prompt: Optional[str] = None


# ---------------------------------------------------------------------------
# Goals, samples and verdicts
# ---------------------------------------------------------------------------


class Goal(BaseModel):
    """One goal to attack, with its position in the run."""

    model_config = _FROZEN

    text: str
    index: int = Field(ge=0)
    labels: Dict[str, str] = Field(default_factory=dict)
    extra: Dict[str, Any] = Field(default_factory=dict)


class Sample(BaseModel):
    """One exchange to judge."""

    model_config = _FROZEN

    goal: str
    prompt: str = ""
    response: str = ""
    tool_calls: List[ToolCall] = Field(default_factory=list)


class JudgeVote(BaseModel):
    """One judge's score for a sample, on the judge's native scale."""

    model_config = _FROZEN

    judge: str
    score: Optional[float] = None
    success: Optional[bool] = None
    explanation: str = ""


#: Every verdict score is normalised onto 0..NORMALIZED_SCORE_MAX.
NORMALIZED_SCORE_MAX = 10.0


class Verdict(BaseModel):
    """The combined judgement of a sample."""

    model_config = _FROZEN

    success: bool
    score: float = Field(ge=0.0, le=NORMALIZED_SCORE_MAX)
    votes: List[JudgeVote] = Field(default_factory=list)
    explanation: str = ""


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class LLM(Protocol):
    """A callable model. Calls never raise for provider errors."""

    def complete(
        self, messages: Union[str, Sequence[Message]], **params: Any
    ) -> Completion: ...

    async def acomplete(
        self, messages: Union[str, Sequence[Message]], **params: Any
    ) -> Completion: ...

    def with_params(self, **params: Any) -> "LLM": ...

    def describe(self) -> ModelSpec: ...


@runtime_checkable
class LLMFactory(Protocol):
    """Builds the LLM for a role model."""

    def for_role(self, spec: ModelSpec) -> LLM: ...


__all__ = [
    "AgentType",
    "Completion",
    "EvalStatus",
    "Goal",
    "GuardrailInfo",
    "JudgeSpec",
    "JudgeVote",
    "LLM",
    "LLMError",
    "LLMFactory",
    "Message",
    "ModelSpec",
    "NORMALIZED_SCORE_MAX",
    "RawExchange",
    "RunStatus",
    "Sample",
    "StepKind",
    "ToolCall",
    "Usage",
    "Verdict",
]
