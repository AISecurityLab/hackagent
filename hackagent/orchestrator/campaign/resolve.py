# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Turn a campaign spec into the objects a run needs.

Resolution loads the goals, creates every model client (target, attack
roles, judges), and constructs each attack from its parameters plus a
traced completion for each of its role models. No request is sent to any
model. The evaluation panel is built here too, and the runner hands it to
iterative attacks as they search.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional

from hackagent.attacks.techniques.iterative import IterativeAttack
from hackagent.attacks.techniques.registry import get_attack_class
from hackagent.attacks.techniques.static.base import StaticAttack
from hackagent.attacks.techniques.trace import traced_completion
from hackagent.core.contracts import Goal
from hackagent.datasets.config import DatasetSpec, load_goals
from hackagent.evaluation.panel import ModelJudge, Panel
from hackagent.models import (
    Model,
    ModelConfig,
    as_completion,
    build_embedder,
    build_model,
)
from hackagent.orchestrator.campaign.spec import (
    AttackSpec,
    CampaignSpec,
    EvaluationSpec,
    GuardrailModelConfig,
    GuardrailsSpec,
)

ModelBuilder = Callable[..., Model]
#: Builds the texts-in, vectors-out callable an embedder role receives.
EmbedderBuilder = Callable[[ModelConfig], Any]
GoalLoader = Callable[[DatasetSpec], list[Goal]]


@dataclass(frozen=True)
class ResolvedAttack:
    """A ready-to-run attack and the configuration it was built from."""

    name: str
    attack: StaticAttack | IterativeAttack
    #: Parameters and role model names, as recorded with the run.
    configuration: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedCampaign:
    spec: CampaignSpec
    goals: tuple[Goal, ...]
    target: Model
    panel: Optional[Panel]
    attacks: tuple[ResolvedAttack, ...]
    classifier: Optional[Model] = None


def resolve_campaign(
    spec: CampaignSpec,
    *,
    build: ModelBuilder = build_model,
    load: GoalLoader = load_goals,
    build_embed: EmbedderBuilder = build_embedder,
) -> ResolvedCampaign:
    """Instantiate everything ``spec`` describes."""
    retries = spec.execution.retries
    return ResolvedCampaign(
        spec=spec,
        goals=tuple(load(spec.dataset)),
        target=_guarded(
            build(spec.target, retries=retries.target),
            spec.guardrails,
            build,
            retries.target,
        ),
        panel=build_panel(spec.evaluation, build, retries=retries.judges),
        attacks=tuple(
            resolve_attack(
                attack, build, retries=retries.roles, build_embed=build_embed
            )
            for attack in spec.attacks
        ),
        classifier=(
            build(spec.dataset.classifier, retries=retries.roles)
            if spec.dataset.classifier is not None
            else None
        ),
    )


def resolve_attack(
    spec: AttackSpec,
    build: ModelBuilder,
    *,
    retries: int = 0,
    build_embed: EmbedderBuilder = build_embedder,
) -> ResolvedAttack:
    """Construct an attack, binding each role model to the shape it declares.

    A completion role receives a traced chat callable; an embedder role
    receives a texts-in, vectors-out callable from the embeddings endpoint.
    """
    attack_type = get_attack_class(spec.name)
    params_type = attack_type.params_type
    role_names = params_type.role_names()
    embedder_roles = params_type.embedder_roles()

    misplaced = role_names & spec.parameters.keys()
    if misplaced:
        raise ValueError(
            f"{spec.name}: configure {', '.join(sorted(misplaced))} under 'roles', not 'parameters'."
        )
    unknown = spec.roles.keys() - role_names
    if unknown:
        expected = ", ".join(sorted(role_names)) or "none"
        raise ValueError(
            f"{spec.name}: unknown roles {', '.join(sorted(unknown))} (expected: {expected})."
        )
    missing = params_type.REQUIRED_ROLES - spec.roles.keys()
    if missing:
        raise ValueError(
            f"{spec.name}: missing required role(s) {', '.join(sorted(missing))}; "
            "configure each under the attack's 'roles'."
        )

    roles = {
        role: (
            build_embed(model)
            if role in embedder_roles
            else traced_completion(role, as_completion(build(model, retries=retries)))
        )
        for role, model in spec.roles.items()
    }
    try:
        params = params_type(**spec.parameters, **roles)
        attack = attack_type(params)
    except ValueError as exc:
        raise ValueError(f"{spec.name}: {exc}") from exc
    return ResolvedAttack(
        name=spec.name,
        attack=attack,
        configuration={
            "parameters": params.model_dump(mode="json"),
            "roles": {role: _model_label(model) for role, model in spec.roles.items()},
        },
    )


def _guarded(
    target: Model,
    guardrails: "GuardrailsSpec",
    build: ModelBuilder,
    retries: int,
) -> Model:
    """Wrap the target in its before/after guardrail classifiers, if any.

    The classifiers are ordinary models built the same way as the target;
    a blocked prompt or reply comes back as a response that is not ``ok``,
    which the runner records as the attack being stopped by a defence.
    """
    if not guardrails.active:
        return target
    from hackagent.models.guardrail import GuardedModel, ModelGuardrail

    def classifier(
        spec: "Optional[GuardrailModelConfig]",
    ) -> "Optional[ModelGuardrail]":
        if spec is None:
            return None
        return ModelGuardrail(
            build(spec, retries=retries), system_prompt=spec.system_prompt
        )

    return GuardedModel(
        target,
        before=classifier(guardrails.before),
        after=classifier(guardrails.after),
    )


def build_panel(
    spec: EvaluationSpec,
    build: ModelBuilder,
    *,
    retries: int = 0,
) -> Optional[Panel]:
    """Bind every judge to its model. ``None`` when no judge is configured."""
    if not spec.judges:
        return None
    kinds = [judge.scoring.type for judge in spec.judges]
    judges = []
    for index, judge in enumerate(spec.judges):
        kind = judge.scoring.type
        # Tracking keys vote columns by judge name: keep the bare type when
        # it is unique, and disambiguate repeated types by model and index.
        name = kind if kinds.count(kind) == 1 else f"{kind}:{judge.name}#{index + 1}"
        judges.append(
            ModelJudge(
                kind,
                build(judge, retries=retries),
                name=name,
                system_prompt=judge.scoring.system_prompt,
                threshold=spec.threshold,
            )
        )
    return Panel(judges, aggregation=spec.aggregation, threshold=spec.threshold)


def _model_label(model: ModelConfig) -> dict[str, Any]:
    return {
        "name": model.name,
        "type": model.connection.type.value,
        "endpoint": model.connection.endpoint,
    }


__all__ = [
    "ResolvedAttack",
    "ResolvedCampaign",
    "build_panel",
    "resolve_attack",
    "resolve_campaign",
]
