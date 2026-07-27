# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Static Template attack configuration spec."""

from __future__ import annotations

from hackagent.cli.tui.attack_specs.types import (
    AttackConfigSpec,
    ConfigField,
    FieldType,
)

SPEC = AttackConfigSpec(
    technique_key="static_template",
    display_name="Static Template",
    description=(
        "Template-based prompt injection attacks. Combines predefined "
        "attack templates with goals across multiple categories "
        "(instruction override, delimiter bypass, role-play, etc.)."
    ),
    fields=[
        # --- Templates ---
        ConfigField(
            key="template_categories",
            label="Template Categories",
            field_type=FieldType.TEXT,
            default=(
                "instruction_override, delimiter_bypass, role_play, "
                "prefix_injection, context_manipulation"
            ),
            description=("Comma-separated list of template categories to use."),
            section="Templates",
        ),
        ConfigField(
            key="templates_per_category",
            label="Templates per Category",
            field_type=FieldType.INTEGER,
            default=3,
            description="Number of templates to sample from each category.",
            min_value=1,
            max_value=20,
            section="Templates",
        ),
        # --- Generation ---
        ConfigField(
            key="max_tokens",
            label="Max New Tokens",
            field_type=FieldType.INTEGER,
            default=150,
            description="Maximum tokens for target model responses.",
            min_value=16,
            max_value=2048,
            section="Generation",
        ),
        ConfigField(
            key="temperature",
            label="Temperature",
            field_type=FieldType.FLOAT,
            default=0.7,
            description="Sampling temperature for target model.",
            min_value=0.0,
            max_value=2.0,
            step=0.1,
            section="Generation",
        ),
        ConfigField(
            key="n_samples_per_template",
            label="Samples per Template",
            field_type=FieldType.INTEGER,
            default=1,
            description="Completions per template-goal combination.",
            min_value=1,
            max_value=10,
            section="Generation",
        ),
        ConfigField(
            key="timeout",
            label="Request Timeout (s)",
            field_type=FieldType.INTEGER,
            default=60,
            description="Timeout in seconds for individual API requests.",
            min_value=10,
            max_value=600,
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
            default="pattern",
            description="Method used to evaluate attack success.",
            choices=[
                ("Pattern Matching", "pattern"),
                ("Keyword Matching", "keyword"),
                ("LLM Judge", "llm_judge"),
            ],
            section="Evaluation",
        ),
        # --- Filtering ---
        ConfigField(
            key="min_response_length",
            label="Min Response Length",
            field_type=FieldType.INTEGER,
            default=10,
            description="Minimum character length for target responses.",
            min_value=1,
            max_value=500,
            section="Filtering",
            advanced=True,
        ),
        ConfigField(
            key="deduplicate_responses",
            label="Deduplicate Responses",
            field_type=FieldType.BOOLEAN,
            default=True,
            description="Remove duplicate responses before evaluation.",
            section="Filtering",
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
