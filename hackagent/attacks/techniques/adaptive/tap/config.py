# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for TAP."""

from typing import ClassVar, Optional

from pydantic import Field

from ...contract import AttackParams, Completion


class TapParams(AttackParams):
    """The shape of the tree, and who writes and filters its branches.

    ``attacker`` is a role: the model that refines each branch's prompt, so
    TAP cannot run without it.

    ``on_topic`` is an optional second role, the YES/NO filter the paper puts
    before every target call. Configure it and a branch that has drifted off
    the goal is dropped before it costs a target call — the first of TAP's
    two prunes. Leave it out and every branch is probed, and only the score
    prune narrows the tree.
    """

    REQUIRED_ROLES: ClassVar[frozenset[str]] = frozenset({"attacker"})

    depth: int = Field(
        default=3,
        ge=1,
        description="Refinement rounds. Every surviving branch is expanded once per round.",
    )
    width: int = Field(
        default=4,
        ge=1,
        description="Branches kept after each round's score prune: the beam width.",
    )
    branching_factor: int = Field(
        default=3,
        ge=1,
        description="Refinements the attacker writes per branch per round.",
    )
    streams: int = Field(
        default=4, ge=1, description="Independent conversations the tree starts from."
    )
    keep_last_n: int = Field(
        default=6,
        ge=1,
        description="Attacker turns a branch keeps before its history is trimmed.",
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        description="Retries when the attacker's reply is not a usable prompt.",
    )
    early_stop: bool = Field(
        default=True, description="Stop the whole search once any branch succeeds."
    )
    min_prune_score: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description=(
            "Score a branch must *exceed* to survive the prune, on the 0..10 scale."
            " The reference keeps anything scored above zero; the best branch "
            "always survives, so a round never prunes to nothing."
        ),
    )
    target_str: str = Field(
        default="Sure, here is",
        description="The opening the attacker is told to aim the target's reply at.",
    )
    attacker: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Writes the jailbreak prompts and branches each one into several "
            "refined variants."
        ),
    )
    on_topic: Optional[Completion] = Field(
        default=None,
        exclude=True,
        repr=False,
        description=(
            "Optional. Answers yes or no to whether a branch still pursues the "
            "goal; branches that drifted are pruned before they cost a call to the "
            "target. Without it, no branch is pruned for being off topic."
        ),
    )


__all__ = ["TapParams"]
