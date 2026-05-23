# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Envelope helpers — pure functions that translate between LiteLLM's
``ModelResponse`` and HackAgent's standardized response dict.

This module exists as the Phase A landing zone of the
``LITELLM_ROUTER_REFACTOR_PLAN.md`` plan: extract the response-shaping
logic out of the adapter classes so it can be reused by
``AgentRouter`` once the call path is hoisted in Phase C.

The functions here are intentionally:
- pure: no I/O, no logging side effects, no LiteLLM imports at module
  level. Any LiteLLM import lives behind a lazy helper.
- agnostic of agent identity: the caller supplies ``agent_id`` and
  ``adapter_type`` as keyword arguments.
- byte-compatible with the previous adapter envelope, so downstream
  consumers (``StepTracker``, attacks, evaluators, dashboard) keep
  seeing exactly the same dict shape.
"""

from typing import Any, Dict, List, Optional


# Provider prefixes that LiteLLM recognises natively. When a model string
# already starts with one of these we leave it alone instead of prepending
# our own provider prefix.
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


# ---- text helpers --------------------------------------------------------


def strip_think_prefix(text: str) -> str:
    """Strip hidden reasoning prefix up to and including ``</think>`` if present."""
    if not isinstance(text, str):
        return text
    marker = "</think>"
    marker_index = text.find(marker)
    if marker_index == -1:
        return text
    return text[marker_index + len(marker) :]


def extract_text_from_response(response: Any, *, model_name: str = "") -> str:
    """Pull the assistant text out of a LiteLLM ``ModelResponse``.

    Falls back to ``reasoning_content`` / ``reasoning`` when ``content``
    is empty so reasoning-only models still produce output. Returns a
    sentinel ``[GENERATION_ERROR: ...]`` string when the response is
    structurally unusable, mirroring the previous adapter behaviour.
    """
    if not (
        response and getattr(response, "choices", None) and response.choices[0].message
    ):
        return "[GENERATION_ERROR: UNEXPECTED_RESPONSE]"

    message = response.choices[0].message
    content = getattr(message, "content", "") or ""

    reasoning_content = None
    if getattr(message, "reasoning_content", None):
        reasoning_content = message.reasoning_content
    elif getattr(message, "reasoning", None):
        reasoning_content = message.reasoning
    else:
        provider_specific = getattr(message, "provider_specific_fields", None)
        if provider_specific:
            reasoning_content = provider_specific.get(
                "reasoning_content"
            ) or provider_specific.get("reasoning")

    if content:
        return content
    if reasoning_content:
        return reasoning_content
    return "[GENERATION_ERROR: EMPTY_RESPONSE]"


def extract_tool_calls(response: Any) -> Optional[List[Dict[str, Any]]]:
    """Return OpenAI-style ``tool_calls`` from a ``ModelResponse``, or ``None``."""
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError, TypeError):
        return None
    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls:
        return None
    out: List[Dict[str, Any]] = []
    for tc in tool_calls:
        try:
            out.append(
                {
                    "id": getattr(tc, "id", None),
                    "type": getattr(tc, "type", "function"),
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
            )
        except AttributeError:
            continue
    return out or None


# ---- LiteLLM kwargs assembly --------------------------------------------


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


def build_litellm_kwargs(
    *,
    model: str,
    messages: List[Dict[str, str]],
    max_tokens: int,
    temperature: float,
    top_p: float,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
    tools: Optional[Any] = None,
    tool_choice: Optional[Any] = None,
    extra_body: Optional[Any] = None,
    thinking_payload: Optional[Dict[str, Any]] = None,
    extra_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the kwargs dict for ``litellm.completion``.

    ``thinking_payload`` is the *already-translated* per-provider dict
    (e.g. ``{"reasoning_effort": "medium"}`` or ``{"think": True}``);
    the caller is responsible for converting the unified ``thinking``
    knob into the provider-specific shape before passing it in here.
    Anything in ``extra_kwargs`` is splat-merged last and wins on
    collision, matching the previous adapter behaviour.
    """
    params: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }

    if api_base:
        params["api_base"] = api_base
    if api_key:
        params["api_key"] = api_key

    # When the caller provides a custom endpoint without a recognised
    # LiteLLM provider prefix, treat it as OpenAI-compatible — same
    # default the previous LiteLLMAgent used.
    if api_base and not model.startswith(KNOWN_LITELLM_PROVIDER_PREFIXES):
        params["custom_llm_provider"] = "openai"
        params["extra_headers"] = {"User-Agent": "HackAgent/0.1.0"}
    elif api_base:
        params["extra_headers"] = {"User-Agent": "HackAgent/0.1.0"}

    if thinking_payload:
        params.update(thinking_payload)

    if tools:
        params["tools"] = tools
        if tool_choice is not None:
            params["tool_choice"] = tool_choice

    if extra_body is not None:
        params["extra_body"] = (
            dict(extra_body) if isinstance(extra_body, dict) else extra_body
        )

    if extra_kwargs:
        params.update(extra_kwargs)

    return params


# ---- response envelopes -------------------------------------------------


def build_success_envelope(
    *,
    agent_id: str,
    adapter_type: str,
    processed_response: Optional[str],
    raw_request: Optional[Dict[str, Any]] = None,
    raw_response_body: Optional[Any] = None,
    raw_response_headers: Optional[Dict[str, str]] = None,
    agent_specific_data: Optional[Dict[str, Any]] = None,
    model_name: Optional[str] = None,
    status_code: int = 200,
) -> Dict[str, Any]:
    """Construct HackAgent's standardised success-response dict."""
    if isinstance(processed_response, str):
        processed_response = strip_think_prefix(processed_response)

    if agent_specific_data is None:
        agent_specific_data = {}
    if model_name and "model_name" not in agent_specific_data:
        agent_specific_data["model_name"] = model_name

    return {
        "raw_request": raw_request,
        "processed_response": processed_response,
        "generated_text": processed_response,
        "status_code": status_code,
        "raw_response_headers": raw_response_headers,
        "raw_response_body": raw_response_body,
        "agent_specific_data": agent_specific_data,
        "error_message": None,
        "agent_id": agent_id,
        "adapter_type": adapter_type,
    }


def build_error_envelope(
    *,
    agent_id: str,
    adapter_type: str,
    error_message: str,
    status_code: Optional[int] = None,
    raw_request: Optional[Dict[str, Any]] = None,
    raw_response_body: Optional[Any] = None,
    raw_response_headers: Optional[Dict[str, str]] = None,
    agent_specific_data: Optional[Dict[str, Any]] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct HackAgent's standardised error-response dict."""
    if agent_specific_data is None:
        agent_specific_data = {}
    if model_name and "model_name" not in agent_specific_data:
        agent_specific_data["model_name"] = model_name

    return {
        "raw_request": raw_request,
        "processed_response": None,
        "generated_text": None,
        "status_code": status_code if status_code is not None else 500,
        "raw_response_headers": raw_response_headers,
        "raw_response_body": raw_response_body,
        "agent_specific_data": agent_specific_data,
        "error_message": error_message,
        "agent_id": agent_id,
        "adapter_type": adapter_type,
    }


def build_agent_specific_data(
    *,
    model_name: Optional[str],
    invoked_parameters: Dict[str, Any],
    completion_result: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the standard ``agent_specific_data`` block shared by adapters."""
    data: Dict[str, Any] = {
        "model_name": model_name,
        "invoked_parameters": invoked_parameters,
    }
    if completion_result:
        # ``response_cost`` and ``litellm_call_id`` are free metrics that
        # LiteLLM attaches to every successful call — surface them so
        # downstream traces can use them without rooting in the raw
        # response object.
        for key in (
            "usage",
            "finish_reason",
            "provider_model",
            "raw_response",
            "response_cost",
            "litellm_call_id",
        ):
            value = completion_result.get(key)
            if value is not None:
                data[key] = value
        if completion_result.get("tool_calls"):
            data["tool_calls"] = completion_result["tool_calls"]
    if extra:
        data.update(extra)
    return data


# ---- LiteLLM response metadata extraction --------------------------------


def extract_response_cost(response: Any) -> Optional[float]:
    """Pull ``response_cost`` off a LiteLLM ``ModelResponse`` if present.

    LiteLLM exposes the per-call cost (when the model is in its pricing
    catalogue) via the ``_hidden_params`` attribute. Returns ``None``
    when unavailable rather than raising, since cost tracking is
    best-effort.
    """
    hidden = getattr(response, "_hidden_params", None) or {}
    cost = hidden.get("response_cost") if isinstance(hidden, dict) else None
    try:
        return float(cost) if cost is not None else None
    except (TypeError, ValueError):
        return None


def extract_litellm_call_id(response: Any) -> Optional[str]:
    """Pull ``litellm_call_id`` (or ``x-litellm-call-id``) off a response."""
    hidden = getattr(response, "_hidden_params", None) or {}
    if isinstance(hidden, dict):
        for key in ("litellm_call_id", "x-litellm-call-id"):
            value = hidden.get(key)
            if value:
                return str(value)
    # LiteLLM also sets ``response.id`` to a unique value per call.
    response_id = getattr(response, "id", None)
    if response_id:
        return str(response_id)
    return None
