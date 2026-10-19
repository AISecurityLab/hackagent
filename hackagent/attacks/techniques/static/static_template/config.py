# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Configuration for the static-template attack."""

from string import Formatter

from pydantic import Field, model_validator

from ..base import AttackParams
from .templates import TEMPLATES

DEFAULT_TEMPLATE_CATEGORIES = (
    "instruction_override",
    "delimiter_bypass",
    "role_play",
)

#: Placeholders the attack fills from the goal itself.
BUILT_IN_PLACEHOLDERS = frozenset(
    {"goal", "goal_encoded", "goal_base64", "goal_obfuscated"}
)


class StaticTemplateParams(AttackParams):
    """Which templates to apply and the values for their extra placeholders."""

    template_categories: tuple[str, ...] = Field(
        default=DEFAULT_TEMPLATE_CATEGORIES,
        min_length=1,
        description=(
            "Families of jailbreak templates to apply: instruction_override, "
            "delimiter_bypass, role_play, encoding, hypothetical, authority, "
            "multi_language."
        ),
    )
    templates_per_category: int = Field(
        default=3,
        ge=1,
        description=(
            "How many templates to take from each family. Each template becomes one"
            " prompt."
        ),
    )
    template_parameters: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Values for extra placeholders a template uses, beyond the built-in "
            "goal, goal_base64, goal_encoded and goal_obfuscated."
        ),
    )

    @model_validator(mode="after")
    def validate_templates(self) -> "StaticTemplateParams":
        unknown = sorted(set(self.template_categories).difference(TEMPLATES))
        if unknown:
            raise ValueError(f"Unknown template categories: {', '.join(unknown)}")
        required = {
            name
            for template in self.selected_templates()
            for _, name, _, _ in Formatter().parse(template)
            if name is not None
        }
        missing = sorted(
            required - BUILT_IN_PLACEHOLDERS - self.template_parameters.keys()
        )
        if missing:
            raise ValueError(f"Missing template parameters: {', '.join(missing)}")
        return self

    def selected_templates(self) -> list[str]:
        """Templates to apply, in stable category order."""
        return [
            template
            for category in self.template_categories
            for template in TEMPLATES[category][: self.templates_per_category]
        ]
