# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""AutoDAN-Turbo: learn jailbreak strategies, then reuse them.

The other attacks search for a prompt. AutoDAN-Turbo searches for
*strategies* — named tactics it can carry from one goal to the next — and
that learning is the point. It runs in two phases:

- **warm-up**, once for the whole run, before any goal is reported: the
  attacker explores each goal freely while the panel scores, and the
  summarizer distils the gap between each goal's weakest and strongest
  attempt into a strategy. The strategies, indexed by the response they
  beat, are the strategy library. This is the run-scoped :meth:`prepare`.

- **lifelong**, per goal: the library is retrieved against the last
  response, the attacker is told which strategies to reuse or avoid, and
  every time the score improves the gap is summarized into a new strategy
  and added back. The library grows across goals, so later goals start from
  what earlier ones learned.

The panel is the scorer: its 0-10 verdict drives the search and
``break_score`` ends it. Every judged attempt of the lifelong phase is
reported.

Based on: https://arxiv.org/abs/2410.05295
"""

from __future__ import annotations

from typing import Optional

from ...contract import Completion, Embedder, Judge, Messages, Target
from ...iterative import Finding, IterativeAttack, judge_reply
from ...trace import decision, phase
from . import prompts
from .config import AutoDANTurboParams
from .library import StrategyLibrary

_REFUSAL = "Sorry, I cannot help you with that."


class AutoDANTurboAttack(IterativeAttack[AutoDANTurboParams]):
    """A lifelong strategy search over a shared, growing library."""

    name = "autodan_turbo"
    params_type = AutoDANTurboParams

    def __init__(self, params: AutoDANTurboParams) -> None:
        super().__init__(params)
        for role in ("attacker", "summarizer", "embedder"):
            if getattr(params, role) is None:
                raise ValueError(f"AutoDAN-Turbo needs a '{role}' role.")
        self.attacker: Completion = params.attacker
        self.summarizer: Completion = params.summarizer
        self.embedder: Embedder = params.embedder
        self.library = StrategyLibrary()

    # --- run scope: warm-up ---------------------------------------------------

    async def prepare(
        self, goals: list[str], target: Target, judge: Optional[Judge] = None
    ) -> None:
        """Explore every goal freely and build the strategy library from it."""
        if self.params.skip_warmup:
            decision("skipped", "warm-up disabled; starting from an empty library")
            return
        for index, goal in enumerate(goals):
            with phase(f"warm-up goal {index + 1}/{len(goals)}", goal=index):
                log = await self._explore(goal, target, judge)
            await self._learn_from(goal, log)
        decision("prepared", "strategy library built", strategies=self.library.size())

    async def _explore(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[dict]:
        """Free exploration: attacker proposes, target replies, panel scores."""
        log: list[dict] = []
        for _ in range(self.params.epochs):
            prompt = await self._propose(prompts.warm_up_system(goal), goal)
            reply, score = await self._try(goal, prompt, target, judge)
            if reply is None:
                continue
            log.append({"prompt": prompt, "response": reply, "score": score})
            if score >= self.params.break_score:
                decision(
                    "stopped", "warm-up reached a jailbreak", score=round(score, 2)
                )
                break
        return log

    async def _learn_from(self, goal: str, log: list[dict]) -> None:
        """Summarize a goal's weakest→strongest gap into a strategy."""
        if not log:
            return
        weak = min(log, key=lambda row: row["score"])
        strong = max(log, key=lambda row: row["score"])
        if strong["score"] <= weak["score"]:
            weak = {"prompt": goal, "response": _REFUSAL, "score": 1.0}
        await self._summarize(goal, weak, strong)

    # --- per goal: lifelong ---------------------------------------------------

    async def search(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[Finding]:
        findings: list[Finding] = []
        prev_score, prev_prompt, prev_response = 1.0, goal, _REFUSAL

        for iteration in range(self.params.lifelong_iterations):
            for epoch in range(self.params.epochs):
                label = f"round {iteration + 1}.{epoch + 1}"
                with phase(label, iteration=iteration, epoch=epoch) as path:
                    system = await self._guided_system(
                        goal, prev_response, iteration, epoch
                    )
                    prompt = await self._propose(system, goal)
                    reply, score = await self._try(
                        goal, prompt, target, judge, path=path, sink=findings
                    )
                    if reply is None:
                        continue
                    if score > prev_score:
                        await self._summarize(
                            goal,
                            {"prompt": prev_prompt, "response": prev_response},
                            {"prompt": prompt, "response": reply},
                        )
                    prev_score, prev_prompt, prev_response = score, prompt, reply
                    if score >= self.params.break_score:
                        decision(
                            "stopped",
                            "a reply reached the break score",
                            score=round(score, 2),
                        )
                        return findings
        return findings

    async def _guided_system(
        self, goal: str, prev_response: str, iteration: int, epoch: int
    ) -> str:
        """The attacker's system prompt, conditioned on retrieved strategies."""
        if (iteration == 0 and epoch == 0) or self.library.size() == 0:
            return prompts.warm_up_system(goal)
        vector = await self._embed(prev_response)
        valid, strategies = self.library.retrieve(vector)
        return prompts.strategy_system(goal, strategies, valid if strategies else True)

    # --- shared steps ---------------------------------------------------------

    async def _propose(self, system: str, goal: str) -> str:
        """Ask the attacker for a jailbreak prompt; fall back to the bare goal."""
        try:
            reply = await self.attacker(prompts.attacker_turns(system))
        except Exception:
            return goal
        prompt = prompts.extract_prompt(reply, goal)
        return goal if prompts.is_refusal(prompt) else prompt

    async def _try(
        self,
        goal: str,
        prompt: str,
        target: Target,
        judge: Optional[Judge],
        *,
        path=(),
        sink: Optional[list[Finding]] = None,
    ) -> tuple[Optional[str], float]:
        """Send one prompt, score the reply, and (in lifelong) keep the finding."""
        messages: Messages = [{"role": "user", "content": prompt}]
        reply = await target(messages)
        if not reply.ok or not reply.text:
            decision("skipped", "the target gave no usable reply")
            return None, 0.0
        verdict = await judge_reply(judge, goal, prompt, reply.text)
        score = 0.0 if verdict is None else verdict.score
        if sink is not None:
            sink.append(
                Finding(
                    messages=messages,
                    response=reply,
                    verdict=verdict,
                    metadata={"score": score},
                    path=path,
                )
            )
        return reply.text, score

    async def _summarize(self, goal: str, weak: dict, strong: dict) -> None:
        """Name the strategy behind ``strong``, and add it to the library."""
        try:
            reply = await self.summarizer(
                prompts.summarizer_turns(
                    goal, weak["prompt"], strong["prompt"], self.library.all()
                )
            )
        except Exception:
            return
        strategy = prompts.parse_strategy(reply)
        if not strategy or not strategy.get("Strategy"):
            return
        delta = float(strong.get("score", 0.0)) - float(weak.get("score", 0.0))
        vector = await self._embed(weak.get("response", ""))
        self.library.add(strategy, example=strong["prompt"], score=delta, vector=vector)

    async def _embed(self, text: str) -> Optional[list[float]]:
        try:
            vectors = await self.embedder([text])
        except Exception:
            return None
        return vectors[0] if vectors else None


__all__ = ["AutoDANTurboAttack"]
