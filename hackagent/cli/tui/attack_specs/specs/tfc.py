# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""tFC-Attack (Text-only flowchart attack) attack configuration spec."""

from __future__ import annotations

from hackagent.cli.tui.attack_specs.types import (
    AttackConfigSpec,
    ConfigField,
    FieldType,
)

SPEC = AttackConfigSpec(
    technique_key="tfc",
    display_name="tFC-Attack",
    description=(
        "Encodes harmful prompts as graph description languages "
        "(DOT, Mermaid, TikZ, PlantUML, ASCII) for any LLM. No VLM required."
    ),
    fields=[
        # --- Layout ---
        ConfigField(
            key="tfc_params.layout",
            label="Layout",
            field_type=FieldType.CHOICE,
            default="vertical",
            description="Flowchart layout style (affects text serialization structure).",
            choices=[
                ("Vertical (top-to-bottom)", "vertical"),
                ("Horizontal (left-to-right)", "horizontal"),
                ("S-Shaped (serpentine)", "s_shaped"),
            ],
            section="Flowchart",
        ),
        ConfigField(
            key="tfc_params.text_format",
            label="Text Format",
            field_type=FieldType.CHOICE,
            default="dot",
            description="Graph description language to encode the flowchart.",
            choices=[
                ("ASCII art", "ascii"),
                ("Graphviz DOT", "dot"),
                ("Mermaid", "mermaid"),
                ("TikZ (LaTeX)", "tikz"),
                ("PlantUML", "plantuml"),
            ],
            section="Flowchart",
        ),
        ConfigField(
            key="tfc_params.num_steps",
            label="Number of Steps",
            field_type=FieldType.INTEGER,
            default=6,
            description="Number of steps to decompose the goal into.",
            min_value=2,
            max_value=15,
            section="Flowchart",
        ),
        ConfigField(
            key="tfc_params.truncate_last_step",
            label="Truncate Last Step",
            field_type=FieldType.BOOLEAN,
            default=True,
            description="Truncate the last step to induce the LLM to complete it.",
            section="Flowchart",
        ),
        # --- Output ---
        ConfigField(
            key="tfc_params.output_dir",
            label="Output Directory",
            field_type=FieldType.STRING,
            default="./logs/tfc",
            description="Directory for saving run artifacts.",
            section="Output",
            advanced=True,
        ),
    ],
)
