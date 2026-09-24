---
sidebar_label: async_utils
title: hackagent.core.async_utils
---

Small shared helpers for bridging synchronous APIs to asyncio internals.

#### run\_coroutine\_blocking

```python
def run_coroutine_blocking(coro_factory: Callable[[], Awaitable[T]]) -> T
```

Run a coroutine factory from synchronous code safely.

Uses `asyncio.run` directly when no event loop is running yet (the
common case for a synchronous public API). `asyncio.run` cannot be
nested, so when called from inside an already-running loop (e.g.
notebooks, async callers) a dedicated bridge thread runs its own loop
instead, giving synchronous callers the same behavior either way.

