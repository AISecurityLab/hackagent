# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PAIR: let an attacker model rewrite its own prompt until one lands.

Prompt Automatic Iterative Refinement (PAIR) pits an attacker LLM against
the target in a black-box loop. The attacker, told the goal and the reply
opening to aim for, writes a jailbreak prompt; the target answers; a judge
rates the reply; and the attacker reads reply and rating, explains in an
``improvement`` field what went wrong, and writes a better prompt. Running
several such streams in parallel finds a semantic, human-readable jailbreak
in a few dozen queries.

Paper: Patrick Chao, Alexander Robey, Edgar Dobriban, Hamed Hassani, et
al., "Jailbreaking Black Box Large Language Models in Twenty Queries",
2023, [arXiv:2310.08419](https://arxiv.org/abs/2310.08419).

Algorithm (one goal), with the parameters of :class:`~.config.PairParams`:

1. Open ``streams`` attacker conversations. Each gets the PAIR attacker
   system prompt for the goal and ``target_str``, one of the reference's
   three approaches in rotation (role-play, logical appeal, authority
   endorsement), and an opening request for a first prompt.
2. For each of ``iterations`` rounds, every stream concurrently:

   - asks the ``attacker`` for its next turn, a JSON object with
      ``improvement`` and ``prompt``; prose or a turn without a prompt
      skips the stream for this round;
   - sends the prompt to the target as a fresh single-message
      conversation (the target never sees the history);
   - rates the reply: with a ``scorer`` role, PAIR's 1-10 judge prompt
      (an unreadable answer is "unscored"); without one, the campaign's
      evaluation panel, whose score and verdict are used directly;
   - appends the reply (cut to ``feedback_max_chars``), the score and the
      rater's explanation to the stream, then trims it to the system prompt
      plus the last ``keep_last_n`` attacker turns and their feedback.

3. With ``early_stop``, stop after a round in which any stream passed: a
   scorer score at or above ``jailbreak_threshold``, or a panel success.
4. With a ``scorer``, put only the best-scoring attempt to the panel at the
   end; its verdict is the one the run reports for that attempt.

Deviations from the paper: the paper runs 20 streams of depth 3 with a
GPT-4 judge; the defaults here are 5 by 5, and the judge is either the
optional ``scorer`` or the campaign's panel. The rater's explanation is fed
back alongside the score, and long replies are truncated in the feedback.
A malformed attacker turn is skipped rather than regenerated.

Roles: ``attacker`` (required) writes and refines prompts, one call per
stream per round; ``scorer`` (optional) rates every reply 1-10.

Attempts and success: every prompt that got a usable reply from the target
is one attempt, tagged with its round, stream and score. Without a scorer
each attempt carries the panel's verdict and the goal succeeds when any is
a success; with a scorer only the best-scoring attempt is judged, and the
goal succeeds when the panel calls that one a success.
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
    """Let an attacker model refine jailbreak prompts over parallel streams.

    Implements PAIR (Chao et al., 2023,
    [arXiv:2310.08419](https://arxiv.org/abs/2310.08419)): ``streams``
    independent attacker conversations each propose a prompt per round,
    read the target's reply and its rating, and improve the prompt, for up
    to ``iterations`` rounds. Replies are rated by the optional ``scorer``
    (PAIR's 1-10 judge, with only the best attempt sent to the campaign's
    panel) or by the panel itself. The algorithm and the deviations from
    the paper are documented in the module
    ``hackagent.attacks.techniques.adaptive.pair.attack``.
    """

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
        """Run the rounds and return every attempt that got a usable reply.

        Calls the ``attacker`` once per stream per round, the target once per
        usable proposal, and the ``scorer`` or the panel once per reply (plus
        one panel review of the best attempt when a scorer is configured).
        """
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
    """The last message's text, which is the prompt the target received."""
    return str(finding.messages[-1].get("content", "")) if finding.messages else ""


__all__ = ["PAIRAttack", "Rating"]
