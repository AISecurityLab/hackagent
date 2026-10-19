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

Based on: https://arxiv.org/abs/2401.06373
"""

from __future__ import annotations

from typing import Optional

from ...contract import Completion, Judge, Target
from ...iterative import Finding, IterativeAttack, judge_reply, succeeded
from ...trace import decision, phase
from .config import PAPParams
from .taxonomy import build_mutation_prompt, extract_mutated_text, resolve_techniques


class PAPAttack(IterativeAttack[PAPParams]):
    """A sweep over persuasion techniques, one request each."""

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
