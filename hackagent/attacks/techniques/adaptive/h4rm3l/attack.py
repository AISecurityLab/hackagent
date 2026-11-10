# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""h4rm3l: compose prompt decorators into a program, and search for one.

A program is an expression in a small language of composable prompt
decorators, and the attack sends the goal rewritten by it. Which program
is the whole question, so this answers it two ways from one configuration.

Without a ``synthesizer`` role it runs the program it was given — a preset
or one written by hand — once per goal: no model in the loop, no search,
the cheap repeatable baseline. With one, :meth:`prepare` searches the
language first, as the paper does: each round shows the synthesizer the
programs that have scored best, compiles what it proposes, scores the
valid ones against the target on goals drawn afresh for each, and keeps
those above the pool's mean. :meth:`search` then applies the best programs
the pool ended with to each goal, one request each.

The pool is what the run learns, so a program proven on one goal is tried
on all of them. Compilation is the validity filter: the h4rm3l compiler
accepts only registered primitives with literal arguments, so a proposal
that is not a well-formed program is discarded rather than run.

Paper: Moussa Koulako Bala Doumbouya, Ananjan Nandi, Gabriel Poesia,
Davide Ghilardi, et al., "h4rm3l: A language for Composable Jailbreak
Attack Synthesis", 2024, [arXiv:2408.04811](https://arxiv.org/abs/2408.04811).
h4rm3l expresses jailbreaks as compositions of parameterised string
transformations ("decorators": encodings, character noise, role-play
templates, refusal suppression, model-assisted rewrites) and synthesises
new compositions with an LLM guided by bandit-style few-shot sampling of
the programs that score best against the target.

Algorithm, with the parameters of :class:`~.config.H4rm3lParams`:

1. Resolve ``program`` (a preset name from
   :data:`~.programs.PRESET_PROGRAMS` or a program written in ``syntax_version``
   1 or 2 syntax) and compile it at construction, so a broken program fails
   before the run starts.
2. Synthesis, in :meth:`H4rm3lAttack.prepare`, once per run and only with a
   ``synthesizer`` role and a configured panel: seed the pool with
   ``program`` and every preset, then for each of ``iterations`` rounds:

   - draw ``examples`` programs from the pool, each scored by a Beta draw
      centred on its success rate whose concentration is ``concentration``
      times the round number (unscored programs draw from a uniform Beta),
      so early rounds explore and later rounds exploit;
   - show them, with their success rates and the signatures of every
      primitive that can be built (model-backed ones only when a
      ``decorator`` role is configured), to the ``synthesizer``, asking for
      ``proposals`` new programs, one per line;
   - compile each new proposal, rejecting anything that is not a chain of
      registered primitives with literal arguments;
   - score each valid one on ``scoring_goals`` goals drawn at random from
      the run's goals (``seed`` makes the draws repeatable): decorate the
      goal, send it as a single user message, and count panel successes;
   - keep a program only when its success rate beats the pool's mean at
      the start of the round.

3. Attack, in :meth:`H4rm3lAttack.search`, per goal: without a synthesizer,
   the one compiled ``program``; with one, the ``programs_per_goal`` best
   programs of the pool, best first. Each program decorates the goal (model
   calls through the ``decorator`` role where a primitive needs one), the
   result is sent as a single user message, and the panel judges the reply;
   the goal stops at the first success.

Deviations from the paper: synthesis runs inside the campaign against the
campaign's own target, scored by its evaluation panel on a few randomly
drawn goals of the same run, rather than as a separate offline study over
a fixed benchmark.
``TransformFxDecorator``, which executes Python, is accepted only when no
synthesizer is configured: with one, it is rejected even in the user's own
program. Some presets
are HackAgent's own measurements, marked in :mod:`.programs`.

Roles: ``synthesizer`` (optional) proposes programs during synthesis;
``decorator`` (optional, required by any program that uses a model-backed
primitive such as ``TranslateDecorator``) performs those rewrites.

Attempts and success: synthesis scoring is run-scoped work and produces no
attempt. Per goal, every program whose decorated prompt got a usable reply
is one attempt, tagged with the program and its pool success rate; the goal
succeeds when the panel calls any of them a success.
"""

from __future__ import annotations

import inspect
import random
from typing import Callable, Optional

from ...contract import Completion, Judge, Target
from ...iterative import Finding, IterativeAttack, judge_reply, succeeded
from ...trace import decision, phase
from .config import H4rm3lParams
from .decorators import compile_program
from .pool import ProgramPool
from .primitives import primitive_signatures
from .programs import PRESET_PROGRAMS, resolve_program
from .prompts import SYSTEM_PROMPT, build_proposal_prompt, parse_programs

Decorate = Callable[[str], object]


class H4rm3lAttack(IterativeAttack[H4rm3lParams]):
    """Rewrite the goal with a composed decorator program, optionally synthesised against the target.

    Implements h4rm3l (Doumbouya et al., 2024,
    [arXiv:2408.04811](https://arxiv.org/abs/2408.04811)): without a
    ``synthesizer`` role it applies one program (a preset or a hand-written
    composition of decorators) to each goal and sends the result once; with
    one, it first searches for programs that work against this target,
    scoring each on a few goals with the campaign's evaluation panel, and
    then attacks every goal with the best ``programs_per_goal`` of them,
    stopping at the first success. The algorithm and the deviations from the
    paper are documented in the module
    ``hackagent.attacks.techniques.adaptive.h4rm3l.attack``.
    """

    name = "h4rm3l"
    params_type = H4rm3lParams

    def __init__(self, params: H4rm3lParams) -> None:
        super().__init__(params)
        self.synthesizer: Optional[Completion] = params.synthesizer
        self._compiled: dict[str, Decorate] = {}
        self.program = resolve_program(params.program)
        # Eagerly, so a program that cannot compile fails while the campaign
        # is being built rather than against the first goal.
        self._compiled[self.program] = self._build(self.program)

        self.pool = ProgramPool()
        self._rng = random.Random(params.seed)
        if params.seed is not None:
            self.pool._random.seed(params.seed)
        if self.synthesizer is not None:
            self.pool.seed([self.program, *PRESET_PROGRAMS.values()])
        self.primitives = primitive_signatures(
            with_decorator_model=params.decorator is not None
        )

    # ── compilation ───────────────────────────────────────────────────────────

    def _build(self, program: str) -> Decorate:
        """Compile ``program`` with this run's ``decorator`` model.

        Code-executing primitives are allowed only when no synthesizer is
        configured, so every program compiled came from the user.
        """
        return compile_program(
            program,
            self.params.syntax_version,
            completion=self.params.decorator,
            allow_code_execution=self.synthesizer is None,
        )

    def _compile(self, program: str) -> Optional[Decorate]:
        """Compile ``program``, or ``None`` when it is not a valid one.

        A rejected program is recorded with the compiler's complaint. It is
        the one failure that says nothing about the attack and everything
        about what the synthesizer was told, so it must not be silent.
        """
        decorate = self._compiled.get(program)
        if decorate is not None:
            return decorate
        try:
            decorate = self._build(program)
        except (ValueError, TypeError, SyntaxError, KeyError) as error:
            decision(
                "skipped",
                f"the program does not compile: {error}",
                program=program,
            )
            return None
        self._compiled[program] = decorate
        return decorate

    async def _apply(self, decorate: Decorate, goal: str) -> Optional[str]:
        """Run a compiled program over ``goal``; ``None`` when it fails.

        The reason is recorded: a decorator that needs a model and cannot
        reach it fails here, and the trace is the only place that shows it.
        """
        try:
            result = decorate(goal)
            prompt = await result if inspect.isawaitable(result) else result
        except Exception as error:
            decision("skipped", f"the program raised: {error}")
            return None
        if not isinstance(prompt, str) or not prompt.strip():
            decision("skipped", "the program returned no prompt")
            return None
        return prompt.strip()

    # ── synthesis ─────────────────────────────────────────────────────────────

    async def _propose(self, round_number: int) -> list[str]:
        """Ask the synthesizer for new programs, shown what has worked."""
        assert self.synthesizer is not None
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
        if self.synthesizer is None:
            decision(
                "skipped",
                "no synthesizer role is configured, so the given program is "
                "run as it is",
                program=self.program,
            )
            return
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

    def _programs(self) -> list[str]:
        """The programs to attack one goal with, best first."""
        if self.synthesizer is None:
            return [self.program]
        return self.pool.best(self.params.programs_per_goal)

    async def search(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[Finding]:
        """Apply the chosen programs to ``goal`` in turn; return every judged attempt.

        Calls the target and the panel once per program that produced a
        prompt (plus the ``decorator`` role for model-backed primitives),
        stopping after the first success.
        """
        findings: list[Finding] = []
        programs = self._programs()

        for index, program in enumerate(programs):
            label = f"program {index + 1}/{len(programs)}"
            with phase(label, program=program, index=index) as path:
                decorate = self._compile(program)
                if decorate is None:
                    continue

                prompt = await self._apply(decorate, goal)
                if prompt is None:
                    continue

                messages = [{"role": "user", "content": prompt}]
                reply = await target(messages)
                if not reply.ok or not reply.text:
                    decision("skipped", _why_unusable(reply))
                    continue

                verdict = await judge_reply(judge, goal, prompt, reply.text)
                entry = self.pool.entries.get(program)
                findings.append(
                    Finding(
                        messages=messages,
                        response=reply,
                        verdict=verdict,
                        metadata={
                            "program": program,
                            "program_index": index,
                            "program_asr": entry.asr if entry else 0.0,
                        },
                        path=path,
                    )
                )
                if succeeded(verdict):
                    decision("stopped", "the panel called this reply a success")
                    break

        return findings


def _why_unusable(reply: object) -> str:
    """Why a reply cannot be judged, in the words the run should report.

    A defence that blocked the prompt and a provider that errored are not
    the same event as a model that answered with nothing, and a single
    program per goal leaves this reason as the whole attempt's explanation.
    """
    guardrail = getattr(reply, "guardrail", None)
    if guardrail is not None:
        return f"blocked by {guardrail.side} guardrail"
    error = getattr(reply, "error", None)
    if error is not None:
        return f"target error ({error.category}): {error.message}"
    return "the target gave no usable reply"


__all__ = ["H4rm3lAttack"]
