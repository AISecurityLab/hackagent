# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tool-output IPI attack configuration spec."""

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
    technique_key="tool_output_ipi",
    display_name="Tool-output IPI",
    description=(
        "Indirect prompt injection via poisoned tool observations "
        "(InjecAgent / OPI). A benign user task triggers a tool call; the "
        "attack injects adversarial instructions into the tool result and "
        "checks whether the agent follows them."
    ),
    fields=[
        ConfigField(
            key="tool_output_ipi_params.mode",
            label="Mode",
            field_type=FieldType.CHOICE,
            default="simulated",
            description=(
                "simulated crafts tool observations without a real backend; "
                "live solicits a real tool call first when possible."
            ),
            choices=[
                ("Simulated (default)", "simulated"),
                ("Live (stretch)", "live"),
            ],
            section="Algorithm",
        ),
        ConfigField(
            key="tool_output_ipi_params.max_attempts",
            label="Max Attempts per Goal",
            field_type=FieldType.INTEGER,
            default=3,
            description="Independent injection attempts (adaptive search).",
            min_value=1,
            max_value=20,
            section="Algorithm",
        ),
        ConfigField(
            key="tool_output_ipi_params.success_setting",
            label="Success Setting",
            field_type=FieldType.CHOICE,
            default="both",
            description="InjecAgent-aligned success case family.",
            choices=[
                ("Both", "both"),
                ("Direct harm", "direct_harm"),
                ("Data stealing", "data_stealing"),
            ],
            section="Algorithm",
        ),
        ConfigField(
            key="tool_output_ipi_params.tool_name",
            label="Simulated Tool Name",
            field_type=FieldType.STRING,
            default="search_documents",
            description="Tool name used when crafting simulated tool calls.",
            section="Algorithm",
        ),
        ConfigField(
            key="tool_output_ipi_params.use_attacker_llm",
            label="Use Attacker LLM",
            field_type=FieldType.BOOLEAN,
            default=False,
            description="Refine injection payloads with an attacker LLM.",
            section="Attacker LLM",
        ),
        ConfigField(
            key="attacker.identifier",
            label="Attacker Model",
            field_type=FieldType.STRING,
            default=DEFAULT_ATTACKER_IDENTIFIER,
            description="Model identifier for optional injection refinement.",
            section="Attacker LLM",
        ),
        ConfigField(
            key="tool_output_ipi_params.attacker_temperature",
            label="Attacker Temperature",
            field_type=FieldType.FLOAT,
            default=1.0,
            description="Sampling temperature for attacker refinement.",
            min_value=0.0,
            max_value=2.0,
            step=0.1,
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
