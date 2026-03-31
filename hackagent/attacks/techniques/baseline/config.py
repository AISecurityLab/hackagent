# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Configuration for baseline attacks.

Baseline attacks use predefined prompt patterns to attempt jailbreaks,
combining templates with goals to generate attack prompts.
"""

from typing import Any, Dict, List, Optional

from pydantic import ConfigDict, Field

from hackagent.attacks.techniques.config import (
    DEFAULT_CONFIG_BASE,
    DEFAULT_STANDARD_TARGET_CONFIG,
    ConfigBase,
)


DEFAULT_TEMPLATE_CONFIG: Dict[str, Any] = {
    **DEFAULT_CONFIG_BASE,
    **DEFAULT_STANDARD_TARGET_CONFIG,
    # --- Target Model ---
    "agent_router": None,  # Will be set at runtime
    # --- Template Selection ---
    "template_categories": [
        "instruction_override",
        "delimiter_bypass",
        "role_play",
        "prefix_injection",
        "context_manipulation",
    ],
    "templates_per_category": 3,  # Number of templates to use per category
    # --- Generation Settings ---
    "n_samples_per_template": 1,  # Completions per template-goal combo
    # --- Evaluation Settings ---
    "objective": "jailbreak",  # Default objective: jailbreak, harmful_behavior, policy_violation
    "evaluator_type": "pattern",  # pattern, keyword, or llm_judge
    "judge_config": None,  # For LLM judge evaluation
    # --- Filtering ---
    "min_response_length": 10,
    "deduplicate_responses": True,
}


class TemplateAttackConfig(ConfigBase):
    """Configuration for baseline attack pipeline."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    # Target
    agent_router: Any = None

    # Template settings
    template_categories: List[str] = Field(
        default_factory=lambda: [
            "instruction_override",
            "delimiter_bypass",
            "role_play",
            "prefix_injection",
            "context_manipulation",
        ]
    )
    templates_per_category: int = 3

    # Generation
    n_samples_per_template: int = 1

    # Evaluation
    objective: str = "jailbreak"
    evaluator_type: str = "pattern"
    judge_config: Optional[Dict[str, Any]] = None

    # Filtering
    min_response_length: int = 10
    deduplicate_responses: bool = True

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "TemplateAttackConfig":
        """Create config from dictionary."""
        return cls.model_validate(config_dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()
