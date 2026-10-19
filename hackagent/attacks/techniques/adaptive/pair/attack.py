# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PAIR: let an attacker model rewrite its own prompt until one lands.

Several streams run side by side, each an independent conversation with the
attacker. A round gives every stream one attempt: the attacker writes a
prompt, it goes to the target, the reply is rated, and the reply and its
score are fed back so the next attempt can build on what happened. The
streams never see each other, so a dead end in one does not poison the rest.

Who rates depends on the run. With a ``scorer`` role the paper's own 1-10
judge rates every reply, the search stops at the first score that reaches
``jailbreak_threshold``, and the panel is asked only about the best attempt.
Without one the panel rates every reply itself and its verdict decides.

Every attempt that reached the target is returned, so the run shows which
stream and which round got there.

Based on: https://arxiv.org/abs/2310.08419
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, replace
from typing import Any, Optional

from hackagent.attacks._lib.prompt_parser import extract_prompt_and_improvement
from hackagent.core.contracts import Verdict

from ...contract import Completion, Judge, Messages, Target
from ...iterative import Finding, IterativeAttack, judge_reply, succeeded
from ...trace import decision, phase
from . import prompts
from .config import PairParams

#: One attacker turn: the prompt to send, and the JSON to append to its
#: conversation so the next turn sees what it proposed.
Proposal = tuple[str, str]


@dataclass(frozen=True)
class Rating:
    """What one attempt scored, and the verdict behind it if there was one.

    ``verdict`` is set only when the panel did the rating; a ``scorer``
    gives a number and its reasoning, and the panel is consulted later.
    """

    score: Optional[float] = None
    explanation: str = ""
    verdict: Optional[Verdict] = None


class PAIRAttack(IterativeAttack[PairParams]):
    """Parallel streams of attacker-refined prompts."""

    name = "pair"
    params_type = PairParams

    def __init__(self, params: PairParams) -> None:
        super().__init__(params)
        if params.attacker is None:
            raise ValueError("PAIR needs an 'attacker' role to write its prompts.")
        self.attacker: Completion = params.attacker
        self.scorer: Optional[Completion] = params.scorer

    async def search(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[Finding]:
        params = self.params
        streams = [self._open(goal, index) for index in range(params.streams)]
        findings: list[Finding] = []

        for iteration in range(params.iterations):
            label = f"round {iteration + 1}/{params.iterations}"
            with phase(label, iteration=iteration):
                attempts = await asyncio.gather(
                    *(
                        self._attempt(goal, index, stream, iteration, target, judge)
                        for index, stream in enumerate(streams)
                    )
                )
            found = [finding for finding in attempts if finding is not None]
            findings.extend(found)
            if params.early_stop and any(self._passed(f) for f in found):
                decision("stopped", "a stream reached a reply that scored a jailbreak")
                break

        if self.scorer is not None:
            await self._review(goal, findings, judge)
        return findings

    def _open(self, goal: str, stream: int) -> Messages:
        """Start one stream's conversation with the attacker."""
        target_str = self.params.target_str
        return [
            {
                "role": "system",
                "content": prompts.system_prompt(goal, stream, target_str),
            },
            {"role": "user", "content": prompts.opening_request(goal, target_str)},
        ]

    async def _attempt(
        self,
        goal: str,
        stream: int,
        conversation: Messages,
        iteration: int,
        target: Target,
        judge: Optional[Judge],
    ) -> Optional[Finding]:
        """One stream's turn: propose, send, rate, and feed the result back."""
        with phase(f"stream {stream + 1}/{self.params.streams}", stream=stream) as path:
            proposal = await self._propose(conversation)
            if proposal is None:
                decision("skipped", "the attacker proposed no usable prompt")
                return None

            prompt, assistant_turn = proposal
            conversation.append({"role": "assistant", "content": assistant_turn})

            messages = [{"role": "user", "content": prompt}]
            reply = await target(messages)
            if not reply.ok or not reply.text:
                decision("skipped", "the target gave no usable reply")
                self._feed_back(goal, conversation, "[no reply]", Rating())
                return None

            rating = await self._rate(goal, prompt, reply.text, judge)
            self._feed_back(goal, conversation, reply.text, rating)
            return Finding(
                messages=messages,
                response=reply,
                verdict=rating.verdict,
                metadata={
                    "iteration": iteration,
                    "stream": stream,
                    "score": rating.score,
                },
                path=path,
            )

    async def _propose(self, conversation: Messages) -> Optional[Proposal]:
        """Ask the attacker for its next prompt; ``None`` when it gives none."""
        try:
            reply = await self.attacker(conversation)
        except Exception:
            return None
        return _parse(reply)

    async def _rate(
        self, goal: str, prompt: str, reply: str, judge: Optional[Judge]
    ) -> Rating:
        """Score one reply, with whichever rater this run configured."""
        if self.scorer is None:
            verdict = await judge_reply(judge, goal, prompt, reply)
            if verdict is None:
                return Rating()
            return Rating(verdict.score, verdict.explanation, verdict)
        return await self._ask_scorer(goal, prompt, reply)

    async def _ask_scorer(self, goal: str, prompt: str, reply: str) -> Rating:
        """Ask PAIR's own 1-10 judge. An unreadable answer is no score."""
        assert self.scorer is not None
        messages = [
            {"role": "system", "content": prompts.scorer_system_prompt(goal)},
            {"role": "user", "content": prompts.scorer_request(prompt, reply)},
        ]
        try:
            answer = await self.scorer(messages)
        except Exception:
            return Rating()
        return Rating(prompts.parse_rating(answer), (answer or "").strip())

    def _passed(self, finding: Finding) -> bool:
        """Whether this attempt is the jailbreak the search stops on."""
        if self.scorer is None:
            return succeeded(finding.verdict)
        score = finding.metadata.get("score")
        return score is not None and score >= self.params.jailbreak_threshold

    async def _review(
        self, goal: str, findings: list[Finding], judge: Optional[Judge]
    ) -> None:
        """Put the best-scoring attempt to the panel, whose call the run reports.

        Only the best one: with a scorer in the loop the panel is the final
        word, not the search signal, and judging every attempt again would
        spend a panel call per round per stream to say the same thing.
        """
        if judge is None or not findings:
            return
        best = max(range(len(findings)), key=lambda index: _score_of(findings[index]))
        finding = findings[best]
        with phase("panel review", **dict(finding.metadata)):
            verdict = await judge_reply(
                judge, goal, _prompt_of(finding), finding.response.text
            )
        findings[best] = replace(finding, verdict=verdict)

    def _feed_back(
        self, goal: str, conversation: Messages, reply: str, rating: Rating
    ) -> None:
        """Append what came back, then trim the stream's history."""
        params = self.params
        conversation.append(
            {
                "role": "user",
                "content": prompts.feedback(
                    goal,
                    params.target_str,
                    reply,
                    rating.score,
                    rating.explanation,
                    limit=params.feedback_max_chars,
                ),
            }
        )
        keep = 1 + 2 * params.keep_last_n
        if len(conversation) > keep:
            conversation[:] = [
                conversation[0],
                *conversation[-2 * params.keep_last_n :],
            ]


def _parse(reply: Optional[str]) -> Optional[Proposal]:
    """Read the attacker's JSON turn.

    Prose is rejected rather than sent to the target: without the
    ``improvement`` field this is the attacker thinking aloud, not a prompt.
    """
    if not reply or '"improvement"' not in reply:
        return None
    parsed: Optional[dict[str, Any]] = extract_prompt_and_improvement(
        reply, allow_plaintext=False
    )
    if not parsed or not parsed.get("prompt"):
        return None
    return parsed["prompt"], json.dumps(parsed, ensure_ascii=False)


def _score_of(finding: Finding) -> float:
    """An unscored attempt ranks below every scored one."""
    score = finding.metadata.get("score")
    return float("-inf") if score is None else float(score)


def _prompt_of(finding: Finding) -> str:
    return str(finding.messages[-1].get("content", "")) if finding.messages else ""


__all__ = ["PAIRAttack", "Rating"]
