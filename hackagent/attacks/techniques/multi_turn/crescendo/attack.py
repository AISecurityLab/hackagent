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
instead: it is dropped from the target's history, it is not judged, and the
attacker is asked to rephrase the same step. The turn counter does not
advance, so a rephrase costs a backtrack rather than a turn. Once the
backtrack budget is spent a refused turn is kept, judged like any other, and
the conversation moves on.

A refusal is decided by an LLM Refusal Judge (paper, section 4.1), as in
the reference implementation, PyRIT's ``CrescendoAttack`` with its default
``SelfAskRefusalScorer``: the strict rubric, read against the attack's goal.

Paper: Mark Russinovich, Ahmed Salem, Ronen Eldan, "Great, Now Write an
Article About That: The Crescendo Multi-Turn LLM Jailbreak Attack", 2024,
[arXiv:2404.01833](https://arxiv.org/abs/2404.01833). The paper's
automated variant (Crescendomation) is reproduced after the reference
implementation, PyRIT's ``CrescendoAttack``
(https://github.com/microsoft/PyRIT,
``pyrit/executor/attack/multi_turn/crescendo.py``).

Algorithm (one goal), with the parameters of
:class:`~.config.CrescendoParams`:

1. Open the attacker's planning log: the Crescendo system prompt for the
   goal and an opening request. The target's own history starts empty.
2. While fewer than ``max_turns`` turns have been accepted:

   - ask the ``attacker`` for the next question (a JSON turn; an unusable
     one ends the search);
   - send the target its history plus the question; an unusable reply
     counts as a turn and is fed back as ``[no reply]``;
   - ask the Refusal Judge (the ``refusal`` role, or the ``attacker`` when
     it is not set) whether the reply refuses the goal; an unreadable or
     failed answer is not a refusal;
   - on a refusal, while fewer than ``max_backtracks`` backtracks have been
     used: record the exchange as not judged, leave it out of the target's
     history, tell the attacker it was refused, and ask again for the same
     turn;
   - otherwise have the campaign's evaluation panel judge the question and
     reply, feed the reply (cut to ``feedback_max_chars``) and the panel's
     score back to the attacker, append the exchange to the target's
     history, and advance the turn; with ``early_stop``, stop at the first
     panel success.

   The attacker's log is trimmed to its system prompt plus the last
   ``keep_last_n`` turns; the target's history is never trimmed.

Deviations from the paper: the paper's evaluation judge is replaced by the
campaign's panel, which sees the latest question and reply rather than the
whole conversation. A reply the target could not give still uses up a
turn.

Roles: ``attacker`` (required) plans the conversation and writes every
question; ``refusal`` (optional) is the Refusal Judge, defaulting to the
attacker model.

Attempts and success: every exchange is one attempt carrying the whole
conversation sent, its turn and whether it was refused or backtracked.
Backtracked exchanges carry a "not judged" verdict; the goal succeeds when
the panel calls any judged exchange a success.
"""

from __future__ import annotations

from typing import Optional

from hackagent.core.contracts import Verdict

from ...contract import Completion, Judge, Messages, Target
from ...iterative import Finding, IterativeAttack, judge_reply, succeeded
from ...trace import decision, evaluation_request, phase
from . import prompts
from .config import CrescendoParams


class CrescendoAttack(IterativeAttack[CrescendoParams]):
    """Escalate one conversation with the target, backtracking on refusals.

    Implements Crescendo (Russinovich et al., 2024,
    [arXiv:2404.01833](https://arxiv.org/abs/2404.01833)), after PyRIT's
    reference implementation: the ``attacker`` writes each next question a
    little closer to the goal, the whole conversation is re-sent, a refused
    turn is dropped and rephrased while the backtrack budget lasts, and the
    campaign's evaluation panel judges every accepted reply. The algorithm
    and the deviations from the paper are documented in the module
    ``hackagent.attacks.techniques.multi_turn.crescendo.attack``.
    """

    name = "crescendo"
    params_type = CrescendoParams

    def __init__(self, params: CrescendoParams) -> None:
        super().__init__(params)
        if params.attacker is None:
            raise ValueError("Crescendo needs an 'attacker' role to write its turns.")
        self.attacker: Completion = params.attacker
        self.refusal_judge: Completion = params.refusal or params.attacker

    async def search(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[Finding]:
        """Run the conversation for ``goal``; return every exchange, in order.

        Calls the ``attacker``, the target and the Refusal Judge once per
        exchange, and the panel once per exchange that is not backtracked.
        """
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

                refused, why = await self._refused(goal, reply.text)
                backtrack = refused and backtracks < params.max_backtracks
                if backtrack:
                    # Backtracked turns are not judged, as in the reference.
                    verdict = (
                        None
                        if judge is None
                        else Verdict(
                            success=False,
                            score=0.0,
                            explanation=f"not judged: backtracked after a refusal. {why}".strip(),
                        )
                    )
                    score = None
                else:
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
                            "refusal_rationale": why,
                            "backtracked": backtrack,
                            "score": score,
                        },
                        path=path,
                    )
                )

                if backtrack:
                    backtracks += 1
                    decision(
                        "backtracked",
                        "the refusal judge found a refusal; rephrasing the same step",
                        used=backtracks,
                        budget=params.max_backtracks,
                    )
                    # The turn index does not advance, and this exchange
                    # never joins the target's history.
                    continue

                history = conversation + [{"role": "assistant", "content": reply.text}]
                turn += 1

                if params.early_stop and succeeded(verdict):
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

    async def _refused(self, goal: str, reply: str) -> tuple[bool, str]:
        """Ask the Refusal Judge whether the reply refuses the goal, and why.

        An unreadable or failed verdict is not a refusal: PyRIT scores it as
        undetermined, which does not trigger a backtrack.
        """
        try:
            with evaluation_request(goal, reply):
                answer = await self.refusal_judge(
                    [
                        {"role": "system", "content": prompts.REFUSAL_JUDGE_PROMPT},
                        {
                            "role": "user",
                            "content": prompts.refusal_request(goal, reply),
                        },
                    ]
                )
        except Exception:
            return False, "the refusal judge could not be reached"
        parsed = prompts.parse_refusal(answer)
        if parsed is None:
            return False, "the refusal judge gave no readable verdict"
        return parsed

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
