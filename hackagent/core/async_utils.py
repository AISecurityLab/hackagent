# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Small shared helpers for bridging synchronous APIs to asyncio internals."""

import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


def run_coroutine_blocking(coro_factory: Callable[[], Awaitable[T]]) -> T:
    """Run a coroutine factory from synchronous code safely.

    Uses ``asyncio.run`` directly when no event loop is running yet (the
    common case for a synchronous public API). ``asyncio.run`` cannot be
    nested, so when called from inside an already-running loop (e.g.
    notebooks, async callers) a dedicated bridge thread runs its own loop
    instead, giving synchronous callers the same behavior either way.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro_factory())).result()
