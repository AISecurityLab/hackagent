# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Build a :class:`Model` from a :class:`ModelConfig`."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Mapping

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.models.completions import LiteLLMModel
from hackagent.models.config import ModelConfig, ModelConnection, ModelGeneration
from hackagent.models.completions.litellm import (
    normalise_ollama_endpoint,
    resolve_litellm_model,
)
from hackagent.models.model import Model
from hackagent.models.provider_config import get_provider_config
from hackagent.models.retry import RetryingModel


class ModelCallError(RuntimeError):
    """A model gave no usable reply."""


def build_model(config: ModelConfig, *, retries: int = 0) -> Model:
    """Create the model client described by ``config``.

    No request is sent. An ``api_key_env`` that is not set fails here, so
    configuration errors surface before a run starts.
    """
    if retries < 0:
        raise ValueError("retries cannot be negative")
    provider = get_provider_config(config.connection.type)
    model = _adapter_model(config) if provider is None else _litellm_model(config)
    return RetryingModel(model, retries) if retries else model


def as_completion(
    model: Model,
) -> Callable[[Sequence[Mapping[str, Any]]], Awaitable[str]]:
    """Expose ``model`` as the text-in, text-out callable attacks depend on."""

    async def complete(messages: Sequence[Mapping[str, Any]]) -> str:
        response = await model.acomplete(messages)
        if response.error is not None:
            raise ModelCallError(response.error.message)
        if response.guardrail is not None:
            raise ModelCallError(f"blocked by guardrail: {response.guardrail.message}")
        return response.text

    return complete


def build_embedder(
    config: ModelConfig,
) -> Callable[[Sequence[str]], Awaitable[list[list[float]]]]:
    """Expose ``config`` as the texts-in, vectors-out callable retrieval needs.

    The embeddings API is a different endpoint from chat, so this does not
    go through :class:`Model`; it builds a LiteLLM embedding request from the
    same connection fields and runs the blocking call off the event loop.
    """
    from hackagent.models.embeddings import (
        embedding_request_kwargs,
        extract_embedding_vector,
    )

    spec = {
        "identifier": config.name,
        "endpoint": config.connection.endpoint,
        "agent_type": config.connection.type.value,
        "api_key_env": config.connection.api_key_env,
        "timeout": config.connection.timeout,
    }
    kwargs = embedding_request_kwargs(spec)
    if kwargs.get("custom_llm_provider") == "openai":
        kwargs["model"] = f"openai/{kwargs['model']}"

    def _embed(texts: Sequence[str]) -> list[list[float]]:
        import litellm

        vectors: list[list[float]] = []
        for text in texts:
            response = litellm.embedding(input=[text], **kwargs)
            vectors.append([float(x) for x in extract_embedding_vector(response)])
        return vectors

    async def embed(texts: Sequence[str]) -> list[list[float]]:
        batch = list(texts)
        if not batch:
            return []
        return await asyncio.to_thread(_embed, batch)

    return embed


def _litellm_model(config: ModelConfig) -> LiteLLMModel:
    connection = config.connection
    provider = get_provider_config(connection.type)
    assert provider is not None
    endpoint = connection.endpoint
    api_key = None
    api_key_env = connection.api_key_env
    if connection.type == AgentType.OLLAMA:
        endpoint = normalise_ollama_endpoint(endpoint)
        api_key_env = None
    elif connection.type == AgentType.OPENAI_SDK and endpoint and not api_key_env:
        # Self-hosted OpenAI-compatible servers accept any key, but the
        # client refuses to send a request without one.
        api_key = "not-needed"

    generation = config.generation
    return LiteLLMModel(
        resolve_litellm_model(config.name, provider_prefix=provider.provider_prefix),
        connection=ModelConnection(
            api_base=endpoint,
            api_key=api_key,
            api_key_env=api_key_env,
            timeout=connection.timeout,
            extra_headers=dict(connection.headers),
        ),
        generation=ModelGeneration(
            **generation.model_dump(exclude={"thinking"}),
            extra_kwargs=provider.thinking_translator(
                generation.thinking, model_name=config.name
            ),
        ),
    )


def _native_model_classes() -> dict:
    """Agent types with a native :class:`Model` backend of their own."""
    from hackagent.models.completions import (
        ADKModel,
        ClaudeCodeModel,
        CodexModel,
        HermesModel,
        WebModel,
    )

    return {
        AgentType.CLAUDE_CODE: ClaudeCodeModel,
        AgentType.CODEX: CodexModel,
        AgentType.HERMES: HermesModel,
        AgentType.GOOGLE_ADK: ADKModel,
        AgentType.WEB: WebModel,
    }


def _adapter_model(config: ModelConfig) -> Model:
    """Agent types LiteLLM cannot speak (CLI agents, ADK, web…), each with a
    native :class:`Model` backend of its own."""
    native_models = _native_model_classes()
    agent_type = config.connection.type
    if agent_type not in native_models:
        supported = sorted(t.value for t in native_models)
        raise ValueError(
            f"Unsupported agent type: {agent_type}. "
            f"Native backends: {supported}, plus the LiteLLM chat providers."
        )
    return native_models[agent_type](_adapter_spec(config))


def _adapter_spec(config: ModelConfig) -> ModelSpec:
    """The :class:`ModelSpec` a non-LiteLLM backend is built from."""
    generation = config.generation.model_dump(exclude_none=True, exclude_defaults=True)
    fields = {
        key: generation.pop(key)
        for key in ("max_tokens", "temperature", "top_p", "thinking")
        if key in generation
    }
    if config.connection.headers:
        generation["extra_headers"] = dict(config.connection.headers)
    # Backend-specific options (binary, user_id, selectors…) ride along in
    # ``extra`` beside the generation knobs.
    extra = {**generation, **dict(config.options)}
    return ModelSpec(
        identifier=config.name,
        endpoint=config.connection.endpoint,
        agent_type=config.connection.type,
        api_key_env=config.connection.api_key_env,
        timeout=config.connection.timeout,
        extra=extra,
        **fields,
    )


__all__ = ["ModelCallError", "as_completion", "build_embedder", "build_model"]
