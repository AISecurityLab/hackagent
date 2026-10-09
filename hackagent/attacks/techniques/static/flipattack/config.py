# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for FlipAttack."""

from typing import Literal

from pydantic import Field

from ..base import AttackParams

#: FWO flips word order, FCW characters within words, FCS the characters of
#: the whole sentence; FMM flips the sentence but demonstrates word flips.
FlipMode = Literal["FWO", "FCW", "FCS", "FMM"]


class FlipAttackParams(AttackParams):
    """How the goal is flipped and which guidance accompanies it."""

    flip_mode: FlipMode = Field(
        default="FCS",
        description=(
            "How the goal is flipped: FWO reverses word order, FCW reverses the "
            "characters inside each word, FCS reverses the whole sentence character"
            " by character, and FMM reverses the sentence but shows word-level "
            "flips as the example."
        ),
    )
    cot: bool = Field(
        default=False,
        description=(
            "Add a chain-of-thought instruction asking the model to decode step by "
            "step."
        ),
    )
    lang_gpt: bool = Field(
        default=False,
        description="Wrap the instructions in a structured LangGPT-style role prompt.",
    )
    few_shot: bool = Field(
        default=False,
        description="Include worked examples of flipping and un-flipping a sentence.",
    )
