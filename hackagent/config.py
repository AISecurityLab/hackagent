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

# ---------------------------------------------------------------------------
# Local Ollama defaults (no API key required)
# ---------------------------------------------------------------------------

# Local Ollama default model. Uncensored so it won't refuse to generate
# red-team prompts. Pull: ``ollama pull Librellama/gemma4:e2b-Uncensored``.
DEFAULT_LOCAL_MODEL = "Librellama/gemma4:e2b-Uncensored"

# LiteLLM provider prefix for talking to a local Ollama chat endpoint.
OLLAMA_PROVIDER_PREFIX = "ollama_chat"

# Same model expressed as a LiteLLM model string (provider-prefixed). Callers
# that hand a single string to LiteLLM (e.g. the discovery planner) want this
# form; callers that split identifier/endpoint/agent_type want DEFAULT_LOCAL_MODEL.
DEFAULT_LOCAL_LITELLM_MODEL = f"{OLLAMA_PROVIDER_PREFIX}/{DEFAULT_LOCAL_MODEL}"

DEFAULT_LOCAL_MODEL_ENDPOINT = "http://localhost:11434"
DEFAULT_LOCAL_AGENT_TYPE = "OLLAMA"

# Local role identifiers — attacker / judge / category-classifier all default
# to the same local model (no API key).
DEFAULT_ATTACKER_IDENTIFIER = DEFAULT_LOCAL_MODEL
DEFAULT_JUDGE_IDENTIFIER = DEFAULT_LOCAL_MODEL
DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER = DEFAULT_LOCAL_MODEL
DEFAULT_CATEGORY_CLASSIFIER_ENDPOINT = DEFAULT_LOCAL_MODEL_ENDPOINT
DEFAULT_CATEGORY_CLASSIFIER_AGENT_TYPE = DEFAULT_LOCAL_AGENT_TYPE
DEFAULT_CATEGORY_CLASSIFIER_MAX_TOKENS = 100
DEFAULT_MAX_OUTPUT_TOKENS = 4096

# ---------------------------------------------------------------------------
# Remote defaults: roles served by the HackAgent API (used when a
# HACKAGENT_API_KEY is available).
# ---------------------------------------------------------------------------

DEFAULT_REMOTE_ROLE_ENDPOINT = "https://api.hackagent.dev/v1"
DEFAULT_REMOTE_AGENT_TYPE = "OPENAI_SDK"
DEFAULT_REMOTE_ATTACKER_IDENTIFIER = "hackagent-attacker"
DEFAULT_REMOTE_JUDGE_IDENTIFIER = "hackagent-judge"

__all__ = [
    # local model
    "DEFAULT_LOCAL_MODEL",
    "OLLAMA_PROVIDER_PREFIX",
    "DEFAULT_LOCAL_LITELLM_MODEL",
    "DEFAULT_LOCAL_MODEL_ENDPOINT",
    "DEFAULT_LOCAL_AGENT_TYPE",
    # local roles
    "DEFAULT_ATTACKER_IDENTIFIER",
    "DEFAULT_JUDGE_IDENTIFIER",
    "DEFAULT_CATEGORY_CLASSIFIER_IDENTIFIER",
    "DEFAULT_CATEGORY_CLASSIFIER_ENDPOINT",
    "DEFAULT_CATEGORY_CLASSIFIER_AGENT_TYPE",
    "DEFAULT_CATEGORY_CLASSIFIER_MAX_TOKENS",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    # remote roles
    "DEFAULT_REMOTE_ROLE_ENDPOINT",
    "DEFAULT_REMOTE_AGENT_TYPE",
    "DEFAULT_REMOTE_ATTACKER_IDENTIFIER",
    "DEFAULT_REMOTE_JUDGE_IDENTIFIER",
]
