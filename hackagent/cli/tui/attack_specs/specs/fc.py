# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""FC-Attack (Flowchart image attack) attack configuration spec."""

from __future__ import annotations

from hackagent.cli.tui.attack_specs.types import (
    AttackConfigSpec,
    ConfigField,
    FieldType,
)

SPEC = AttackConfigSpec(
    technique_key="fc",
    display_name="FC-Attack",
    description=(
        "Renders harmful prompts as flowchart images and sends them "
        "to a Vision-Language Model. Requires a VLM target."
    ),
    fields=[
        # --- Layout ---
        ConfigField(
            key="fc_params.layout",
            label="Layout",
            field_type=FieldType.CHOICE,
            default="vertical",
            description="Flowchart layout style for rendering steps.",
            choices=[
                ("Vertical (top-to-bottom)", "vertical"),
                ("Horizontal (left-to-right)", "horizontal"),
                ("S-Shaped (serpentine)", "s_shaped"),
            ],
            section="Flowchart",
        ),
        ConfigField(
            key="fc_params.num_steps",
            label="Number of Steps",
            field_type=FieldType.INTEGER,
            default=6,
            description="Number of steps to decompose the goal into.",
            min_value=2,
            max_value=15,
            section="Flowchart",
        ),
        ConfigField(
            key="fc_params.truncate_last_step",
            label="Truncate Last Step",
            field_type=FieldType.BOOLEAN,
            default=True,
            description="Truncate the last step to induce the VLM to complete it.",
            section="Flowchart",
        ),
        # --- Output ---
        ConfigField(
            key="fc_params.output_dir",
            label="Output Directory",
            field_type=FieldType.STRING,
            default="./logs/fc",
            description="Directory for saving run artifacts.",
            section="Output",
            advanced=True,
        ),
    ],
)
