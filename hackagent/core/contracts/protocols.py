# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Protocols for callable models."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, Sequence, Union, runtime_checkable

from hackagent.core.contracts.completion import Completion, LLMError
from hackagent.core.contracts.messages import Message
from hackagent.core.contracts.specs import ModelSpec


@runtime_checkable
class LLM(Protocol):
    """A callable model. Calls never raise for provider errors."""

    def complete(
        self,
        messages: Union[str, Sequence[Union[Message, Mapping[str, Any]]]],
        **params: Any,
    ) -> Completion:
        """Send ``messages`` and return the completion.

        Args:
            messages: A prompt string, or a conversation of messages.
            **params: Per-call overrides such as ``temperature`` or ``max_tokens``.

        Returns:
            The completion; a provider failure is in its ``error``, never raised.
        """

    async def acomplete(
        self,
        messages: Union[str, Sequence[Union[Message, Mapping[str, Any]]]],
        **params: Any,
    ) -> Completion:
        """Asynchronous :meth:`complete`."""

    def with_params(self, **params: Any) -> "LLM":
        """Return an LLM that applies ``params`` to every call."""

    def describe(self) -> ModelSpec:
        """Return the spec that says how this model is reached."""


@runtime_checkable
class LLMFactory(Protocol):
    """Builds the LLM for a role model."""

    def for_role(self, spec: ModelSpec) -> LLM:
        """Build the callable model for ``spec``."""


class CompletionResult(Protocol):
    """The part of a completion that evaluation reads."""

    @property
    def text(self) -> Optional[str]:
        """The generated text, or None when the call produced none."""

    @property
    def ok(self) -> bool:
        """Whether the call succeeded."""

    @property
    def error(self) -> Optional[LLMError]:
        """Why the call failed, or None."""


class CompletionModel(Protocol):
    """Minimal model capability used by domain-independent evaluation."""

    def complete(
        self, messages: Sequence[Mapping[str, Any]], **params: Any
    ) -> CompletionResult:
        """Send ``messages`` and return the result; provider errors are returned, not raised."""


__all__ = [
    "CompletionModel",
    "CompletionResult",
    "LLM",
    "LLMFactory",
]
