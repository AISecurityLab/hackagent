# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""h4rm3l attack configuration spec."""

from __future__ import annotations

from hackagent.cli.tui.attack_specs.types import (
    AttackConfigSpec,
    ConfigField,
    FieldType,
)

SPEC = AttackConfigSpec(
    technique_key="h4rm3l",
    display_name="h4rm3l",
    description=(
        "Composable prompt-decoration attack that applies configurable "
        "obfuscation/transformation chains before evaluating target behavior."
    ),
    fields=[
        ConfigField(
            key="h4rm3l_params.program",
            label="Decorator Program",
            field_type=FieldType.TEXT,
            default="refusal_suppression",
            description=("Preset name or raw decorator chain expression for h4rm3l."),
            section="Program",
        ),
        ConfigField(
            key="h4rm3l_params.syntax_version",
            label="Syntax Version",
            field_type=FieldType.CHOICE,
            default=2,
            description="Program parser mode for decorator chaining syntax.",
            choices=[("v1 (semicolon)", 1), ("v2 (.then chaining)", 2)],
            section="Program",
        ),
        ConfigField(
            key="goal_batch_size",
            label="Goal Batch Size",
            field_type=FieldType.INTEGER,
            default=1,
            description="Number of goals processed per orchestrator batch.",
            min_value=1,
            max_value=32,
            section="Execution",
        ),
        ConfigField(
            key="goal_batch_workers",
            label="Goal Batch Workers",
            field_type=FieldType.INTEGER,
            default=1,
            description="Parallel workers used within each goal batch.",
            min_value=1,
            max_value=32,
            section="Execution",
        ),
        ConfigField(
            key="max_tokens",
            label="Target Max Tokens",
            field_type=FieldType.INTEGER,
            default=4096,
            description="Max tokens for target model responses.",
            min_value=16,
            max_value=8192,
            section="Execution",
        ),
        ConfigField(
            key="temperature",
            label="Target Temperature",
            field_type=FieldType.FLOAT,
            default=0.6,
            description="Sampling temperature for target model.",
            min_value=0.0,
            max_value=2.0,
            step=0.1,
            section="Execution",
        ),
        ConfigField(
            key="timeout",
            label="Request Timeout (s)",
            field_type=FieldType.INTEGER,
            default=120,
            description="Timeout in seconds for individual API requests.",
            min_value=10,
            max_value=600,
            section="Execution",
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
