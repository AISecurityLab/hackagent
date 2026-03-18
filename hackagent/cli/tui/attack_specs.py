# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
TUI-local attack configuration specifications.

This module is the **single source of truth** for the form fields that the
TUI renders when configuring an attack.  It is intentionally decoupled from
the attack domain code (``hackagent.attacks``) so that:

* Adding / removing a field never touches the attack implementation.
* The TUI remains agnostic to the selected attack strategy — every
  strategy is just another ``AttackConfigSpec`` entry in the registry
  below.
* The framework (``ConfigField``, ``FieldType``, ``AttackConfigSpec``)
  can be re-used by future CLIs or web UIs without pulling in attack
  dependencies.

To add a new attack to the TUI, simply append an ``AttackConfigSpec``
to ``_SPECS`` at the bottom of this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


# =====================================================================
# Field / Spec primitives
# =====================================================================


class FieldType(str, Enum):
    """Supported configuration field types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    CHOICE = "choice"
    TEXT = "text"


@dataclass
class ConfigField:
    """Specification for a single configuration parameter.

    Attributes:
        key: Dot-separated key path (e.g. ``"attacker.temperature"``).
             Dotted keys are expanded into nested dicts at collection time.
        label: Human-readable label shown in the UI.
        field_type: One of :class:`FieldType` values.
        default: Default value for the field.
        description: Tooltip / help text shown to the user.
        required: Whether the field must be provided.
        choices: For ``CHOICE`` type, the list of ``(label, value)`` pairs.
        min_value: Minimum value for numeric fields.
        max_value: Maximum value for numeric fields.
        step: Step increment for numeric fields (sliders / spinners).
        section: Logical grouping (e.g. ``"Generation"``).  The TUI uses
                 this to organize fields into collapsible sections.
        advanced: If ``True`` the field is hidden behind the
                  "Show advanced settings" toggle.
    """

    key: str
    label: str
    field_type: FieldType
    default: Any = None
    description: str = ""
    required: bool = False
    choices: Optional[Sequence[Tuple[str, Any]]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    step: Optional[Union[int, float]] = None
    section: str = "General"
    advanced: bool = False


@dataclass
class AttackConfigSpec:
    """Complete configuration specification for an attack technique.

    Attributes:
        technique_key: Internal identifier (e.g. ``"advprefix"``).
        display_name: Human-friendly name shown in the UI selector.
        description: Short description of the technique.
        fields: Ordered list of :class:`ConfigField`.
    """

    technique_key: str
    display_name: str
    description: str = ""
    fields: List[ConfigField] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def sections(self) -> List[str]:
        """Return unique section names in order of first appearance."""
        seen: set[str] = set()
        result: list[str] = []
        for f in self.fields:
            if f.section not in seen:
                seen.add(f.section)
                result.append(f.section)
        return result

    def fields_for_section(
        self, section: str, *, include_advanced: bool = False
    ) -> List[ConfigField]:
        """Return fields belonging to *section*."""
        return [
            f
            for f in self.fields
            if f.section == section and (include_advanced or not f.advanced)
        ]

    def defaults_dict(self) -> Dict[str, Any]:
        """Build a flat ``{key: default}`` mapping for all fields."""
        return {f.key: f.default for f in self.fields if f.default is not None}

    def validate(self, values: Dict[str, Any]) -> List[str]:
        """Validate *values* against the spec.

        Returns:
            A list of human-readable error strings (empty = valid).
        """
        errors: list[str] = []
        for f in self.fields:
            val = values.get(f.key)

            if f.required and (val is None or val == ""):
                errors.append(f"{f.label} is required.")
                continue

            if val is None or val == "":
                continue

            if f.field_type == FieldType.INTEGER:
                try:
                    int_val = int(val)
                except (TypeError, ValueError):
                    errors.append(f"{f.label} must be an integer.")
                    continue
                if f.min_value is not None and int_val < f.min_value:
                    errors.append(f"{f.label} must be ≥ {f.min_value} (got {int_val}).")
                if f.max_value is not None and int_val > f.max_value:
                    errors.append(f"{f.label} must be ≤ {f.max_value} (got {int_val}).")

            elif f.field_type == FieldType.FLOAT:
                try:
                    float_val = float(val)
                except (TypeError, ValueError):
                    errors.append(f"{f.label} must be a number.")
                    continue
                if f.min_value is not None and float_val < f.min_value:
                    errors.append(
                        f"{f.label} must be ≥ {f.min_value} (got {float_val})."
                    )
                if f.max_value is not None and float_val > f.max_value:
                    errors.append(
                        f"{f.label} must be ≤ {f.max_value} (got {float_val})."
                    )

            elif f.field_type == FieldType.CHOICE:
                valid_values = [c[1] for c in (f.choices or [])]
                if val not in valid_values:
                    errors.append(f"{f.label}: '{val}' is not a valid choice.")

        return errors


# =====================================================================
# Spec registry — populated statically below
# =====================================================================

_SPECS: Dict[str, AttackConfigSpec] = {}


def _register(spec: AttackConfigSpec) -> AttackConfigSpec:
    """Register and return *spec* (convenience for inline use)."""
    _SPECS[spec.technique_key] = spec
    return spec


def get_attack_config_spec(technique_key: str) -> Optional[AttackConfigSpec]:
    """Return the config spec for *technique_key*, or ``None``."""
    return _SPECS.get(technique_key)


def get_all_attack_specs() -> Dict[str, AttackConfigSpec]:
    """Return all registered attack config specs."""
    return dict(_SPECS)


# =====================================================================
# AdvPrefix
# =====================================================================

_register(
    AttackConfigSpec(
        technique_key="advprefix",
        display_name="AdvPrefix",
        description=(
            "Generates adversarial prefixes using an uncensored surrogate "
            "model, then evaluates them with judge LLMs to find effective "
            "jailbreak prefixes."
        ),
        fields=[
            # --- Generation ---
            ConfigField(
                key="batch_size",
                label="Batch Size",
                field_type=FieldType.INTEGER,
                default=2,
                description="Number of prefixes to generate per batch.",
                min_value=1,
                max_value=64,
                section="Generation",
            ),
            ConfigField(
                key="max_new_tokens",
                label="Max New Tokens",
                field_type=FieldType.INTEGER,
                default=512,
                description="Maximum tokens per generated prefix.",
                min_value=16,
                max_value=2048,
                section="Generation",
            ),
            ConfigField(
                key="temperature",
                label="Temperature",
                field_type=FieldType.FLOAT,
                default=0.7,
                description="Sampling temperature for prefix generation.",
                min_value=0.0,
                max_value=2.0,
                step=0.1,
                section="Generation",
            ),
            ConfigField(
                key="guided_topk",
                label="Top-K",
                field_type=FieldType.INTEGER,
                default=50,
                description="Top-K tokens to consider during generation.",
                min_value=1,
                max_value=200,
                section="Generation",
                advanced=True,
            ),
            ConfigField(
                key="meta_prefix_samples",
                label="Meta-Prefix Samples",
                field_type=FieldType.INTEGER,
                default=2,
                description="Number of meta-prefix variations to try per goal.",
                min_value=1,
                max_value=10,
                section="Generation",
                advanced=True,
            ),
            ConfigField(
                key="n_candidates_per_goal",
                label="Candidates per Goal",
                field_type=FieldType.INTEGER,
                default=5,
                description="Prefix candidates to keep per goal after filtering.",
                min_value=1,
                max_value=50,
                section="Generation",
            ),
            # --- Execution ---
            ConfigField(
                key="max_new_tokens_completion",
                label="Max Completion Tokens",
                field_type=FieldType.INTEGER,
                default=512,
                description="Max tokens for target model completions.",
                min_value=16,
                max_value=2048,
                section="Execution",
            ),
            ConfigField(
                key="n_samples",
                label="Samples per Prefix",
                field_type=FieldType.INTEGER,
                default=1,
                description="Number of completions to request per prefix.",
                min_value=1,
                max_value=10,
                section="Execution",
            ),
            ConfigField(
                key="request_timeout",
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
                key="n_prefixes_per_goal",
                label="Prefixes per Goal",
                field_type=FieldType.INTEGER,
                default=2,
                description="Best prefixes to select per goal after evaluation.",
                min_value=1,
                max_value=20,
                section="Evaluation",
            ),
            ConfigField(
                key="batch_size_judge",
                label="Judge Batch Size",
                field_type=FieldType.INTEGER,
                default=1,
                description="Batch size for judge evaluation requests.",
                min_value=1,
                max_value=16,
                section="Evaluation",
                advanced=True,
            ),
            ConfigField(
                key="max_new_tokens_eval",
                label="Max Judge Tokens",
                field_type=FieldType.INTEGER,
                default=512,
                description="Max tokens for judge evaluation responses.",
                min_value=16,
                max_value=2048,
                section="Evaluation",
                advanced=True,
            ),
            # --- Filtering ---
            ConfigField(
                key="max_ce",
                label="Max Cross-Entropy",
                field_type=FieldType.FLOAT,
                default=0.9,
                description="Max cross-entropy threshold for prefix filtering.",
                min_value=0.0,
                max_value=5.0,
                step=0.1,
                section="Filtering",
                advanced=True,
            ),
            ConfigField(
                key="min_char_length",
                label="Min Char Length",
                field_type=FieldType.INTEGER,
                default=10,
                description="Minimum character length for generated prefixes.",
                min_value=1,
                max_value=500,
                section="Filtering",
                advanced=True,
            ),
            ConfigField(
                key="filter_len",
                label="Min Response Length",
                field_type=FieldType.INTEGER,
                default=10,
                description="Minimum response length to consider for evaluation.",
                min_value=1,
                max_value=500,
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
)


# =====================================================================
# Baseline
# =====================================================================

_register(
    AttackConfigSpec(
        technique_key="baseline",
        display_name="Baseline",
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
                key="max_new_tokens",
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
                key="request_timeout",
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
)


# =====================================================================
# PAIR
# =====================================================================

_register(
    AttackConfigSpec(
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
                default="gpt-4",
                description="Model ID for the attacker LLM that generates prompts.",
                section="Attacker LLM",
            ),
            ConfigField(
                key="attacker.max_new_tokens",
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
                key="max_new_tokens",
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
                key="request_timeout",
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
)


# =====================================================================
# AutoDAN-Turbo
# =====================================================================

_register(
    AttackConfigSpec(
        technique_key="autodan_turbo",
        display_name="AutoDAN-Turbo",
        description=(
            "Lifelong jailbreak attack with automatic strategy discovery. "
            "Uses a warm-up phase to bootstrap a strategy library, then a "
            "lifelong phase with retrieval-augmented prompt generation."
        ),
        fields=[
            # --- Algorithm ---
            ConfigField(
                key="autodan_turbo_params.epochs",
                label="Epochs per Goal",
                field_type=FieldType.INTEGER,
                default=100,
                description="Maximum attack attempts per goal.",
                min_value=1,
                max_value=500,
                section="Algorithm",
            ),
            ConfigField(
                key="autodan_turbo_params.break_score",
                label="Break Score",
                field_type=FieldType.FLOAT,
                default=8.5,
                description="Score threshold (1-10) to consider jailbreak successful.",
                min_value=1.0,
                max_value=10.0,
                step=0.5,
                section="Algorithm",
            ),
            ConfigField(
                key="autodan_turbo_params.warm_up_iterations",
                label="Warm-up Iterations",
                field_type=FieldType.INTEGER,
                default=1,
                description="Number of warm-up iterations (strategy exploration).",
                min_value=0,
                max_value=10,
                section="Algorithm",
            ),
            ConfigField(
                key="autodan_turbo_params.lifelong_iterations",
                label="Lifelong Iterations",
                field_type=FieldType.INTEGER,
                default=1,
                description="Number of lifelong iterations (strategy-guided).",
                min_value=1,
                max_value=10,
                section="Algorithm",
            ),
            ConfigField(
                key="autodan_turbo_params.skip_warm_up",
                label="Skip Warm-up",
                field_type=FieldType.BOOLEAN,
                default=False,
                description="Skip warm-up phase (requires pre-built library).",
                section="Algorithm",
                advanced=True,
            ),
            # --- Attacker LLM ---
            ConfigField(
                key="attacker.identifier",
                label="Attacker Model",
                field_type=FieldType.STRING,
                default="hackagent-attacker",
                description="Model identifier for the attacker LLM.",
                section="Attacker LLM",
            ),
            ConfigField(
                key="autodan_turbo_params.attacker_temperature",
                label="Attacker Temperature",
                field_type=FieldType.FLOAT,
                default=1.0,
                description="Sampling temperature for attacker LLM.",
                min_value=0.0,
                max_value=2.0,
                step=0.1,
                section="Attacker LLM",
            ),
            # --- Scorer LLM ---
            ConfigField(
                key="scorer.identifier",
                label="Scorer Model",
                field_type=FieldType.STRING,
                default="hackagent-scorer",
                description="Model identifier for the scorer LLM.",
                section="Scorer LLM",
            ),
            # --- Target Model ---
            ConfigField(
                key="max_new_tokens",
                label="Target Max Tokens",
                field_type=FieldType.INTEGER,
                default=4096,
                description="Max tokens for target model responses.",
                min_value=16,
                max_value=8192,
                section="Target Model",
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
                section="Target Model",
            ),
            ConfigField(
                key="request_timeout",
                label="Request Timeout (s)",
                field_type=FieldType.INTEGER,
                default=120,
                description="Timeout in seconds for individual API requests.",
                min_value=10,
                max_value=600,
                section="Target Model",
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
)


# =====================================================================
# FlipAttack
# =====================================================================

_register(
    AttackConfigSpec(
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
                key="max_new_tokens_eval",
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
                key="judge_request_timeout",
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
)


# =====================================================================
# TAP
# =====================================================================

_register(
    AttackConfigSpec(
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
                key="max_new_tokens",
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
                key="request_timeout",
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
)


# =====================================================================
# BoN
# =====================================================================

_register(
    AttackConfigSpec(
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
                key="max_new_tokens",
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
                key="request_timeout",
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
)


# =====================================================================
# h4rm3l
# =====================================================================

_register(
    AttackConfigSpec(
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
                description=(
                    "Preset name or raw decorator chain expression for h4rm3l."
                ),
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
                key="max_new_tokens",
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
                key="request_timeout",
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
)
