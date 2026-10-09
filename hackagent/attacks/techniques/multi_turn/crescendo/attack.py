# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Crescendo: escalate one conversation instead of restarting it.

PAIR and TAP send each attempt cold: the target sees one prompt and no
history. Crescendo sends a conversation. Every accepted turn is appended to
it and the whole thing is re-sent, so by the time the harmful question
arrives the target has already agreed to discuss the subject at length, and
the question reads as the next step rather than the first one.

That makes refusals special. Escalating from a refusal teaches the
conversation that refusing is acceptable, so a refused turn is *backtracked*
instead: it is dropped from the target's history and the attacker is asked
to rephrase the same step. The turn counter does not advance, so a rephrase
costs a backtrack rather than a turn. Once the backtrack budget is spent a
refusal is accepted and the conversation moves on.

Based on: https://arxiv.org/abs/2404.01833
"""

from __future__ import annotations

from typing import Optional

from ...contract import Completion, Judge, Messages, Target
from ...iterative import Finding, IterativeAttack, judge_reply, succeeded
from ...trace import decision, phase
from . import prompts
from .config import CrescendoParams


class CrescendoAttack(IterativeAttack[CrescendoParams]):
    """One conversation with the target, escalated a turn at a time."""

    name = "crescendo"
    params_type = CrescendoParams

    def __init__(self, params: CrescendoParams) -> None:
        super().__init__(params)
        if params.attacker is None:
            raise ValueError("Crescendo needs an 'attacker' role to write its turns.")
        self.attacker: Completion = params.attacker

    async def search(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[Finding]:
        params = self.params
        plan: Messages = [
            {"role": "system", "content": prompts.system_prompt(goal)},
            {"role": "user", "content": prompts.opening_request(goal)},
        ]
        #: The target's own conversation. Only accepted turns reach it.
        history: Messages = []
        findings: list[Finding] = []
        backtracks = 0
        turn = 0

        while turn < params.max_turns:
            label = f"turn {turn + 1}/{params.max_turns}"
            with phase(label, turn=turn, backtracks=backtracks) as path:
                question = await self._ask(plan)
                if question is None:
                    decision("stopped", "the attacker proposed no usable question")
                    break

                conversation = history + [{"role": "user", "content": question}]
                reply = await target(conversation)
                if not reply.ok or not reply.text:
                    decision("skipped", "the target gave no usable reply")
                    self._feed_back(goal, plan, "[no reply]", None, refused=True)
                    turn += 1
                    continue

                refused = prompts.refused(reply.text)
                verdict = await judge_reply(judge, goal, question, reply.text)
                score = None if verdict is None else verdict.score
                self._feed_back(goal, plan, reply.text, score, refused=refused)

                findings.append(
                    Finding(
                        messages=conversation,
                        response=reply,
                        verdict=verdict,
                        metadata={
                            "turn": turn,
                            "refused": refused,
                            "backtracked": refused
                            and backtracks < params.max_backtracks,
                            "score": score,
                        },
                        path=path,
                    )
                )

                if refused and backtracks < params.max_backtracks:
                    backtracks += 1
                    decision(
                        "backtracked",
                        "the target refused; rephrasing the same step",
                        used=backtracks,
                        budget=params.max_backtracks,
                    )
                    # The turn index does not advance, and this exchange
                    # never joins the target's history.
                    continue

                history = conversation + [{"role": "assistant", "content": reply.text}]
                turn += 1

                # A refusal accepted only because the budget ran out is
                # still a refusal, so it does not end the search.
                if params.early_stop and not refused and succeeded(verdict):
                    decision("stopped", "a turn reached a reply the panel passed")
                    break

        return findings

    async def _ask(self, plan: Messages) -> Optional[str]:
        """Ask the attacker for the next question, and log what it proposed."""
        try:
            reply = await self.attacker(plan)
        except Exception:
            return None
        parsed = prompts.parse_turn(reply)
        if parsed is None:
            return None
        question, logged = parsed
        plan.append({"role": "assistant", "content": logged})
        return question

    def _feed_back(
        self,
        goal: str,
        plan: Messages,
        reply: str,
        score: Optional[float],
        *,
        refused: bool,
        explanation: str = "",
    ) -> None:
        """Append what came back to the attacker's log, then trim it."""
        params = self.params
        plan.append(
            {
                "role": "user",
                "content": prompts.feedback(
                    goal,
                    reply,
                    score,
                    refused=refused,
                    explanation=explanation,
                    limit=params.feedback_max_chars,
                ),
            }
        )
        keep = 1 + 2 * params.keep_last_n
        if len(plan) > keep:
            plan[:] = [plan[0], *plan[-2 * params.keep_last_n :]]


__all__ = ["CrescendoAttack"]
