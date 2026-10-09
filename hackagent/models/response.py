# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Normalized responses returned by model backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

from hackagent.core.contracts import GuardrailInfo, LLMError

_MISSING = object()


def _as_dict(value: Any) -> Optional[Dict[str, Any]]:
    """Convert LiteLLM/OpenAI mapping-like values to plain dictionaries."""
    if value is None:
        return None
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(exclude_none=True)
        return dict(dumped) if isinstance(dumped, Mapping) else None
    if isinstance(value, Mapping):
        return {key: item for key, item in value.items() if item is not None}
    return None


def _get(value: Any, key: str, default: Any = None) -> Any:
    """Read a field from either a mapping or an object."""
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _content_text(content: Any) -> str:
    """Normalize string and structured message content to text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            text = _get(part, "text")
            if text is not None:
                parts.append(str(text))
        return "".join(parts)
    return str(content)


@dataclass
class ModelResponse:
    """Backend-independent view of a model completion response."""

    text: str
    raw_response: Any = None
    reasoning_content: Optional[str] = None
    tool_calls: list[Dict[str, Any]] = field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None
    model: Optional[str] = None
    response_id: Optional[str] = None
    created: Optional[int] = None
    system_fingerprint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[LLMError] = None
    guardrail: Optional[GuardrailInfo] = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.guardrail is None

    @classmethod
    def failed(cls, error: Exception) -> "ModelResponse":
        """Represent provider failures without losing their status or category."""
        failure = LLMError(
            message=str(error),
            category=type(error).__name__,
            status_code=getattr(error, "status_code", None),
        )
        return cls(
            text="",
            error=failure,
            metadata={
                "ok": False,
                "error": failure.model_dump(exclude_none=True),
            },
        )

    @property
    def reasoning(self) -> Optional[str]:
        """Return reasoning content using a backend-independent name."""
        return self.reasoning_content

    @classmethod
    def from_value(cls, value: Any) -> "ModelResponse":
        """Normalize common values, including LiteLLM ``ModelResponse`` objects."""
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls(text=value, raw_response=value)
        if hasattr(value, "choices") or (
            isinstance(value, Mapping) and "choices" in value
        ):
            return cls.from_litellm(value)
        if isinstance(value, Mapping):
            return cls._from_mapping(value)
        raise TypeError(f"Unsupported model response type: {type(value).__name__}")

    @classmethod
    def from_litellm(cls, value: Any) -> "ModelResponse":
        """Normalize a LiteLLM ``ModelResponse`` without discarding its metadata."""
        return cls._from_litellm(value)

    @classmethod
    def _from_mapping(cls, value: Mapping[str, Any]) -> "ModelResponse":
        text = value.get("text")
        if text is None:
            text = value.get("processed_response", value.get("generated_text", ""))
        metadata = dict(value.get("agent_specific_data") or {})
        error = None
        if value.get("error_message"):
            error = LLMError(
                message=str(value["error_message"]),
                category=value.get("error_category"),
                status_code=value.get("status_code", value.get("raw_response_status")),
            )
            metadata["error"] = error.model_dump(exclude_none=True)
        guardrail = None
        if metadata.get("guardrail"):
            guardrail = GuardrailInfo(
                side=metadata.get("side") or "before",
                message=metadata.get("message") or "",
                categories=metadata.get("categories") or [],
                reasoning=metadata.get("reasoning") or "",
            )
        return cls(
            text=str(text or ""),
            raw_response=value,
            reasoning_content=value.get("reasoning_content"),
            tool_calls=list(
                value.get("tool_calls") or metadata.get("tool_calls") or []
            ),
            usage=_as_dict(value.get("usage") or metadata.get("usage")),
            finish_reason=value.get("finish_reason") or metadata.get("finish_reason"),
            model=value.get("model") or metadata.get("provider_model"),
            response_id=value.get("id"),
            created=value.get("created"),
            system_fingerprint=value.get("system_fingerprint"),
            metadata=metadata,
            error=error,
            guardrail=guardrail,
        )

    @classmethod
    def _from_litellm(cls, value: Any) -> "ModelResponse":
        choices = _get(value, "choices") or []
        choice = choices[0] if choices else None
        message = _get(choice, "message")
        reasoning_content = _get(message, "reasoning_content")
        content = _content_text(_get(message, "content"))
        tool_calls = []
        for tool_call in _get(message, "tool_calls", []) or []:
            normalized = _as_dict(tool_call)
            tool_calls.append(
                normalized if normalized is not None else {"value": tool_call}
            )

        hidden_value = _get(value, "_hidden_params", _MISSING)
        hidden = None if hidden_value is _MISSING else _as_dict(hidden_value)
        metadata = dict(hidden or {})
        if hidden is not None:
            metadata["hidden_params"] = hidden
        response_ms = _get(value, "response_ms")
        if response_ms is not None:
            metadata["response_ms"] = response_ms
        system_fingerprint = _get(value, "system_fingerprint")
        if system_fingerprint is not None:
            metadata["system_fingerprint"] = system_fingerprint
        headers_value = _get(value, "_response_headers", _MISSING)
        response_headers = (
            None if headers_value is _MISSING else _as_dict(headers_value)
        )
        if response_headers is not None:
            metadata["response_headers"] = response_headers
        return cls(
            text=content or str(reasoning_content or ""),
            raw_response=value,
            reasoning_content=reasoning_content,
            tool_calls=tool_calls,
            usage=_as_dict(_get(value, "usage")),
            finish_reason=_get(choice, "finish_reason"),
            model=_get(value, "model"),
            response_id=_get(value, "id"),
            created=_get(value, "created"),
            system_fingerprint=system_fingerprint,
            metadata=metadata,
        )
