# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""FlipAttack attack configuration spec."""

from __future__ import annotations

from hackagent.cli.tui.attack_specs.types import (
    AttackConfigSpec,
    ConfigField,
    FieldType,
)

SPEC = AttackConfigSpec(
    technique_key="flipattack",
    display_name="FlipAttack",
    description=(
        "Prompt obfuscation attack that applies reversible text flipping "
        "strategies (word/character transforms) and optional prompting "
        "enhancements before target evaluation."
    ),
    fields=[
        ConfigField(
            key="flipattack_params.flip_mode",
            label="Flip Mode",
            field_type=FieldType.CHOICE,
            default="FCS",
            description="Transformation mode applied to the goal prompt.",
            choices=[
                ("FCS (Flip chars in sentence)", "FCS"),
                ("FCW (Flip chars in words)", "FCW"),
                ("FWO (Flip word order)", "FWO"),
                ("FMM (Fool model mode)", "FMM"),
            ],
            section="Algorithm",
        ),
        ConfigField(
            key="flipattack_params.cot",
            label="Enable Chain-of-Thought Prompting",
            field_type=FieldType.BOOLEAN,
            default=False,
            description="Append reasoning-oriented decoding instructions.",
            section="Algorithm",
            advanced=True,
        ),
        ConfigField(
            key="flipattack_params.lang_gpt",
            label="Enable LangGPT Wrapper",
            field_type=FieldType.BOOLEAN,
            default=False,
            description="Wrap prompts in a structured LangGPT format.",
            section="Algorithm",
            advanced=True,
        ),
        ConfigField(
            key="flipattack_params.few_shot",
            label="Enable Few-shot Examples",
            field_type=FieldType.BOOLEAN,
            default=False,
            description="Inject few-shot decoding demonstrations.",
            section="Algorithm",
            advanced=True,
        ),
        ConfigField(
            key="max_tokens_eval",
            label="Max Judge Tokens",
            field_type=FieldType.INTEGER,
            default=256,
            description="Max tokens for judge evaluation responses.",
            min_value=16,
            max_value=2048,
            section="Evaluation",
        ),
        ConfigField(
            key="judge_temperature",
            label="Judge Temperature",
            field_type=FieldType.FLOAT,
            default=0.0,
            description="Sampling temperature for judge requests.",
            min_value=0.0,
            max_value=2.0,
            step=0.1,
            section="Evaluation",
            advanced=True,
        ),
        ConfigField(
            key="judge_timeout",
            label="Judge Timeout (s)",
            field_type=FieldType.INTEGER,
            default=120,
            description="Timeout in seconds for judge API requests.",
            min_value=10,
            max_value=600,
            section="Evaluation",
            advanced=True,
        ),
        ConfigField(
            key="output_dir",
            label="Output Directory",
            field_type=FieldType.STRING,
            default="./logs/runs",
            description="Directory for saving run artifacts.",
            section="Output",
            advanced=True,
        ),
    ],
)
