# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for h4rm3l."""

from typing import Literal, Optional

from pydantic import Field

from ...contract import AttackParams, Completion


class H4rm3lParams(AttackParams):
    """The program to run, and how long to search for a better one.

    With no ``synthesizer`` role the attack runs ``program`` and nothing
    else: one decorated request per goal, cheap and repeatable. Configure a
    ``synthesizer`` and it first searches the decorator language for
    programs that work against this target, seeded with ``program`` and the
    presets, and then attacks each goal with the best it found; every field
    from ``iterations`` down governs that search and is ignored without it.

    ``decorator`` is needed only when a program contains an LLM-assisted
    primitive such as ``TranslateDecorator``.
    """

    program: str = Field(
        default="IdentityDecorator()",
        min_length=1,
        description=(
            "The obfuscation program applied to the goal: a preset name such as "
            "refusal_suppression, base64_refusal_suppression or translate_zulu, or "
            "a program written in the h4rm3l decorator language. It is what the "
            "attack sends without a synthesizer, and a seed for the search with one."
        ),
    )
    syntax_version: Literal[1, 2] = Field(
        default=2,
        description=(
            "Version of the h4rm3l program syntax the program is written in (1 or 2)."
        ),
    )
    iterations: int = Field(
        default=10,
        ge=1,
        description=(
            "Synthesis rounds; each proposes, scores and keeps programs. "
            "Only used when a synthesizer role is configured."
        ),
    )
    proposals: int = Field(
        default=8,
        ge=1,
        description="Programs the synthesizer is asked for in each round.",
    )
    examples: int = Field(
        default=10,
        ge=1,
        description="Programs from the pool shown to the synthesizer as examples.",
    )
    scoring_goals: int = Field(
        default=3,
        ge=1,
        description=(
            "Goals each proposal is scored on, drawn at random from the run's "
            "goals for every proposal. The product of iterations, proposals "
            "and this is how many target calls synthesis costs."
        ),
    )
    programs_per_goal: int = Field(
        default=3,
        ge=1,
        description=(
            "Best programs from the pool applied to each goal after synthesis. "
            "Without a synthesizer each goal gets one request, from `program`."
        ),
    )
    concentration: float = Field(
        default=1.0,
        gt=0.0,
        description=(
            "Rate at which selection shifts from exploration to exploitation: "
            "the Beta concentration grows with this times the round number."
        ),
    )
    seed: Optional[int] = Field(
        default=None, description="Seed for program sampling, for a repeatable search."
    )
    synthesizer: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Optional. Writes new decorator programs from the ones that scored "
            "well. Configure it to search the language; leave it out to run "
            "`program` as it is."
        ),
    )
    decorator: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Optional. Model used by decorators that need an LLM, such as "
            "TranslateDecorator. Only needed when a program contains one."
        ),
    )


__all__ = ["H4rm3lParams"]
