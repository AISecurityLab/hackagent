# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Configuration for static template attacks.

Static template attacks use predefined prompt patterns to attempt jailbreaks,
combining templates with goals to generate attack prompts.
"""

from typing import Any, Dict, List, Optional

from pydantic import ConfigDict, Field, model_validator

from hackagent.attacks.generator import AttackTemplates
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
    ],
    "templates_per_category": 3,  # Number of templates to use per category
    "template_parameters": {},  # Explicit substitutions, including translations
    "batch_size": 0,  # Use all selected templates unless a per-goal batch is requested
    # --- Generation Settings ---
    "n_samples_per_template": 1,  # Completions per template-goal combo
    # --- Evaluation Settings ---
    "objective": "jailbreak",  # Default objective: jailbreak, harmful_behavior, policy_violation
    "evaluator_type": "llm_judge",  # Deprecated: static/baseline always use LLM judge
    "judge_config": None,  # For LLM judge evaluation
    # --- Filtering ---
    "min_response_length": 10,
    "deduplicate_responses": True,
}


def validate_template_config(config: Dict[str, Any]) -> None:
    """Validate selected categories and substitutions without calling a model."""
    categories = config.get(
        "template_categories", DEFAULT_TEMPLATE_CONFIG["template_categories"]
    )
    if not isinstance(categories, list) or not categories:
        raise ValueError(
            "template_categories must be a non-empty list of category names"
        )

    parameters = config.get("template_parameters", {})
    if not isinstance(parameters, dict) or any(
        not isinstance(key, str) for key in parameters
    ):
        raise ValueError("template_parameters must be a dictionary with string keys")
    if {"goal", "template"} & parameters.keys():
        raise ValueError(
            "template_parameters cannot override reserved 'goal' or 'template'"
        )

    available = AttackTemplates.get_all_categories()
    for category in categories:
        if not isinstance(category, str) or category not in available:
            raise ValueError(
                f"Unknown template category {category!r}. Available: {', '.join(available)}"
            )
        for template in AttackTemplates.get_by_category(category):
            try:
                AttackTemplates.apply_template(template, "", **parameters)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid static_template category '{category}': {exc} "
                    "Check template_parameters."
                ) from exc


class TemplateAttackConfig(ConfigBase):
    """Configuration for static template attack pipeline."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    # Target
    agent_router: Any = None

    # Template settings
    template_categories: List[str] = Field(
        default_factory=lambda: [
            "instruction_override",
            "delimiter_bypass",
            "role_play",
        ]
    )
    templates_per_category: int = 3
    template_parameters: Dict[str, Any] = Field(default_factory=dict)
    batch_size: int = Field(default=0, ge=0)

    # Generation
    n_samples_per_template: int = 1

    # Evaluation
    objective: str = "jailbreak"
    evaluator_type: str = "llm_judge"  # Deprecated compatibility field
    judge_config: Optional[Dict[str, Any]] = None

    # Filtering
    min_response_length: int = 10
    deduplicate_responses: bool = True

    @model_validator(mode="after")
    def validate_templates(self) -> "TemplateAttackConfig":
        validate_template_config(
            {
                "template_categories": self.template_categories,
                "template_parameters": self.template_parameters,
            }
        )
        return self

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "TemplateAttackConfig":
        """Create config from dictionary."""
        return cls.model_validate(config_dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()
