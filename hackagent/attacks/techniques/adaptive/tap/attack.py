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

Paper: Anay Mehrotra, Manolis Zampetakis, Paul Kassianik, Blaine Nelson, et
al., "Tree of Attacks: Jailbreaking Black-Box LLMs Automatically", 2023,
[arXiv:2312.02119](https://arxiv.org/abs/2312.02119). Tree of Attacks with
Pruning (TAP) extends PAIR (:mod:`..pair`) with tree-of-thought branching
and an evaluator that prunes before and after each target query.

Algorithm (one goal), with the parameters of :class:`~.config.TapParams`:

1. Start ``streams`` root branches, each an attacker conversation holding
   the TAP attacker system prompt for the goal and ``target_str`` and an
   opening request.
2. For each of ``depth`` levels:

   - **Branch.** Ask the ``attacker`` for ``branching_factor`` refinements
      of every surviving branch, each on its own copy of the parent's
      conversation. A refinement must be a JSON turn with ``improvement``
      and ``prompt``; the attacker gets up to ``max_attempts`` tries before
      that child is dropped.
   - **Prune off-topic.** With an ``on_topic`` role, ask it YES/NO whether
      each new prompt still asks for the goal and drop the NOs (an
      unreadable answer keeps the branch). If nothing is left, stop.
   - **Attack and assess.** Send every remaining prompt to the target as
      a fresh single-message conversation, have the campaign's evaluation
      panel judge each usable reply, and feed reply and score back into the
      branch's conversation, trimmed to the system prompt plus the last
      ``keep_last_n`` attacker turns.
   - With ``early_stop``, stop when any reply is a panel success.
   - **Prune by score.** Shuffle (to break ties at random), rank by panel
      score, keep the branches scoring above ``min_prune_score``, at most
      ``width`` of them; when none scores above it, keep the single best.

Deviations from the paper: the paper's defaults are depth 10, width 10
and branching factor 4, with one GPT-4 evaluator doing both prunes; here
the defaults are smaller, the off-topic check is a separate optional
``on_topic`` role, and the score prune and the success decision use the
campaign's panel. Feedback to the attacker carries the reply and the score,
not the panel's explanation. With no judges every score is 0, so each round
keeps a single random branch.

Roles: ``attacker`` (required) writes every refinement; ``on_topic``
(optional) filters off-topic prompts before they cost a target call.

Attempts and success: every prompt that got a usable reply from the target
is one attempt, judged by the campaign's evaluation panel and tagged with
its position in the tree (``candidate_path``, ``parent_path``) and score.
The goal succeeds when any attempt is a success.
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
    parent_path: Path = ()
    response: Any = None

    @property
    def score(self) -> float:
        """The panel's score for the last reply; 0 when it was not judged."""
        return 0.0 if self.verdict is None else self.verdict.score

    def child(self) -> "Branch":
        """A new branch under this one, with a copy of its conversation."""
        return Branch(
            conversation=[dict(turn) for turn in self.conversation],
            parent_path=self.path,
        )


@dataclass
class Round:
    """What one depth level produced, before anything is pruned."""

    branches: list[Branch] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


class TAPAttack(IterativeAttack[TapParams]):
    """Grow a tree of attacker-refined prompts, pruning off-topic and low-scoring branches.

    Implements Tree of Attacks with Pruning (Mehrotra et al., 2023,
    [arXiv:2312.02119](https://arxiv.org/abs/2312.02119)): every round the
    ``attacker`` branches each surviving prompt ``branching_factor`` ways,
    the optional ``on_topic`` role drops prompts that drifted from the goal
    before they reach the target, the campaign's evaluation panel judges
    every reply, and only the best ``width`` branches continue, for up to
    ``depth`` rounds. The algorithm and the deviations from the paper are
    documented in the module ``hackagent.attacks.techniques.adaptive.tap.attack``.
    """

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
        """Grow and prune the tree; return every attempt that got a usable reply.

        Calls the ``attacker`` at least once per child, ``on_topic`` once per
        child when configured, and the target and the panel once per kept
        child.
        """
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
        with phase("candidate", parent_path=list(parent.path)) as path:
            branch.path = path
            for _ in range(self.params.max_attempts):
                try:
                    reply = await self.attacker(branch.conversation)
                except Exception:
                    continue
                proposal = _parse(reply)
                if proposal is None:
                    continue
                branch.prompt, assistant_turn = proposal
                branch.conversation.append(
                    {"role": "assistant", "content": assistant_turn}
                )
                return branch
            decision("skipped", "the attacker proposed no usable prompt")
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
        if len(kept) < len(branches):
            decision(
                "pruned",
                "off the goal",
                dropped=len(branches) - len(kept),
                kept=len(kept),
                candidate_paths=[list(b.path) for b in branches if b not in kept],
            )
        return kept

    async def _ask_on_topic(self, goal: str, prompt: str) -> Optional[bool]:
        """Ask the ``on_topic`` role about one prompt; ``None`` when it gave no answer."""
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
        with phase(
            f"branch {index + 1}/{total}",
            branch=index,
            candidate_path=list(branch.path),
        ) as path:
            messages = [{"role": "user", "content": branch.prompt}]
            reply = await target(messages)
            if not reply.ok or not reply.text:
                decision(
                    "skipped",
                    "the target gave no usable reply",
                    candidate_paths=[list(branch.path)],
                )
                self._feed_back(goal, branch, "[no reply]")
                return branch, None

            branch.verdict = await judge_reply(judge, goal, branch.prompt, reply.text)
            branch.response = reply
            self._feed_back(goal, branch, reply.text)
            return branch, Finding(
                messages=messages,
                response=reply,
                verdict=branch.verdict,
                metadata={
                    "score": branch.verdict.score if branch.verdict else None,
                    "candidate_path": list(branch.path),
                    "parent_path": list(branch.parent_path),
                },
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
                candidate_paths=[list(b.path) for b in branches if b not in survivors],
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
