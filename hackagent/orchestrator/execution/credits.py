# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Stop a run when the HackAgent gateway says the credits are spent.

A model call returns provider errors as values, and the runner and the
attacks turn them into per-attempt errors, so a 402 from the gateway would
otherwise leave a run that "completes" with every attempt failed. Gateway
models are wrapped so that their first 402 trips a :class:`CreditGuard`: the
executor cancels the campaign, every later gateway call is refused without
being sent, and the run ends FAILED with "Out of credits". A 402 from any
other provider, such as the target's own, stays an ordinary attempt error.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Mapping, Optional, Sequence

from hackagent.core.credentials import reference_name
from hackagent.models import Model, ModelConfig, ModelResponse, Reachability
from hackagent.orchestrator.campaign.gateway import GATEWAY_KEY_ENV
from hackagent.orchestrator.campaign.resolve import ModelBuilder

PAYMENT_REQUIRED = 402


class OutOfCredits(RuntimeError):
    """The gateway refused a call because the organization has no credits."""

    status_code = PAYMENT_REQUIRED

    def __init__(self) -> None:
        super().__init__("the HackAgent gateway answered 402: out of credits")


class CreditGuard:
    """Trips once on the first 402 from a model bound to ``base_url``'s gateway."""

    def __init__(self, base_url: str) -> None:
        self.endpoint = f"{base_url.rstrip('/')}/v1"
        self.tripped = threading.Event()
        #: Runs once, when the guard trips (the executor cancels the campaign).
        self.on_trip: Optional[Callable[[], None]] = None

    def is_gateway(self, config: ModelConfig) -> bool:
        connection = config.connection
        return (
            connection.endpoint == self.endpoint
            and reference_name(connection.api_key) == GATEWAY_KEY_ENV
        )

    def wrap(self, build: ModelBuilder) -> ModelBuilder:
        """``build``, with every gateway model it builds guarded."""

        def guarded_build(config: ModelConfig, **kwargs: Any) -> Model:
            model = build(config, **kwargs)
            return _GatewayModel(model, self) if self.is_gateway(config) else model

        return guarded_build

    def check(self, response: ModelResponse) -> ModelResponse:
        error = response.error
        if error is not None and error.status_code == PAYMENT_REQUIRED:
            self.trip()
            raise OutOfCredits()
        return response

    def refuse_if_tripped(self) -> None:
        if self.tripped.is_set():
            raise OutOfCredits()

    def trip(self) -> None:
        if self.tripped.is_set():
            return
        self.tripped.set()
        if self.on_trip is not None:
            self.on_trip()


class _GatewayModel(Model):
    """A gateway model whose 402 trips the guard; refused once it has."""

    def __init__(self, model: Model, guard: CreditGuard) -> None:
        self.model = model
        self.guard = guard

    def __getattr__(self, name: str) -> Any:
        if name == "model":  # not set yet, e.g. while copying
            raise AttributeError(name)
        return getattr(self.model, name)

    async def is_reachable(self) -> Reachability:
        # Ping through this wrapper, so a 402 at preflight trips the guard.
        return await Model.is_reachable(self)

    def complete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        self.guard.refuse_if_tripped()
        return self.guard.check(self.model.complete(messages, **overrides))

    async def acomplete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        self.guard.refuse_if_tripped()
        return self.guard.check(await self.model.acomplete(messages, **overrides))


__all__ = ["CreditGuard", "OutOfCredits"]
