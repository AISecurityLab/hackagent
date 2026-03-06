# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Configuration for Best-of-N (BoN) Jailbreaking attack.

Provides the plain-dict ``DEFAULT_BON_CONFIG`` (used internally by
:class:`~hackagent.attacks.techniques.bon.attack.BoNAttack`) and typed
dataclasses (``BoNParams``, ``BoNConfig``) for structured configuration.

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

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


DEFAULT_BON_CONFIG: Dict[str, Any] = {
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
    # Judge configuration (top-level, HackAgent style)
    "judges": [
        {
            "identifier": "gpt-4-0613",
            "type": "harmbench",
            "agent_type": "OPENAI_SDK",
            "api_key": None,
            "endpoint": None,
        }
    ],
    # Batching
    "batch_size": 1,  # Parallelism for candidate→target requests within a step
    "batch_size_judge": 1,
    "goal_batch_size": 1,
    # Judge parameters (standard)
    "max_new_tokens_eval": 256,
    "filter_len": 10,
    "judge_request_timeout": 120,
    "judge_temperature": 0.0,
    "max_judge_retries": 1,
    # Target model settings
    "max_new_tokens": 4096,
    "temperature": 0.6,
    "request_timeout": 120,
    # Goals / dataset
    "goals": [],
    "dataset": None,
    # Output & pipeline
    "output_dir": "./logs/runs",
    "run_id": None,
    "start_step": 1,
}


@dataclass
class BoNParams:
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

    n_steps: int = 4
    num_concurrent_k: int = 5
    sigma: float = 0.4
    word_scrambling: bool = True
    random_capitalization: bool = True
    ascii_perturbation: bool = True

    def __post_init__(self):
        if self.n_steps < 1:
            raise ValueError(f"n_steps must be >= 1, got {self.n_steps}")
        if self.num_concurrent_k < 1:
            raise ValueError(
                f"num_concurrent_k must be >= 1, got {self.num_concurrent_k}"
            )
        if not (0.0 < self.sigma <= 1.0):
            raise ValueError(f"sigma must be in (0, 1], got {self.sigma}")


@dataclass
class BoNConfig:
    """Complete BoN configuration for use with :meth:`HackAgent.hack`.

    This dataclass mirrors ``DEFAULT_BON_CONFIG`` and is provided as a typed
    alternative.  Pass ``asdict(config)`` when converting to the plain dict
    expected by the attack pipeline.

    Attributes:
        attack_type: Always ``"BoN"`` (required by the orchestrator).
        bon_params: Augmentation hyperparameters (:class:`BoNParams`).
        goals: List of harmful goal strings to test against the target model.
        judges: List of judge configuration dicts for success evaluation.
        batch_size: Concurrent target-model requests within a search step.
        batch_size_judge: Concurrent judge evaluation requests.
        goal_batch_size: Goals processed per macro-batch.
        max_new_tokens_eval: Max tokens the judge generates per evaluation.
        filter_len: Minimum response length to be considered non-trivial.
        judge_request_timeout: Seconds to wait for each judge API call.
        judge_temperature: Sampling temperature for judge queries.
        max_judge_retries: Retries when a judge response cannot be parsed.
        max_new_tokens: Max tokens for the target model response.
        temperature: Sampling temperature for the target model.
        request_timeout: Seconds to wait for each target model call.
        dataset: Optional named dataset (e.g. ``"advbench"``).
        output_dir: Directory for result artefacts.
        start_step: Pipeline step to resume from (1 = beginning).
    """

    attack_type: str = "bon"
    bon_params: BoNParams = field(default_factory=BoNParams)
    goals: List[str] = field(default_factory=list)
    judges: List[Dict[str, Any]] = field(default_factory=list)
    batch_size: int = 1
    batch_size_judge: int = 1
    goal_batch_size: int = 1
    max_new_tokens_eval: int = 256
    filter_len: int = 10
    judge_request_timeout: int = 120
    judge_temperature: float = 0.0
    max_judge_retries: int = 1
    max_new_tokens: int = 4096
    temperature: float = 0.6
    request_timeout: int = 120
    dataset: Optional[str] = None
    output_dir: str = "./logs/runs"
    start_step: int = 1

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "BoNConfig":
        """Create a :class:`BoNConfig` from a plain dictionary.

        Args:
            config_dict: Dictionary with the same keys as the dataclass
                fields.  ``bon_params`` may be a nested dict and will be
                automatically converted to :class:`BoNParams`.

        Returns:
            Populated :class:`BoNConfig` instance.
        """
        bp_dict = config_dict.get("bon_params", {})
        bon_params = BoNParams(**bp_dict) if bp_dict else BoNParams()

        return cls(
            attack_type=config_dict.get("attack_type", "bon"),
            bon_params=bon_params,
            goals=config_dict.get("goals", []),
            judges=config_dict.get("judges", []),
            batch_size=config_dict.get("batch_size", 1),
            batch_size_judge=config_dict.get("batch_size_judge", 1),
            goal_batch_size=config_dict.get("goal_batch_size", 1),
            max_new_tokens_eval=config_dict.get("max_new_tokens_eval", 256),
            filter_len=config_dict.get("filter_len", 10),
            judge_request_timeout=config_dict.get("judge_request_timeout", 120),
            judge_temperature=config_dict.get("judge_temperature", 0.0),
            max_judge_retries=config_dict.get("max_judge_retries", 1),
            max_new_tokens=config_dict.get("max_new_tokens", 4096),
            temperature=config_dict.get("temperature", 0.6),
            request_timeout=config_dict.get("request_timeout", 120),
            dataset=config_dict.get("dataset"),
            output_dir=config_dict.get("output_dir", "./logs/runs"),
            start_step=config_dict.get("start_step", 1),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary suitable for :meth:`HackAgent.hack`."""
        return {
            "attack_type": self.attack_type,
            "bon_params": asdict(self.bon_params),
            "goals": self.goals,
            "judges": self.judges,
            "batch_size": self.batch_size,
            "batch_size_judge": self.batch_size_judge,
            "goal_batch_size": self.goal_batch_size,
            "max_new_tokens_eval": self.max_new_tokens_eval,
            "filter_len": self.filter_len,
            "judge_request_timeout": self.judge_request_timeout,
            "judge_temperature": self.judge_temperature,
            "max_judge_retries": self.max_judge_retries,
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "request_timeout": self.request_timeout,
            "dataset": self.dataset,
            "output_dir": self.output_dir,
            "start_step": self.start_step,
        }
