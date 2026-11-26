"""Provider-error retries for the canonical model interface."""

import asyncio
import random
import time
from typing import Any, Mapping, Optional, Sequence

from hackagent.models.model import Model, Reachability
from hackagent.models.response import ModelResponse

#: Status codes worth asking again: a timeout, a conflict, "too early", a
#: rate limit, and every server error. Others (a bad request, a refused
#: key, a missing model, no credits) fail the same way every time.
RETRYABLE_STATUS = frozenset({408, 409, 425, 429})

#: The longest wait between two attempts, in seconds.
MAX_DELAY = 30.0


def retryable(response: ModelResponse) -> bool:
    """True when the response's error may go away if the call is repeated.

    An error without a status code (a dropped connection, a timeout raised
    before any reply) is taken to be transient.
    """
    if response.error is None:
        return False
    status: Optional[int] = response.error.status_code
    return status is None or status in RETRYABLE_STATUS or status >= 500


class RetryingModel(Model):
    """Retry a model's calls that return a transient provider error.

    A call is repeated up to ``retries`` more times, with the same arguments,
    while it returns an error that :func:`retryable` says may go away: a
    timeout, a rate limit or a server error. Before each repeat it waits
    ``backoff * 2**n`` seconds (capped at :data:`MAX_DELAY`), with full
    jitter so that concurrent calls do not retry in step. The last response
    is returned either way. Guardrail blocks are not errors and are not
    retried, nor are errors that would fail again (a 400, 401, 402 or 404).

    Args:
        model: The model to wrap.
        retries: Extra attempts after the first; 0 disables retrying.
        backoff: The base wait, in seconds; 0 retries at once.

    Raises:
        ValueError: If ``retries`` or ``backoff`` is negative.
    """

    def __init__(self, model: Model, retries: int = 0, backoff: float = 1.0) -> None:
        if retries < 0:
            raise ValueError("retries cannot be negative")
        if backoff < 0:
            raise ValueError("backoff cannot be negative")
        self.model = model
        self.retries = retries
        self.backoff = backoff

    def _delay(self, attempt: int) -> float:
        """How long to wait before repeating the ``attempt``-th call."""
        return random.uniform(0, min(MAX_DELAY, self.backoff * 2**attempt))

    async def is_reachable(self) -> Reachability:
        """Delegate to the wrapped model; the probe itself is not retried."""
        return await self.model.is_reachable()

    def complete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        """Call the wrapped model, retrying while it returns a transient error."""
        for attempt in range(self.retries + 1):
            response = self.model.complete(messages, **overrides)
            if attempt == self.retries or not retryable(response):
                return response
            time.sleep(self._delay(attempt))
        raise AssertionError("unreachable")

    async def acomplete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        """Asynchronous :meth:`complete`."""
        for attempt in range(self.retries + 1):
            response = await self.model.acomplete(messages, **overrides)
            if attempt == self.retries or not retryable(response):
                return response
            await asyncio.sleep(self._delay(attempt))
        raise AssertionError("unreachable")
