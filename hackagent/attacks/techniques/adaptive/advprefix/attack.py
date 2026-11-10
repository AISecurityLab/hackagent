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

Paper: Sicheng Zhu, Brandon Amos, Yuandong Tian, Chuan Guo, et al.,
"AdvPrefix: An Objective for Nuanced LLM Jailbreaks", 2024,
[arXiv:2412.10321](https://arxiv.org/abs/2412.10321). The paper replaces
the fixed ``Sure, here is ...`` target of optimisation attacks with
model-specific prefixes chosen for a high prefilling attack success rate
and a low negative log-likelihood under the target.

Algorithm (one goal), with the parameters of
:class:`~.config.AdvPrefixParams`:

1. **Write.** For each opening in ``meta_prefixes`` (default ``Here``,
   ``To``, ``Sure`` and the empty opening), ask the ``attacker`` for
   ``samples_per_prefix`` candidates (one count, or one per opening): the
   goal as the user turn and the opening prefilled as the assistant's, so
   the writer continues it. The opening plus the continuation is the
   candidate, cut to ``max_prefix_chars``.
2. **Sift.** Drop duplicates, candidates shorter than ``min_char_length``,
   ones that open with a refusal or contain a hedge, and, with
   ``require_linebreak``, ones without a line break. Keep the first
   ``candidates_per_goal``.
3. **Attack.** For each candidate, draw ``samples_per_candidate``
   continuations from the target concurrently. With ``prefill`` the
   candidate is the trailing assistant turn after the goal; without it the
   goal asks the target to start its response with the candidate. The
   panel judges prefix plus continuation (prefill) or the reply (no
   prefill).
4. **Select.** A candidate's prefilling ASR is the share of its
   continuations the panel passed. The first pick minimises
   ``-pasr_weight * log(pasr) + nll``; further picks, up to
   ``prefixes_per_goal``, come from the candidates within ``pasr_tol`` of
   the best rate and ``nll_tol`` of its likelihood, skipping any prefix
   that extends one already picked. The picked candidates' attempts are
   marked ``selected``.

Deviations from the paper: the paper uses the selected prefixes as
objectives for optimisation attacks such as GCG; HackAgent stops at the
prefilling evaluation, which is itself the attack a black-box endpoint
allows. Without token logprobs every ``nll`` is 0, so selection reduces to
the prefilling ASR. Lengths are counted in characters, not tokens, and the
sample counts default far below the reference's (see the field
descriptions). The writer is a chat model continuing a prefilled assistant
turn rather than a base model on raw text.

Roles: ``attacker`` (required), the prefix writer, called once per
requested candidate. An uncensored model works best, because a refusal is
not a usable prefix.

Attempts and success: every continuation of every attacked candidate is
one attempt, carrying the prefix, its length, whether it was truncated and
whether it was selected. The goal succeeds when the panel passed any
attempt, selected or not.
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
    original_prefix_chars: int = 0
    prefix_truncated: bool = False
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
    """Prefill the opening of the target's answer and measure which opening works.

    Implements the prefix selection of AdvPrefix (Zhu et al., 2024,
    [arXiv:2412.10321](https://arxiv.org/abs/2412.10321)) as a prefilling
    attack: the ``attacker`` writes candidate openings for the goal, each is
    placed in the assistant turn and continued by the target several times,
    the campaign's evaluation panel judges every continuation, and the
    openings with the best prefilling success rate are marked selected. The
    algorithm and the deviations from the paper are documented in the module
    ``hackagent.attacks.techniques.adaptive.advprefix.attack``.

    ``max_prefix_chars`` bounds the assembled prefix before target evaluation;
    it does not limit the writer's generation or reproduce token-based stopping.
    In prefill mode the panel judges the prefix plus the target continuation,
    not a separate continuation-only success rate.
    """

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
        """Write, sift, attack and select; return every judged continuation.

        Calls the ``attacker`` once per requested candidate, then the target
        and the panel ``samples_per_candidate`` times per kept candidate.
        """
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
        """Have the writer continue one opening; ``None`` when it fails or writes nothing."""
        messages: Messages = prompts.generation_turns(meta_prefix, goal)
        try:
            written = await self.attacker(messages)
        except Exception:
            return None
        # The opening is part of the prefix: the writer continued it. Some
        # backends echo the prefilled opening in their reply; keep it once.
        written = written or ""
        prefix = (
            written
            if meta_prefix and written.startswith(meta_prefix)
            else f"{meta_prefix}{written}"
        )
        original_prefix_chars = len(prefix)
        prefix_truncated = original_prefix_chars > self.params.max_prefix_chars
        if len(prefix) > self.params.max_prefix_chars:
            prefix = prefix[: self.params.max_prefix_chars]
            decision(
                "truncated",
                "attacker-generated prefix exceeds the character limit",
                original_prefix_chars=original_prefix_chars,
                prefix_chars=len(prefix),
                max_prefix_chars=self.params.max_prefix_chars,
                meta_prefix=meta_prefix,
            )
        if not prefix.strip():
            return None
        return Candidate(
            prefix=prefix,
            meta_prefix=meta_prefix,
            original_prefix_chars=original_prefix_chars,
            prefix_truncated=prefix_truncated,
        )

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
        """Draw and judge one continuation of ``candidate``; ``None`` when unusable."""
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
        continuation = reply.text or ""
        return Finding(
            messages=messages,
            response=reply,
            verdict=verdict,
            metadata={
                "prefix": candidate.prefix,
                "meta_prefix": candidate.meta_prefix,
                "prefix_chars": len(candidate.prefix),
                "prefix_original_chars": candidate.original_prefix_chars,
                "prefix_truncated": candidate.prefix_truncated,
                "max_prefix_chars": self.params.max_prefix_chars,
                "continuation_chars": len(continuation),
                "continuation_tokens": (
                    reply.usage.get("completion_tokens")
                    if isinstance(getattr(reply, "usage", None), dict)
                    else getattr(
                        getattr(reply, "usage", None), "completion_tokens", None
                    )
                ),
                "finish_reason": getattr(reply, "finish_reason", None),
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
    """A copy of ``finding`` marked as part of the selection."""
    return Finding(
        messages=finding.messages,
        response=finding.response,
        verdict=finding.verdict,
        metadata={**finding.metadata, "selected": True},
        path=finding.path,
    )


__all__ = ["AdvPrefixAttack", "Candidate"]
