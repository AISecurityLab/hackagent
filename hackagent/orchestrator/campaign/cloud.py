# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What a campaign may contain to run on HackAgent cloud.

The cloud worker calls chat APIs over HTTP and nothing else. Every model of
a campaign it runs is either the HackAgent gateway marker, exactly as
:mod:`.gateway` describes it, with no headers and only the
:data:`GATEWAY_GENERATION` settings, or a model of a
:data:`CLOUD_MODEL_TYPES` type with only the :data:`CLOUD_OPTIONS` of its
type. Each model's LiteLLM provider, as LiteLLM itself infers it from the
model string the model is built with, must be one of
:data:`HOSTED_PROVIDERS` without an endpoint, or of
:data:`ENDPOINT_PROVIDERS` with one, and the variable its key is read from
must pass :func:`secret_name_reason`. Goals come from a preset or the
campaign itself; no technique parameter may carry code (see
:meth:`~hackagent.attacks.techniques.contract.AttackParams.cloud_parameter_issues`),
no setting may name a path, and ``trust_remote_code`` is never set.
Anything not listed here is refused.

Whether an endpoint's address is reachable from the cloud is up to whoever
queues the run: :func:`cloud_issues` resolves no host names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterator, Mapping, Optional

from hackagent.attacks.techniques.registry import get_attack_class
from hackagent.core.contracts import AgentType
from hackagent.datasets.calibration import CalibrationSpec
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
    "ollama",
    "ollama_chat",
    "lm_studio",
    "llamafile",
}

UNKNOWN_PROVIDER_REASON = "can't tell which provider this model uses"

#: The ``generation`` settings the HackAgent gateway marker may set.
GATEWAY_GENERATION = frozenset({"temperature", "top_p", "max_tokens"})

#: Where a cloud run's goals may come from: a built-in preset, or goals
#: written in the campaign.
CLOUD_DATASET_SOURCES = frozenset({"preset", "inline"})

#: What a variable a cloud run reads a secret from may be called.
SECRET_NAME = re.compile(r"[A-Z][A-Z0-9_]*(?:API_KEY|_KEY|_TOKEN)")
#: Prefixes of the variables HackAgent and its libraries read settings from.
RESERVED_SECRET_PREFIXES = (
    "HACKAGENT_",
    "HF_",
    "LITELLM_",
    "SSL_",
    "REQUESTS_",
    "CURL_",
    "PYTHON",
    "XDG_",
)
#: Variables the system reads.
RESERVED_SECRET_NAMES = frozenset({"PATH", "HOME", "LD_PRELOAD", "LD_LIBRARY_PATH"})
#: Words of variables that name an address rather than a secret.
RESERVED_SECRET_WORDS = ("PROXY", "BASE", "URL", "ENDPOINT", "HOST")


@dataclass(frozen=True)
class CloudIssue:
    """Why the cloud cannot run the model at ``path`` of a campaign."""

    path: str
    reason: str


def cloud_issues(spec: CampaignSpec) -> list[CloudIssue]:
    """Why HackAgent cloud cannot run ``spec``; empty when it can."""
    issues = [
        issue
        for path, config in spec_models(spec)
        for issue in model_cloud_issues(config, path)
    ]
    issues.extend(_attack_issues(spec))
    issues.extend(_setting_issues(spec))
    issues.extend(
        CloudIssue(path, "trust_remote_code can't be used in the cloud")
        for path in _key_paths(spec.model_dump(mode="json"), "trust_remote_code")
    )
    return issues


def secret_name_reason(name: str) -> Optional[str]:
    """Why a cloud run may not read a secret from the variable ``name``, or
    None when it may: an upper-case name ending in ``API_KEY``, ``_KEY`` or
    ``_TOKEN`` that no library reads a setting or an address from."""
    if not SECRET_NAME.fullmatch(name):
        return (
            "a secret's variable must be upper case and end in API_KEY, _KEY or _TOKEN"
        )
    if (
        name in RESERVED_SECRET_NAMES
        or name.startswith(RESERVED_SECRET_PREFIXES)
        or any(word in name for word in RESERVED_SECRET_WORDS)
    ):
        return f"{name} can't hold a secret in the cloud"
    return None


def model_cloud_issues(config: ModelConfig, path: str) -> list[CloudIssue]:
    """Why HackAgent cloud cannot run the model ``config`` found at ``path``
    of a campaign; empty when it can."""
    if is_gateway(config):
        return _gateway_issues(config, path)
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
    if connection.api_key_env is not None:
        reason = secret_name_reason(connection.api_key_env)
        if reason:
            issues.append(CloudIssue(f"{path}.connection.api_key_env", reason))
    reason = _provider_reason(
        connection.type,
        config.name,
        api_base=connection.endpoint or None,
        at_endpoint=bool(connection.endpoint),
    )
    if reason:
        issues.append(CloudIssue(path, reason))
    return issues


def _gateway_issues(config: ModelConfig, path: str) -> list[CloudIssue]:
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
    issues = [CloudIssue(path, reason) for reason in reasons]
    if connection.headers:
        issues.append(
            CloudIssue(
                f"{path}.connection.headers", "the HackAgent gateway takes no headers"
            )
        )
    issues.extend(
        CloudIssue(
            f"{path}.generation.{key}",
            "the HackAgent gateway takes only temperature, top_p and max_tokens",
        )
        for key in config.generation.model_dump(exclude_defaults=True)
        if key not in GATEWAY_GENERATION
    )
    return issues


def _attack_issues(spec: CampaignSpec) -> Iterator[CloudIssue]:
    """Technique parameters a cloud run may not use."""
    for index, attack in enumerate(spec.attacks):
        params_type = get_attack_class(attack.name).params_type
        for name, reason in params_type.cloud_parameter_issues(
            attack.parameters
        ).items():
            yield CloudIssue(f"attacks.{index}.parameters.{name}", reason)


def _setting_issues(spec: CampaignSpec) -> Iterator[CloudIssue]:
    """Goals from anywhere but a preset or the campaign, and settings that
    name a path on the machine or a repository revision."""
    source = spec.dataset.source.type
    if source not in CLOUD_DATASET_SOURCES:
        yield CloudIssue(
            "dataset.source",
            f"dataset source {source!r} can't be used in the cloud; use a preset "
            "or inline goals",
        )
    calibration = spec.evaluation.audit.dataset
    for name in ("cache_dir", "revision"):
        if getattr(calibration, name) != CalibrationSpec.model_fields[name].default:
            yield CloudIssue(
                f"evaluation.audit.dataset.{name}", f"{name} can't be set in the cloud"
            )
    if spec.execution.output.run_id is not None:
        yield CloudIssue("execution.output.run_id", "run_id can't be set in the cloud")


def _key_paths(data: Any, name: str, path: str = "") -> Iterator[str]:
    """Dotted paths of every ``name`` key in ``data``, at any depth."""
    if isinstance(data, dict):
        for key, value in data.items():
            child = f"{path}.{key}" if path else str(key)
            if key == name:
                yield child
            yield from _key_paths(value, name, child)
    elif isinstance(data, list):
        for index, value in enumerate(data):
            yield from _key_paths(
                value, name, f"{path}.{index}" if path else str(index)
            )


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
    "CLOUD_DATASET_SOURCES",
    "CLOUD_MODEL_TYPES",
    "CLOUD_OPTIONS",
    "ENDPOINT_PROVIDERS",
    "GATEWAY_GENERATION",
    "HOSTED_PROVIDERS",
    "UNKNOWN_PROVIDER_REASON",
    "CloudIssue",
    "cloud_issues",
    "model_cloud_issues",
    "secret_name_reason",
]
