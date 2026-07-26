# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""MML (Multi-Modal Linkage) attack configuration spec."""

from __future__ import annotations

from hackagent.cli.tui.attack_specs.types import (
    AttackConfigSpec,
    ConfigField,
    FieldType,
)

SPEC = AttackConfigSpec(
    technique_key="mml",
    display_name="MML (Multi-Modal Linkage)",
    description=(
        "Encodes harmful prompts into images using visual "
        "transformations (word replacement, mirror, rotation, base64, "
        "mixed) and instructs a Vision-Language Model to decode them."
    ),
    fields=[
        # --- Encoding ---
        ConfigField(
            key="mml_params.encoding_mode",
            label="Encoding Mode",
            field_type=FieldType.CHOICE,
            default="word_replacement",
            description="Visual encoding strategy for the harmful prompt.",
            choices=[
                ("Word Replacement", "word_replacement"),
                ("Mirror", "mirror"),
                ("Rotate", "rotate"),
                ("Base64", "base64"),
                ("Mixed", "mixed"),
            ],
            section="Encoding",
        ),
        ConfigField(
            key="mml_params.prompt_style",
            label="Prompt Style",
            field_type=FieldType.CHOICE,
            default="game",
            description="Prompt framing: 'game' uses villain scenario, 'control' is neutral.",
            choices=[
                ("Game (villain scenario)", "game"),
                ("Control (neutral)", "control"),
            ],
            section="Encoding",
        ),
        ConfigField(
            key="mml_params.num_replacements",
            label="Word Replacements",
            field_type=FieldType.INTEGER,
            default=3,
            description="Number of words to replace (word_replacement mode only).",
            min_value=1,
            max_value=10,
            section="Encoding",
        ),
        # --- Image Rendering ---
        ConfigField(
            key="mml_params.image_width",
            label="Image Width (px)",
            field_type=FieldType.INTEGER,
            default=800,
            description="Width of the generated image in pixels.",
            min_value=100,
            max_value=2048,
            section="Image",
        ),
        ConfigField(
            key="mml_params.image_height",
            label="Image Height (px)",
            field_type=FieldType.INTEGER,
            default=400,
            description="Height of the generated image in pixels.",
            min_value=100,
            max_value=2048,
            section="Image",
        ),
        ConfigField(
            key="mml_params.font_size",
            label="Font Size",
            field_type=FieldType.INTEGER,
            default=24,
            description="Font size for rendered text in the image.",
            min_value=8,
            max_value=72,
            section="Image",
        ),
        ConfigField(
            key="mml_params.background_color",
            label="Background Color",
            field_type=FieldType.STRING,
            default="white",
            description="Background color of the generated image.",
            section="Image",
            advanced=True,
        ),
        ConfigField(
            key="mml_params.text_color",
            label="Text Color",
            field_type=FieldType.STRING,
            default="black",
            description="Text color in the generated image.",
            section="Image",
            advanced=True,
        ),
        # --- Output ---
        ConfigField(
            key="output_dir",
            label="Output Directory",
            field_type=FieldType.STRING,
            default="./logs/mml",
            description="Directory for saving run artifacts.",
            section="Output",
            advanced=True,
        ),
    ],
)
