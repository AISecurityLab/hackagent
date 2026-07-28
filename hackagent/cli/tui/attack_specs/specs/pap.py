# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""PAP attack configuration spec."""

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
    technique_key="pap",
    display_name="PAP",
    description=(
        "Persuasive Adversarial Prompts. Uses an attacker LLM to paraphrase "
        "goals with persuasion techniques, then evaluates target responses "
        "with judges and early stopping."
    ),
    fields=[
        ConfigField(
            key="pap_params.techniques",
            label="Technique Set",
            field_type=FieldType.CHOICE,
            default="top5",
            description="Persuasion technique set to use.",
            choices=[
                ("Top-5 (paper default)", "top5"),
                ("All 40 techniques", "all"),
            ],
            section="Algorithm",
        ),
        ConfigField(
            key="pap_params.max_techniques_per_goal",
            label="Max Techniques per Goal",
            field_type=FieldType.INTEGER,
            default=0,
            description="0 means try all selected techniques.",
            min_value=0,
            max_value=40,
            section="Algorithm",
        ),
        ConfigField(
            key="pap_params.attacker_temperature",
            label="Attacker Temperature",
            field_type=FieldType.FLOAT,
            default=1.0,
            description="Sampling temperature for attacker paraphrasing.",
            min_value=0.0,
            max_value=2.0,
            step=0.1,
            section="Algorithm",
        ),
        ConfigField(
            key="pap_params.attacker_max_tokens",
            label="Attacker Max Tokens",
            field_type=FieldType.INTEGER,
            default=1024,
            description="Max tokens for attacker LLM output.",
            min_value=32,
            max_value=4096,
            section="Algorithm",
        ),
        ConfigField(
            key="attacker.identifier",
            label="Attacker Model",
            field_type=FieldType.STRING,
            default=DEFAULT_ATTACKER_IDENTIFIER,
            description="Model identifier for persuasive paraphrasing.",
            section="Attacker LLM",
        ),
        ConfigField(
            key="batch_size",
            label="Goal Batch Size",
            field_type=FieldType.INTEGER,
            default=1,
            description="Parallelism for processing goals.",
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
            key="judge_concurrency",
            label="Judge Concurrency",
            field_type=FieldType.INTEGER,
            default=1,
            description="Parallelism for judge evaluation requests.",
            min_value=1,
            max_value=16,
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
