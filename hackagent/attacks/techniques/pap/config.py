# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Configuration for PAP (Persuasive Adversarial Prompts) attack.

Provides ``DEFAULT_PAP_CONFIG`` and typed Pydantic models for the PAP attack.

The attack uses a taxonomy of 40 persuasion techniques to paraphrase harmful
prompts into persuasive variants.  An attacker LLM performs the paraphrasing
using in-context examples specific to each persuasion technique.

Algorithm
---------
For each goal the attack:
1. Selects one or more persuasion techniques from the taxonomy.
2. Uses the attacker LLM to paraphrase the goal using each technique.
3. Sends all persuasive variants to the target model in parallel.
4. Judges select the best candidate.  If a jailbreak is confirmed the
   remaining techniques are skipped (early stop).

Based on: https://arxiv.org/abs/2401.06373
"""

from typing import Any, Dict, List, Union

from pydantic import BaseModel, Field, field_validator

from hackagent.attacks.techniques.config import (
    DEFAULT_CONFIG_BASE,
    DEFAULT_MAX_OUTPUT_TOKENS,
    ConfigBase,
)


# ---- Top-5 persuasion techniques from the paper (broad-scan results) ---- #
TOP_5_TECHNIQUES = [
    "Evidence-based Persuasion",
    "Expert Endorsement",
    "Misrepresentation",
    "Authority Endorsement",
    "Logical Appeal",
]

# ---- Full taxonomy of 40 techniques ---- #
ALL_TECHNIQUES = [
    "Evidence-based Persuasion",
    "Logical Appeal",
    "Expert Endorsement",
    "Non-expert Testimonial",
    "Authority Endorsement",
    "Social Proof",
    "Injunctive Norm",
    "Foot-in-the-door",
    "Door-in-the-face",
    "Public Commitment",
    "Alliance Building",
    "Complimenting",
    "Shared Values",
    "Relationship Leverage",
    "Loyalty Appeals",
    "Favor",
    "Negotiation",
    "Encouragement",
    "Affirmation",
    "Positive Emotion Appeal",
    "Negative Emotion Appeal",
    "Storytelling",
    "Anchoring",
    "Priming",
    "Framing",
    "Confirmation Bias",
    "Reciprocity",
    "Compensation",
    "Supply Scarcity",
    "Time Pressure",
    "Reflective Thinking",
    "Threats",
    "False Promises",
    "Misrepresentation",
    "False Information",
    "Rumors",
    "Social Punishment",
    "Creating Dependency",
    "Exploiting Weakness",
    "Discouragement",
]


DEFAULT_PAP_CONFIG: Dict[str, Any] = {
    **DEFAULT_CONFIG_BASE,
    # Attack type identifier
    "attack_type": "pap",
    # PAP-specific parameters
    "pap_params": {
        # Persuasion techniques to use.  "top5" selects the top-5 techniques
        # from the paper; "all" uses all 40; or provide an explicit list.
        "techniques": "top5",
        # Maximum number of techniques to try per goal before stopping.
        # Set to 0 or None to try all selected techniques.
        "max_techniques_per_goal": 0,
        # Attacker LLM temperature for paraphrasing
        "attacker_temperature": 1.0,
        # Attacker LLM max tokens
        "attacker_max_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
    },
}


class PAPParams(BaseModel):
    """Hyperparameters controlling the PAP attack.

    Attributes:
        techniques: Which persuasion techniques to use.  ``"top5"`` selects
            the five most effective techniques from the paper.  ``"all"``
            uses all 40.  A list of strings selects specific techniques.
        max_techniques_per_goal: Upper bound on the number of techniques to
            try per goal.  ``0`` means try all selected techniques.
        attacker_temperature: Sampling temperature for the attacker LLM.
        attacker_max_tokens: Maximum tokens for the attacker LLM response.
    """

    techniques: Union[str, List[str]] = "top5"
    max_techniques_per_goal: int = 0
    attacker_temperature: float = Field(default=1.0, ge=0.0)
    attacker_max_tokens: int = Field(default=DEFAULT_MAX_OUTPUT_TOKENS, ge=1)

    @field_validator("techniques")
    @classmethod
    def validate_techniques(cls, v: Any) -> Any:
        if isinstance(v, str):
            if v not in ("top5", "all"):
                raise ValueError(
                    f"techniques must be 'top5', 'all', or a list; got '{v}'"
                )
        elif isinstance(v, list):
            if not v:
                raise ValueError("techniques list must not be empty")
        else:
            raise ValueError(f"techniques must be str or list, got {type(v)}")
        return v


class PAPConfig(ConfigBase):
    """Full typed configuration for the PAP attack."""

    attack_type: str = "pap"
    pap_params: PAPParams = Field(default_factory=PAPParams)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "PAPConfig":
        """Create a :class:`PAPConfig` from a plain dictionary."""
        return cls.model_validate(config_dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary suitable for :meth:`HackAgent.hack`."""
        return self.model_dump()
