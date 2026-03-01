# Copyright 2025 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Configuration for FlipAttack attacks.

Provides both the plain-dict ``DEFAULT_FLIPATTACK_CONFIG`` (used internally
by :class:`~hackagent.attacks.techniques.flipattack.attack.FlipAttack`) and
typed dataclasses (``FlipAttackParams``, ``FlipAttackConfig``) for users who
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

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

DEFAULT_FLIPATTACK_CONFIG: Dict[str, Any] = {
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
    "batch_size_judge": 1,
    "max_new_tokens_eval": 256,
    "filter_len": 10,
    "judge_request_timeout": 120,
    "judge_temperature": 0.0,
    "max_judge_retries": 1,
    # Goals/prompts to attack (required by attack strategies)
    "goals": [],  # Will be populated by user or dataset
    # Dataset configuration (optional - if using preset datasets)
    "dataset": None,  # e.g., "advbench", "advbench_subset"
    # Output parameters
    "output_dir": "./logs/runs",
    # Pipeline control
    "start_step": 1,
}


@dataclass
class FlipAttackParams:
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

    flip_mode: str = "FCS"
    cot: bool = False
    lang_gpt: bool = False
    few_shot: bool = False

    def __post_init__(self):
        valid_modes = ["FWO", "FCW", "FCS", "FMM"]
        if self.flip_mode not in valid_modes:
            raise ValueError(
                f"flip_mode must be one of {valid_modes}, got {self.flip_mode}"
            )


@dataclass
class FlipAttackConfig:
    """Complete FlipAttack configuration for use with :meth:`HackAgent.hack`.

    This dataclass mirrors ``DEFAULT_FLIPATTACK_CONFIG`` and is provided as
    a typed alternative.  Pass ``asdict(config)`` (or call
    :meth:`FlipAttackConfig.from_dict`) when you need to convert to/from the
    plain dict expected by the attack pipeline.

    Attributes:
        attack_type: Always ``"flipattack"`` (required by the orchestrator).
        flipattack_params: Obfuscation hyperparameters (:class:`FlipAttackParams`).
        goals: List of harmful goal strings to test against the target model.
        judges: List of judge configuration dicts used for success evaluation.
            Each dict is expected to have at minimum ``"identifier"`` and
            ``"type"`` keys (e.g., ``"harmbench"``, ``"jailbreakbench"``).
        batch_size_judge: Number of responses sent per judge request.
        max_new_tokens_eval: Max tokens the judge generates per evaluation.
        filter_len: Minimum number of tokens a response must contain to be
            evaluated (shorter responses are skipped as trivial refusals).
        judge_request_timeout: Seconds to wait for each judge API call.
        judge_temperature: Sampling temperature for judge queries (0.0 for
            deterministic outputs).
        max_judge_retries: Number of retries when a judge response cannot be
            parsed.
        dataset: Optional named dataset (e.g. ``"advbench"``).  When set the
            pipeline loads goals from the dataset instead of ``goals``.
        output_dir: Directory for result artefacts.
        start_step: Pipeline step to resume from (1 = beginning).
    """

    attack_type: str = "flipattack"
    flipattack_params: FlipAttackParams = field(default_factory=FlipAttackParams)
    goals: List[str] = field(default_factory=list)
    judges: List[Dict[str, Any]] = field(default_factory=list)
    batch_size_judge: int = 1
    max_new_tokens_eval: int = 256
    filter_len: int = 10
    judge_request_timeout: int = 120
    judge_temperature: float = 0.0
    max_judge_retries: int = 1
    dataset: Optional[str] = None
    output_dir: str = "./logs/flipattack"
    start_step: int = 1

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "FlipAttackConfig":
        """Create a :class:`FlipAttackConfig` from a plain dictionary.

        Args:
            config_dict: Dictionary with the same keys as the dataclass
                fields.  ``flipattack_params`` may be a nested dict and
                will be automatically converted to :class:`FlipAttackParams`.

        Returns:
            Populated :class:`FlipAttackConfig` instance.
        """
        # Parse flipattack_params from dict to dataclass
        # Parse flipattack_params from dict to dataclass
        fa_params_dict = config_dict.get("flipattack_params", {})
        flipattack_params = (
            FlipAttackParams(**fa_params_dict) if fa_params_dict else FlipAttackParams()
        )

        return cls(
            attack_type=config_dict.get("attack_type", "flipattack"),
            flipattack_params=flipattack_params,
            goals=config_dict.get("goals", []),
            judges=config_dict.get("judges", []),
            batch_size_judge=config_dict.get("batch_size_judge", 1),
            max_new_tokens_eval=config_dict.get("max_new_tokens_eval", 256),
            filter_len=config_dict.get("filter_len", 10),
            judge_request_timeout=config_dict.get("judge_request_timeout", 120),
            judge_temperature=config_dict.get("judge_temperature", 0.0),
            max_judge_retries=config_dict.get("max_judge_retries", 1),
            dataset=config_dict.get("dataset"),
            output_dir=config_dict.get("output_dir", "./logs/flipattack"),
            start_step=config_dict.get("start_step", 1),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "attack_type": self.attack_type,
            "flipattack_params": asdict(
                self.flipattack_params
            ),  # Convert dataclass to dict
            "goals": self.goals,
            "judges": self.judges,
            "batch_size_judge": self.batch_size_judge,
            "max_new_tokens_eval": self.max_new_tokens_eval,
            "filter_len": self.filter_len,
            "judge_request_timeout": self.judge_request_timeout,
            "judge_temperature": self.judge_temperature,
            "max_judge_retries": self.max_judge_retries,
            "dataset": self.dataset,
            "output_dir": self.output_dir,
            "start_step": self.start_step,
        }
