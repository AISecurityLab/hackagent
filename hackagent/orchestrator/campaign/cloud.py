# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What a campaign may contain to run on HackAgent cloud.

The cloud worker calls chat APIs over HTTP and nothing else. Every model of
a campaign it runs is either the HackAgent gateway marker, exactly as
:mod:`.gateway` describes it, or a model of a :data:`CLOUD_MODEL_TYPES` type
with only the :data:`CLOUD_OPTIONS` of its type. A model without an endpoint
must name a hosted API: an ``OPENAI`` model a bare OpenAI model name, a
``LITELLM`` model one with a :data:`HOSTED_LITELLM_PREFIXES` prefix. A model
with an endpoint may name no other LiteLLM provider than those of
:data:`ENDPOINT_LITELLM_PREFIXES`, whose clients call that endpoint with the
key the campaign names. Anything not listed here is refused.

Whether an endpoint's address is reachable from the cloud is up to whoever
queues the run: :func:`cloud_issues` resolves no host names.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from hackagent.core.contracts import AgentType
from hackagent.models.completions.litellm import KNOWN_LITELLM_PROVIDER_PREFIXES
from hackagent.models.config import ModelConfig
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

#: LiteLLM model prefixes of hosted APIs, which a ``LITELLM`` model without
#: an endpoint must start with.
HOSTED_LITELLM_PREFIXES = (
    "openai/",
    "anthropic/",
    "openrouter/",
    "gemini/",
    "mistral/",
    "groq/",
    "together_ai/",
    "deepseek/",
    "cohere/",
    "fireworks_ai/",
    "perplexity/",
    "xai/",
)

#: LiteLLM model prefixes a model with an endpoint may start with.
ENDPOINT_LITELLM_PREFIXES = (
    *HOSTED_LITELLM_PREFIXES,
    "hosted_vllm/",
    "vllm/",
    "ollama/",
    "ollama_chat/",
    "lm_studio/",
    "llamafile/",
)


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
    if connection.endpoint:
        reason = _provider_reason(connection.type, config.name)
    else:
        reason = _endpointless_reason(connection.type, config.name)
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
    # Bound, the gateway is an OPENAI model with an endpoint.
    provider = _provider_reason(AgentType.OPENAI, config.name)
    if provider:
        reasons.append(provider)
    return reasons


def _provider_reason(model_type: AgentType, name: str) -> str | None:
    """Why a model of ``model_type`` named ``name`` cannot run in the cloud
    at an endpoint, or None when its LiteLLM provider calls that endpoint.

    ``OPENAI`` and ``OLLAMA`` models get their own provider prefix unless the
    name already starts with a known LiteLLM one (see
    :func:`~hackagent.models.completions.litellm.resolve_litellm_model`); a
    ``LITELLM`` model's prefix is its provider.
    """
    if "/" not in name:
        return None
    prefix = name.split("/", 1)[0] + "/"
    if prefix in ENDPOINT_LITELLM_PREFIXES:
        return None
    if model_type == AgentType.LITELLM or prefix in KNOWN_LITELLM_PROVIDER_PREFIXES:
        return f"{prefix} models can't run in the cloud"
    return None


def _endpointless_reason(model_type: AgentType, name: str) -> str | None:
    """Why a model of ``model_type`` named ``name`` cannot run in the cloud
    without an endpoint, or None when it calls a hosted API."""
    if model_type == AgentType.OLLAMA:
        return "set an endpoint; Ollama models can't run in the cloud without one"
    if "/" not in name:
        if model_type == AgentType.OPENAI:
            return None
        return (
            "set an endpoint, or start the model name with a provider "
            f"({', '.join(HOSTED_LITELLM_PREFIXES)})"
        )
    if model_type == AgentType.LITELLM and name.startswith(HOSTED_LITELLM_PREFIXES):
        return None
    # A provider an endpoint does not help.
    provider = _provider_reason(model_type, name)
    if provider:
        return provider
    prefix = name.split("/", 1)[0] + "/"
    return f"set an endpoint; {prefix} models can't run in the cloud without one"


__all__ = [
    "CLOUD_MODEL_TYPES",
    "CLOUD_OPTIONS",
    "ENDPOINT_LITELLM_PREFIXES",
    "HOSTED_LITELLM_PREFIXES",
    "CloudIssue",
    "cloud_issues",
    "model_cloud_issues",
]
