# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for MML."""

from typing import Literal

from pydantic import Field

from ..base import AttackParams

EncodingMode = Literal["word_replacement", "mirror", "rotate", "base64", "mixed"]
PromptStyle = Literal["game", "control"]


class MMLParams(AttackParams):
    """How the goal is encoded into an image and how the target is prompted."""

    encoding_mode: EncodingMode = Field(
        default="word_replacement",
        description=(
            "How the goal is hidden in the image: word_replacement swaps key words "
            "for placeholders shown in the image, mirror and rotate distort the "
            "text, base64 encodes it, mixed combines them."
        ),
    )
    image_width: int = Field(
        default=800, ge=100, description="Width of the generated image, in pixels."
    )
    image_height: int = Field(
        default=400, ge=100, description="Height of the generated image, in pixels."
    )
    font_size: int = Field(
        default=24, ge=8, description="Font size of the text drawn in the image."
    )
    background_color: str = Field(
        default="white", description="Background color of the image."
    )
    text_color: str = Field(
        default="black", description="Color of the text drawn in the image."
    )
    num_replacements: int = Field(
        default=3,
        ge=1,
        description=(
            "For word_replacement: how many words of the goal are moved into the image."
        ),
    )
    prompt_style: PromptStyle = Field(
        default="game",
        description=(
            "How the target is asked to decode the image: game frames it as a "
            "puzzle, control asks plainly."
        ),
    )
