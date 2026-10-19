# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""TAP: grow a tree of attacker prompts and prune it twice a round.

PAIR refines a fixed set of conversations. TAP grows them: each surviving
branch asks the attacker for ``branching_factor`` refinements, so a round
multiplies the candidates and the prunes bring them back down.

There are two prunes, and the order is the point:

- **off topic**, before the target is called. A branch whose prompt has
  drifted away from the goal is dropped while it is still free. This needs
  an ``on_topic`` role; without one nothing is dropped here.
- **by score**, after. The branches are ranked by what the panel made of
  their replies and only ``width`` survive into the next round, so the tree
  stays the same size however wide it fans out.

The best branch always survives the score prune. A round that pruned to
nothing would end the search on one bad judging pass.

Based on: https://arxiv.org/abs/2312.02119
"""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, field
from typing import Any, Optional

from hackagent.attacks._lib.prompt_parser import extract_prompt_and_improvement
from hackagent.core.contracts import Verdict

from ...contract import Completion, Judge, Messages, Target
from ...iterative import Finding, IterativeAttack, judge_reply, succeeded
from ...trace import Path, decision, phase
from . import prompts
from .config import TapParams


@dataclass
class Branch:
    """One node of the tree: its conversation, and what it last scored."""

    #: The attacker conversation that produced this branch, parent history
    #: included. A child copies it, so siblings cannot overwrite each other.
    conversation: Messages
    #: The prompt the attacker proposed. Empty on a root, which has not
    #: proposed anything yet.
    prompt: str = ""
    verdict: Optional[Verdict] = None
    path: Path = ()
    response: Any = None

    @property
    def score(self) -> float:
        return 0.0 if self.verdict is None else self.verdict.score

    def child(self) -> "Branch":
        return Branch(conversation=[dict(turn) for turn in self.conversation])


@dataclass
class Round:
    """What one depth level produced, before anything is pruned."""

    branches: list[Branch] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


class TAPAttack(IterativeAttack[TapParams]):
    """A pruned tree of attacker-refined prompts."""

    name = "tap"
    params_type = TapParams

    def __init__(self, params: TapParams) -> None:
        super().__init__(params)
        if params.attacker is None:
            raise ValueError("TAP needs an 'attacker' role to write its prompts.")
        self.attacker: Completion = params.attacker
        self.on_topic: Optional[Completion] = params.on_topic

    async def search(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[Finding]:
        params = self.params
        branches = [self._root(goal) for _ in range(params.streams)]
        findings: list[Finding] = []

        for level in range(params.depth):
            with phase(f"depth {level + 1}/{params.depth}", depth=level):
                grown = await self._expand(goal, branches)
                kept = await self._keep_on_topic(goal, grown)
                if not kept:
                    decision("stopped", "every branch drifted off the goal")
                    break

                round_ = await self._probe(goal, kept, target, judge)
                findings.extend(round_.findings)
                if params.early_stop and any(
                    succeeded(found.verdict) for found in round_.findings
                ):
                    decision("stopped", "a branch reached a reply the panel passed")
                    break
                branches = self._prune(goal, round_.branches)

        return findings

    def _root(self, goal: str) -> Branch:
        """One stream's opening conversation with the attacker."""
        target_str = self.params.target_str
        return Branch(
            conversation=[
                {
                    "role": "system",
                    "content": prompts.system_prompt(goal, target_str),
                },
                {
                    "role": "user",
                    "content": prompts.opening_request(goal, target_str),
                },
            ]
        )

    async def _expand(self, goal: str, branches: list[Branch]) -> list[Branch]:
        """Ask the attacker for every refinement of every surviving branch."""
        _ = goal
        with phase("expand", branches=len(branches)):
            grown = await asyncio.gather(
                *(
                    self._refine(branch)
                    for branch in branches
                    for _ in range(self.params.branching_factor)
                )
            )
        kept = [branch for branch in grown if branch is not None]
        if len(kept) < len(grown):
            decision(
                "skipped",
                "the attacker proposed no usable prompt",
                dropped=len(grown) - len(kept),
            )
        return kept

    async def _refine(self, parent: Branch) -> Optional[Branch]:
        """One refinement of one branch, retried while the attacker rambles."""
        branch = parent.child()
        for _ in range(self.params.max_attempts):
            try:
                reply = await self.attacker(branch.conversation)
            except Exception:
                continue
            proposal = _parse(reply)
            if proposal is None:
                continue
            branch.prompt, assistant_turn = proposal
            branch.conversation.append({"role": "assistant", "content": assistant_turn})
            return branch
        return None

    async def _keep_on_topic(self, goal: str, branches: list[Branch]) -> list[Branch]:
        """Drop branches that no longer ask for the goal, before they cost a call."""
        if self.on_topic is None or not branches:
            return branches
        with phase("on topic", branches=len(branches)):
            answers = await asyncio.gather(
                *(self._ask_on_topic(goal, branch.prompt) for branch in branches)
            )
        # An unreadable answer keeps the branch: a stuttering judge should
        # not narrow the search.
        kept = [
            branch
            for branch, on_topic in zip(branches, answers)
            if on_topic is not False
        ]
        # The reference caps this prune at the beam width too, so a wide
        # fan-out costs at most ``width`` target calls per round rather
        # than one per surviving branch.
        survivors = kept[: self.params.width]
        if len(survivors) < len(branches):
            decision(
                "pruned",
                "off the goal, then down to the beam",
                dropped=len(branches) - len(survivors),
                kept=len(survivors),
            )
        return survivors

    async def _ask_on_topic(self, goal: str, prompt: str) -> Optional[bool]:
        assert self.on_topic is not None
        messages = [
            {"role": "system", "content": prompts.on_topic_system_prompt(goal)},
            {"role": "user", "content": prompts.on_topic_request(goal, prompt)},
        ]
        try:
            return prompts.parse_on_topic(await self.on_topic(messages))
        except Exception:
            return None

    async def _probe(
        self, goal: str, branches: list[Branch], target: Target, judge: Optional[Judge]
    ) -> Round:
        """Send every surviving branch to the target and judge what comes back."""
        results = await asyncio.gather(
            *(
                self._attempt(goal, index, len(branches), branch, target, judge)
                for index, branch in enumerate(branches)
            )
        )
        round_ = Round()
        for branch, finding in results:
            round_.branches.append(branch)
            if finding is not None:
                round_.findings.append(finding)
        return round_

    async def _attempt(
        self,
        goal: str,
        index: int,
        total: int,
        branch: Branch,
        target: Target,
        judge: Optional[Judge],
    ) -> tuple[Branch, Optional[Finding]]:
        """One branch's turn: send, judge, and feed the result back."""
        with phase(f"branch {index + 1}/{total}", branch=index) as path:
            branch.path = path
            messages = [{"role": "user", "content": branch.prompt}]
            reply = await target(messages)
            if not reply.ok or not reply.text:
                decision("skipped", "the target gave no usable reply")
                self._feed_back(goal, branch, "[no reply]")
                return branch, None

            branch.verdict = await judge_reply(judge, goal, branch.prompt, reply.text)
            branch.response = reply
            self._feed_back(goal, branch, reply.text)
            return branch, Finding(
                messages=messages,
                response=reply,
                verdict=branch.verdict,
                metadata={"score": branch.verdict.score if branch.verdict else None},
                path=path,
            )

    def _prune(self, goal: str, branches: list[Branch]) -> list[Branch]:
        """Keep the best ``width`` branches, and always at least one.

        Ties are broken at random rather than by position, so a branch is
        not favoured for having been expanded first.
        """
        _ = goal
        params = self.params
        ordered = list(branches)
        random.shuffle(ordered)
        ordered.sort(key=lambda branch: branch.score, reverse=True)

        above = [branch for branch in ordered if branch.score > params.min_prune_score]
        survivors = (above or ordered[:1])[: params.width]
        if survivors and len(survivors) < len(branches):
            decision(
                "pruned",
                "below the beam",
                dropped=len(branches) - len(survivors),
                kept=len(survivors),
                best=round(survivors[0].score, 3),
            )
        return survivors

    def _feed_back(self, goal: str, branch: Branch, reply: str) -> None:
        """Append what came back, then trim the branch's history."""
        branch.conversation.append(
            {
                "role": "user",
                "content": prompts.feedback(
                    goal,
                    reply,
                    None if branch.verdict is None else branch.verdict.score,
                ),
            }
        )
        keep = 1 + 2 * self.params.keep_last_n
        if len(branch.conversation) > keep:
            branch.conversation[:] = [
                branch.conversation[0],
                *branch.conversation[-2 * self.params.keep_last_n :],
            ]


def _parse(reply: Optional[str]) -> Optional[tuple[str, str]]:
    """Read the attacker's JSON turn, as PAIR's parser does."""
    if not reply or '"improvement"' not in reply:
        return None
    parsed: Optional[dict[str, Any]] = extract_prompt_and_improvement(
        reply, allow_plaintext=False
    )
    if not parsed or not parsed.get("prompt"):
        return None
    return parsed["prompt"], json.dumps(parsed, ensure_ascii=False)


__all__ = ["Branch", "TAPAttack"]
