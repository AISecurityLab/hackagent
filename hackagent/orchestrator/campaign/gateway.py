# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The HackAgent LLM gateway as a symbolic model connection.

A stored campaign refers to the gateway as ``connection: {provider: hackagent,
type: OPENAI}`` with no endpoint and no key variable. Whoever executes the run
binds it to its own base URL and key with :func:`bind_gateway`.
"""

from __future__ import annotations

from typing import Optional, TypeVar

from hackagent.core.contracts import AgentType
from hackagent.models.config import ModelConfig
from hackagent.orchestrator.campaign.spec import CampaignSpec

GATEWAY_PROVIDER = "hackagent"
GATEWAY_KEY_ENV = "HACKAGENT_GATEWAY_KEY"

M = TypeVar("M", bound=ModelConfig)


def is_gateway(config: ModelConfig) -> bool:
    """Whether the model is the (possibly unbound) HackAgent gateway."""
    return config.connection.provider == GATEWAY_PROVIDER


def _bind(config: M, endpoint: str) -> M:
    if not is_gateway(config):
        return config
    if config.connection.type != AgentType.OPENAI:
        raise ValueError(
            "The HackAgent gateway is an OPENAI model; "
            f"got type {config.connection.type.value}."
        )
    connection = config.connection.model_copy(
        update={"endpoint": endpoint, "api_key_env": GATEWAY_KEY_ENV}
    )
    return config.model_copy(update={"connection": connection})


def _bind_optional(config: Optional[M], endpoint: str) -> Optional[M]:
    return None if config is None else _bind(config, endpoint)


def spec_models(spec: CampaignSpec) -> list[tuple[str, ModelConfig]]:
    """``(path, model)`` of every model ``spec`` names: the target, attack
    roles (embedders included), judges, guardrails and the goal classifier.
    ``path`` is dotted, e.g. ``attacks.0.roles.attacker``."""
    models: list[tuple[str, ModelConfig]] = [("target", spec.target)]
    for index, attack in enumerate(spec.attacks):
        models.extend(
            (f"attacks.{index}.roles.{role}", config)
            for role, config in attack.roles.items()
        )
    models.extend(
        (f"evaluation.judges.{index}", judge)
        for index, judge in enumerate(spec.evaluation.judges)
    )
    for side in ("before", "after"):
        guardrail = getattr(spec.guardrails, side)
        if guardrail is not None:
            models.append((f"guardrails.{side}", guardrail))
    if spec.dataset.classifier is not None:
        models.append(("dataset.classifier", spec.dataset.classifier))
    return models


def bind_gateway(spec: CampaignSpec, base_url: str) -> CampaignSpec:
    """Point every gateway model of ``spec`` at ``base_url`` and its key variable.

    Raises ``ValueError`` for a gateway model whose type is not ``OPENAI``.
    """
    endpoint = f"{base_url.rstrip('/')}/v1"
    attacks = tuple(
        attack.model_copy(
            update={
                "roles": {
                    role: _bind(config, endpoint)
                    for role, config in attack.roles.items()
                }
            }
        )
        for attack in spec.attacks
    )
    evaluation = spec.evaluation.model_copy(
        update={"judges": tuple(_bind(j, endpoint) for j in spec.evaluation.judges)}
    )
    guardrails = spec.guardrails.model_copy(
        update={
            "before": _bind_optional(spec.guardrails.before, endpoint),
            "after": _bind_optional(spec.guardrails.after, endpoint),
        }
    )
    dataset = spec.dataset.model_copy(
        update={"classifier": _bind_optional(spec.dataset.classifier, endpoint)}
    )
    return spec.model_copy(
        update={
            "target": _bind(spec.target, endpoint),
            "attacks": attacks,
            "evaluation": evaluation,
            "guardrails": guardrails,
            "dataset": dataset,
        }
    )


def key_envs(spec: CampaignSpec) -> set[str]:
    """Every non-gateway API-key variable the spec reads."""
    return {
        m.connection.api_key_env
        for _, m in spec_models(spec)
        if not is_gateway(m) and m.connection.api_key_env
    }


def uses_gateway(spec: CampaignSpec) -> bool:
    """Whether any model of ``spec`` is the gateway."""
    return any(is_gateway(m) for _, m in spec_models(spec))
