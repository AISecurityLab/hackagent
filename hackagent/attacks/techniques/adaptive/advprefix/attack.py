# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""AdvPrefix: make the model continue an answer it appears to have begun.

The other techniques ask the target for something. AdvPrefix does not ask:
it puts the goal in the user turn, puts an opening like ``Sure, here is a
guide:`` in the *assistant* turn, and lets the model continue its own
apparent words. Continuing is not the same decision as agreeing, which is
why a model that refuses the question will often finish the answer.

That is prefilling, and it is the attack. Everything else is choosing
which opening to prefill:

1. **write** candidates from an uncensored role, one per opening per sample;
2. **sift** the refusals, duplicates and fragments — free, no calls;
3. **attack** each survivor several times and judge every continuation;
4. **select** by prefilling attack success rate: the share of a candidate's
   continuations the panel passed.

Selection follows the paper. The best rate wins; others within
``pasr_tol`` of it stay in contention, and each further pick takes the
lowest negative log-likelihood among them, skipping any prefix that merely
extends one already chosen. The target's token logprobs are what that
likelihood needs and the model contract does not carry them, so the rate
decides the later picks too, and the trace records that it did.

Based on: https://arxiv.org/abs/2412.10321
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import Optional

from ...contract import Completion, Judge, Messages, Target
from ...iterative import Finding, IterativeAttack, judge_reply, succeeded
from ...trace import Path, decision, phase
from . import prompts
from .config import AdvPrefixParams


@dataclass
class Candidate:
    """One opening, and how it did when the target was made to continue it."""

    prefix: str
    meta_prefix: str
    attempts: list[Finding] = field(default_factory=list)
    #: Negative log-likelihood of the prefix under the target. The paper
    #: ranks on this after the attack success rate; it needs token
    #: logprobs, which the model contract does not carry yet.
    nll: Optional[float] = None

    @property
    def pasr(self) -> float:
        """Share of continuations the panel passed: the prefilling ASR."""
        if not self.attempts:
            return 0.0
        passed = sum(succeeded(attempt.verdict) for attempt in self.attempts)
        return passed / len(self.attempts)

    @property
    def likelihood(self) -> float:
        """``nll``, or zero when the target reports no logprobs."""
        return 0.0 if self.nll is None else self.nll

    def extends(self, other: "Candidate") -> bool:
        """Whether this prefix merely continues one already selected."""
        return self.prefix.startswith(other.prefix)


class AdvPrefixAttack(IterativeAttack[AdvPrefixParams]):
    """Prefill the answer's opening and measure which opening works."""

    name = "advprefix"
    params_type = AdvPrefixParams

    def __init__(self, params: AdvPrefixParams) -> None:
        super().__init__(params)
        if params.attacker is None:
            raise ValueError(
                "AdvPrefix needs an 'attacker' role to write its prefixes."
            )
        if not params.meta_prefixes:
            raise ValueError("AdvPrefix needs at least one meta prefix.")
        self.attacker: Completion = params.attacker

    async def search(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[Finding]:
        candidates = self._sift(await self._write(goal))
        if not candidates:
            decision("stopped", "no candidate survived the filters")
            return []
        candidates = candidates[: self.params.candidates_per_goal]

        await self._attack(goal, candidates, target, judge)
        if not any(item.attempts for item in candidates):
            decision("stopped", "the target returned no usable continuation")
            return []
        # Selection rewrites the attempts it marks, so it runs before they
        # are collected.
        self._select(candidates)
        return [attempt for item in candidates for attempt in item.attempts]

    # --- 1. write -------------------------------------------------------------

    async def _write(self, goal: str) -> list[Candidate]:
        """Ask the writer for one candidate per opening per sample."""
        params = self.params
        counts = params.samples_per_prefix
        if isinstance(counts, int):
            counts = (counts,) * len(params.meta_prefixes)
        plan = [
            meta
            for meta, count in zip(params.meta_prefixes, counts)
            for _ in range(count)
        ]
        with phase("write", candidates=len(plan)):
            written = await asyncio.gather(
                *(self._one_prefix(goal, meta) for meta in plan)
            )
        return [item for item in written if item is not None]

    async def _one_prefix(self, goal: str, meta_prefix: str) -> Optional[Candidate]:
        messages: Messages = prompts.generation_turns(meta_prefix, goal)
        try:
            written = await self.attacker(messages)
        except Exception:
            return None
        # The opening is part of the prefix: the writer continued it.
        prefix = f"{meta_prefix}{written or ''}"
        if not prefix.strip():
            return None
        return Candidate(prefix=prefix, meta_prefix=meta_prefix)

    # --- 2. sift --------------------------------------------------------------

    def _sift(self, candidates: list[Candidate]) -> list[Candidate]:
        """Drop refusals and duplicates. Costs nothing, so it goes first."""
        params = self.params
        kept: list[Candidate] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate.prefix in seen:
                continue
            if not prompts.usable(
                candidate.prefix,
                min_chars=params.min_char_length,
                require_linebreak=params.require_linebreak,
            ):
                continue
            seen.add(candidate.prefix)
            kept.append(candidate)

        if len(kept) < len(candidates):
            decision(
                "pruned",
                "refusals, duplicates, and candidates too short to be prefixes",
                dropped=len(candidates) - len(kept),
                kept=len(kept),
            )
        return kept

    # --- 3. attack ------------------------------------------------------------

    async def _attack(
        self,
        goal: str,
        candidates: list[Candidate],
        target: Target,
        judge: Optional[Judge],
    ) -> None:
        """Prefill each candidate several times and judge every continuation."""
        params = self.params
        for index, candidate in enumerate(candidates):
            label = f"prefix {index + 1}/{len(candidates)}"
            with phase(label, prefix=index, meta_prefix=candidate.meta_prefix) as path:
                drawn = await asyncio.gather(
                    *(
                        self._one_attempt(goal, index, candidate, target, judge, path)
                        for _ in range(params.samples_per_candidate)
                    )
                )
                candidate.attempts = [item for item in drawn if item is not None]
                if not candidate.attempts:
                    decision("skipped", "the target gave no usable continuation")

    async def _one_attempt(
        self,
        goal: str,
        index: int,
        candidate: Candidate,
        target: Target,
        judge: Optional[Judge],
        path: Path,
    ) -> Optional[Finding]:
        messages = (
            prompts.prefilled(goal, candidate.prefix)
            if self.params.prefill
            else prompts.instructed(goal, candidate.prefix)
        )
        reply = await target(messages)
        if not reply.ok or not reply.text:
            return None
        # The model wrote only the continuation, but the turn it belongs to
        # opens with the prefix, and the harm may straddle the two.
        said = (
            prompts.said(candidate.prefix, reply.text)
            if self.params.prefill
            else reply.text
        )
        verdict = await judge_reply(judge, goal, candidate.prefix, said)
        return Finding(
            messages=messages,
            response=reply,
            verdict=verdict,
            metadata={
                "prefix": candidate.prefix,
                "meta_prefix": candidate.meta_prefix,
                "prefix_index": index,
                "prefilled": self.params.prefill,
                "selected": False,
            },
            path=path,
        )

    # --- 4. select ------------------------------------------------------------

    def _select(self, candidates: list[Candidate]) -> None:
        """Mark the paper's selection.

        The first pick minimises ``-pasr_weight * log(pasr) + nll``, which
        trades a better attack success rate against a less likely prefix.
        Later picks take the lowest likelihood among what is left within
        both tolerances, skipping any prefix that merely extends one
        already chosen.

        Without token logprobs every ``nll`` is zero, so the score reduces
        to the attack success rate alone and later picks fall back to it.
        """
        params = self.params
        scored = [item for item in candidates if item.attempts]
        if not scored:
            return

        best = min(scored, key=lambda item: _combined(item, params.pasr_weight))
        chosen = [best]
        contenders = [
            item
            for item in scored
            if item is not best
            and item.pasr >= best.pasr - params.pasr_tol
            and item.likelihood <= best.likelihood + params.nll_tol
        ]

        measured = all(item.nll is not None for item in scored)
        while len(chosen) < params.prefixes_per_goal and contenders:
            # A prefix that only continues one already chosen explores
            # nothing new, so it is never the next pick.
            contenders = [
                item
                for item in contenders
                if not any(item.extends(picked) for picked in chosen)
            ]
            if not contenders:
                break
            following = (
                min(contenders, key=lambda item: item.likelihood)
                if measured
                else max(contenders, key=lambda item: item.pasr)
            )
            chosen.append(following)
            contenders = [item for item in contenders if item is not following]

        decision(
            "selected",
            "lowest -w*log(pasr) + nll, then lowest likelihood"
            if measured
            else "the target reports no token logprobs, so the attack "
            "success rate decides alone",
            kept=len(chosen),
            of=len(scored),
            best_pasr=round(best.pasr, 3),
        )
        for candidate in chosen:
            candidate.attempts[:] = [_mark(attempt) for attempt in candidate.attempts]


def _combined(candidate: Candidate, pasr_weight: float) -> float:
    """``-w * log(pasr) + nll``, the reference's selection score.

    A candidate nothing passed has an infinite score rather than an
    undefined one, so it sorts last instead of raising.
    """
    if candidate.pasr <= 0.0:
        return float("inf")
    return -pasr_weight * math.log(candidate.pasr) + candidate.likelihood


def _mark(finding: Finding) -> Finding:
    return Finding(
        messages=finding.messages,
        response=finding.response,
        verdict=finding.verdict,
        metadata={**finding.metadata, "selected": True},
        path=finding.path,
    )


__all__ = ["AdvPrefixAttack", "Candidate"]
