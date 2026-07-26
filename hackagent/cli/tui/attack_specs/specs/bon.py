# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""BoN attack configuration spec."""

from __future__ import annotations

from hackagent.cli.tui.attack_specs.types import (
    AttackConfigSpec,
    ConfigField,
    FieldType,
)

SPEC = AttackConfigSpec(
    technique_key="bon",
    display_name="BoN",
    description=(
        "Best-of-N jailbreak search with stochastic text augmentations and "
        "judge-based candidate selection."
    ),
    fields=[
        ConfigField(
            key="bon_params.n_steps",
            label="Search Steps",
            field_type=FieldType.INTEGER,
            default=4,
            description="Number of sequential optimization steps.",
            min_value=1,
            max_value=100,
            section="Algorithm",
        ),
        ConfigField(
            key="bon_params.num_concurrent_k",
            label="Candidates per Step (K)",
            field_type=FieldType.INTEGER,
            default=5,
            description="Parallel augmented candidates evaluated each step.",
            min_value=1,
            max_value=100,
            section="Algorithm",
        ),
        ConfigField(
            key="bon_params.sigma",
            label="Augmentation Strength (Sigma)",
            field_type=FieldType.FLOAT,
            default=0.4,
            description="Mutation strength for text perturbations.",
            min_value=0.01,
            max_value=1.0,
            step=0.01,
            section="Algorithm",
        ),
        ConfigField(
            key="bon_params.word_scrambling",
            label="Enable Word Scrambling",
            field_type=FieldType.BOOLEAN,
            default=True,
            description="Shuffle internal characters in eligible words.",
            section="Algorithm",
            advanced=True,
        ),
        ConfigField(
            key="bon_params.random_capitalization",
            label="Enable Random Capitalization",
            field_type=FieldType.BOOLEAN,
            default=True,
            description="Randomly toggle character case.",
            section="Algorithm",
            advanced=True,
        ),
        ConfigField(
            key="bon_params.ascii_perturbation",
            label="Enable ASCII Perturbation",
            field_type=FieldType.BOOLEAN,
            default=True,
            description="Apply small printable-ASCII shifts.",
            section="Algorithm",
            advanced=True,
        ),
        ConfigField(
            key="batch_size",
            label="Target Batch Size",
            field_type=FieldType.INTEGER,
            default=1,
            description="Parallel target requests within each step.",
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
