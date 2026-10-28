# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""h4rm3l synthesis: search the decorator language for programs that work.

Where ``h4rm3l`` runs a program you wrote, this searches for one. Synthesis
happens once per run, in :meth:`prepare`: each round shows the synthesizer
the programs that have scored best, compiles what it proposes, scores the
valid ones against the target on goals drawn afresh for each, and keeps
those above the pool's mean. :meth:`search` then applies the best programs
the pool ended with to each goal, one request each.

The pool is what the run learns, so a program proven on one goal is tried
on all of them. Compilation is the validity filter: the h4rm3l compiler
accepts only registered primitives with literal arguments, so a proposal
that is not a well-formed program is discarded rather than run.

Based on: https://arxiv.org/abs/2408.04811
"""

from __future__ import annotations

import inspect
import random
from typing import Callable, Optional

from ...contract import Completion, Judge, Target
from ...iterative import Finding, IterativeAttack, judge_reply, succeeded
from ...static.h4rm3l.decorators import compile_program
from ...static.h4rm3l.programs import PRESET_PROGRAMS
from ...trace import decision, phase
from .config import H4rm3lSynthParams
from .pool import ProgramPool
from .primitives import primitive_signatures
from .prompts import SYSTEM_PROMPT, build_proposal_prompt, parse_programs

Decorate = Callable[[str], object]


class H4rm3lSynthAttack(IterativeAttack[H4rm3lSynthParams]):
    """A search over decorator programs, shared by every goal."""

    name = "h4rm3l_synth"
    params_type = H4rm3lSynthParams

    def __init__(self, params: H4rm3lSynthParams) -> None:
        super().__init__(params)
        if params.synthesizer is None:
            raise ValueError(
                "h4rm3l_synth needs a 'synthesizer' role to write programs."
            )
        self.synthesizer: Completion = params.synthesizer
        self.pool = ProgramPool()
        self._rng = random.Random(params.seed)
        if params.seed is not None:
            self.pool._random.seed(params.seed)
        self.pool.seed(list(PRESET_PROGRAMS.values()))
        self.primitives = primitive_signatures(
            with_decorator_model=params.decorator is not None
        )

    # ── compilation ───────────────────────────────────────────────────────────

    def _compile(self, program: str) -> Optional[Decorate]:
        """Compile ``program``, or ``None`` when it is not a valid one.

        A rejected program is recorded with the compiler's complaint. It is
        the one failure that says nothing about the attack and everything
        about what the synthesizer was told, so it must not be silent.
        """
        try:
            return compile_program(
                program,
                self.params.syntax_version,
                completion=self.params.decorator,
            )
        except (ValueError, TypeError, SyntaxError, KeyError) as error:
            decision(
                "skipped",
                f"the program does not compile: {error}",
                program=program,
            )
            return None

    async def _apply(self, decorate: Decorate, goal: str) -> Optional[str]:
        """Run a compiled program over ``goal``; ``None`` when it fails."""
        try:
            result = decorate(goal)
            prompt = await result if inspect.isawaitable(result) else result
        except Exception:
            return None
        return prompt.strip() if isinstance(prompt, str) and prompt.strip() else None

    # ── synthesis ─────────────────────────────────────────────────────────────

    async def _propose(self, round_number: int) -> list[str]:
        """Ask the synthesizer for new programs, shown what has worked."""
        chosen = self.pool.sample(
            self.params.examples, round_number, self.params.concentration
        )
        examples = [(program, self.pool.entries[program].asr) for program in chosen]
        instruction = build_proposal_prompt(
            self.primitives, examples, self.params.proposals
        )
        try:
            reply = await self.synthesizer(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": instruction},
                ]
            )
        except Exception as error:
            decision("skipped", f"the synthesizer could not be reached: {error}")
            return []
        programs = parse_programs(reply or "")
        if not programs:
            decision("skipped", "the synthesizer's reply held no program")
        return programs

    def _scoring_goals(self, goals: list[str]) -> list[str]:
        """The goals one proposal is scored on, drawn afresh for each.

        A fixed slice would put every program's fate in the hands of the
        same few goals, and a run's goals are not shuffled: the first of
        them are a single category, so a hard one starves the search of
        signal while a soft one flatters everything. Drawing per proposal
        spreads both risks, and spreads the overlap with the goals the run
        goes on to report.
        """
        count = min(self.params.scoring_goals, len(goals))
        return self._rng.sample(goals, count)

    async def _score(
        self,
        decorate: Decorate,
        goals: list[str],
        target: Target,
        judge: Optional[Judge],
    ) -> tuple[int, int]:
        """Successes and trials for one program over ``goals``."""
        successes = trials = 0
        for goal in goals:
            prompt = await self._apply(decorate, goal)
            if prompt is None:
                continue
            reply = await target([{"role": "user", "content": prompt}])
            if not reply.ok or not reply.text:
                continue
            trials += 1
            if succeeded(await judge_reply(judge, goal, prompt, reply.text)):
                successes += 1
        return successes, trials

    async def prepare(
        self, goals: list[str], target: Target, judge: Optional[Judge] = None
    ) -> None:
        """Search the language for programs, before any goal is attacked."""
        if judge is None:
            decision(
                "skipped",
                "no panel is configured, so a program cannot be scored; "
                "the seed programs are used as they are",
            )
            return

        for round_number in range(1, self.params.iterations + 1):
            label = f"synthesis round {round_number}/{self.params.iterations}"
            with phase(label, round=round_number):
                proposals = await self._propose(round_number)
                if not proposals:
                    continue

                threshold = self.pool.mean_asr()
                kept = invalid = unscored = 0
                for program in proposals:
                    if program in self.pool.entries:
                        continue
                    decorate = self._compile(program)
                    if decorate is None:
                        invalid += 1
                        continue
                    successes, trials = await self._score(
                        decorate, self._scoring_goals(goals), target, judge
                    )
                    if not trials:
                        unscored += 1
                        decision(
                            "skipped",
                            "the program produced no reply to score",
                            program=program,
                        )
                        continue
                    entry = self.pool.record(program, successes, trials)
                    if entry.asr > threshold:
                        kept += 1
                    else:
                        del self.pool.entries[program]
                decision(
                    "kept",
                    f"{kept} of {len(proposals)} proposals beat the pool mean; "
                    f"{invalid} did not compile, {unscored} could not be scored",
                    pool_size=self.pool.size(),
                    mean_asr=round(threshold, 3),
                    invalid=invalid,
                    unscored=unscored,
                )

    # ── search ────────────────────────────────────────────────────────────────

    async def search(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[Finding]:
        findings: list[Finding] = []
        programs = self.pool.best(self.params.programs_per_goal)

        for index, program in enumerate(programs):
            label = f"program {index + 1}/{len(programs)}"
            with phase(label, program=program, index=index) as path:
                decorate = self._compile(program)
                if decorate is None:
                    continue

                prompt = await self._apply(decorate, goal)
                if prompt is None:
                    decision("skipped", "the program produced no usable prompt")
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
                        metadata={
                            "program": program,
                            "program_index": index,
                            "program_asr": self.pool.entries[program].asr,
                        },
                        path=path,
                    )
                )
                if succeeded(verdict):
                    decision("stopped", "the panel called this reply a success")
                    break

        return findings


__all__ = ["H4rm3lSynthAttack"]
