# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Shared Pydantic configuration primitives for attack techniques.

This module is the single source of truth for the pieces that are genuinely
standard across attacks:

* attacker routing defaults
* judge routing defaults
* judge-evaluation scalars
* goals/dataset input shape
* run/output bookkeeping

Technique-specific modules should extend these building blocks with their own
algorithm parameters, but they should not redefine the shared defaults.

Victim-model request defaults are still defined here for compatibility and
for callers that want the canonical schema, but the preferred runtime source
for those settings is now `HackAgent(..., target_config=...)`.

Two export styles are intentionally supported:

* Pydantic models such as :class:`AttackerConfig` and :class:`RunConfig`
* plain Python dict helpers such as :func:`default_attacker` and
    :data:`DEFAULT_RUN_CONFIG`

The dict helpers are not a compatibility shim; they are the canonical bridge
for attack modules that still build top-level ``DEFAULT_*_CONFIG`` mappings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Canonical service defaults
# ---------------------------------------------------------------------------

HACKAGENT_API_BASE = "https://api.hackagent.dev/v1"
HACKAGENT_AGENT_TYPE = "OPENAI_SDK"
DEFAULT_ATTACKER_IDENTIFIER = "hackagent-attacker"
DEFAULT_JUDGE_IDENTIFIER = "hackagent-judge"
DEFAULT_MAX_OUTPUT_TOKENS = 4096

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AttackerConfig(BaseModel):
    """Configuration for the attacker LLM.

    Defaults to the shared HackAgent attacker endpoint so users only need
    to override what is different for their deployment.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    identifier: str = DEFAULT_ATTACKER_IDENTIFIER
    endpoint: str = HACKAGENT_API_BASE
    agent_type: str = HACKAGENT_AGENT_TYPE
    api_key: Optional[str] = None
    max_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    temperature: float = 1.0
    top_p: float = 0.9
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    seed: Optional[int] = None
    stop: Optional[List[str]] = None
    reasoning_effort: Optional[str] = None
    extra_body: Optional[Dict[str, Any]] = None
    response_format: Optional[Dict[str, Any]] = None
    logit_bias: Optional[Dict[str, int]] = None


class JudgeConfig(BaseModel):
    """Configuration for one judge evaluator.

    Defaults to the HarmBench judge on the shared HackAgent endpoint.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    identifier: str = DEFAULT_JUDGE_IDENTIFIER
    endpoint: Optional[str] = HACKAGENT_API_BASE
    agent_type: str = HACKAGENT_AGENT_TYPE
    type: str = "harmbench"
    api_key: Optional[str] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    seed: Optional[int] = None
    stop: Optional[List[str]] = None
    reasoning_effort: Optional[str] = None
    extra_body: Optional[Dict[str, Any]] = None
    response_format: Optional[Dict[str, Any]] = None
    logit_bias: Optional[Dict[str, int]] = None


class JudgeEvalConfig(BaseModel):
    """Scalar evaluation parameters shared by every attack that uses a judge."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    batch_size_judge: int = Field(default=1, ge=1)
    max_tokens_eval: int = Field(default=DEFAULT_MAX_OUTPUT_TOKENS, ge=1)
    filter_len: int = Field(default=10, ge=0)
    judge_timeout: int = Field(default=120, ge=1)
    judge_temperature: float = Field(default=0.0, ge=0.0)
    max_judge_retries: int = Field(default=1, ge=0)


class TargetConfig(BaseModel):
    """Default generation parameters for the target (victim) model."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    max_tokens: int = Field(default=DEFAULT_MAX_OUTPUT_TOKENS, ge=1)
    temperature: float = Field(default=0.6, ge=0.0)
    top_p: Optional[float] = 1.0
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    seed: Optional[int] = None
    stop: Optional[List[str]] = None
    reasoning_effort: Optional[str] = None
    extra_body: Optional[Dict[str, Any]] = None
    response_format: Optional[Dict[str, Any]] = None
    logit_bias: Optional[Dict[str, int]] = None
    timeout: int = Field(default=120, ge=1)


class GoalsDatasetConfig(BaseModel):
    """Shared input source fields for attacks that accept goals or datasets."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    goals: List[str] = Field(default_factory=list)
    dataset: Optional[str] = None


class RunConfig(BaseModel):
    """Pipeline-level bookkeeping shared by every attack."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    output_dir: str = "./logs/runs"
    run_id: Optional[str] = None
    start_step: int = Field(default=1, ge=1)


class ExecutionConfig(BaseModel):
    """Shared batching and orchestration defaults used across attacks."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    batch_size: int = Field(default=1, ge=1)
    goal_batch_size: int = Field(default=1, ge=1)
    goal_batch_workers: int = Field(default=1, ge=1)


class ConfigBase(
    GoalsDatasetConfig,
    RunConfig,
    ExecutionConfig,
    JudgeEvalConfig,
    TargetConfig,
):
    """Base typed config for the shared user-facing attack defaults."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    attacker: Dict[str, Any] = Field(
        default_factory=lambda: AttackerConfig().model_dump()
    )
    judge: Dict[str, Any] = Field(default_factory=lambda: JudgeConfig().model_dump())
    judges: List[Dict[str, Any]] = Field(
        default_factory=lambda: [JudgeConfig().model_dump()]
    )


# Backward-compatible aliases while the shared config layer settles.
TechniqueConfigBase = ConfigBase
JudgeConfigBase = ConfigBase
JudgeTechniqueConfigBase = ConfigBase
JudgeTargetConfigBase = ConfigBase
JudgeTargetTechniqueConfigBase = ConfigBase


# ---------------------------------------------------------------------------
# Factory helpers (always return fresh copies — safe for dict mutation)
# ---------------------------------------------------------------------------


def default_attacker() -> Dict[str, Any]:
    """Return a fresh attacker config dict."""
    return AttackerConfig().model_dump()


def default_judge() -> Dict[str, Any]:
    """Return a fresh single judge config dict."""
    return JudgeConfig().model_dump()


def default_judges() -> List[Dict[str, Any]]:
    """Return a fresh default judges list (one HarmBench judge)."""
    return [default_judge()]


def default_judge_eval() -> Dict[str, Any]:
    """Return a fresh dict of shared judge-evaluation scalar defaults."""
    return JudgeEvalConfig().model_dump()


def default_target() -> Dict[str, Any]:
    """Return a fresh dict of shared target-generation defaults."""
    return TargetConfig().model_dump()


def default_goals_and_dataset() -> Dict[str, Any]:
    """Return a fresh goals/dataset mapping used by attack default dicts."""
    return GoalsDatasetConfig().model_dump()


def default_run() -> Dict[str, Any]:
    """Return a fresh dict of shared run/output defaults."""
    return RunConfig().model_dump()


def default_execution() -> Dict[str, Any]:
    """Return a fresh dict of shared execution/batching defaults."""
    return ExecutionConfig().model_dump()


def default_config_base() -> Dict[str, Any]:
    """Return shared attack defaults excluding victim request defaults."""
    config = ConfigBase().model_dump()
    for key in TargetConfig.model_fields:
        config.pop(key, None)
    return config


# ---------------------------------------------------------------------------
# Canonical plain-dict projections used by technique DEFAULT_*_CONFIG mappings
# ---------------------------------------------------------------------------

DEFAULT_RUN_CONFIG: Dict[str, Any] = default_run()
DEFAULT_EXECUTION_CONFIG: Dict[str, Any] = default_execution()
DEFAULT_CONFIG_BASE: Dict[str, Any] = default_config_base()
DEFAULT_STANDARD_JUDGE_CONFIG: Dict[str, Any] = default_judge_eval()
DEFAULT_STANDARD_TARGET_CONFIG: Dict[str, Any] = default_target()
DEFAULT_GOALS_AND_DATASET_CONFIG: Dict[str, Any] = default_goals_and_dataset()

# Individual scalar re-exports that technique configs reference by name
DEFAULT_OUTPUT_DIR: str = RunConfig.model_fields["output_dir"].default
DEFAULT_RUN_ID: Optional[str] = RunConfig.model_fields["run_id"].default
DEFAULT_START_STEP: int = RunConfig.model_fields["start_step"].default
DEFAULT_BATCH_SIZE: int = ExecutionConfig.model_fields["batch_size"].default
DEFAULT_GOAL_BATCH_SIZE: int = ExecutionConfig.model_fields["goal_batch_size"].default
DEFAULT_GOAL_BATCH_WORKERS: int = ExecutionConfig.model_fields[
    "goal_batch_workers"
].default

DEFAULT_TIMEOUT: int = TargetConfig.model_fields["timeout"].default
DEFAULT_STANDARD_TARGET_MAX_TOKENS: int = TargetConfig.model_fields[
    "max_tokens"
].default
DEFAULT_STANDARD_TARGET_TEMPERATURE: float = TargetConfig.model_fields[
    "temperature"
].default

DEFAULT_BATCH_SIZE_JUDGE: int = JudgeEvalConfig.model_fields["batch_size_judge"].default
DEFAULT_MAX_TOKENS_EVAL: int = JudgeEvalConfig.model_fields["max_tokens_eval"].default
DEFAULT_FILTER_LEN: int = JudgeEvalConfig.model_fields["filter_len"].default
DEFAULT_JUDGE_TIMEOUT: int = JudgeEvalConfig.model_fields["judge_timeout"].default
DEFAULT_JUDGE_TEMPERATURE: float = JudgeEvalConfig.model_fields[
    "judge_temperature"
].default
DEFAULT_MAX_JUDGE_RETRIES: int = JudgeEvalConfig.model_fields[
    "max_judge_retries"
].default

__all__ = [
    "HACKAGENT_API_BASE",
    "HACKAGENT_AGENT_TYPE",
    "DEFAULT_ATTACKER_IDENTIFIER",
    "DEFAULT_JUDGE_IDENTIFIER",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "AttackerConfig",
    "JudgeConfig",
    "JudgeEvalConfig",
    "TargetConfig",
    "GoalsDatasetConfig",
    "RunConfig",
    "ExecutionConfig",
    "ConfigBase",
    "TechniqueConfigBase",
    "JudgeConfigBase",
    "JudgeTechniqueConfigBase",
    "JudgeTargetConfigBase",
    "JudgeTargetTechniqueConfigBase",
    "default_attacker",
    "default_judge",
    "default_judges",
    "default_judge_eval",
    "default_target",
    "default_goals_and_dataset",
    "default_run",
    "default_execution",
    "default_config_base",
    "DEFAULT_RUN_CONFIG",
    "DEFAULT_EXECUTION_CONFIG",
    "DEFAULT_CONFIG_BASE",
    "DEFAULT_STANDARD_JUDGE_CONFIG",
    "DEFAULT_STANDARD_TARGET_CONFIG",
    "DEFAULT_GOALS_AND_DATASET_CONFIG",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_RUN_ID",
    "DEFAULT_START_STEP",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_GOAL_BATCH_SIZE",
    "DEFAULT_GOAL_BATCH_WORKERS",
    "DEFAULT_TIMEOUT",
    "DEFAULT_STANDARD_TARGET_MAX_TOKENS",
    "DEFAULT_STANDARD_TARGET_TEMPERATURE",
    "DEFAULT_BATCH_SIZE_JUDGE",
    "DEFAULT_MAX_TOKENS_EVAL",
    "DEFAULT_FILTER_LEN",
    "DEFAULT_JUDGE_TIMEOUT",
    "DEFAULT_JUDGE_TEMPERATURE",
    "DEFAULT_MAX_JUDGE_RETRIES",
]
