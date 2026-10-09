"""Provider-error retries for the canonical model interface."""

from typing import Any, Mapping, Sequence

from hackagent.models.model import Model
from hackagent.models.response import ModelResponse


class RetryingModel(Model):
    def __init__(self, model: Model, retries: int = 0) -> None:
        if retries < 0:
            raise ValueError("retries cannot be negative")
        self.model = model
        self.retries = retries

    def complete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        for attempt in range(self.retries + 1):
            response = self.model.complete(messages, **overrides)
            if response.error is None or attempt == self.retries:
                return response
        raise AssertionError("unreachable")

    async def acomplete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        for attempt in range(self.retries + 1):
            response = await self.model.acomplete(messages, **overrides)
            if response.error is None or attempt == self.retries:
                return response
        raise AssertionError("unreachable")
