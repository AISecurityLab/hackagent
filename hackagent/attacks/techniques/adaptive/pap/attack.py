# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PAP: restate the goal with one persuasion technique after another.

Each technique is a taxonomy entry the attacker model rewrites the goal
with. The rewrite goes to the target, the panel judges the reply, and the
search stops at the first technique the panel calls a success. A technique
whose rewrite fails is skipped, so one unusable attacker reply does not end
the search.

Every technique that reached the target is returned, so the panel rates
each one and the run reports which techniques worked.

Persuasive Adversarial Prompts (PAP) treat the target as a person to be
persuaded rather than a system to be broken: the request keeps its intent
but is rephrased with a technique from social-science persuasion research,
such as citing evidence, invoking an expert or an authority, or a logical
appeal. Such humanised requests are often answered where the plain request
is refused.

Paper: Yi Zeng, Hongpeng Lin, Jingwen Zhang, Diyi Yang, et al., "How Johnny
Can Persuade LLMs to Jailbreak Them: Rethinking Persuasion to Challenge AI
Safety by Humanizing LLMs", 2024,
[arXiv:2401.06373](https://arxiv.org/abs/2401.06373). The 40-technique
taxonomy and the mutation prompt are ported from the authors' code,
https://github.com/CHATS-lab/persuasive_jailbreaker.

Algorithm (one goal), with the parameters of :class:`~.config.PAPParams`:

1. Resolve ``techniques`` to an ordered list: ``"top5"`` (the five the
   paper found most effective: evidence-based persuasion, expert
   endorsement, misrepresentation, authority endorsement, logical appeal),
   ``"all"`` (the 40 techniques in taxonomy order) or explicit names; keep
   the first ``max_techniques`` when it is not 0.
2. For each technique in order:

   - ask the ``attacker`` to mutate the goal with it, from a prompt giving
      the technique's definition and one worked example, and extract the
      ``#mutated_text...`` field of the reply (the whole reply when the tag
      is missing); a failed or empty rewrite skips the technique;
   - send the rewrite to the target as a single user message; an unusable
      reply skips the technique;
   - have the campaign's evaluation panel judge the reply, and stop at
      the first success.

Deviations from the paper: the paper paraphrases with a persuasive
paraphraser fine-tuned on PAP examples; here any chat model is prompted
with a one-shot mutation prompt (one example per top-5 technique, a generic
example for the rest) instead of the authors' five-shot templates. Each
technique is tried once, in order, and the panel replaces the paper's GPT-4
harmfulness judge.

Roles: ``attacker`` (required), the persuasive paraphraser, called once per
technique tried.

Attempts and success: every rewrite that got a usable reply is one
attempt, tagged with its technique; the goal succeeds when the panel calls
any of them a success, and the sweep stops there.
"""

from __future__ import annotations

from typing import Optional

from ...contract import Completion, Judge, Target
from ...iterative import Finding, IterativeAttack, judge_reply, succeeded
from ...trace import decision, phase
from .config import PAPParams
from .taxonomy import build_mutation_prompt, extract_mutated_text, resolve_techniques


class PAPAttack(IterativeAttack[PAPParams]):
    """Rephrase the goal with one persuasion technique after another until one works.

    Implements Persuasive Adversarial Prompts (Zeng et al., 2024,
    [arXiv:2401.06373](https://arxiv.org/abs/2401.06373)): for each selected
    technique of the 40-technique persuasion taxonomy, the ``attacker``
    rewrites the goal, the rewrite is sent once, and the campaign's
    evaluation panel judges the reply; the sweep stops at the first success.
    The algorithm and the deviations from the paper are documented in the
    module ``hackagent.attacks.techniques.adaptive.pap.attack``.
    """

    name = "pap"
    params_type = PAPParams

    def __init__(self, params: PAPParams) -> None:
        super().__init__(params)
        if params.attacker is None:
            raise ValueError("PAP needs an 'attacker' role to rewrite the goal.")
        self.attacker: Completion = params.attacker
        techniques = resolve_techniques(params.techniques)
        self.techniques = (
            techniques[: params.max_techniques] if params.max_techniques else techniques
        )

    async def search(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[Finding]:
        """Try each technique in order and return every judged attempt.

        Calls the ``attacker``, the target and the panel once per technique
        tried, and stops after the first success.
        """
        findings: list[Finding] = []
        total = len(self.techniques)

        for index, technique in enumerate(self.techniques):
            label = f"technique {index + 1}/{total}: {technique}"
            with phase(label, technique=technique, index=index) as path:
                prompt = await self._rewrite(goal, technique)
                if prompt is None:
                    decision("skipped", "the attacker produced no usable rewrite")
                    continue

                messages = [{"role": "user", "content": prompt}]
                reply = await target(messages)
                if not reply.ok or not reply.text:
                    decision("skipped", "the target gave no usable reply")
                    continue

                verdict = await judge_reply(judge, goal, prompt, reply.text)
                findings.append(
                    Finding(
                        messages=messages,
                        response=reply,
                        verdict=verdict,
                        metadata={"technique": technique, "technique_index": index},
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

    async def _rewrite(self, goal: str, technique: str) -> Optional[str]:
        """Restate ``goal`` using ``technique``; ``None`` when that fails."""
        instruction = build_mutation_prompt(goal, technique)
        try:
            reply = await self.attacker([{"role": "user", "content": instruction}])
        except Exception:
            return None
        rewritten = extract_mutated_text(reply or "").strip()
        return rewritten or None


__all__ = ["PAPAttack"]
