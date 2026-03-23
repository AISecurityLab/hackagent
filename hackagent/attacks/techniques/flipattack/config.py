# Copyright 2025 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Configuration for FlipAttack attacks.

Provides both the plain-dict ``DEFAULT_FLIPATTACK_CONFIG`` (used internally
by :class:`~hackagent.attacks.techniques.flipattack.attack.FlipAttack`) and
typed Pydantic models (``FlipAttackParams``, ``FlipAttackConfig``) for users who
prefer structured configuration.

Flip modes
----------
FWO
    Flip Word Order — reverses the word sequence of the sentence.
FCW
    Flip Chars in Word — reverses characters within each individual word.
FCS  *(default)*
    Flip Chars in Sentence — reverses all characters in the whole sentence.
FMM
    Fool Model Mode — FCS obfuscation with FWO decoding instruction.

Enhancements
------------
cot
    Appends a chain-of-thought instruction to encourage step-by-step answers.
lang_gpt
    Wraps the system prompt in a LangGPT Role/Profile/Rules template.
few_shot
    Injects two task-oriented decoding demonstrations into the prompt.
"""

from typing import Any, Dict, Literal

from pydantic import BaseModel, Field

from hackagent.attacks.techniques.config import (
    DEFAULT_CONFIG_BASE,
    ConfigBase,
)

DEFAULT_FLIPATTACK_CONFIG: Dict[str, Any] = {
    **DEFAULT_CONFIG_BASE,
    # Attack type identifier (required by hack())
    "attack_type": "flipattack",
    # FlipAttack specific parameters
    "flipattack_params": {
        # Flip mode: FWO, FCW, FCS, FMM
        "flip_mode": "FCS",
        # Enhancement options
        "cot": False,  # Chain-of-thought
        "lang_gpt": False,  # LangGPT structured prompting
        "few_shot": False,  # Few-shot examples
    },
}


class FlipAttackParams(BaseModel):
    """Hyperparameters controlling the FlipAttack obfuscation strategy.

    Attributes:
        flip_mode: Obfuscation mode.  One of ``"FWO"`` (flip word order),
            ``"FCW"`` (flip chars in word), ``"FCS"`` (flip chars in sentence,
            default), or ``"FMM"`` (fool model mode — FCS transform with
            FWO decoding instruction).
        cot: When ``True``, adds a chain-of-thought suffix to the decoding
            instruction so the model answers step by step.
        lang_gpt: When ``True``, wraps the system prompt in a structured
            LangGPT Role/Profile/Rules template instead of the plain prompt.
        few_shot: When ``True``, injects two task-oriented decoding
            demonstrations into the prompt.
    """

    flip_mode: Literal["FWO", "FCW", "FCS", "FMM"] = "FCS"
    cot: bool = False
    lang_gpt: bool = False
    few_shot: bool = False


class FlipAttackConfig(ConfigBase):
    """Complete FlipAttack configuration for use with :meth:`HackAgent.hack`.

    Mirrors ``DEFAULT_FLIPATTACK_CONFIG`` as a typed alternative.  Call
    :meth:`model_dump` (or :meth:`to_dict`) to obtain the plain dict expected
    by the attack pipeline.

    Attributes:
        attack_type: Always ``"flipattack"`` (required by the orchestrator).
        flipattack_params: Obfuscation hyperparameters (:class:`FlipAttackParams`).
    """

    attack_type: str = "flipattack"
    output_dir: str = "./logs/flipattack"
    judges: list[Dict[str, Any]] = Field(default_factory=list)
    flipattack_params: FlipAttackParams = Field(default_factory=FlipAttackParams)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "FlipAttackConfig":
        """Create a :class:`FlipAttackConfig` from a plain dictionary.

        Args:
            config_dict: Configuration dictionary (extra keys are ignored).

        Returns:
            Populated :class:`FlipAttackConfig` instance.
        """
        filtered_config = {
            key: value for key, value in config_dict.items() if key in cls.model_fields
        }
        return cls.model_validate(filtered_config)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()
