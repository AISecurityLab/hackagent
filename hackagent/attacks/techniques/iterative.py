# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Contract shared by every iterative attack.

An iterative attack talks to the target while it runs: each reply decides
what it sends next. It receives the target as a :data:`Target` and the
campaign's evaluation panel as a :data:`Judge`, and it asks the panel about
each exchange as it goes, because the verdict is what tells it whether to
stop. Every call it makes is traced by the runner.

It returns every exchange it had judged, each carrying that verdict and
the :func:`~.trace.phase` it came from, so the run reports the comparison
the attack exists to make (which technique, which step), no exchange is
judged twice, and each one keeps the part of the search that produced it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Generic, Mapping, Optional, TypeVar

from hackagent.core.contracts import Sample, Verdict
from hackagent.core.contracts.protocols import CompletionResult

from .contract import AttackParams, Judge, Messages, Target
from .trace import Path

ParamsT = TypeVar("ParamsT", bound=AttackParams)


@dataclass(frozen=True)
class Finding:
    """One judged exchange of a search.

    ``messages`` is the request sent to the target, ``response`` its reply,
    and ``verdict`` what the panel made of it — ``None`` only when the
    campaign configured no judges. ``path`` is the phase this came out of,
    which is how the run attaches that phase's trace to this exchange.
    """

    messages: Messages
    response: CompletionResult
    verdict: Optional[Verdict] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    path: Path = ()


class IterativeAttack(ABC, Generic[ParamsT]):
    """A search against the target for one goal."""

    name: ClassVar[str]
    params_type: ClassVar[type[AttackParams]]

    def __init__(self, params: ParamsT) -> None:
        if not isinstance(params, self.params_type):
            raise TypeError(
                f"{type(self).__name__} expects {self.params_type.__name__}, "
                f"got {type(params).__name__}"
            )
        self.params = params

    async def prepare(
        self, goals: list[str], target: Target, judge: Optional[Judge] = None
    ) -> None:
        """Run-scoped setup, done once before any goal is searched.

        Most attacks need none and the default does nothing. One that learns
        across goals — AutoDAN-Turbo building its strategy library — does that
        work here, where it belongs to the run rather than to any goal, and
        stores what it built on ``self`` for :meth:`search` to read.
        """
        _ = (goals, target, judge)

    async def run(
        self, goal: str, target: Target, judge: Optional[Judge] = None
    ) -> list[Finding]:
        """Search for ``goal``; empty when the target never replied usably."""
        goal = goal.strip()
        if not goal:
            raise ValueError("goal cannot be empty")
        return await self.search(goal, target, judge)

    @abstractmethod
    async def search(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[Finding]:
        """Search for a stripped, non-empty goal.

        Return one :class:`Finding` per exchange that was judged, in the
        order they were tried. ``judge`` is ``None`` when the campaign
        configured no judges: the search then has nothing to stop on and
        runs to its configured end.
        """

    def decode(self, response: str) -> str:
        """Map a target reply back to plain text before it is judged."""
        return response


async def judge_reply(
    judge: Optional[Judge], goal: str, prompt: str, response: str
) -> Optional[Verdict]:
    """Ask the panel about one reply.

    ``None`` when there is no panel, or when the call failed — the trace
    records why. A search treats that as "no verdict", never as a failure.
    """
    if judge is None:
        return None
    try:
        return await judge(Sample(goal=goal, prompt=prompt, response=response))
    except Exception:
        return None


def succeeded(verdict: Optional[Verdict]) -> bool:
    """Whether the panel called this exchange a success."""
    return verdict is not None and verdict.error is None and verdict.success


__all__ = ["Finding", "IterativeAttack", "judge_reply", "succeeded"]
