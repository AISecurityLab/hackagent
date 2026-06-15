# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
``AgentType`` → ``ProviderConfig`` table.

The lookup table is the single source of truth for how each agent type
maps to a LiteLLM call: provider prefix, the ``thinking`` knob
translator, the allow-list of extra request keys that should pass
through, and an optional :class:`litellm.CustomLLM` factory for agent
types LiteLLM cannot speak natively (ADK, future MCP/A2A).
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from hackagent.router.types import AgentTypeEnum


# ---- thinking translators -----------------------------------------------
# Each translator takes the raw ``thinking`` value and the model name and
# returns the (possibly empty) dict of provider-specific request fields
# that should be merged into the LiteLLM kwargs.


def default_thinking_translator(
    thinking: Any, *, model_name: str = ""
) -> Dict[str, Any]:
    """Provider-agnostic translation that matches LiteLLM's own conventions."""
    if thinking is None:
        return {}
    if isinstance(thinking, dict):
        return {"thinking": dict(thinking)}
    if isinstance(thinking, str):
        return {"reasoning_effort": thinking}
    if isinstance(thinking, bool):
        return {"thinking": {"type": "enabled" if thinking else "disabled"}}
    if isinstance(thinking, int):
        return {"thinking": {"type": "enabled", "budget_tokens": int(thinking)}}
    return {"thinking": thinking}


_OPENAI_REASONING_MODEL_PREFIXES = ("o1", "o3", "o4", "gpt-5", "gpt-6")


def openai_thinking_translator(
    thinking: Any, *, model_name: str = ""
) -> Dict[str, Any]:
    """Map ``thinking`` to ``reasoning_effort`` for OpenAI reasoning models."""
    if thinking is None:
        return {}
    bare = model_name.split("/")[-1]
    is_reasoning = bare.startswith(_OPENAI_REASONING_MODEL_PREFIXES)
    if is_reasoning:
        if thinking is True:
            return {"reasoning_effort": "medium"}
        if thinking is False:
            return {}
        if isinstance(thinking, str):
            return {"reasoning_effort": thinking}
        if isinstance(thinking, dict):
            effort = thinking.get("reasoning_effort") or thinking.get("effort")
            if effort:
                return {"reasoning_effort": effort}
            return {"thinking": dict(thinking)}
    return default_thinking_translator(thinking, model_name=model_name)


def ollama_thinking_translator(
    thinking: Any, *, model_name: str = ""
) -> Dict[str, Any]:
    """Map ``thinking`` to Ollama's native ``think`` field."""
    if thinking is None:
        return {}
    if isinstance(thinking, bool):
        return {"think": thinking}
    if isinstance(thinking, str):
        return {"think": thinking}
    if isinstance(thinking, int):
        return {"think": thinking > 0}
    if isinstance(thinking, dict):
        kind = (thinking.get("type") or "").lower()
        return {"think": False if kind == "disabled" else True}
    return {"think": bool(thinking)}


# ---- provider config -----------------------------------------------------


@dataclass(frozen=True)
class ProviderConfig:
    """Per-``AgentType`` knobs the router uses to drive ``litellm.completion``."""

    # LiteLLM provider prefix to prepend to ``model`` (``"openai"``,
    # ``"ollama_chat"``…). ``None`` means leave the user-supplied model
    # string unchanged (the LITELLM passthrough type).
    provider_prefix: Optional[str]

    # Translates the unified ``thinking`` value into provider-specific
    # request fields. Receives the raw value plus the model name.
    thinking_translator: Callable[..., Dict[str, Any]]

    # ``adapter_type`` label that appears in the response envelope.
    adapter_label: str

    # Additional request-data keys allowed to pass through into the
    # LiteLLM call (e.g. ``top_k`` for Ollama, ``tools`` for OpenAI).
    extra_passthrough_keys: Tuple[str, ...] = ()

    # Optional zero-arg factory returning a (provider_name, handler)
    # tuple to register with LiteLLM's ``custom_provider_map`` — only
    # used by agent types whose protocol LiteLLM doesn't speak
    # natively (ADK today; MCP/A2A in the future).
    custom_llm_factory: Optional[Callable[..., Any]] = None


# ---- the table ----------------------------------------------------------
# ADK isn't in the lookup table because its custom-LLM handler is
# constructed per-instance (it captures endpoint/user_id/session policy
# from the adapter config). It stays driven by ``ADKAgent`` for now and
# moves into ``router/providers/`` in Phase E.

PROVIDER_CONFIGS: Dict[AgentTypeEnum, ProviderConfig] = {
    AgentTypeEnum.LITELLM: ProviderConfig(
        provider_prefix=None,
        thinking_translator=default_thinking_translator,
        adapter_label="LiteLLMAgent",
    ),
    AgentTypeEnum.OPENAI_SDK: ProviderConfig(
        provider_prefix="openai",
        thinking_translator=openai_thinking_translator,
        adapter_label="OpenAIAgent",
        extra_passthrough_keys=("tools", "tool_choice", "extra_body"),
    ),
    AgentTypeEnum.OLLAMA: ProviderConfig(
        provider_prefix="ollama_chat",
        thinking_translator=ollama_thinking_translator,
        adapter_label="OllamaAgent",
        extra_passthrough_keys=("top_k", "num_ctx", "stream"),
    ),
    AgentTypeEnum.LANGCHAIN: ProviderConfig(
        # LangServe endpoints are OpenAI-compatible by convention; the
        # generic LiteLLM passthrough already handles them.
        provider_prefix=None,
        thinking_translator=default_thinking_translator,
        adapter_label="LiteLLMAgent",
    ),
}


def get_provider_config(agent_type: AgentTypeEnum) -> Optional[ProviderConfig]:
    """Return the ``ProviderConfig`` for ``agent_type``, or ``None``."""
    return PROVIDER_CONFIGS.get(agent_type)
