"""Provider-error retries for the canonical model interface."""

from typing import Any, Mapping, Sequence

from hackagent.models.model import Model, Reachability
from hackagent.models.response import ModelResponse


class RetryingModel(Model):
    """Retry a model's calls that return a provider error.

    A call is repeated up to ``retries`` more times, immediately and with the
    same arguments, until it returns no ``error``; the last response is
    returned either way. Guardrail blocks are not errors and are not retried.

    Args:
        model: The model to wrap.
        retries: Extra attempts after the first; 0 disables retrying.

    Raises:
        ValueError: If ``retries`` is negative.
    """

    def __init__(self, model: Model, retries: int = 0) -> None:
        if retries < 0:
            raise ValueError("retries cannot be negative")
        self.model = model
        self.retries = retries

    async def is_reachable(self) -> Reachability:
        """Delegate to the wrapped model; the probe itself is not retried."""
        return await self.model.is_reachable()

    def complete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        """Call the wrapped model, retrying while it returns an error."""
        for attempt in range(self.retries + 1):
            response = self.model.complete(messages, **overrides)
            if response.error is None or attempt == self.retries:
                return response
        raise AssertionError("unreachable")

    async def acomplete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        """Asynchronous :meth:`complete`."""
        for attempt in range(self.retries + 1):
            response = await self.model.acomplete(messages, **overrides)
            if response.error is None or attempt == self.retries:
                return response
        raise AssertionError("unreachable")
