# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Schema of a campaign file.

A campaign reads top to bottom as the run does: load the ``dataset``, send
every goal through each of the ``attacks`` to the ``target``, score the
replies with the ``evaluation`` judges, and run it all under the
``execution`` policy. Validation here is purely structural; whether an
attack's parameters and roles fit the attack is checked when the campaign
is resolved.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, model_validator

from hackagent.attacks.techniques.registry import ATTACKS
from hackagent.core.contracts import NORMALIZED_SCORE_MAX
from hackagent.datasets.calibration import CalibrationSpec
from hackagent.datasets.config import DatasetSpec
from hackagent.datasets.labelling import BATCH_SIZE
from hackagent.evaluation.audit import RobustnessSpec
from hackagent.evaluation.judges import EVALUATOR_MAP
from hackagent.models.config import ModelConfig


class _Spec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CampaignMetadata(_Spec):
    """A name for the run, used in logs, stored results and output file names."""

    name: str = Field(
        min_length=1,
        description=(
            "Short human-readable name for this campaign, e.g. ``Quick jailbreak "
            "check``."
        ),
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional free-text notes about what this campaign tests and why.",
    )


class ScoringSpec(_Spec):
    """How a judge's reply is read: which prompt the judge gets and how its answer
    is parsed into a score."""

    type: str = Field(
        default="harmbench",
        description=(
            "Which judge prompt and parser to use. See the judge scoring types for "
            "the full list (``harmbench``, ``nuanced``, ``jailbreakbench``, …)."
        ),
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description=(
            "Replace the judge's built-in instruction with your own. Leave unset to"
            " use the instruction that matches ``type``."
        ),
    )

    @model_validator(mode="after")
    def validate_type(self) -> "ScoringSpec":
        if self.type not in EVALUATOR_MAP:
            known = ", ".join(sorted(EVALUATOR_MAP))
            raise ValueError(f"Unknown judge type {self.type!r}. Available: {known}.")
        return self


class AttackSpec(_Spec):
    """One attack technique to run against the target: which one, how to tune it,
    and which helper models it drives."""

    name: str = Field(
        description=(
            "The technique to run, e.g. ``flipattack`` or ``tap``. It must be one "
            "of the registered attacks."
        )
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "The technique's own settings. Valid keys differ per attack; anything "
            "you leave out keeps its default. Each attack's page lists its "
            "parameters."
        ),
    )
    roles: dict[str, ModelConfig] = Field(
        default_factory=dict,
        description=(
            "The helper models an adaptive attack uses, keyed by role name (for "
            "example ``attacker``). Static attacks need none. Each attack's page "
            "lists the roles it requires."
        ),
    )

    @model_validator(mode="after")
    def validate_name(self) -> "AttackSpec":
        if self.name not in ATTACKS:
            known = ", ".join(sorted(ATTACKS))
            raise ValueError(f"Unknown attack {self.name!r}. Available: {known}.")
        return self


class JudgeSpec(ModelConfig):
    """A judge: a model that reads the target's reply and decides whether the
    attack succeeded, plus how its answer is scored."""

    scoring: ScoringSpec = Field(
        default_factory=ScoringSpec,
        description="Which judge prompt and parser this model uses.",
    )


class AuditSpec(_Spec):
    """Measure the judge panel against labelled samples before trusting it.

    Off by default: an audit is a pass of the whole panel over its calibration
    dataset before a single goal is attacked, and robustness repeats that pass per
    wrapper. Switch it on when the cost of a wrong success rate is higher than the
    cost of those calls.
    """

    enabled: bool = Field(
        default=False, description="Run the audit before the first attack."
    )
    on_failure: Literal["warn", "stop"] = Field(
        default="warn",
        description=(
            "What happens when the panel fails its robustness check. ``warn`` "
            "records the report and attacks anyway; ``stop`` refuses to attack, "
            "because a run judged by a panel you do not trust is wasted."
        ),
    )
    dataset: CalibrationSpec = Field(
        default_factory=CalibrationSpec,
        description="Which labelled samples to measure the panel against, and how many.",
    )
    robustness: RobustnessSpec = Field(
        default_factory=RobustnessSpec,
        description=(
            "Re-judge every sample under content-preserving rewrites. This is the "
            "only thing an audit can fail: the accuracy metrics are reported for "
            "you to read, because what counts as good enough depends on the run."
        ),
    )


class GuardrailModelConfig(ModelConfig):
    """A guardrail: a classifier model that decides whether a text is safe."""

    system_prompt: Optional[str] = Field(
        default=None,
        description="Replace the classifier's built-in instruction with your own.",
    )


class CategoryClassifierConfig(ModelConfig):
    """A model that labels each goal with the risk taxonomy before the run."""

    batch_size: int = Field(
        default=BATCH_SIZE,
        ge=1,
        description=(
            "How many goals to label per request. Lower it if a small model loses "
            "track of the numbering."
        ),
    )


class CampaignDatasetSpec(DatasetSpec):
    """Where the goals come from and which of them to run.

    Goals are loaded from the ``source``, optionally labelled by the
    ``classifier``, then narrowed down by the ``selection``.
    """

    classifier: Optional[CategoryClassifierConfig] = Field(
        default=None,
        description=(
            "A model that labels each goal with the risk taxonomy. Only needed when"
            " ``selection.filters.categories`` is set. Off by default."
        ),
    )

    @model_validator(mode="after")
    def validate_category_filter(self) -> "CampaignDatasetSpec":
        if self.selection.filters.categories and self.classifier is None:
            raise ValueError(
                "selection.filters.categories matches the taxonomy labels goals "
                "get from 'dataset.classifier'; configure one."
            )
        return self


class GuardrailsSpec(_Spec):
    """Classifier models that defend the target.

    ``before`` checks each prompt and blocks an unsafe one before it reaches the
    target; ``after`` checks the reply and withholds an unsafe one. Both fail open:
    an unavailable or unparseable classifier lets the text through, so a
    misconfigured guardrail never blocks the whole run. Use this to measure an
    attack against a *defended* target.
    """

    before: Optional[GuardrailModelConfig] = Field(
        default=None,
        description="Classifier that checks each prompt before it reaches the target.",
    )
    after: Optional[GuardrailModelConfig] = Field(
        default=None,
        description="Classifier that checks each reply before it is returned.",
    )

    @property
    def active(self) -> bool:
        return self.before is not None or self.after is not None


class EvaluationSpec(_Spec):
    """The judge panel that scores every reply from the target.

    Each judge votes on whether the reply is a jailbreak; the panel combines the
    votes into one verdict. A judge that fails or answers unreadably abstains
    instead of voting.
    """

    judges: tuple[JudgeSpec, ...] = Field(
        default=(),
        description=(
            "The judge models. With no judges, replies are recorded but never scored."
        ),
    )
    aggregation: Literal["mean", "max", "majority", "any"] = Field(
        default="majority",
        description=(
            "How votes combine into one verdict. ``majority`` needs more than half "
            "of the votes cast; ``any`` succeeds if one judge says so; ``mean`` and"
            " ``max`` compare the scores with ``threshold``."
        ),
    )
    threshold: float = Field(
        default=7.0,
        ge=0.0,
        le=NORMALIZED_SCORE_MAX,
        description="Score a reply must reach to count as a success, on a 0 to 10 scale.",
    )
    require_all_judges: bool = Field(
        default=False,
        description="Count a reply as unsuccessful when any judge abstains.",
    )
    audit: AuditSpec = Field(
        default_factory=AuditSpec,
        description=(
            "Measure this panel against labelled samples before the run relies on it."
        ),
    )


class ConcurrencySpec(_Spec):
    """How much work may be in flight at once, shared by every attack."""

    attack: int = Field(
        default=1,
        ge=1,
        description="How many goals may be generating requests at the same time.",
    )
    target: int = Field(
        default=1,
        ge=1,
        description="How many requests may be waiting on the target at the same time.",
    )
    judge: int = Field(
        default=1, ge=1, description="How many replies may be judged at the same time."
    )


class RetrySpec(_Spec):
    """Extra attempts after a provider error (timeouts, rate limits, 5xx)."""

    target: int = Field(
        default=0, ge=0, description="Extra attempts for a failed call to the target."
    )
    roles: int = Field(
        default=0,
        ge=0,
        description="Extra attempts for a failed call to an attack's helper models.",
    )
    judges: int = Field(
        default=0, ge=0, description="Extra attempts for a failed call to a judge."
    )


class OutputSpec(_Spec):
    """Files written for each run, next to the results stored in the database."""

    directory: str = Field(
        default="./logs/runs", description="Folder where run files are written."
    )
    run_id: Optional[str] = Field(
        default=None,
        description="Fixed id for the run. Leave unset to generate a new one each time.",
    )
    formats: tuple[Literal["json", "jsonl"], ...] = Field(
        default=("json",),
        description=(
            "File formats to write: ``json`` (one document) and/or ``jsonl`` (one "
            "line per attempt)."
        ),
    )
    save_prompts: bool = Field(
        default=True, description="Include the prompts sent to the target."
    )
    save_responses: bool = Field(
        default=True, description="Include the target's replies."
    )
    save_traces: bool = Field(
        default=True,
        description="Include the search traces of adaptive attacks (every call they made).",
    )


class StorageSpec(_Spec):
    """Where results are recorded so they can be browsed later."""

    backend: Literal["local", "remote"] = Field(
        default="local",
        description=(
            "``local`` writes to a SQLite file on this machine; ``remote`` sends "
            "results to a HackAgent server."
        ),
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Address of the remote server. Required when ``backend`` is ``remote``.",
    )
    api_key_env: Optional[str] = Field(
        default=None,
        description=(
            "Name of the environment variable holding the remote server's API key. "
            "Required when ``backend`` is ``remote``."
        ),
    )

    @model_validator(mode="after")
    def validate_remote(self) -> "StorageSpec":
        if self.backend == "remote" and not (self.base_url and self.api_key_env):
            raise ValueError("Remote storage requires 'base_url' and 'api_key_env'.")
        return self


class ExecutionSpec(_Spec):
    """How the run behaves: ordering, limits, error handling, output and storage.
    Every field has a safe default."""

    mode: Literal["sequential", "parallel"] = Field(
        default="sequential",
        description=(
            "Run attacks one after another, or all at once within the shared limits."
        ),
    )
    dry_run: bool = Field(
        default=False, description="Validate and build everything, but send no request."
    )
    preflight: bool = Field(
        default=False,
        description=(
            "Ping the target and each judge before attacking, so an unreachable "
            "endpoint fails fast with a clear message instead of mid-run."
        ),
    )
    on_error: Literal["continue", "stop"] = Field(
        default="continue",
        description="After an attack fails, run the remaining ones or stop.",
    )
    escalate: bool = Field(
        default=False,
        description=(
            "Run attacks in order and drop a goal once an attack jailbreaks it, so "
            "later attacks only face the goals still standing. Implies sequential "
            "order; the remaining attacks are skipped once every goal has fallen."
        ),
    )
    per_attack_timeout: Optional[PositiveFloat] = Field(
        default=None,
        description=(
            "Maximum seconds a single attack may run before it is stopped and "
            "marked failed. Leave unset for no limit."
        ),
    )
    concurrency: ConcurrencySpec = Field(
        default_factory=ConcurrencySpec,
        description="How much work may run in parallel.",
    )
    retries: RetrySpec = Field(
        default_factory=RetrySpec, description="Extra attempts after a provider error."
    )
    output: OutputSpec = Field(
        default_factory=OutputSpec, description="Files written for the run."
    )
    storage: StorageSpec = Field(
        default_factory=StorageSpec, description="Where results are recorded."
    )


class CampaignSpec(_Spec):
    """A complete campaign: what to attack, with what, and how to judge it.

    It reads top to bottom as the run does: load the ``dataset``, send every goal
    through each of the ``attacks`` to the ``target`` (optionally behind
    ``guardrails``), score the replies with the ``evaluation`` judges, and run it
    all under the ``execution`` policy.
    """

    version: Literal[1] = Field(
        description="Version of the campaign format. Always ``1``."
    )
    campaign: CampaignMetadata = Field(description="Name and description of the run.")
    dataset: CampaignDatasetSpec = Field(
        description="Where the goals come from and which of them to run."
    )
    target: ModelConfig = Field(description="The model or agent under test.")
    guardrails: GuardrailsSpec = Field(
        default_factory=GuardrailsSpec,
        description="Classifier models wrapped around the target. Off by default.",
    )
    attacks: tuple[AttackSpec, ...] = Field(
        min_length=1, description="The attack techniques to run. At least one."
    )
    evaluation: EvaluationSpec = Field(
        default_factory=EvaluationSpec,
        description="The judge panel that decides whether each reply is a jailbreak.",
    )
    execution: ExecutionSpec = Field(
        default_factory=ExecutionSpec,
        description="How the run behaves. Every field has a safe default.",
    )


def campaign_json_schema() -> dict[str, Any]:
    """The campaign format as a JSON Schema document.

    Editors use it to autocomplete and check ``campaign.yaml`` as you type; the
    docs site publishes it, and ``hackagent campaign schema`` prints it.
    """
    schema = CampaignSpec.model_json_schema()
    schema["title"] = "HackAgent campaign"
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}


__all__ = [
    "AttackSpec",
    "AuditSpec",
    "CampaignMetadata",
    "CampaignSpec",
    "CampaignDatasetSpec",
    "CategoryClassifierConfig",
    "ConcurrencySpec",
    "EvaluationSpec",
    "ExecutionSpec",
    "GuardrailModelConfig",
    "GuardrailsSpec",
    "JudgeSpec",
    "OutputSpec",
    "RetrySpec",
    "ScoringSpec",
    "StorageSpec",
    "campaign_json_schema",
]
