# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for Best-of-N."""

from pydantic import Field

from ...contract import AttackParams


class BoNParams(AttackParams):
    """How many candidates to try, and how far each is perturbed.

    Whether a step succeeded is the evaluation panel's call, so there is no
    threshold here; a campaign with no judges runs every step.
    """

    steps: int = Field(
        default=4,
        ge=1,
        description="Sequential search steps. Each one sends ``candidates`` requests.",
    )
    candidates: int = Field(
        default=5,
        ge=1,
        description="Independently seeded candidates generated per step.",
    )
    sigma: float = Field(
        default=0.4,
        gt=0.0,
        le=1.0,
        description="Augmentation strength, from untouched (0) to heavily perturbed (1).",
    )
    word_scrambling: bool = Field(
        default=True, description="Shuffle the middle letters of words."
    )
    random_capitalization: bool = Field(
        default=True, description="Randomly change the case of letters."
    )
    ascii_perturbation: bool = Field(
        default=True,
        description="Randomly shift some characters to nearby ASCII characters.",
    )


__all__ = ["BoNParams"]
