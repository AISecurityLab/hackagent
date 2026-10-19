# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for Crescendo."""

from typing import ClassVar, Optional

from pydantic import Field

from ...contract import AttackParams, Completion


class CrescendoParams(AttackParams):
    """How far the conversation escalates, and how often it may rephrase.

    ``attacker`` is a role: the model that proposes each next question, so
    Crescendo cannot run without it.
    """

    REQUIRED_ROLES: ClassVar[frozenset[str]] = frozenset({"attacker"})

    max_turns: int = Field(
        default=10,
        ge=1,
        description=(
            "Turns the conversation may grow to. A backtracked turn is retried, not"
            " counted, so the conversation never escalates on a refusal."
        ),
    )
    max_backtracks: int = Field(
        default=10,
        ge=0,
        description=(
            "Rephrasings allowed across the whole goal. Once spent, a refused turn "
            "is accepted as-is and the conversation moves on."
        ),
    )
    keep_last_n: int = Field(
        default=6,
        ge=1,
        description=(
            "Attacker turns kept before its planning log is trimmed. The target's "
            "own conversation is never trimmed: that history is the attack."
        ),
    )
    early_stop: bool = Field(
        default=True,
        description="Stop as soon as a turn the target did not refuse passes the panel.",
    )
    feedback_max_chars: int = Field(
        default=2500,
        ge=1,
        description="Longest reply and explanation fed back to the attacker.",
    )
    attacker: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Plans the conversation and writes each next question, a little closer "
            "to the goal than the last."
        ),
    )


__all__ = ["CrescendoParams"]
