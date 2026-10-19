# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Best-of-N: resend the goal until one perturbation of it gets through.

Each step sends several independently seeded augmentations of the goal at
once. The step's longest usable reply is the one the panel judges, since a
long reply is a cheap proxy for the target engaging rather than refusing.
The search stops at the first step the panel calls a success.

That one reply per step is what the panel rates: the other candidates of a
step differ only by noise, and judging all of them would multiply the
panel's work by the fan-out without telling the run anything more. They are
still in the trace, under the step that sent them.

Based on: https://arxiv.org/abs/2412.03556
"""

from __future__ import annotations

import asyncio
from typing import Optional

from hackagent.core.contracts.protocols import CompletionResult

from ...contract import Judge, Target
from ...iterative import Finding, IterativeAttack, judge_reply, succeeded
from ...trace import decision, phase
from .augment import augment_text
from .config import BoNParams


class BoNAttack(IterativeAttack[BoNParams]):
    """A stochastic search over augmentations of the goal."""

    name = "bon"
    params_type = BoNParams

    async def search(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[Finding]:
        params = self.params
        findings: list[Finding] = []

        for step in range(params.steps):
            with phase(f"step {step + 1}/{params.steps}", step=step) as path:
                prompts = self._candidates(goal, step)
                replies = await asyncio.gather(
                    *(
                        target([{"role": "user", "content": prompt}])
                        for prompt in prompts
                    )
                )
                candidate = _longest_reply(prompts, replies)
                if candidate is None:
                    decision(
                        "skipped",
                        f"none of the {len(prompts)} candidates got a usable reply",
                    )
                    continue

                index, prompt, reply = candidate
                verdict = await judge_reply(judge, goal, prompt, reply.text)
                findings.append(
                    Finding(
                        messages=[{"role": "user", "content": prompt}],
                        response=reply,
                        verdict=verdict,
                        metadata={
                            "step": step,
                            "candidate": index,
                            "seed": _seed(params, step, index),
                        },
                        path=path,
                    )
                )
                if succeeded(verdict):
                    decision(
                        "stopped",
                        "the panel called this reply a success",
                        score=verdict.score,
                    )
                    break

        return findings

    def _candidates(self, goal: str, step: int) -> list[str]:
        """The augmented prompts of one step. The same seed is the same text."""
        params = self.params
        return [
            augment_text(
                goal,
                params.sigma,
                _seed(params, step, index),
                word_scrambling=params.word_scrambling,
                random_capitalization=params.random_capitalization,
                ascii_perturbation=params.ascii_perturbation,
            )
            for index in range(params.candidates)
        ]


def _seed(params: BoNParams, step: int, index: int) -> int:
    return step * params.candidates + index


def _longest_reply(
    prompts: list[str], replies: list[CompletionResult]
) -> Optional[tuple[int, str, CompletionResult]]:
    """The usable candidate with the longest reply, if any."""
    usable = [
        (index, prompts[index], reply)
        for index, reply in enumerate(replies)
        if reply.ok and reply.text
    ]
    if not usable:
        return None
    return max(usable, key=lambda item: len(item[2].text or ""))


__all__ = ["BoNAttack"]
