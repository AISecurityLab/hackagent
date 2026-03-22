# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Configuration for Best-of-N (BoN) Jailbreaking attack.

Provides the plain-dict ``DEFAULT_BON_CONFIG`` (used internally by
:class:`~hackagent.attacks.techniques.bon.attack.BoNAttack`) and typed
Pydantic models (``BoNParams``, ``BoNConfig``) for structured configuration.

Text augmentations
------------------
word_scrambling
    Shuffles middle characters of words longer than 3 characters.
    Probability per word: ``sigma^(1/2)``.
random_capitalization
    Randomly toggles letter case.
    Probability per character: ``sigma^(1/2)``.
ascii_perturbation
    Shifts printable ASCII characters by ±1.
    Probability per character: ``sigma^3``.

Algorithm
---------
The attack runs ``n_steps`` sequential search steps.  Within each step,
``num_concurrent_k`` independently-seeded augmented candidates are generated
and sent to the target in parallel.  The best candidate per step is selected
by the judge.  If a successful jailbreak is found the search terminates early.
"""

from typing import Any, Dict

from pydantic import BaseModel, Field

from hackagent.attacks.techniques.config import (
    DEFAULT_CONFIG_BASE,
    ConfigBase,
)


DEFAULT_BON_CONFIG: Dict[str, Any] = {
    **DEFAULT_CONFIG_BASE,
    # Attack type identifier (required by hack())
    "attack_type": "bon",
    # BoN-specific parameters
    "bon_params": {
        # Number of sequential search steps
        "n_steps": 4,
        # Number of augmented candidates generated per step (parallelised)
        "num_concurrent_k": 5,
        # Proportion of characters to augment (controls augmentation strength)
        "sigma": 0.4,
        # Augmentation toggles
        "word_scrambling": True,
        "random_capitalization": True,
        "ascii_perturbation": True,
    },
}


class BoNParams(BaseModel):
    """Hyperparameters controlling the Best-of-N augmentation strategy.

    Attributes:
        n_steps: Number of sequential search steps.  Each step generates
            ``num_concurrent_k`` augmented candidates.
        num_concurrent_k: Number of independently-seeded augmented candidates
            generated per step.  All K candidates are evaluated in parallel.
        sigma: Controls augmentation strength.  Higher values produce more
            aggressive mutations.  Range: 0.0–1.0.
        word_scrambling: When ``True``, shuffles middle characters of words
            longer than 3 characters with probability ``sigma^(1/2)``.
        random_capitalization: When ``True``, randomly toggles letter case
            with probability ``sigma^(1/2)``.
        ascii_perturbation: When ``True``, shifts printable ASCII characters
            by ±1 with probability ``sigma^3``.
    """

    n_steps: int = Field(default=4, ge=1)
    num_concurrent_k: int = Field(default=5, ge=1)
    sigma: float = Field(default=0.4, gt=0.0, le=1.0)
    word_scrambling: bool = True
    random_capitalization: bool = True
    ascii_perturbation: bool = True


class BoNConfig(ConfigBase):
    """Complete BoN configuration for use with :meth:`HackAgent.hack`.

    Mirrors ``DEFAULT_BON_CONFIG`` as a typed alternative.  Call
    :meth:`model_dump` (or :meth:`to_dict`) to obtain the plain dict expected
    by the attack pipeline.

    Attributes:
        attack_type: Always ``"bon"`` (required by the orchestrator).
        bon_params: Augmentation hyperparameters (:class:`BoNParams`).
        batch_size: Concurrent target-model requests within a search step.
        goal_batch_size: Goals processed per macro-batch.
    """

    attack_type: str = "bon"
    bon_params: BoNParams = Field(default_factory=BoNParams)

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "BoNConfig":
        """Create a :class:`BoNConfig` from a plain dictionary.

        Pydantic automatically coerces nested dicts into :class:`BoNParams`
        and applies defaults for any missing keys.

        Args:
            config_dict: Configuration dictionary (extra keys are ignored).

        Returns:
            Populated :class:`BoNConfig` instance.
        """
        return cls.model_validate(config_dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary suitable for :meth:`HackAgent.hack`."""
        return self.model_dump()
