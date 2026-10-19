# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Common configuration, response, and execution contracts for models."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence

from .response import ModelResponse

#: The smallest request that still exercises a model's whole request path.
PING: tuple[Mapping[str, Any], ...] = ({"role": "user", "content": "ping"},)


@dataclass(frozen=True)
class Reachability:
    """Whether a model answered, why not, and how long it took."""

    ok: bool
    detail: str = ""
    latency_s: Optional[float] = None

    def __bool__(self) -> bool:
        return self.ok


class Model(ABC):
    """Common interface implemented by every model backend."""

    async def is_reachable(self) -> Reachability:
        """Send :data:`PING` and report whether a usable reply came back.

        Backends where a request is costly or intrusive override this with a
        check that sends nothing.
        """
        started = time.monotonic()
        try:
            response = await self.acomplete(PING)
        except Exception as exc:
            return Reachability(False, f"{type(exc).__name__}: {exc}")
        latency = time.monotonic() - started
        if response.error is not None:
            detail = f"{response.error.category}: {response.error.message}"
            return Reachability(False, detail, latency)
        return Reachability(True, latency_s=latency)

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

        return list(
            await asyncio.gather(
                *(complete_one(index, item) for index, item in enumerate(requests))
            )
        )

    @staticmethod
    def _validate_max_concurrency(max_concurrency: int) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
