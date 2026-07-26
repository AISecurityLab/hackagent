# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Baseline attack configuration spec."""

from __future__ import annotations

from hackagent.cli.tui.attack_specs.types import (
    AttackConfigSpec,
    ConfigField,
    FieldType,
)

SPEC = AttackConfigSpec(
    technique_key="baseline",
    display_name="Baseline",
    description=(
        "Sends goals directly to the target with no transformation — a "
        "control condition for measuring the target's default refusal "
        "rate against unobfuscated requests."
    ),
    fields=[
        # --- Generation ---
        ConfigField(
            key="max_tokens",
            label="Max New Tokens",
            field_type=FieldType.INTEGER,
            default=1024,
            description="Maximum tokens for target model responses.",
            min_value=16,
            max_value=4096,
            section="Generation",
        ),
        ConfigField(
            key="temperature",
            label="Temperature",
            field_type=FieldType.FLOAT,
            default=0.0,
            description="Sampling temperature for target model.",
            min_value=0.0,
            max_value=2.0,
            step=0.1,
            section="Generation",
        ),
        ConfigField(
            key="batch_size",
            label="Batch Size",
            field_type=FieldType.INTEGER,
            default=16,
            description="Number of goals sent to the target in parallel.",
            min_value=1,
            max_value=64,
            section="Generation",
        ),
        # --- Evaluation ---
        ConfigField(
            key="objective",
            label="Objective",
            field_type=FieldType.CHOICE,
            default="jailbreak",
            description="Vulnerability objective to evaluate against.",
            choices=[
                ("Jailbreak", "jailbreak"),
                ("Harmful Behavior", "harmful_behavior"),
                ("Policy Violation", "policy_violation"),
            ],
            section="Evaluation",
        ),
        ConfigField(
            key="evaluator_type",
            label="Evaluator Type",
            field_type=FieldType.CHOICE,
            default="llm_judge",
            description="Method used to evaluate attack success.",
            choices=[
                ("LLM Judge", "llm_judge"),
                ("Pattern Matching", "pattern"),
                ("Keyword Matching", "keyword"),
            ],
            section="Evaluation",
        ),
        ConfigField(
            key="min_response_length",
            label="Min Response Length",
            field_type=FieldType.INTEGER,
            default=10,
            description="Minimum character length for target responses.",
            min_value=1,
            max_value=500,
            section="Evaluation",
            advanced=True,
        ),
        # --- Output ---
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
