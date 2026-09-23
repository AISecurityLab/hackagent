# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Build role-model LLMs, with credentials from :class:`Settings`.

:class:`ModelFactory` implements the ``LLMFactory`` protocol. A role model
uses the key its spec names. The only credential the factory adds is the
HackAgent API key, and only for a spec whose endpoint is the hosted LLM
gateway; it is never sent to any other provider.

:func:`spec_from_config` reads the role-model dicts attack configs still
use (``identifier``, ``endpoint``, ``agent_type``, ``api_key`` given as a
literal or an environment variable name, ...).
"""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping, Optional, Type, TypeVar

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.core.logging import get_logger
from hackagent.core.settings import Mode, Settings
from hackagent.models.client import ModelClient, connect

logger = get_logger(__name__)

SpecT = TypeVar("SpecT", bound=ModelSpec)

#: Provider request parameters a role config may set.
PASSTHROUGH_REQUEST_KEYS = (
    "top_p",
    "frequency_penalty",
    "presence_penalty",
    "seed",
    "stop",
    "reasoning_effort",
    "extra_body",
    "response_format",
    "logit_bias",
    "tools",
    "tool_choice",
    "thinking",
)

#: Config keys that become :class:`ModelSpec` fields rather than ``extra``.
_SPEC_FIELD_KEYS = ("max_tokens", "temperature", "top_p", "thinking")

#: ``agent_metadata`` keys that never override the model's identity.
_IDENTITY_KEYS = frozenset(
    {"api_key", "name", "identifier", "model", "endpoint", "agent_type"}
)


def passthrough_params(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Return the provider request parameters set in ``config``."""
    return {
        key: config[key]
        for key in PASSTHROUGH_REQUEST_KEYS
        if key in config and config[key] is not None
    }


def _agent_type(raw: Any, identifier: str, default: AgentType) -> AgentType:
    if not raw:
        return default
    if isinstance(raw, AgentType):
        return raw
    try:
        return AgentType(str(raw))
    except ValueError:
        logger.warning(
            "Invalid agent_type '%s' for %s, defaulting to %s",
            raw,
            identifier,
            default.value,
        )
        return default


def _split_api_key(value: Any) -> Dict[str, str]:
    """Map a legacy ``api_key`` (literal or env var name) onto spec fields."""
    if not value:
        return {}
    value = str(value)
    if os.environ.get(value):
        return {"api_key_env": value}
    return {"api_key": value}


def spec_from_config(
    config: Mapping[str, Any],
    *,
    spec_type: Type[SpecT] = ModelSpec,  # type: ignore[assignment]
    default_agent_type: AgentType = AgentType.OPENAI_SDK,
) -> SpecT:
    """Build a spec from a role-model config dict.

    A missing or invalid ``agent_type`` becomes ``default_agent_type``.
    ``model`` overrides ``identifier`` as the model name; ``request_timeout``
    is accepted for ``timeout``; keys under ``agent_metadata`` fill any the
    config leaves unset. ``thinking`` is kept only for Ollama, which is the
    only role-model type that has ever honoured it. Fields of ``spec_type``
    beyond :class:`ModelSpec` (e.g. ``system_prompt``) are read too.

    Raises:
        ValueError: If the config has no ``identifier``.
    """
    identifier = config.get("identifier")
    if not identifier:
        raise ValueError(
            "Model config must include an 'identifier' key "
            f"(e.g. 'ollama/llama3'). Got keys: {list(config.keys())}"
        )
    agent_type = _agent_type(
        config.get("agent_type"), str(identifier), default_agent_type
    )
    metadata = dict(config.get("agent_metadata") or {})

    values: Dict[str, Any] = {**passthrough_params(config)}
    for key in ("max_tokens", "temperature"):
        if config.get(key) is not None:
            values[key] = config[key]
    timeout = config.get("timeout", config.get("request_timeout"))
    if timeout is not None:
        values["timeout"] = timeout
    for key, value in metadata.items():
        if key in _IDENTITY_KEYS or value is None:
            continue
        if values.get(key) is None:
            values[key] = value
    if agent_type != AgentType.OLLAMA:
        values.pop("thinking", None)

    fields: Dict[str, Any] = {
        "identifier": str(config.get("model") or identifier),
        "endpoint": config.get("endpoint") or None,
        "agent_type": agent_type,
        **_split_api_key(config.get("api_key") or metadata.get("api_key")),
    }
    for key in ("timeout", *_SPEC_FIELD_KEYS):
        if key in values:
            fields[key] = values.pop(key)
    for name in spec_type.model_fields:
        if name not in ModelSpec.model_fields and config.get(name) is not None:
            fields[name] = config[name]
    fields["extra"] = values
    return spec_type(**fields)


class ModelFactory:
    """Builds the LLM for a role model. Implements ``LLMFactory``."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_gateway(self, endpoint: Optional[str]) -> bool:
        """Whether ``endpoint`` is the hosted LLM gateway of a remote run."""
        if self.settings.mode is not Mode.REMOTE or not endpoint:
            return False
        return endpoint.strip().rstrip("/").startswith(self.settings.base_url)

    def with_credentials(self, spec: SpecT) -> SpecT:
        """Add the gateway key to a gateway spec that names no key."""
        if spec.api_key or spec.api_key_env or not self.is_gateway(spec.endpoint):
            return spec
        return spec.model_copy(update={"api_key": self.settings.api_key})

    def for_role(self, spec: ModelSpec) -> ModelClient:
        return connect(self.with_credentials(spec))


__all__ = [
    "ModelFactory",
    "PASSTHROUGH_REQUEST_KEYS",
    "passthrough_params",
    "spec_from_config",
]
