# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""TAP attack configuration spec."""

from __future__ import annotations

from hackagent.cli.tui.attack_specs.types import (
    AttackConfigSpec,
    ConfigField,
    FieldType,
)

SPEC = AttackConfigSpec(
    technique_key="tap",
    display_name="TAP",
    description=(
        "Tree of Attacks with Pruning. Explores adversarial prompt trees "
        "with attacker/judge feedback and branch pruning."
    ),
    fields=[
        ConfigField(
            key="tap_params.depth",
            label="Tree Depth",
            field_type=FieldType.INTEGER,
            default=3,
            description="Maximum search depth for refinement tree.",
            min_value=1,
            max_value=10,
            section="Algorithm",
        ),
        ConfigField(
            key="tap_params.width",
            label="Tree Width",
            field_type=FieldType.INTEGER,
            default=4,
            description="Candidates retained per level.",
            min_value=1,
            max_value=20,
            section="Algorithm",
        ),
        ConfigField(
            key="tap_params.branching_factor",
            label="Branching Factor",
            field_type=FieldType.INTEGER,
            default=3,
            description="New candidates generated per parent node.",
            min_value=1,
            max_value=20,
            section="Algorithm",
        ),
        ConfigField(
            key="tap_params.n_streams",
            label="Parallel Streams",
            field_type=FieldType.INTEGER,
            default=4,
            description="Parallel attacker streams per goal.",
            min_value=1,
            max_value=20,
            section="Algorithm",
        ),
        ConfigField(
            key="tap_params.early_stop_on_success",
            label="Early Stop on Success",
            field_type=FieldType.BOOLEAN,
            default=True,
            description="Stop search immediately after successful jailbreak.",
            section="Algorithm",
        ),
        ConfigField(
            key="target_str",
            label="Target Prefix",
            field_type=FieldType.STRING,
            default="Sure, here is",
            description="Desired beginning of target model response.",
            section="Evaluation",
        ),
        ConfigField(
            key="max_tokens",
            label="Target Max Tokens",
            field_type=FieldType.INTEGER,
            default=256,
            description="Max tokens for target model responses.",
            min_value=16,
            max_value=4096,
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
