# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What a campaign may contain to run on HackAgent cloud.

The cloud worker calls chat APIs over HTTP and nothing else. Every model of
a campaign it runs is either the HackAgent gateway marker, exactly as
:mod:`.gateway` describes it, or a model of a :data:`CLOUD_MODEL_TYPES` type
with only the :data:`CLOUD_OPTIONS` of its type. Each model's LiteLLM
provider, as LiteLLM itself infers it from the model string the model is
built with, must be one of :data:`HOSTED_PROVIDERS` without an endpoint, or
of :data:`ENDPOINT_PROVIDERS` with one. Anything not listed here is refused.

Whether an endpoint's address is reachable from the cloud is up to whoever
queues the run: :func:`cloud_issues` resolves no host names.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

from hackagent.core.contracts import AgentType
from hackagent.models.completions.litellm import resolve_litellm_model
from hackagent.models.config import ModelConfig
from hackagent.models.provider_config import get_provider_config
from hackagent.orchestrator.campaign.gateway import is_gateway, spec_models
from hackagent.orchestrator.campaign.spec import CampaignSpec

#: Model types the cloud worker runs: chat APIs it calls over HTTP.
CLOUD_MODEL_TYPES = frozenset({AgentType.OPENAI, AgentType.LITELLM, AgentType.OLLAMA})

#: The ``options`` each cloud model type may set.
CLOUD_OPTIONS: Mapping[AgentType, frozenset[str]] = MappingProxyType(
    {
        AgentType.OPENAI: frozenset(),
        AgentType.LITELLM: frozenset(),
        AgentType.OLLAMA: frozenset({"num_ctx", "top_k"}),
    }
)

#: LiteLLM providers of hosted APIs: all a model without an endpoint may use.
HOSTED_PROVIDERS = frozenset(
    {
        "openai",
        "anthropic",
        "openrouter",
        "gemini",
        "mistral",
        "groq",
        "together_ai",
        "deepseek",
        "cohere",
        "fireworks_ai",
        "perplexity",
        "xai",
    }
)

#: LiteLLM providers a model with an endpoint may use: they call that
#: endpoint with the key the campaign names.
ENDPOINT_PROVIDERS = HOSTED_PROVIDERS | {
    "hosted_vllm",
    "vllm",
    "ollama",
    "ollama_chat",
    "lm_studio",
    "llamafile",
}

UNKNOWN_PROVIDER_REASON = "can't tell which provider this model uses"


@dataclass(frozen=True)
class CloudIssue:
    """Why the cloud cannot run the model at ``path`` of a campaign."""

    path: str
    reason: str


def cloud_issues(spec: CampaignSpec) -> list[CloudIssue]:
    """Why HackAgent cloud cannot run ``spec``; empty when it can."""
    return [
        issue
        for path, config in spec_models(spec)
        for issue in model_cloud_issues(config, path)
    ]


def model_cloud_issues(config: ModelConfig, path: str) -> list[CloudIssue]:
    """Why HackAgent cloud cannot run the model ``config`` found at ``path``
    of a campaign; empty when it can."""
    if is_gateway(config):
        return [CloudIssue(path, reason) for reason in _gateway_reasons(config)]
    connection = config.connection
    if connection.type not in CLOUD_MODEL_TYPES:
        return [
            CloudIssue(
                path, f"model type {connection.type.value} can't run in the cloud"
            )
        ]
    allowed = CLOUD_OPTIONS[connection.type]
    issues = [
        CloudIssue(
            f"{path}.options.{key}", f"option {key!r} can't be used in the cloud"
        )
        for key in config.options
        if key not in allowed
    ]
    reason = _provider_reason(
        connection.type,
        config.name,
        api_base=connection.endpoint or None,
        at_endpoint=bool(connection.endpoint),
    )
    if reason:
        issues.append(CloudIssue(path, reason))
    return issues


def _gateway_reasons(config: ModelConfig) -> list[str]:
    connection = config.connection
    reasons = []
    if connection.type != AgentType.OPENAI:
        reasons.append("the HackAgent gateway must have type OPENAI")
    if connection.endpoint is not None or connection.api_key_env is not None:
        reasons.append("the HackAgent gateway must not set endpoint or api_key_env")
    if config.options:
        reasons.append("the HackAgent gateway takes no options")
    if connection.type == AgentType.OPENAI:
        # Bound, the gateway is an OPENAI model at an endpoint (its own).
        provider = _provider_reason(
            AgentType.OPENAI, config.name, api_base=None, at_endpoint=True
        )
        if provider:
            reasons.append(provider)
    return reasons


def _provider_reason(
    model_type: AgentType, name: str, *, api_base: Optional[str], at_endpoint: bool
) -> Optional[str]:
    """Why the cloud may not call the LiteLLM provider a ``model_type``
    model named ``name`` resolves to, or None when it may."""
    provider = _inferred_provider(model_type, name, api_base)
    if provider is None:
        return UNKNOWN_PROVIDER_REASON
    if at_endpoint:
        return None if provider in ENDPOINT_PROVIDERS else _refused(provider)
    if provider in HOSTED_PROVIDERS:
        return None
    if provider in ENDPOINT_PROVIDERS:
        return _without_endpoint(provider)
    return _refused(provider)


def _refused(provider: str) -> str:
    return f"{provider} models can't run in the cloud"


def _without_endpoint(provider: str) -> str:
    return f"set an endpoint; {provider} models can't run in the cloud without one"


def _inferred_provider(
    model_type: AgentType, name: str, api_base: Optional[str]
) -> Optional[str]:
    """The provider LiteLLM routes the model to, from the model string
    :func:`~hackagent.models.build.build_model` passes it; None when LiteLLM
    cannot tell."""
    import litellm

    provider_config = get_provider_config(model_type)
    assert provider_config is not None  # every CLOUD_MODEL_TYPES type has one
    model = resolve_litellm_model(name, provider_prefix=provider_config.provider_prefix)
    try:
        _, provider, _, _ = litellm.get_llm_provider(model=model, api_base=api_base)
    except Exception:
        return None
    return provider or None


__all__ = [
    "CLOUD_MODEL_TYPES",
    "CLOUD_OPTIONS",
    "ENDPOINT_PROVIDERS",
    "HOSTED_PROVIDERS",
    "UNKNOWN_PROVIDER_REASON",
    "CloudIssue",
    "cloud_issues",
    "model_cloud_issues",
]
