# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for h4rm3l program synthesis."""

from typing import ClassVar, Literal, Optional

from pydantic import Field

from ...contract import AttackParams, Completion


class H4rm3lSynthParams(AttackParams):
    """How long synthesis runs, and the models it writes programs with.

    ``synthesizer`` proposes new decorator programs from the ones that
    already scored well; it is required. ``decorator`` is only needed when a
    proposal uses an LLM-assisted primitive such as ``TranslateDecorator``.
    The judge is the campaign panel: its verdicts are the score a program is
    selected on, so synthesis with no panel configured has nothing to learn
    from and falls back to the seed programs.
    """

    REQUIRED_ROLES: ClassVar[frozenset[str]] = frozenset({"synthesizer"})

    iterations: int = Field(
        default=10,
        ge=1,
        description="Synthesis rounds; each proposes, scores and keeps programs.",
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
        description="Best programs from the pool applied to each goal afterwards.",
    )
    syntax_version: Literal[1, 2] = Field(
        default=2,
        description="Syntax the programs are written in (1 or 2).",
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
        description="Writes new decorator programs from the ones that scored well.",
    )
    decorator: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Model used by LLM-assisted primitives such as TranslateDecorator."
            " Only needed when a program contains one."
        ),
    )


__all__ = ["H4rm3lSynthParams"]
