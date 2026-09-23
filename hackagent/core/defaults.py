# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Default model identifiers and endpoints for the attacker, judge and helper roles.

Only plain values live here, so every package can import them. Runtime
resolution (API key, base URL, database path) belongs to
:mod:`hackagent.core.settings`.

The endpoint defaults below are computed from the environment when this
module is first imported.
"""

from __future__ import annotations

from hackagent.core.settings import (
    resolve_ollama_base_url,
    resolve_remote_role_endpoint,
)

# ---------------------------------------------------------------------------
# Local Ollama defaults (no API key required)
# ---------------------------------------------------------------------------

# Local Ollama default model. Uncensored so it won't refuse to generate
# red-team prompts. Pull: ``ollama pull huihui_ai/gemma-4-abliterated:12b``.
DEFAULT_LOCAL_MODEL = "huihui_ai/gemma-4-abliterated:12b"

# LiteLLM provider prefix for talking to a local Ollama chat endpoint.
OLLAMA_PROVIDER_PREFIX = "ollama_chat"


# Default local embedder served by Ollama (used by any attack that needs an
# embedder, e.g. the RAG Attack and AutoDAN-Turbo strategy retrieval).
DEFAULT_EMBEDDER_IDENTIFIER = "embeddinggemma"
DEFAULT_EMBEDDER_ENDPOINT = resolve_ollama_base_url()
DEFAULT_EMBEDDER_AGENT_TYPE = "OLLAMA"
# OpenAI-compatible base URL exposed by Ollama (used by the RAG Attack, which
# embeds through an OpenAI-compatible client and posts to ``/v1/embeddings``).
DEFAULT_EMBEDDER_OPENAI_ENDPOINT = f"{resolve_ollama_base_url()}/v1"
# Ollama ignores the key but the OpenAI client requires a non-empty value.
DEFAULT_EMBEDDER_OPENAI_API_KEY = "ollama"

# Same model expressed as a LiteLLM model string (provider-prefixed). Callers
# that hand a single string to LiteLLM (e.g. the discovery planner) want this
# form; callers that split identifier/endpoint/agent_type want DEFAULT_LOCAL_MODEL.
DEFAULT_LOCAL_LITELLM_MODEL = f"{OLLAMA_PROVIDER_PREFIX}/{DEFAULT_LOCAL_MODEL}"

DEFAULT_LOCAL_MODEL_ENDPOINT = resolve_ollama_base_url()
DEFAULT_LOCAL_AGENT_TYPE = "OLLAMA"

# Local role identifiers — attacker / judge / category-classifier all default
# to the same local model (no API key).
DEFAULT_ATTACKER_IDENTIFIER = DEFAULT_LOCAL_MODEL
DEFAULT_JUDGE_IDENTIFIER = DEFAULT_LOCAL_MODEL
DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER = "gemma3:4b"
DEFAULT_CATEGORY_CLASSIFIER_ENDPOINT = DEFAULT_LOCAL_MODEL_ENDPOINT
DEFAULT_CATEGORY_CLASSIFIER_AGENT_TYPE = DEFAULT_LOCAL_AGENT_TYPE
DEFAULT_CATEGORY_CLASSIFIER_MAX_TOKENS = 100
DEFAULT_MAX_OUTPUT_TOKENS = 4096

# ---------------------------------------------------------------------------
# Remote defaults: roles served by the HackAgent API (used when a
# HACKAGENT_API_KEY is available).
# ---------------------------------------------------------------------------

DEFAULT_REMOTE_ROLE_ENDPOINT = resolve_remote_role_endpoint()
DEFAULT_REMOTE_AGENT_TYPE = "OPENAI_SDK"
DEFAULT_REMOTE_ATTACKER_IDENTIFIER = "hackagent-attacker"
DEFAULT_REMOTE_JUDGE_IDENTIFIER = "hackagent-judge"

__all__ = [
    "DEFAULT_LOCAL_MODEL",
    "OLLAMA_PROVIDER_PREFIX",
    "DEFAULT_EMBEDDER_IDENTIFIER",
    "DEFAULT_EMBEDDER_ENDPOINT",
    "DEFAULT_EMBEDDER_AGENT_TYPE",
    "DEFAULT_EMBEDDER_OPENAI_ENDPOINT",
    "DEFAULT_EMBEDDER_OPENAI_API_KEY",
    "DEFAULT_LOCAL_LITELLM_MODEL",
    "DEFAULT_LOCAL_MODEL_ENDPOINT",
    "DEFAULT_LOCAL_AGENT_TYPE",
    "DEFAULT_ATTACKER_IDENTIFIER",
    "DEFAULT_JUDGE_IDENTIFIER",
    "DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER",
    "DEFAULT_CATEGORY_CLASSIFIER_ENDPOINT",
    "DEFAULT_CATEGORY_CLASSIFIER_AGENT_TYPE",
    "DEFAULT_CATEGORY_CLASSIFIER_MAX_TOKENS",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "DEFAULT_REMOTE_ROLE_ENDPOINT",
    "DEFAULT_REMOTE_AGENT_TYPE",
    "DEFAULT_REMOTE_ATTACKER_IDENTIFIER",
    "DEFAULT_REMOTE_JUDGE_IDENTIFIER",
]
