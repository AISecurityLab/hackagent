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
        self, messages: Union[str, Sequence[Union[Message, Mapping[str, Any]]]], **params: Any
    ) -> Completion: ...

    async def acomplete(
        self, messages: Union[str, Sequence[Union[Message, Mapping[str, Any]]]], **params: Any
    ) -> Completion: ...

    def with_params(self, **params: Any) -> "LLM": ...

    def describe(self) -> ModelSpec: ...


@runtime_checkable
class LLMFactory(Protocol):
    """Builds the LLM for a role model."""

    def for_role(self, spec: ModelSpec) -> LLM: ...


class CompletionResult(Protocol):
    @property
    def text(self) -> Optional[str]: ...

    @property
    def ok(self) -> bool: ...

    @property
    def error(self) -> Optional[LLMError]: ...


class CompletionModel(Protocol):
    """Minimal model capability used by domain-independent evaluation."""

    def complete(self, messages: Sequence[Mapping[str, Any]], **params: Any) -> CompletionResult: ...


__all__ = [
    "CompletionModel",
    "CompletionResult",
    "LLM",
    "LLMFactory",
]
