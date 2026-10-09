# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Model implementation backed directly by LiteLLM."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence

from hackagent.core.settings import resolve_ollama_base_url

from ..config import ModelConnection, ModelGeneration
from ..model import Model
from ..response import ModelResponse

#: LiteLLM provider prefixes a model string may already carry.
KNOWN_LITELLM_PROVIDER_PREFIXES = (
    "openai/",
    "anthropic/",
    "azure/",
    "bedrock/",
    "vertex_ai/",
    "huggingface/",
    "replicate/",
    "together_ai/",
    "anyscale/",
    "ollama/",
    "ollama_chat/",
    "groq/",
    "mistral/",
    "cohere/",
    "gemini/",
    "deepseek/",
)


def resolve_litellm_model(
    raw_model: str, *, provider_prefix: Optional[str] = None
) -> str:
    """Return the model string to pass to ``litellm.completion``.

    Honors a caller-supplied ``provider_prefix`` while leaving names that
    already carry an explicit LiteLLM provider prefix untouched.
    """
    if not provider_prefix:
        return raw_model
    if raw_model.startswith(KNOWN_LITELLM_PROVIDER_PREFIXES):
        return raw_model
    return f"{provider_prefix}/{raw_model}"


def normalise_ollama_endpoint(endpoint: Optional[str]) -> str:
    """Resolve and normalise an Ollama endpoint URL to its base form."""
    resolved = endpoint or resolve_ollama_base_url()
    resolved = resolved.rstrip("/")
    for suffix in ("/api/generate", "/api/chat", "/api/tags", "/api/show", "/api"):
        if resolved.endswith(suffix):
            resolved = resolved[: -len(suffix)]
            break
    return resolved


class LiteLLMModel(Model):
    """Execute synchronous and asynchronous LiteLLM completions."""

    _RESERVED_OVERRIDES = {
        "api_base",
        "api_key",
        "extra_headers",
        "messages",
        "model",
        "timeout",
    }

    def __init__(
        self,
        model: str,
        *,
        connection: Optional[ModelConnection] = None,
        generation: Optional[ModelGeneration] = None,
    ) -> None:
        self.model = model
        self.connection = connection or ModelConnection()
        self.generation = generation or ModelGeneration()
        self.connection.to_litellm()

    def _litellm_kwargs(
        self,
        messages: Sequence[Mapping[str, Any]],
        overrides: Mapping[str, Any],
    ) -> Dict[str, Any]:
        if overrides.get("stream"):
            raise ValueError(
                "Streaming is not supported by complete(); use a streaming model API."
            )
        invalid = self._RESERVED_OVERRIDES.intersection(overrides)
        if invalid:
            raise ValueError(
                f"Cannot override model connection fields: {sorted(invalid)}"
            )
        kwargs = self.connection.to_litellm()
        kwargs.update(self.generation.to_kwargs())
        kwargs.update(overrides)
        kwargs["model"] = self.model
        kwargs["messages"] = [dict(message) for message in messages]
        return kwargs

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        **overrides: Any,
    ) -> ModelResponse:
        """Run a synchronous LiteLLM completion."""
        import litellm

        kwargs = self._litellm_kwargs(messages, overrides)
        try:
            response = litellm.completion(**kwargs)
        except Exception as exc:
            return ModelResponse.failed(exc)
        return ModelResponse.from_value(response)

    async def acomplete(
        self,
        messages: Sequence[Mapping[str, Any]],
        **overrides: Any,
    ) -> ModelResponse:
        """Run an asynchronous LiteLLM completion."""
        import litellm

        kwargs = self._litellm_kwargs(messages, overrides)
        try:
            response = await litellm.acompletion(**kwargs)
        except Exception as exc:
            return ModelResponse.failed(exc)
        return ModelResponse.from_value(response)
