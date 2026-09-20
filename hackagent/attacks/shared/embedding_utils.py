# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Embedding-only provider requests shared by retrieval and preflight."""

import os
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import numpy as np

from hackagent.config import DEFAULT_EMBEDDER_ENDPOINT


def normalize_embedding_endpoint(endpoint: str, *, ollama: bool = False) -> str:
    """Return an OpenAI-compatible API base, not a full embeddings URL.

    Ollama's native endpoint spellings select its compatible ``/v1`` API.
    Preserve reverse-proxy prefixes and custom OpenAI-compatible API paths.
    """
    base = endpoint.strip().rstrip("/")
    if ollama:
        for suffix in ("/api/embed", "/api/embeddings", "/v1/embeddings", "/v1"):
            if base.lower().endswith(suffix):
                base = base[: -len(suffix)]
                break
        return f"{base}/v1"
    if base.lower().endswith("/embeddings"):
        return base[: -len("/embeddings")]
    if not urlsplit(base).path:
        return f"{base}/v1"
    return base


def embedding_request_kwargs(config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve provider, endpoint and credentials without consulting storage."""
    model = str(config.get("identifier") or "").strip()
    if not model:
        raise ValueError("An embedding model identifier is required")
    agent_type = config.get("agent_type") or "OPENAI_SDK"
    agent_type = str(getattr(agent_type, "value", agent_type)).upper()
    ollama = agent_type == "OLLAMA" or (
        agent_type == "LITELLM" and model.startswith(("ollama/", "ollama_chat/"))
    )
    endpoint = config.get("endpoint")
    kwargs: Dict[str, Any] = {"model": model, "encoding_format": "float"}
    if ollama:
        for prefix in ("ollama/", "ollama_chat/"):
            if model.startswith(prefix):
                model = model[len(prefix) :]
                break
        kwargs.update(model=model, custom_llm_provider="openai")
        kwargs["api_base"] = normalize_embedding_endpoint(
            str(endpoint or DEFAULT_EMBEDDER_ENDPOINT), ollama=True
        )
    elif agent_type == "OPENAI_SDK":
        # Custom compatible servers own their model namespace. Only the OpenAI
        # service itself treats an optional "openai/" as a routing prefix here.
        if not endpoint or urlsplit(str(endpoint)).hostname == "api.openai.com":
            model = model.removeprefix("openai/")
        kwargs.update(model=model, custom_llm_provider="openai")
        if endpoint:
            kwargs["api_base"] = normalize_embedding_endpoint(str(endpoint))
    elif agent_type == "LITELLM":
        if endpoint:
            kwargs["api_base"] = (
                normalize_embedding_endpoint(str(endpoint))
                if model.startswith("openai/")
                else str(endpoint)
            )
    else:
        raise ValueError(f"Unsupported embedding agent_type: {agent_type}")

    raw_key = config.get("api_key")
    if raw_key:
        key = str(raw_key)
        if key.startswith("${") and key.endswith("}"):
            env_name = key[2:-1]
            key = os.environ.get(env_name, "")
            if not key:
                raise ValueError(
                    f"Embedding API key environment variable {env_name} is unset"
                )
        else:
            key = os.environ.get(key) or key
        kwargs["api_key"] = key
    elif ollama:
        # Ollama's compatible API needs a client key, but has no default auth.
        kwargs["api_key"] = "ollama"
    elif agent_type == "OPENAI_SDK" and os.environ.get("OPENAI_API_KEY"):
        kwargs["api_key"] = os.environ["OPENAI_API_KEY"]
    if config.get("timeout") is not None:
        kwargs["timeout"] = config["timeout"]
    return kwargs


def validate_embedding_vector(
    value: Any, *, dimension: Optional[int] = None
) -> np.ndarray:
    """Require a nonempty, finite, one-dimensional float32 numeric vector."""
    try:
        vector = np.asarray(value)
        if vector.ndim != 1 or not vector.size or vector.dtype.kind not in "fiu":
            raise ValueError("expected a nonempty numeric vector")
        with np.errstate(over="ignore", invalid="ignore"):
            vector = vector.astype(np.float32)
        if not np.isfinite(vector).all():
            raise ValueError("embedding contains nonfinite values")
        if dimension is not None and vector.size != dimension:
            raise ValueError(
                f"embedding dimension changed: expected {dimension}, got {vector.size}"
            )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid embedding vector: {exc}") from exc
    return vector


def extract_embedding_vector(response: Any) -> np.ndarray:
    """Extract and validate the single requested vector from a LiteLLM response."""
    data = (
        response.get("data")
        if isinstance(response, dict)
        else getattr(response, "data", None)
    )
    if not isinstance(data, list) or len(data) != 1:
        raise ValueError("Embedding endpoint returned no single embedding vector")
    item = data[0]
    vector = (
        item.get("embedding")
        if isinstance(item, dict)
        else getattr(item, "embedding", None)
    )
    return validate_embedding_vector(vector)


def request_embedding(config: Dict[str, Any], text: str) -> np.ndarray:
    """Request a real embedding, never chat completions or textual signatures."""
    import litellm

    kwargs = embedding_request_kwargs(config)
    if kwargs.get("custom_llm_provider") == "openai":
        # LiteLLM consumes one routing prefix, even with custom_llm_provider set.
        # Add our own so a server-native ID such as "openai/model" stays intact.
        kwargs["model"] = f"openai/{kwargs['model']}"
    response = litellm.embedding(input=[text], **kwargs)
    return extract_embedding_vector(response)
