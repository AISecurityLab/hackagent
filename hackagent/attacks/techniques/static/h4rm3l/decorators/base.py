# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Base classes and callable types for h4rm3l decorators."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable
from typing import TypeAlias

from numpy.random import RandomState

from ...base import Completion

DecorationResult: TypeAlias = str | Awaitable[str]


class PromptDecorator:
    """Base class for all h4rm3l decorators.

    Each decorator implements :meth:`decorate` to transform a prompt string.
    Decorators can be chained with :meth:`then`.
    """

    def __init__(self, seed: int = 42) -> None:
        self._random_state = RandomState(seed=seed)
        self._chain: list[PromptDecorator] = [self]

    def decorate(self, prompt: str) -> DecorationResult:
        raise NotImplementedError

    def then(self, composing_decorator: "PromptDecorator") -> "PromptDecorator":
        """Chain this decorator with another, returning a new composite decorator."""
        d = PromptDecorator()

        def decorate(prompt: str) -> DecorationResult:
            first = self.decorate(prompt)
            if inspect.isawaitable(first):

                async def await_chain() -> str:
                    second = composing_decorator.decorate(await first)
                    return await second if inspect.isawaitable(second) else second

                return await_chain()
            return composing_decorator.decorate(first)

        d.decorate = decorate
        left_chain = getattr(self, "_chain", [self])
        right_chain = getattr(composing_decorator, "_chain", [composing_decorator])
        d._chain = [*left_chain, *right_chain]
        return d


class LLMPromptDecorator(PromptDecorator):
    """Base class for decorators that rewrite the prompt with a model."""

    def __init__(self, completion: Completion, seed: int = 42) -> None:
        super().__init__(seed=seed)
        self._completion = completion

    async def prompt_model(self, prompt: str) -> str:
        text = await self._completion([{"role": "user", "content": prompt}])
        if not text.strip():
            raise ValueError(
                f"{type(self).__name__}: the decorator model returned an empty reply"
            )
        return text


__all__ = [
    "DecorationResult",
    "LLMPromptDecorator",
    "PromptDecorator",
]
