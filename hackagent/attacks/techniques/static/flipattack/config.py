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
    """How the goal is flipped and which guidance accompanies it.

    ``flip_mode`` chooses the disguise; ``cot``, ``lang_gpt`` and
    ``few_shot`` are the paper's three optional guidance modules and can be
    combined freely. The defaults give the plainest variant: ``FCS`` with
    the base system prompt and no extra guidance.
    """

    flip_mode: FlipMode = Field(
        default="FCS",
        description=(
            "How the goal is flipped: FWO reverses word order, FCW reverses the "
            "characters inside each word, FCS reverses the whole sentence character"
            " by character, and FMM (fool model mode) flips like FCS but describes"
            " and demonstrates word-order flips."
        ),
    )
    cot: bool = Field(
        default=False,
        description=(
            "Add a chain-of-thought instruction asking the model to give its "
            "solution step by step."
        ),
    )
    lang_gpt: bool = Field(
        default=False,
        description=(
            "Wrap the persona in a structured LangGPT-style role prompt and move "
            "the decoding steps into the user message."
        ),
    )
    few_shot: bool = Field(
        default=False,
        description=(
            "Show the two halves of the goal flipped and unflipped as worked "
            "examples. The goal needs at least two words."
        ),
    )
