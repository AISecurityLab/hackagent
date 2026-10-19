# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The result of one model call, and why a call failed."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from hackagent.core.contracts._base import FROZEN
from hackagent.core.contracts.messages import ToolCall


class Usage(BaseModel):
    model_config = FROZEN

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class RawExchange(BaseModel):
    """The provider-level request and response, for callers that need them."""

    model_config = FROZEN

    request: Dict[str, Any] = Field(default_factory=dict)
    status_code: Optional[int] = None
    headers: Optional[Dict[str, Any]] = None
    body: Any = None


class LLMError(BaseModel):
    """Why a call failed. Calls return errors as values."""

    model_config = FROZEN

    message: str
    category: Optional[str] = None
    status_code: Optional[int] = None


class GuardrailInfo(BaseModel):
    """A guardrail blocked the prompt (``before``) or the response (``after``)."""

    model_config = FROZEN

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

    model_config = FROZEN

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

    @property
    def blocked(self) -> bool:
        """True when a guardrail blocked or censored the call."""
        return self.guardrail is not None

    @property
    def guardrail_info(self) -> Dict[str, Any]:
        """Guardrail metadata as a plain dict (empty when not blocked)."""
        if self.guardrail is None:
            return {}
        return {
            "side": self.guardrail.side,
            "message": self.guardrail.message,
            "categories": list(self.guardrail.categories),
            "reasoning": self.guardrail.reasoning,
        }


__all__ = [
    "Completion",
    "GuardrailInfo",
    "LLMError",
    "RawExchange",
    "Usage",
]
