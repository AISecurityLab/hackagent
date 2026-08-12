# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Canonical package-wide configuration defaults.

This is a dependency-free leaf module (stdlib only) so that any layer —
``router``, ``attacks``, examples, tests — can import these constants without
creating a circular dependency. Define a default here once and reference it
everywhere rather than hardcoding the literal in multiple places.

Only plain scalar defaults live here. Defaults that are *derived* from a
Pydantic model field (e.g. ``DEFAULT_TIMEOUT``) stay next to their model in
``hackagent.attacks.techniques.config``, which re-exports the scalars below for
backward compatibility.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Local Ollama defaults (no API key required)
# ---------------------------------------------------------------------------

# Environment variables consulted (in order) to locate the local Ollama server
# before falling back to the upstream default host/port. ``OLLAMA_HOST`` is the
# variable Ollama itself honours, so a user who moved the server off 11434 gets
# picked up automatically.
OLLAMA_BASE_URL_ENV_VARS = ("OLLAMA_BASE_URL", "OLLAMA_API_BASE", "OLLAMA_HOST")

DEFAULT_OLLAMA_HOST = "localhost"
DEFAULT_OLLAMA_PORT = "11434"


def _normalize_ollama_base_url(raw: str) -> str:
    """Normalise an ``OLLAMA_HOST``-style value into a full base URL.

    Accepts ``http://host:port``, ``host:port``, ``host`` and ``:port`` forms.
    A missing scheme defaults to ``http``, a missing host to ``localhost`` and a
    missing port to Ollama's default port (``https`` values keep the implicit
    443 instead).
    """
    value = raw.strip().rstrip("/")
    scheme, sep, remainder = value.partition("://")
    if not sep:
        scheme, remainder = "http", value
    remainder = remainder.lstrip("/")
    authority, slash, path = remainder.partition("/")
    if authority.startswith(":"):
        authority = f"{DEFAULT_OLLAMA_HOST}{authority}"
    # Only append the default port for a bare http host (no port, not IPv6).
    # https values are left alone so they keep the implicit 443.
    if scheme == "http" and ":" not in authority and not authority.endswith("]"):
        authority = f"{authority}:{DEFAULT_OLLAMA_PORT}"
    return f"{scheme}://{authority}{slash}{path}"


def resolve_ollama_base_url() -> str:
    """Return the local Ollama base URL, honouring environment overrides."""
    for env_var in OLLAMA_BASE_URL_ENV_VARS:
        raw = os.environ.get(env_var, "").strip()
        if raw:
            return _normalize_ollama_base_url(raw)
    return f"http://{DEFAULT_OLLAMA_HOST}:{DEFAULT_OLLAMA_PORT}"


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

# Hardcoded fallback for remote API base URL. Override via HACKAGENT_BASE_URL env var
# or by passing base_url to CLIConfig/Agent.
_DEFAULT_REMOTE_BASE_URL = "https://api.hackagent.dev"


def resolve_remote_base_url() -> str:
	"""Return the HackAgent remote API base URL, honouring environment and config overrides."""
	# Check HACKAGENT_BASE_URL env var first
	env_base_url = os.environ.get("HACKAGENT_BASE_URL", "").strip()
	if env_base_url:
		return env_base_url.rstrip("/")
	return _DEFAULT_REMOTE_BASE_URL


def resolve_remote_role_endpoint() -> str:
	"""Return the remote API endpoint for LLM roles (base URL + /v1)."""
	base_url = resolve_remote_base_url()
	return f"{base_url}/v1"


DEFAULT_REMOTE_BASE_URL = resolve_remote_base_url()
DEFAULT_REMOTE_ROLE_ENDPOINT = resolve_remote_role_endpoint()
DEFAULT_REMOTE_AGENT_TYPE = "OPENAI_SDK"
DEFAULT_REMOTE_ATTACKER_IDENTIFIER = "hackagent-attacker"
DEFAULT_REMOTE_JUDGE_IDENTIFIER = "hackagent-judge"

__all__ = [
    # ollama endpoint resolution
    "OLLAMA_BASE_URL_ENV_VARS",
    "DEFAULT_OLLAMA_HOST",
    "DEFAULT_OLLAMA_PORT",
    "resolve_ollama_base_url",
    # local model
    "DEFAULT_LOCAL_MODEL",
    "OLLAMA_PROVIDER_PREFIX",
    "DEFAULT_LOCAL_LITELLM_MODEL",
    "DEFAULT_LOCAL_MODEL_ENDPOINT",
    "DEFAULT_LOCAL_AGENT_TYPE",
    # local embedder
    "DEFAULT_EMBEDDER_IDENTIFIER",
    "DEFAULT_EMBEDDER_ENDPOINT",
    "DEFAULT_EMBEDDER_AGENT_TYPE",
    "DEFAULT_EMBEDDER_OPENAI_ENDPOINT",
    "DEFAULT_EMBEDDER_OPENAI_API_KEY",
    # local roles
    "DEFAULT_ATTACKER_IDENTIFIER",
    "DEFAULT_JUDGE_IDENTIFIER",
    "DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER",
    "DEFAULT_CATEGORY_CLASSIFIER_ENDPOINT",
    "DEFAULT_CATEGORY_CLASSIFIER_AGENT_TYPE",
    "DEFAULT_CATEGORY_CLASSIFIER_MAX_TOKENS",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    # remote roles
    "resolve_remote_base_url",
    "resolve_remote_role_endpoint",
    "DEFAULT_REMOTE_BASE_URL",
    "DEFAULT_REMOTE_ROLE_ENDPOINT",
    "DEFAULT_REMOTE_AGENT_TYPE",
    "DEFAULT_REMOTE_ATTACKER_IDENTIFIER",
    "DEFAULT_REMOTE_JUDGE_IDENTIFIER",
]
