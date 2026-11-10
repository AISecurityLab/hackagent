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
    """Which templates to apply and the values for their extra placeholders.

    ``template_categories`` and ``templates_per_category`` pick the
    templates, so the number of requests per goal is their product (capped
    by the size of each family). ``template_parameters`` supplies any
    placeholder a template needs beyond the four the attack derives from the
    goal. Validation rejects unknown families and unfilled placeholders.
    """

    template_categories: tuple[str, ...] = Field(
        default=DEFAULT_TEMPLATE_CATEGORIES,
        min_length=1,
        description=(
            "Families of jailbreak templates to apply, in order: "
            "instruction_override, delimiter_bypass, role_play, encoding, "
            "hypothetical, authority, multi_language. multi_language needs "
            "goal_translated and goal_foreign in template_parameters."
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
            "goal, goal_base64, goal_encoded (ROT13) and goal_obfuscated "
            "(reversed). A key with a built-in name overrides it."
        ),
    )

    @model_validator(mode="after")
    def validate_templates(self) -> "StaticTemplateParams":
        """Reject unknown families and selected templates with unfilled placeholders.

        Raises:
            ValueError: A category is not in :data:`~.templates.TEMPLATES`, or a
                selected template needs a placeholder that is neither built in
                nor given in ``template_parameters``.
        """
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
