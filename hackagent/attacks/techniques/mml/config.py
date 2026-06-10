# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Configuration for MML (Multi-Modal Linkage) attacks.

Provides both the plain-dict ``DEFAULT_MML_CONFIG`` (used internally by
:class:`~hackagent.attacks.techniques.mml.attack.MMLAttack`) and typed
Pydantic models for structured configuration.

Encoding Modes
--------------
word_replacement
    Replaces key words in the prompt with random substitutes,
    renders to image, and provides a replacement dictionary.
mirror
    Renders the harmful prompt as text in an image, then mirrors
    the image horizontally.
rotate
    Renders the harmful prompt as text in an image, then rotates
    the image 180 degrees.
base64
    Encodes the harmful prompt in Base64, renders that encoded
    text in an image.
"""

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field

from hackagent.attacks.techniques.config import (
    DEFAULT_CONFIG_BASE,
    ConfigBase,
)

DEFAULT_MML_CONFIG: Dict[str, Any] = {
    **DEFAULT_CONFIG_BASE,
    # Attack type identifier (required by hack())
    "attack_type": "mml",
    # MML specific parameters
    "mml_params": {
        # Encoding mode: word_replacement, mirror, rotate, base64
        "encoding_mode": "word_replacement",
        # Image rendering settings
        "image_width": 800,
        "image_height": 400,
        "font_size": 24,
        "background_color": "white",
        "text_color": "black",
        # Word replacement specific settings
        "num_replacements": 3,
        # Prompt style: "game" uses villain's lair scenario, "control" is neutral
        "prompt_style": "game",
    },
}


class MMLParams(BaseModel):
    """Hyperparameters controlling the MML encoding strategy.

    Attributes:
        encoding_mode: Visual encoding mode. One of ``"word_replacement"``
            (replace key words and provide dictionary), ``"mirror"`` (flip
            image horizontally), ``"rotate"`` (rotate image 180 degrees),
            or ``"base64"`` (encode text in Base64 in image).
        image_width: Width of the generated image in pixels.
        image_height: Height of the generated image in pixels.
        font_size: Font size for rendered text.
        background_color: Background color of the generated image.
        text_color: Text color in the generated image.
        num_replacements: Number of words to replace in word_replacement mode.
        prompt_style: Prompt framing style. ``"game"`` uses the villain's
            lair scenario; ``"control"`` uses a neutral list-filling prompt.
    """

    encoding_mode: Literal[
        "word_replacement", "mirror", "rotate", "base64", "mixed"
    ] = "word_replacement"
    image_width: int = Field(default=800, ge=100)
    image_height: int = Field(default=400, ge=100)
    font_size: int = Field(default=24, ge=8)
    background_color: str = "white"
    text_color: str = "black"
    num_replacements: int = Field(default=3, ge=1)
    prompt_style: Literal["game", "control"] = "game"


class MMLConfig(ConfigBase):
    """Complete MML configuration for use with :meth:`HackAgent.hack`.

    Mirrors ``DEFAULT_MML_CONFIG`` as a typed alternative. Call
    :meth:`model_dump` (or :meth:`to_dict`) to obtain the plain dict
    expected by the attack pipeline.

    Attributes:
        attack_type: Always ``"mml"`` (required by the orchestrator).
        mml_params: Encoding hyperparameters (:class:`MMLParams`).
    """

    attack_type: str = "mml"
    output_dir: str = "./logs/mml"
    judges: List[Dict[str, Any]] = Field(default_factory=list)
    mml_params: MMLParams = Field(default_factory=MMLParams)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "MMLConfig":
        """Create a :class:`MMLConfig` from a plain dictionary."""
        filtered_config = {
            key: value for key, value in config_dict.items() if key in cls.model_fields
        }
        return cls.model_validate(filtered_config)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()
