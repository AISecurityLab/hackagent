# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Configuration for PAP (Persuasive Adversarial Prompts) attack.

Provides ``DEFAULT_PAP_CONFIG`` and typed dataclasses for the PAP attack.

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

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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
        "attacker_max_tokens": 1024,
    },
    # Attacker LLM endpoint (performs persuasive paraphrasing)
    "attacker": {
        "identifier": "gpt-4",
        "endpoint": "https://api.openai.com/v1",
        "agent_type": "OPENAI_SDK",
        "api_key": None,
    },
    # Judge configuration
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
    "batch_size": 1,       # Parallelism for goal processing
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
class PAPParams:
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

    techniques: Any = "top5"
    max_techniques_per_goal: int = 0
    attacker_temperature: float = 1.0
    attacker_max_tokens: int = 1024

    def __post_init__(self):
        if isinstance(self.techniques, str):
            if self.techniques not in ("top5", "all"):
                raise ValueError(
                    f"techniques must be 'top5', 'all', or a list; got '{self.techniques}'"
                )
        elif isinstance(self.techniques, list):
            if not self.techniques:
                raise ValueError("techniques list must not be empty")
        else:
            raise TypeError(f"techniques must be str or list, got {type(self.techniques)}")
        if self.attacker_temperature < 0:
            raise ValueError(f"attacker_temperature must be >= 0, got {self.attacker_temperature}")
        if self.attacker_max_tokens < 1:
            raise ValueError(f"attacker_max_tokens must be >= 1, got {self.attacker_max_tokens}")


@dataclass
class PAPConfig:
    """Full typed configuration for the PAP attack."""

    attack_type: str = "pap"
    pap_params: PAPParams = field(default_factory=PAPParams)
    attacker: Dict[str, Any] = field(
        default_factory=lambda: {
            "identifier": "gpt-4",
            "endpoint": "https://api.openai.com/v1",
            "agent_type": "OPENAI_SDK",
            "api_key": None,
        }
    )
    judges: List[Dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "identifier": "gpt-4-0613",
                "type": "harmbench",
                "agent_type": "OPENAI_SDK",
                "api_key": None,
                "endpoint": None,
            }
        ]
    )
    batch_size: int = 1
    batch_size_judge: int = 1
    goal_batch_size: int = 1

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)
