# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Common configuration, response, and execution contracts for models."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Mapping, Sequence

from .response import ModelResponse


class Model(ABC):
    """Common interface implemented by every model backend."""

    @abstractmethod
    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        **overrides: Any,
    ) -> ModelResponse:
        """Run a synchronous completion."""

    @abstractmethod
    async def acomplete(
        self,
        messages: Sequence[Mapping[str, Any]],
        **overrides: Any,
    ) -> ModelResponse:
        """Run an asynchronous completion."""

    def complete_batch(
        self,
        requests: Sequence[Sequence[Mapping[str, Any]]],
        *,
        max_concurrency: int = 1,
        **overrides: Any,
    ) -> list[ModelResponse]:
        """Complete requests concurrently while preserving input order."""
        self._validate_max_concurrency(max_concurrency)

        def complete_one(messages: Sequence[Mapping[str, Any]]) -> ModelResponse:
            return self.complete(messages, **overrides)

        if max_concurrency == 1:
            return [complete_one(messages) for messages in requests]
        with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
            return list(pool.map(complete_one, requests))

    async def acomplete_batch(
        self,
        requests: Sequence[Sequence[Mapping[str, Any]]],
        *,
        max_concurrency: int = 1,
        on_complete: Callable[[int, ModelResponse], None] | None = None,
        **overrides: Any,
    ) -> list[ModelResponse]:
        """Return input-ordered responses, notifying as each request finishes."""
        self._validate_max_concurrency(max_concurrency)
        semaphore = asyncio.Semaphore(max_concurrency)

        async def complete_one(
            request_index: int,
            messages: Sequence[Mapping[str, Any]],
        ) -> ModelResponse:
            async with semaphore:
                response = await self.acomplete(messages, **overrides)
                if on_complete is not None:
                    on_complete(request_index, response)
                return response

        return list(await asyncio.gather(*(complete_one(index, item) for index, item in enumerate(requests))))

    @staticmethod
    def _validate_max_concurrency(max_concurrency: int) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
