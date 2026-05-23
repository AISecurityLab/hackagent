# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Lightweight per-registration config used by ``AgentRouter`` for
chat-completion AgentTypes.

Phase E.2 of the LiteLLM router refactor (issue #379) replaces the
``LiteLLMAgent`` / ``OpenAIAgent`` / ``OllamaAgent`` adapter instances
in ``AgentRouter._agent_registry`` with instances of this class. The
router's ``_dispatch_via_litellm`` reads the same attributes off either
object (``litellm_model``, ``api_base_url``, ``actual_api_key``,
``default_*``…), so consumers that mutate ``adapter.default_max_tokens``
or similar keep working.

``ADKAgent`` is unaffected — it stays as an :class:`Agent` subclass
because its custom-LLM registration with LiteLLM is per-instance and
needs construction-time side effects.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from hackagent.logger import get_logger
from hackagent.router import envelope as _envelope
from hackagent.router.provider_config import ProviderConfig
from hackagent.router.types import AgentTypeEnum

logger = get_logger(__name__)


# ---- per-AgentType config normalisation ---------------------------------
# These helpers cover the small adapter-class quirks that used to live
# in ``OpenAIAgent.__init__`` and ``OllamaAgent.__init__``.

_OLLAMA_DEFAULT_ENDPOINT = "http://localhost:11434"


def _normalise_ollama_endpoint(endpoint: Optional[str]) -> str:
    """Resolve & normalise the Ollama endpoint URL the way OllamaAgent did."""
    resolved = endpoint or os.environ.get("OLLAMA_BASE_URL", _OLLAMA_DEFAULT_ENDPOINT)
    resolved = resolved.rstrip("/")
    for suffix in ("/api/generate", "/api/chat", "/api/tags", "/api/show", "/api"):
        if resolved.endswith(suffix):
            resolved = resolved[: -len(suffix)]
            break
    return resolved


def _resolve_api_key_from_config(
    config: Dict[str, Any], env_var_fallback: Optional[str]
) -> Optional[str]:
    """Mirror the API-key resolution path in ``Agent._resolve_api_key``."""
    api_key_config = config.get("api_key")
    if api_key_config:
        # The config value may itself be an env-var name.
        env_val = os.environ.get(api_key_config)
        if env_val:
            return env_val
        return api_key_config
    if env_var_fallback:
        env_val = os.environ.get(env_var_fallback)
        if env_val:
            return env_val
    return None


def _default_api_key_env_var(
    litellm_model: str, api_base_url: Optional[str]
) -> Optional[str]:
    if api_base_url:
        return None
    if litellm_model.startswith(("openai/", "gpt-")):
        return "OPENAI_API_KEY"
    if litellm_model.startswith(("anthropic/", "claude-")):
        return "ANTHROPIC_API_KEY"
    return None


class _ChatRegistration:
    """Mutable config holder consumed by ``AgentRouter._dispatch_via_litellm``.

    Exposes exactly the attributes the dispatch path and external code
    used to read off ``LiteLLMAgent`` / ``OpenAIAgent`` / ``OllamaAgent``
    instances: ``id``, ``ADAPTER_TYPE``, ``model_name``,
    ``litellm_model``, ``api_base_url``, ``actual_api_key``,
    ``default_max_tokens``, ``default_temperature``, ``default_top_p``,
    ``default_thinking``, ``default_tools``, ``default_tool_choice``,
    ``default_extra_body``, and any Ollama-specific extras
    (``default_top_k``, ``default_num_ctx``, ``default_stream``).
    """

    DEFAULT_MAX_TOKENS: int = 100
    DEFAULT_TEMPERATURE: float = 0.8
    DEFAULT_TOP_P: float = 0.95

    def __init__(
        self,
        *,
        id: str,
        agent_type: AgentTypeEnum,
        provider_config: ProviderConfig,
        config: Dict[str, Any],
    ):
        self.id = id
        self.agent_type = agent_type
        self.config: Dict[str, Any] = dict(config)
        self.ADAPTER_TYPE: str = provider_config.adapter_label

        # ---- model + endpoint ----
        # OpenAI custom-endpoint quirk: if endpoint is set but no model
        # name, default to ``"default"`` so the server decides.
        if "name" not in self.config:
            if agent_type == AgentTypeEnum.OPENAI_SDK and self.config.get("endpoint"):
                self.model_name = "default"
            else:
                raise ValueError(
                    f"Missing required configuration key 'name' for "
                    f"{provider_config.adapter_label}: {id}"
                )
        else:
            self.model_name = self.config["name"]

        # Ollama special-cases the endpoint default + normalisation.
        if agent_type == AgentTypeEnum.OLLAMA:
            self.api_base_url: Optional[str] = _normalise_ollama_endpoint(
                self.config.get("endpoint")
            )
        else:
            self.api_base_url = self.config.get("endpoint") or None

        self.litellm_model = _envelope.resolve_litellm_model(
            self.model_name, provider_prefix=provider_config.provider_prefix
        )

        # ---- API key resolution ----
        env_var_fallback = _default_api_key_env_var(
            self.litellm_model, self.api_base_url
        )
        self.actual_api_key: Optional[str] = _resolve_api_key_from_config(
            self.config, env_var_fallback
        )
        # OpenAI custom-endpoint quirk: when no key is configured but an
        # endpoint is, use a placeholder so the OpenAI client (under
        # LiteLLM) doesn't choke.
        if (
            agent_type == AgentTypeEnum.OPENAI_SDK
            and not self.actual_api_key
            and self.api_base_url
        ):
            self.actual_api_key = "not-required"

        # ---- generation defaults ----
        self.default_max_tokens: int = self.config.get(
            "max_tokens", self.DEFAULT_MAX_TOKENS
        )
        # OpenAI's default temperature historically was 1.0; everyone else is 0.8.
        self.default_temperature: float = self.config.get(
            "temperature",
            1.0 if agent_type == AgentTypeEnum.OPENAI_SDK else self.DEFAULT_TEMPERATURE,
        )
        self.default_top_p: float = self.config.get("top_p", self.DEFAULT_TOP_P)
        self.default_thinking = self.config.get("thinking")
        self.default_tools = self.config.get("tools")
        self.default_tool_choice = self.config.get("tool_choice")
        self.default_extra_body = self.config.get("extra_body")

        # Ollama extras — also tolerated for the other AgentTypes but only
        # used by LiteLLM for ``ollama_chat/``.
        self.default_top_k = self.config.get("top_k")
        self.default_num_ctx = self.config.get("num_ctx")
        self.default_stream = self.config.get("stream", False)

        logger.info(
            f"{self.ADAPTER_TYPE} '{self.id}' registered for LiteLLM model: "
            f"'{self.litellm_model}'"
            + (f" API Base: '{self.api_base_url}'" if self.api_base_url else "")
        )

    def get_identifier(self) -> str:
        return self.id
