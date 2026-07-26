# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PAIR attack configuration spec."""

from __future__ import annotations

from hackagent.attacks.techniques.config import (
    DEFAULT_ATTACKER_IDENTIFIER,
)
from hackagent.cli.tui.attack_specs.types import (
    AttackConfigSpec,
    ConfigField,
    FieldType,
)

SPEC = AttackConfigSpec(
    technique_key="pair",
    display_name="PAIR",
    description=(
        "Prompt Automatic Iterative Refinement. Uses an attacker LLM to "
        "iteratively craft and refine adversarial prompts based on target "
        "model responses and judge scores."
    ),
    fields=[
        # --- Iteration ---
        ConfigField(
            key="n_iterations",
            label="Iterations",
            field_type=FieldType.INTEGER,
            default=5,
            description="Number of refinement iterations per stream.",
            min_value=1,
            max_value=50,
            section="Iteration",
        ),
        ConfigField(
            key="n_streams",
            label="Parallel Streams",
            field_type=FieldType.INTEGER,
            default=5,
            description="Number of parallel refinement streams.",
            min_value=1,
            max_value=20,
            section="Iteration",
        ),
        ConfigField(
            key="early_stop_on_success",
            label="Early Stop on Success",
            field_type=FieldType.BOOLEAN,
            default=True,
            description="Stop iterating once a jailbreak is found.",
            section="Iteration",
        ),
        # --- Attacker LLM ---
        ConfigField(
            key="attacker.model",
            label="Attacker Model",
            field_type=FieldType.STRING,
            default=DEFAULT_ATTACKER_IDENTIFIER,
            description="Model ID for the attacker LLM that generates prompts.",
            section="Attacker LLM",
        ),
        ConfigField(
            key="attacker.max_tokens",
            label="Attacker Max Tokens",
            field_type=FieldType.INTEGER,
            default=500,
            description="Max tokens for attacker LLM responses.",
            min_value=50,
            max_value=2048,
            section="Attacker LLM",
        ),
        ConfigField(
            key="attacker.temperature",
            label="Attacker Temperature",
            field_type=FieldType.FLOAT,
            default=1.0,
            description="Sampling temperature for the attacker LLM.",
            min_value=0.0,
            max_value=2.0,
            step=0.1,
            section="Attacker LLM",
        ),
        # --- Target Model ---
        ConfigField(
            key="max_tokens",
            label="Target Max Tokens",
            field_type=FieldType.INTEGER,
            default=150,
            description="Max tokens for target model responses.",
            min_value=16,
            max_value=2048,
            section="Target Model",
        ),
        ConfigField(
            key="temperature",
            label="Target Temperature",
            field_type=FieldType.FLOAT,
            default=0.7,
            description="Sampling temperature for target model.",
            min_value=0.0,
            max_value=2.0,
            step=0.1,
            section="Target Model",
        ),
        ConfigField(
            key="timeout",
            label="Request Timeout (s)",
            field_type=FieldType.INTEGER,
            default=120,
            description="Timeout in seconds for individual API requests.",
            min_value=10,
            max_value=600,
            section="Target Model",
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
