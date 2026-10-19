# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Contract shared by every static attack.

A static attack turns one goal into one or more chat requests for the
target. It never builds, configures, or calls a model on its own: when an
algorithm needs an auxiliary model (a *role*, such as h4rm3l's decorator),
its parameters declare a :data:`~..contract.Completion` field and whoever
constructs the parameters supplies the callable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Generic, TypeVar

from ..contract import AttackParams, Completion, Message, Messages

ParamsT = TypeVar("ParamsT", bound=AttackParams)


class StaticAttack(ABC, Generic[ParamsT]):
    """A fixed transformation from a goal to target requests."""

    name: ClassVar[str]
    params_type: ClassVar[type[AttackParams]]

    def __init__(self, params: ParamsT) -> None:
        if not isinstance(params, self.params_type):
            raise TypeError(
                f"{type(self).__name__} expects {self.params_type.__name__}, "
                f"got {type(params).__name__}"
            )
        self.params = params

    async def generate(self, goal: str) -> list[Messages]:
        """Return the chat requests to send to the target for ``goal``."""
        goal = goal.strip()
        if not goal:
            raise ValueError("goal cannot be empty")
        return await self.build_requests(goal)

    @abstractmethod
    async def build_requests(self, goal: str) -> list[Messages]:
        """Build requests for a stripped, non-empty goal."""

    def decode(self, response: str) -> str:
        """Map a target reply back to plain text before it is judged."""
        return response


__all__ = [
    "AttackParams",
    "Completion",
    "Message",
    "Messages",
    "StaticAttack",
]
