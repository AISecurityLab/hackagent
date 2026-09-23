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
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from hackagent.core.contracts import LLM, Message, ModelSpec
from hackagent.core.logging import get_logger
from hackagent.models import envelope as _envelope
from hackagent.models.client import EnvelopeLLM

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


class LLMGuardrail:
    """A guardrail that asks a classifier model for a JSON verdict."""

    def __init__(self, llm: LLM, system_prompt: Optional[str] = None) -> None:
        self.llm = llm
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    def describe(self) -> ModelSpec:
        """The classifier model's spec."""
        return self.llm.describe()

    def check(self, text: str) -> GuardrailResult:
        """Classify ``text``; fails open when the classifier is unavailable."""
        if not text or not text.strip():
            return GuardrailResult(is_safe=True, explanation="No content to classify.")

        completion = self.llm.complete(
            [
                Message(role="system", content=self.system_prompt),
                Message(role="user", content=text),
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


class Guarded(EnvelopeLLM):
    """``llm`` with guardrails applied to every call."""

    def __init__(
        self,
        llm: EnvelopeLLM,
        before: Optional[Guardrail] = None,
        after: Optional[Guardrail] = None,
    ) -> None:
        self.llm = llm
        self.before = before
        self.after = after
        self.instance_id = llm.instance_id
        self.adapter = llm.adapter

    def with_params(self, **params: Any) -> "Guarded":
        return Guarded(self.llm.with_params(**params), self.before, self.after)

    def describe(self) -> ModelSpec:
        return self.llm.describe()

    def _blocked_before(self, request_data: Dict[str, Any]) -> Optional[Dict]:
        if self.before is None:
            return None
        text = _envelope.prompt_text(request_data)
        if not text.strip():
            return None
        return self._verdict_envelope("before", self.before, text, request_data)

    def _censored_after(
        self, request_data: Dict[str, Any], response: Dict[str, Any]
    ) -> Optional[Dict]:
        if self.after is None:
            return None
        text = str(
            response.get("processed_response") or response.get("generated_text") or ""
        ).strip()
        if not text:
            return None
        return self._verdict_envelope("after", self.after, text, request_data)

    def _verdict_envelope(
        self,
        side: str,
        guardrail: Guardrail,
        text: str,
        request_data: Dict[str, Any],
    ) -> Optional[Dict]:
        result = guardrail.check(text)
        if result.is_safe:
            return None
        logger.warning(
            "%s guardrail flagged %s for agent %s: %s",
            side,
            "prompt" if side == "before" else "response",
            self.instance_id,
            result.explanation,
        )
        return _envelope.build_guardrail_envelope(
            side=side,
            agent_id=self.instance_id,
            request_data=request_data,
            categories=list(result.categories),
            reasoning=result.explanation,
        )

    def send(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        blocked = self._blocked_before(request_data)
        if blocked is not None:
            return blocked
        response = self.llm.send(request_data)
        return self._censored_after(request_data, response) or response

    async def asend(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        blocked = await asyncio.to_thread(self._blocked_before, request_data)
        if blocked is not None:
            return blocked
        response = await self.llm.asend(request_data)
        censored = await asyncio.to_thread(self._censored_after, request_data, response)
        return censored or response


__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "Guarded",
    "Guardrail",
    "GuardrailResult",
    "GuardrailSpec",
    "LLMGuardrail",
    "parse_verdict",
]
