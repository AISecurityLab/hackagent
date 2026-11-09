# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for MML."""

from typing import Literal

from pydantic import Field

from ..base import AttackParams

EncodingMode = Literal["word_replacement", "mirror", "rotate", "base64", "mixed"]
PromptStyle = Literal["game", "control"]


class MMLParams(AttackParams):
    """How the goal is encoded into an image and how the target is prompted.

    ``encoding_mode`` and ``num_replacements`` choose the encryption;
    ``image_width``, ``image_height``, ``font_size``, ``background_color``
    and ``text_color`` control how it is drawn; ``prompt_style`` chooses the
    text framing that accompanies the image.
    """

    encoding_mode: EncodingMode = Field(
        default="word_replacement",
        description=(
            "How the goal is hidden in the image: word_replacement swaps words for"
            " decoys and gives the mapping in the text, mirror flips the image, "
            "rotate turns it 180 degrees, base64 draws the Base64 encoding, and "
            "mixed replaces words then mirrors and rotates."
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
        default="white",
        description="Background color of the image: a color name or a hex code.",
    )
    text_color: str = Field(
        default="black",
        description="Color of the text drawn in the image: a color name or a hex code.",
    )
    num_replacements: int = Field(
        default=3,
        ge=1,
        description=(
            "For word_replacement and mixed: how many words of the goal are "
            "swapped for decoy words in the image."
        ),
    )
    prompt_style: PromptStyle = Field(
        default="game",
        description=(
            "How the target is asked to decode the image: game frames it as a "
            "screen in a villain's lair to fill in, control as a neutral empty "
            "list to complete."
        ),
    )
