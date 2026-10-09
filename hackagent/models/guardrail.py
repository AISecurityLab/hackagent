# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Guardrails around a model: check prompts before, and responses after.

A guardrail classifies text as safe or unsafe. :class:`Guarded` wraps an
LLM with an optional ``before`` guardrail (checks the prompt; a blocked
prompt never reaches the model) and an optional ``after`` guardrail
(checks the response; a flagged response is withheld). Either way the call
returns a completion whose ``guardrail`` field says what happened.

The default :class:`LLMGuardrail` asks a classifier model for a JSON
verdict. It fails open: an unavailable or unparseable classifier lets the
text through, so a misconfigured guardrail never blocks all traffic.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field, replace
from typing import Any, List, Literal, Mapping, Optional, Protocol, Sequence

from hackagent.core.contracts import GuardrailInfo, ModelSpec
from hackagent.core.contracts.protocols import CompletionModel
from hackagent.core.logging import get_logger
from hackagent.models.completions.cli import last_user_text
from hackagent.models.model import Model
from hackagent.models.response import ModelResponse

logger = get_logger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are a content safety classifier. "
    "Evaluate the text provided by the user and respond ONLY with a JSON "
    "object in the following format:\n"
    '{"safe": true|false, "categories": [<list of harm categories if unsafe>], '
    '"reasoning": "<one-sentence explanation>"}\n'
    "Do not include any text outside the JSON object."
)


class GuardrailSpec(ModelSpec):
    """A guardrail classifier model, with an optional custom system prompt."""

    system_prompt: Optional[str] = None


@dataclass(frozen=True)
class GuardrailResult:
    """Outcome of one guardrail check.

    Attributes:
        is_safe: ``True`` if the text passed the check.
        explanation: The classifier's reason.
        categories: Harm categories flagged (empty when safe).
        raw_response: The classifier's raw text, if any.
    """

    is_safe: bool
    explanation: str
    categories: List[str] = field(default_factory=list)
    raw_response: Optional[str] = None


class Guardrail(Protocol):
    """Anything that can classify a piece of text."""

    def check(self, text: str) -> GuardrailResult: ...


class ModelGuardrail:
    """A guardrail that asks a classifier model for a JSON verdict."""

    def __init__(
        self, llm: CompletionModel, system_prompt: Optional[str] = None
    ) -> None:
        self.llm = llm
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    def describe(self) -> ModelSpec:
        """The classifier model's spec."""
        return getattr(self.llm, "describe")()

    def check(self, text: str) -> GuardrailResult:
        """Classify ``text``; fails open when the classifier is unavailable."""
        if not text or not text.strip():
            return GuardrailResult(is_safe=True, explanation="No content to classify.")

        completion = self.llm.complete(
            [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": text},
            ],
            max_tokens=256,
            temperature=0,
        )
        if completion.error is not None:
            logger.warning(
                "Guardrail model error — failing open. Error: %s",
                completion.error.message,
            )
            return GuardrailResult(
                is_safe=True,
                explanation=f"Guardrail unavailable: {completion.error.message}",
            )
        return parse_verdict(completion.text or "")


LLMGuardrail = ModelGuardrail


def parse_verdict(raw: str) -> GuardrailResult:
    """Parse ``{"safe": ..., "categories": [...], "reasoning": ...}``.

    Falls back to keyword detection when the text is not JSON.
    """
    if not raw or not raw.strip():
        return GuardrailResult(
            is_safe=True,
            explanation="Empty guardrail response — failing open.",
            raw_response=raw,
        )
    try:
        result = json.loads(raw.strip())
    except json.JSONDecodeError:
        lower = raw.lower()
        if "unsafe" in lower or '"safe": false' in lower:
            return GuardrailResult(
                is_safe=False, explanation=raw.strip()[:200], raw_response=raw
            )
        return GuardrailResult(
            is_safe=True,
            explanation="Unparseable guardrail response — failing open.",
            raw_response=raw,
        )
    is_safe = result.get("safe", True) is True
    return GuardrailResult(
        is_safe=is_safe,
        explanation=result.get("reasoning", ""),
        categories=result.get("categories", []) if not is_safe else [],
        raw_response=raw,
    )


class GuardedModel(Model):
    """Apply the shared guardrail policy to native completions."""

    def __init__(
        self,
        model: Model,
        before: Optional[Guardrail] = None,
        after: Optional[Guardrail] = None,
    ) -> None:
        self.model = model
        self.before = before
        self.after = after

    def _check(
        self, side: Literal["before", "after"], text: str, response: ModelResponse
    ) -> ModelResponse:
        guardrail = self.before if side == "before" else self.after
        if guardrail is None or not text.strip():
            return response
        result = guardrail.check(text)
        if result.is_safe:
            return response
        info = GuardrailInfo(
            side=side, categories=result.categories, reasoning=result.explanation
        )
        return replace(
            response,
            text="",
            raw_response=None,
            reasoning_content=None,
            tool_calls=[],
            guardrail=info,
            metadata={
                **response.metadata,
                "ok": False,
                "guardrail": info.model_dump(exclude_none=True),
            },
        )

    def complete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        blocked = self._check(
            "before", last_user_text(list(messages)) or "", ModelResponse(text="")
        )
        if blocked.guardrail is not None:
            return blocked
        response = self.model.complete(messages, **overrides)
        return (
            self._check("after", response.text, response) if response.ok else response
        )

    async def acomplete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        blocked = await asyncio.to_thread(
            self._check,
            "before",
            last_user_text(list(messages)) or "",
            ModelResponse(text=""),
        )
        if blocked.guardrail is not None:
            return blocked
        response = await self.model.acomplete(messages, **overrides)
        return (
            await asyncio.to_thread(self._check, "after", response.text, response)
            if response.ok
            else response
        )


__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "GuardedModel",
    "Guardrail",
    "GuardrailResult",
    "GuardrailSpec",
    "LLMGuardrail",
    "ModelGuardrail",
    "parse_verdict",
]
