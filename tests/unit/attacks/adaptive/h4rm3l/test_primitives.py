# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The catalogue the synthesizer writes against.

A primitive is worth offering only if a program naming it can be compiled,
and usable only if the synthesizer is told what it takes. A proposal the
compiler rejects says nothing about the attack and everything about what
the synthesizer was told, so it is recorded rather than dropped.
"""

from __future__ import annotations

import asyncio
import inspect

from hackagent.attacks.techniques.adaptive.h4rm3l import (
    H4rm3lAttack,
    primitive_signatures,
)
from hackagent.attacks.techniques.adaptive.h4rm3l.primitives import (
    needs_decorator_model,
)
from hackagent.attacks.techniques.adaptive.h4rm3l.decorators import (
    compile_program,
    decorator_namespace,
)
from hackagent.attacks.techniques.trace import recording

from .test_synthesis import GOAL, Panel, Synthesizer, Target, params


def _names(signatures: list[str]) -> set[str]:
    return {signature.split("(", 1)[0] for signature in signatures}


def _prepare_with(program: str):
    """Run one synthesis round over ``program`` and return the trace nodes."""
    attack = H4rm3lAttack(params(synthesizer=Synthesizer(program)))

    async def go():
        with recording(scope="run") as trace:
            await attack.prepare([GOAL], Target(), Panel(10.0))
            return list(trace.nodes)

    return attack, asyncio.run(go())


def test_only_names_the_compiler_accepts_are_offered():
    # The package's ``__all__`` also exports the base classes, the name set
    # and the compiler itself; none of those can appear in a program.
    assert _names(primitive_signatures(with_decorator_model=True)) == set(
        decorator_namespace()
    )


def test_model_backed_primitives_are_withheld_without_a_decorator_role():
    withheld = {
        name
        for name, cls in decorator_namespace().items()
        if needs_decorator_model(cls)
    }
    assert withheld, "some primitives rewrite the prompt with a model"
    offered = _names(primitive_signatures(with_decorator_model=False))
    assert offered == set(decorator_namespace()) - withheld


def test_every_offered_primitive_is_shown_its_own_parameters():
    namespace = decorator_namespace()
    for signature in primitive_signatures(with_decorator_model=False):
        name, _, rest = signature.partition("(")
        shown = {
            part.split(":")[0].split("=")[0].strip()
            for part in rest.rstrip(")").split(",")
            if part.strip()
        }
        expected = {
            parameter
            for parameter in inspect.signature(namespace[name].__init__).parameters
            if parameter not in ("self", "completion")
        }
        assert shown == expected, name


def test_a_signature_with_no_parameters_is_directly_usable():
    nullary = [
        s for s in primitive_signatures(with_decorator_model=False) if s.endswith("()")
    ]
    assert len(nullary) > 3
    head, *rest = nullary[:3]
    program = head + "".join(f".then({call})" for call in rest)
    assert compile_program(program, 2) is not None


def test_a_rejected_proposal_says_why_in_the_trace():
    # The exact mistake the live synthesizer made: a real primitive, an
    # invented keyword argument.
    attack, nodes = _prepare_with("CharCorrupt(corruption_rate=0.1)")
    skipped = [n for n in nodes if n.node == "decision" and n.label == "skipped"]
    assert skipped, "an uncompilable proposal must not be dropped silently"
    assert "does not compile" in skipped[0].data["reason"]
    assert "corruption_rate" in skipped[0].data["reason"]
    assert "CharCorrupt(corruption_rate=0.1)" not in attack.pool.entries


def test_the_round_summary_separates_invalid_from_unconvincing():
    _attack, nodes = _prepare_with("NopeDecorator()")
    kept = [n for n in nodes if n.node == "decision" and n.label == "kept"]
    assert kept and kept[0].data["invalid"] == 1


def test_a_compiling_proposal_is_not_counted_as_invalid():
    attack, nodes = _prepare_with("AIMDecorator().then(Base64Decorator())")
    kept = [n for n in nodes if n.node == "decision" and n.label == "kept"]
    assert kept and kept[0].data["invalid"] == 0
    assert "AIMDecorator().then(Base64Decorator())" in attack.pool.entries


def test_scoring_goals_are_drawn_afresh_for_each_proposal():
    # A fixed slice would score every program on the same few goals.
    goals = [f"goal {i}" for i in range(20)]
    attack = H4rm3lAttack(params(scoring_goals=3, seed=1))
    draws = {tuple(attack._scoring_goals(goals)) for _ in range(12)}
    assert len(draws) > 1, "every proposal was scored on the same goals"
    assert all(len(d) == 3 and set(d) <= set(goals) for d in draws)


def test_scoring_never_asks_for_more_goals_than_the_run_has():
    attack = H4rm3lAttack(params(scoring_goals=50, seed=1))
    assert attack._scoring_goals(["only one"]) == ["only one"]


def test_an_unreachable_synthesizer_says_so():
    class Broken:
        calls = 0

        async def __call__(self, messages):
            raise RuntimeError("connection refused")

    attack = H4rm3lAttack(params(synthesizer=Broken()))

    async def go():
        with recording(scope="run") as trace:
            await attack.prepare([GOAL], Target(), Panel(10.0))
            return list(trace.nodes)

    nodes = asyncio.run(go())
    skipped = [n for n in nodes if n.node == "decision" and n.label == "skipped"]
    assert skipped, "an unreachable synthesizer must not look like a bad proposal"
    assert "could not be reached" in skipped[0].data["reason"]
    assert "connection refused" in skipped[0].data["reason"]


def test_a_reply_with_no_program_is_distinguished_from_an_outage():
    _attack, nodes = _prepare_with("I'm sorry, I can't help with that.")
    skipped = [n for n in nodes if n.node == "decision" and n.label == "skipped"]
    assert skipped and "held no program" in skipped[0].data["reason"]
