# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Build the adapter for a :class:`ModelSpec` and send requests through it.

Chat-completion agent types (``LITELLM``, ``OPENAI_SDK``, ``OLLAMA``,
``LANGCHAIN``) are driven through LiteLLM from a :class:`ProviderConfig`
and a ``_ChatRegistration``. The other supported types use an adapter class
whose ``handle_request`` does the call.

Sending never raises: every failure becomes an error envelope.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional, Tuple, Type

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.core.logging import get_logger
from hackagent.models import envelope as _envelope
from hackagent.models.adapters import litellm_callbacks as _callbacks
from hackagent.models.adapters.adk import ADKAgent
from hackagent.models.adapters.base import Agent, get_litellm
from hackagent.models.adapters.claude import ClaudeCodeAgent
from hackagent.models.adapters.codex import CodexAgent
from hackagent.models.adapters.hermes import HermesAgent
from hackagent.models.adapters.litellm import _ChatRegistration
from hackagent.models.adapters.web import WebAgent
from hackagent.models.provider_config import (
    PROVIDER_CONFIGS,
    ProviderConfig,
    get_provider_config,
)

logger = get_logger(__name__)

#: Agent types that need an adapter object rather than a chat registration.
ADAPTER_CLASSES: Dict[AgentType, Type[Agent]] = {
    AgentType.GOOGLE_ADK: ADKAgent,
    AgentType.CLAUDE_CODE: ClaudeCodeAgent,
    AgentType.CODEX: CodexAgent,
    AgentType.HERMES: HermesAgent,
    AgentType.WEB: WebAgent,
}

#: ADK sessions need a user id; used when the spec does not carry one.
DEFAULT_ADK_USER_ID = "hackagent"


def check_supported(agent_type: AgentType) -> None:
    """Raise ``ValueError`` unless ``agent_type`` can be connected to."""
    if get_provider_config(agent_type) is None and agent_type not in ADAPTER_CLASSES:
        supported = [*ADAPTER_CLASSES, *PROVIDER_CONFIGS]
        raise ValueError(
            f"Unsupported agent type: {agent_type}. Supported types: {supported}"
        )


def resolve_api_key(spec: ModelSpec) -> Optional[str]:
    """Return the spec's API key: the literal one, else its env variable."""
    if spec.api_key:
        return spec.api_key
    if spec.api_key_env:
        return os.environ.get(spec.api_key_env) or None
    return None


def adapter_config(spec: ModelSpec) -> Dict[str, Any]:
    """Flatten ``spec`` into the config dict the adapters read."""
    config: Dict[str, Any] = dict(spec.extra)
    config["name"] = spec.identifier
    if spec.endpoint:
        config["endpoint"] = spec.endpoint
    api_key = resolve_api_key(spec)
    if api_key:
        config["api_key"] = api_key
    for field in ("max_tokens", "temperature", "top_p", "timeout", "thinking"):
        value = getattr(spec, field)
        if value is not None:
            config[field] = value
    if spec.agent_type == AgentType.GOOGLE_ADK:
        config.setdefault("user_id", DEFAULT_ADK_USER_ID)
    return config


def build_adapter(spec: ModelSpec, *, instance_id: str) -> Any:
    """Instantiate the adapter for ``spec``. Does no network I/O.

    Raises:
        ValueError: If the agent type is unsupported or the adapter rejects
            its configuration.
    """
    check_supported(spec.agent_type)
    config = adapter_config(spec)
    provider_config = get_provider_config(spec.agent_type)
    try:
        if provider_config is not None:
            return _ChatRegistration(
                id=instance_id,
                agent_type=spec.agent_type,
                provider_config=provider_config,
                config=config,
            )
        return ADAPTER_CLASSES[spec.agent_type](id=instance_id, config=config)
    except Exception as e:
        label = (
            provider_config.adapter_label
            if provider_config is not None
            else ADAPTER_CLASSES[spec.agent_type].__name__
        )
        raise ValueError(f"Failed to instantiate adapter {label}: {e}") from e


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


def _adapter_exception(
    instance_id: str, request_data: Dict[str, Any], exc: Exception
) -> Dict[str, Any]:
    logger.error(
        "Error handling request for agent %s: %s", instance_id, exc, exc_info=True
    )
    return {
        "raw_request": request_data,
        "processed_response": None,
        "generated_text": None,
        "status_code": 500,
        "raw_response_status": 500,
        "raw_response_headers": None,
        "raw_response_body": None,
        "agent_specific_data": None,
        "error_message": f"Agent {instance_id} failed to handle request: {exc}",
        "error_category": "AdapterException",
        "agent_id": instance_id,
        "adapter_type": "dispatch",
    }


def _extract_messages(
    request_data: Dict[str, Any],
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    messages = request_data.get("messages")
    prompt = request_data.get("prompt")
    if messages:
        return messages, None
    if prompt:
        return [{"role": "user", "content": prompt}], None
    return None, "Request data must include either 'messages' or 'prompt' field."


def _prepare_chat(
    instance_id: str,
    adapter: Any,
    provider_config: ProviderConfig,
    request_data: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Build LiteLLM kwargs and the context needed to shape its response."""
    adapter_label = provider_config.adapter_label or adapter.ADAPTER_TYPE
    model_name = getattr(adapter, "litellm_model", None) or getattr(
        adapter, "model_name", None
    )
    if model_name is None:
        return None, _envelope.build_error_envelope(
            agent_id=instance_id,
            adapter_type=adapter_label,
            error_message=(
                f"Adapter for '{instance_id}' has no model name; "
                "cannot dispatch via LiteLLM."
            ),
            status_code=500,
            raw_request=request_data,
        )
    messages, validation_error = _extract_messages(request_data)
    if validation_error:
        return None, _envelope.build_error_envelope(
            agent_id=instance_id,
            adapter_type=adapter_label,
            error_message=validation_error,
            status_code=400,
            raw_request=request_data,
        )
    max_tokens = request_data.get(
        "max_tokens", getattr(adapter, "default_max_tokens", 100)
    )
    temperature = request_data.get(
        "temperature", getattr(adapter, "default_temperature", 0.8)
    )
    top_p = request_data.get("top_p", getattr(adapter, "default_top_p", 0.95))
    thinking = request_data.get("thinking", getattr(adapter, "default_thinking", None))
    tools = request_data.get("tools", getattr(adapter, "default_tools", None))
    tool_choice = request_data.get(
        "tool_choice", getattr(adapter, "default_tool_choice", None)
    )
    extra_body = request_data.get(
        "extra_body", getattr(adapter, "default_extra_body", None)
    )
    excluded_keys = {
        "prompt",
        "messages",
        "max_tokens",
        "temperature",
        "top_p",
        "tools",
        "tool_choice",
        "thinking",
        "extra_body",
        "metadata",
    }
    extra_kwargs: Dict[str, Any] = {
        key: value for key, value in request_data.items() if key not in excluded_keys
    }
    for key in provider_config.extra_passthrough_keys:
        if key not in request_data and key not in extra_kwargs:
            default = getattr(adapter, f"default_{key}", None)
            if default is not None:
                extra_kwargs[key] = default
    caller_metadata = request_data.get("metadata")
    hackagent_block: Dict[str, Any] = {"id": instance_id, "adapter_type": adapter_label}
    caller_hackagent = (
        caller_metadata.get(_callbacks.HACKAGENT_METADATA_KEY)
        if isinstance(caller_metadata, dict)
        else None
    )
    if isinstance(caller_hackagent, dict):
        hackagent_block.update(caller_hackagent)
    merged_metadata = dict(caller_metadata) if isinstance(caller_metadata, dict) else {}
    merged_metadata[_callbacks.HACKAGENT_METADATA_KEY] = hackagent_block
    extra_kwargs["metadata"] = merged_metadata
    kwargs = _envelope.build_litellm_kwargs(
        model=model_name,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        api_base=getattr(adapter, "api_base_url", None),
        api_key=getattr(adapter, "actual_api_key", None),
        tools=tools,
        tool_choice=tool_choice,
        extra_body=extra_body,
        thinking_payload=provider_config.thinking_translator(
            thinking, model_name=model_name
        ),
        extra_kwargs=extra_kwargs,
    )
    return {
        "kwargs": kwargs,
        "instance_id": instance_id,
        "adapter_label": adapter_label,
        "model_name": model_name,
        "request_data": request_data,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "tools": tools,
        "tool_choice": tool_choice,
        "extra_kwargs": extra_kwargs,
    }, None


def _chat_error(prep: Dict[str, Any], message: str) -> Dict[str, Any]:
    return _envelope.build_error_envelope(
        agent_id=prep["instance_id"],
        adapter_type=prep["adapter_label"],
        error_message=message,
        status_code=500,
        raw_request=prep["request_data"],
        model_name=prep["model_name"],
    )


def _finalize_chat(response: Any, prep: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a LiteLLM response into an envelope."""
    text = _envelope.extract_text_from_response(response, model_name=prep["model_name"])
    if isinstance(text, str) and text.startswith("[GENERATION_ERROR:"):
        return _chat_error(prep, f"{prep['adapter_label']} generation error: {text}")
    invoked_parameters: Dict[str, Any] = {
        "max_tokens": prep["max_tokens"],
        "temperature": prep["temperature"],
        "top_p": prep["top_p"],
        **prep["extra_kwargs"],
    }
    if prep["tools"] is not None:
        invoked_parameters["tools"] = prep["tools"]
    if prep["tool_choice"] is not None:
        invoked_parameters["tool_choice"] = prep["tool_choice"]
    completion_result: Dict[str, Any] = {
        "success": True,
        "content": text,
        "raw_response": response,
    }
    tool_calls = _envelope.extract_tool_calls(response)
    if tool_calls is not None:
        completion_result["tool_calls"] = tool_calls
    try:
        completion_result["finish_reason"] = response.choices[0].finish_reason
    except (AttributeError, IndexError, TypeError):
        pass
    try:
        if response.usage is not None:
            completion_result["usage"] = response.usage.model_dump()
    except AttributeError:
        pass
    try:
        completion_result["provider_model"] = response.model
    except AttributeError:
        pass
    response_cost = _envelope.extract_response_cost(response)
    if response_cost is not None:
        completion_result["response_cost"] = response_cost
    call_id = _envelope.extract_litellm_call_id(response)
    if call_id is not None:
        completion_result["litellm_call_id"] = call_id
    return _envelope.build_success_envelope(
        agent_id=prep["instance_id"],
        adapter_type=prep["adapter_label"],
        processed_response=text,
        raw_request=prep["request_data"],
        raw_response_body=response,
        agent_specific_data=_envelope.build_agent_specific_data(
            model_name=prep["model_name"],
            invoked_parameters=invoked_parameters,
            completion_result=completion_result,
        ),
        model_name=prep["model_name"],
    )


def send(
    adapter: Any,
    agent_type: AgentType,
    request_data: Dict[str, Any],
    *,
    instance_id: str,
) -> Dict[str, Any]:
    """Send one request through ``adapter`` and return its envelope."""
    provider_config = get_provider_config(agent_type)
    try:
        if provider_config is None:
            return adapter.handle_request(request_data)
        prep, error = _prepare_chat(instance_id, adapter, provider_config, request_data)
        if error is not None:
            return error
        assert prep is not None
        litellm, available = get_litellm()
        if not available:
            return _chat_error(prep, "litellm is not installed")
        try:
            response = litellm.completion(**prep["kwargs"])
        except Exception as exc:
            logger.exception(
                "LiteLLM dispatch failed for agent %s (model=%s): %s",
                instance_id,
                prep["model_name"],
                exc,
            )
            return _chat_error(
                prep, f"{prep['adapter_label']} error ({type(exc).__name__}): {exc}"
            )
        return _finalize_chat(response, prep)
    except Exception as exc:
        return _adapter_exception(instance_id, request_data, exc)


async def asend(
    adapter: Any,
    agent_type: AgentType,
    request_data: Dict[str, Any],
    *,
    instance_id: str,
) -> Dict[str, Any]:
    """Asynchronous :func:`send`; adapter-driven types run in a thread."""
    provider_config = get_provider_config(agent_type)
    try:
        if provider_config is None:
            return await asyncio.to_thread(adapter.handle_request, request_data)
        prep, error = _prepare_chat(instance_id, adapter, provider_config, request_data)
        if error is not None:
            return error
        assert prep is not None
        litellm, available = get_litellm()
        if not available:
            return _chat_error(prep, "litellm is not installed")
        try:
            response = await litellm.acompletion(**prep["kwargs"])
        except Exception as exc:
            logger.exception(
                "LiteLLM async dispatch failed for agent %s (model=%s): %s",
                instance_id,
                prep["model_name"],
                exc,
            )
            return _chat_error(
                prep, f"{prep['adapter_label']} error ({type(exc).__name__}): {exc}"
            )
        return _finalize_chat(response, prep)
    except Exception as exc:
        return _adapter_exception(instance_id, request_data, exc)
