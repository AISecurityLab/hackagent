# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The HackAgent LLM gateway as a symbolic model connection.

A stored campaign refers to the gateway as ``connection: {provider: hackagent,
type: OPENAI}`` with no endpoint and no key variable. Whoever executes the run
binds it to its own base URL and key with :func:`bind_gateway`.
"""

from __future__ import annotations

from typing import Optional, TypeVar

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
    connection = config.connection.model_copy(
        update={"endpoint": endpoint, "api_key_env": GATEWAY_KEY_ENV}
    )
    return config.model_copy(update={"connection": connection})


def _bind_optional(config: Optional[M], endpoint: str) -> Optional[M]:
    return None if config is None else _bind(config, endpoint)


def _models(spec: CampaignSpec) -> list[ModelConfig]:
    models: list[ModelConfig] = [spec.target]
    for attack in spec.attacks:
        models.extend(attack.roles.values())
    models.extend(spec.evaluation.judges)
    models.extend(
        m for m in (spec.guardrails.before, spec.guardrails.after) if m is not None
    )
    if spec.dataset.classifier is not None:
        models.append(spec.dataset.classifier)
    return models


def bind_gateway(spec: CampaignSpec, base_url: str) -> CampaignSpec:
    """Point every gateway model of ``spec`` at ``base_url`` and its key variable."""
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
        for m in _models(spec)
        if not is_gateway(m) and m.connection.api_key_env
    }


def uses_gateway(spec: CampaignSpec) -> bool:
    """Whether any model of ``spec`` is the gateway."""
    return any(is_gateway(m) for m in _models(spec))
