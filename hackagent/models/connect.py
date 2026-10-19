# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Connect to the model a :class:`ModelSpec` describes, as a :class:`Model`.

This is the native replacement for the legacy ``models.client.connect``: it
returns a :class:`Model` (``acomplete`` → :class:`ModelResponse`) rather than an
envelope-based ``ModelClient``. Native agent types (CLI agents, ADK, web) are
built straight from the spec so their ``extra`` options (binary, url, user_id…)
survive; LiteLLM chat providers go through the same ``build_model`` path as a
campaign, via a spec → :class:`ModelConfig` projection.

No network I/O happens here; an ``api_key_env`` that is not set fails when the
underlying model is built, so configuration errors surface before a run starts.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.models.build import _native_model_classes, build_model
from hackagent.models.config import GenerationSpec, ModelConfig
from hackagent.models.model import Model
from hackagent.models.provider_config import PROVIDER_CONFIGS, get_provider_config

#: Spec fields that project onto :class:`GenerationSpec`.
_GENERATION_FIELDS = frozenset(GenerationSpec.model_fields)


def check_supported(agent_type: AgentType) -> None:
    """Raise ``ValueError`` unless ``agent_type`` can be connected to."""
    native = _native_model_classes()
    if get_provider_config(agent_type) is None and agent_type not in native:
        supported = [*native, *PROVIDER_CONFIGS]
        raise ValueError(
            f"Unsupported agent type: {agent_type}. Supported types: {supported}"
        )


def connect(spec: ModelSpec, *, instance_id: Optional[str] = None) -> Model:
    """Build the :class:`Model` ``spec`` describes. Does no network I/O.

    ``instance_id`` is accepted for call-site compatibility and ignored: a
    native model names its own LiteLLM provider instance.
    """
    _ = instance_id
    check_supported(spec.agent_type)
    native = _native_model_classes()
    if spec.agent_type in native:
        return native[spec.agent_type](spec)
    return build_model(_config_from_spec(spec))


def _config_from_spec(spec: ModelSpec) -> ModelConfig:
    """Project a chat-provider spec onto a :class:`ModelConfig`.

    Only the generation knobs LiteLLM understands are carried; any other
    ``extra`` keys are left out, since the chat path never forwarded unknown
    options as request parameters.
    """
    generation: Dict[str, Any] = {}
    for field in ("max_tokens", "temperature", "top_p", "thinking"):
        value = getattr(spec, field, None)
        if value is not None:
            generation[field] = value
    for key, value in spec.extra.items():
        if key in _GENERATION_FIELDS and value is not None:
            generation[key] = value

    connection: Dict[str, Any] = {
        "provider": "legacy",
        "type": spec.agent_type.value,
        "endpoint": spec.endpoint,
    }
    if spec.timeout:
        connection["timeout"] = spec.timeout
    if spec.api_key_env:
        connection["api_key_env"] = spec.api_key_env
    headers = spec.extra.get("extra_headers")
    if isinstance(headers, dict) and headers:
        connection["headers"] = headers

    return ModelConfig.model_validate(
        {
            "name": spec.identifier,
            "connection": connection,
            "generation": generation,
        }
    )


__all__ = ["check_supported", "connect"]
