# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CipherChat attack configuration spec."""

from __future__ import annotations

from hackagent.cli.tui.attack_specs.types import (
    AttackConfigSpec,
    ConfigField,
    FieldType,
)

SPEC = AttackConfigSpec(
    technique_key="cipherchat",
    display_name="CipherChat",
    description=(
        "Encodes the goal (and optional few-shot demonstrations) using a "
        "cipher (Caesar, ASCII, Morse, Unicode, ...) and asks the target "
        "to reply using the same encoding, bypassing safety filters that "
        "only recognize plain-text harmful requests."
    ),
    fields=[
        # --- Cipher ---
        ConfigField(
            key="cipherchat_params.encode_method",
            label="Encoding Method",
            field_type=FieldType.CHOICE,
            default="caesar",
            description="Cipher used to encode the goal and expected reply.",
            choices=[
                ("Caesar", "caesar"),
                ("Atbash", "atbash"),
                ("Morse", "morse"),
                ("ASCII", "ascii"),
                ("Unicode", "unicode"),
                ("UTF-8", "utf"),
                ("GBK", "gbk"),
                ("Self-defined", "selfdefine"),
                ("Unchanged (no cipher)", "unchange"),
            ],
            section="Cipher",
        ),
        ConfigField(
            key="cipherchat_params.use_system_role",
            label="Use System Role",
            field_type=FieldType.BOOLEAN,
            default=True,
            description="Send the cipher instructions as a system message.",
            section="Cipher",
            advanced=True,
        ),
        ConfigField(
            key="cipherchat_params.use_demonstrations",
            label="Use Few-shot Demonstrations",
            field_type=FieldType.BOOLEAN,
            default=True,
            description=(
                "Include encoded few-shot examples in the prompt. "
                "Disable to shrink the prompt and speed up generation."
            ),
            section="Cipher",
        ),
        ConfigField(
            key="cipherchat_params.num_demonstrations",
            label="Number of Demonstrations",
            field_type=FieldType.INTEGER,
            default=3,
            description="Few-shot examples to include (when enabled).",
            min_value=0,
            max_value=10,
            section="Cipher",
        ),
        ConfigField(
            key="cipherchat_params.demonstration_toxicity",
            label="Demonstration Toxicity",
            field_type=FieldType.CHOICE,
            default="toxic",
            description="Whether demonstration examples model harmful or refusal responses.",
            choices=[
                ("Toxic (harmful example)", "toxic"),
                ("Harmless (refusal example)", "harmless"),
            ],
            section="Cipher",
            advanced=True,
        ),
        ConfigField(
            key="cipherchat_params.instruction_type",
            label="Instruction Category",
            field_type=FieldType.CHOICE,
            default="Crimes_And_Illegal_Activities",
            description="Demonstration category matching the goal's topic.",
            choices=[
                ("Crimes & Illegal Activities", "Crimes_And_Illegal_Activities"),
                ("Ethics & Morality", "Ethics_And_Morality"),
                ("Inquiry with Unsafe Opinion", "Inquiry_With_Unsafe_Opinion"),
                ("Insult", "Insult"),
                ("Mental Health", "Mental_Health"),
                ("Physical Harm", "Physical_Harm"),
                ("Privacy & Property", "Privacy_And_Property"),
                ("Reverse Exposure", "Reverse_Exposure"),
                ("Role-Play Instruction", "Role_Play_Instruction"),
                ("Unfairness & Discrimination", "Unfairness_And_Discrimination"),
                ("Unsafe Instruction Topic", "Unsafe_Instruction_Topic"),
            ],
            section="Cipher",
            advanced=True,
        ),
        ConfigField(
            key="cipherchat_params.language",
            label="Demonstration Language",
            field_type=FieldType.CHOICE,
            default="en",
            description="Language of the few-shot demonstration examples.",
            choices=[("English", "en"), ("Chinese", "zh")],
            section="Cipher",
            advanced=True,
        ),
        ConfigField(
            key="cipherchat_params.decode_response",
            label="Decode Target Response",
            field_type=FieldType.BOOLEAN,
            default=True,
            description="Attempt to decode the target's encoded reply before evaluation.",
            section="Cipher",
            advanced=True,
        ),
        # --- Execution ---
        ConfigField(
            key="batch_size",
            label="Batch Size",
            field_type=FieldType.INTEGER,
            default=8,
            description="Number of goals sent to the target in parallel.",
            min_value=1,
            max_value=32,
            section="Execution",
        ),
        ConfigField(
            key="max_tokens",
            label="Target Max Tokens",
            field_type=FieldType.INTEGER,
            default=512,
            description="Max tokens for target model responses.",
            min_value=16,
            max_value=4096,
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
        # --- Evaluation ---
        ConfigField(
            key="batch_size_judge",
            label="Judge Batch Size",
            field_type=FieldType.INTEGER,
            default=1,
            description="Parallelism for judge evaluation requests.",
            min_value=1,
            max_value=16,
            section="Evaluation",
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
