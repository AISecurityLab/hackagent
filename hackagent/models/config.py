# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Model configuration.

:class:`ModelConfig` is the declarative description of a model (name,
transport, sampling) used everywhere a campaign names one: the target, the
attack roles, and the judges. :class:`ModelConnection` and
:class:`ModelGeneration` are the resolved LiteLLM arguments built from it.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    SecretStr,
    model_validator,
)

from hackagent.core.contracts import AgentType

__all__ = [
    "ConnectionSpec",
    "GenerationSpec",
    "ModelConfig",
    "ModelConnection",
    "ModelGeneration",
]


class ConnectionSpec(BaseModel):
    """How to reach a model: which client to use, where it lives, and how to
    authenticate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(
        min_length=1,
        description=(
            "A label for who serves the model (``openai``, ``ollama``, ``vllm``, "
            "``local``…). Informational only: launch tooling reads it, but the "
            "request path uses ``type``."
        ),
    )
    type: AgentType = Field(
        description=(
            "Which client talks to the model. This is the field that matters: it "
            "decides whether HackAgent calls a chat API (``OPENAI``, "
            "``OLLAMA``, ``LITELLM``…) or drives an agent directly "
            "(``CLAUDE_CODE``, ``GOOGLE_ADK``, ``WEB``…)."
        )
    )
    endpoint: Optional[str] = Field(
        default=None,
        description=(
            "Base URL of the model's API, e.g. ``http://localhost:11434`` for "
            "Ollama. Leave unset for local agents such as ``CLAUDE_CODE``, which "
            "run on this machine."
        ),
    )
    api_key_env: Optional[str] = Field(
        default=None,
        description=(
            "Name of the environment variable that holds the API key, e.g. "
            "``OPENAI_API_KEY``. The key itself never goes in the campaign file."
        ),
    )
    headers: Mapping[str, str] = Field(
        default_factory=dict, description="Extra HTTP headers sent with every request."
    )
    timeout: PositiveFloat = Field(
        default=120.0, description="Seconds to wait for one reply before giving up."
    )


class GenerationSpec(BaseModel):
    """Sampling settings applied to every request the model receives. All optional:
    anything left unset uses the provider's own default."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_tokens: Optional[int] = Field(
        default=None, ge=1, description="Longest reply, in tokens."
    )
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Randomness of the reply. ``0`` is the most deterministic.",
    )
    top_p: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Nucleus sampling: only consider the most likely tokens whose "
            "probabilities add up to this value."
        ),
    )
    frequency_penalty: Optional[float] = Field(
        default=None, description="Discourage repeating the same tokens."
    )
    presence_penalty: Optional[float] = Field(
        default=None, description="Encourage introducing new topics."
    )
    seed: Optional[int] = Field(
        default=None,
        description=(
            "Fixed random seed, for repeatable replies where the provider supports it."
        ),
    )
    stop: Optional[str | tuple[str, ...]] = Field(
        default=None,
        description="Text (or list of texts) at which the model stops writing.",
    )
    reasoning_effort: Optional[str] = Field(
        default=None,
        description=(
            "How hard a reasoning model should think (``low``, ``medium``, "
            "``high``), for providers that support it."
        ),
    )
    response_format: Optional[Dict[str, Any]] = Field(
        default=None,
        description='Ask for a structured reply, e.g. ``{"type": "json_object"}``.',
    )
    extra_body: Dict[str, Any] = Field(
        default_factory=dict,
        description="Any other provider-specific request fields, passed through unchanged.",
    )
    thinking: Optional[bool] = Field(
        default=None,
        description="Turn a model's thinking mode on or off. Judges default to off.",
    )


class ModelConfig(BaseModel):
    """A model HackAgent talks to: its name, how to reach it, and how to sample from
    it.

    The same shape describes the target, every attack helper (role), every judge,
    every guardrail and the goal classifier.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(
        min_length=1,
        description=(
            "The model to use, as the provider names it, e.g. ``gpt-4o-mini`` or "
            "``llama3``. Also used to label the model in results."
        ),
    )
    connection: ConnectionSpec = Field(description="How to reach the model.")
    generation: GenerationSpec = Field(
        default_factory=GenerationSpec,
        description="Sampling settings for every request.",
    )
    options: Mapping[str, Any] = Field(
        default_factory=dict,
        description=(
            "Settings specific to one kind of agent that are neither connection nor"
            " sampling, e.g. the ``binary`` path of a CLI agent, ADK's ``user_id``,"
            " or a web target's CSS selectors."
        ),
    )


_PROTECTED_LITELLM_FIELDS = frozenset(
    {
        "api_base",
        "api_key",
        "extra_headers",
        "messages",
        "model",
        "stream",
        "timeout",
    }
)


class ModelGeneration(GenerationSpec):
    """Validated generation defaults shared by model implementations."""

    thinking: Optional[Any] = None
    extra_kwargs: Mapping[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_extra_kwargs(self) -> "ModelGeneration":
        """Keep transport and unsupported streaming options out of generation."""
        invalid = _PROTECTED_LITELLM_FIELDS.intersection(self.extra_kwargs)
        if invalid:
            raise ValueError(
                f"Generation options cannot contain protected fields: {sorted(invalid)}"
            )
        return self

    def to_kwargs(self) -> Dict[str, Any]:
        """Return non-null generation arguments for a completion call."""
        kwargs = self.model_dump(
            exclude={"extra_kwargs"},
            exclude_none=True,
            exclude_defaults=True,
        )
        kwargs.update(self.extra_kwargs)
        return kwargs


class ModelConnection(BaseModel):
    """Validated LiteLLM provider and transport settings."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    api_base: Optional[str] = None
    api_key: Optional[SecretStr] = None
    api_key_env: Optional[str] = None
    timeout: Optional[PositiveFloat] = 120.0
    extra_headers: Mapping[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_api_key_source(self) -> "ModelConnection":
        """Require an unambiguous API-key source."""
        if self.api_key is not None and self.api_key_env is not None:
            raise ValueError("Set either api_key or api_key_env, not both.")
        if self.api_key is not None and not self.api_key.get_secret_value().strip():
            raise ValueError("api_key cannot be empty.")
        if self.api_key_env is not None and not self.api_key_env.strip():
            raise ValueError("api_key_env cannot be empty.")
        return self

    def to_litellm(self) -> Dict[str, Any]:
        """Resolve secrets and return LiteLLM connection arguments."""
        kwargs = self.model_dump(
            exclude={"api_key", "api_key_env", "extra_headers"},
            exclude_none=True,
        )
        if self.api_key is not None:
            kwargs["api_key"] = self.api_key.get_secret_value()
        elif self.api_key_env:
            try:
                api_key = os.environ[self.api_key_env]
            except KeyError as exc:
                raise ValueError(
                    f"Environment variable '{self.api_key_env}' is not set."
                ) from exc
            if not api_key.strip():
                raise ValueError(f"Environment variable '{self.api_key_env}' is empty.")
            kwargs["api_key"] = api_key
        if self.extra_headers:
            kwargs["extra_headers"] = dict(self.extra_headers)
        return kwargs
