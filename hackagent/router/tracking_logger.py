# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
LiteLLM callback that captures every ``litellm.completion`` call.

LiteLLM exposes a ``CustomLogger`` base class with hook methods that
fire pre-call, on success, and on failure. We register a single
:class:`HackAgentTrackingLogger` instance on ``litellm.callbacks`` and
attach ``metadata`` to every call so the logger can correlate the I/O
back to the originating HackAgent registration.

The logger only emits structured records to ``hackagent.logger``; it
does not write to the backend storage directly. Downstream sinks (TUI
event bus, dashboard, file logs) can pick the records up from there.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from hackagent.logger import get_logger


# Singleton — one logger per process so we don't double-register on
# ``litellm.callbacks``. ``ensure_registered`` is idempotent and is
# called from :meth:`AgentRouter.__init__`. The instance type is
# dynamically built by ``_build_handler_class`` once litellm is
# importable, so we annotate it as ``Optional[Any]`` here.
_REGISTERED: bool = False
_LOGGER_INSTANCE: Optional[Any] = None
_TRACKING_LOGGER = get_logger("hackagent.router.tracking_logger")

# Sentinel metadata keys the logger uses to identify HackAgent-owned
# calls. Other tools wiring their own ``litellm.callbacks`` won't see
# their calls double-logged because we filter on this key.
HACKAGENT_AGENT_ID_KEY = "hackagent_agent_id"
HACKAGENT_ADAPTER_TYPE_KEY = "hackagent_adapter_type"


def _try_import_custom_logger() -> Optional[type]:
    """Return ``litellm.integrations.custom_logger.CustomLogger`` or ``None``."""
    try:
        from litellm.integrations.custom_logger import CustomLogger

        return CustomLogger
    except ImportError:
        return None


def _extract_hackagent_metadata(kwargs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pull the HackAgent metadata block out of a LiteLLM callback ``kwargs``.

    LiteLLM nests user-supplied ``metadata`` under ``litellm_params``. We
    only return a dict when the metadata carries our sentinel key so
    that callbacks fired by other libraries' calls don't get logged.
    """
    litellm_params = kwargs.get("litellm_params") or {}
    metadata = (
        litellm_params.get("metadata") if isinstance(litellm_params, dict) else None
    )
    if not isinstance(metadata, dict):
        return None
    if HACKAGENT_AGENT_ID_KEY not in metadata:
        return None
    return metadata


def _extract_response_text(response_obj: Any) -> Optional[str]:
    """Best-effort string extraction from a LiteLLM ``ModelResponse``."""
    try:
        message = response_obj.choices[0].message
    except (AttributeError, IndexError, TypeError):
        return None
    content = getattr(message, "content", None)
    if isinstance(content, str) and content:
        return content
    reasoning = getattr(message, "reasoning_content", None) or getattr(
        message, "reasoning", None
    )
    if isinstance(reasoning, str) and reasoning:
        return reasoning
    return None


def _last_user_message(kwargs: Dict[str, Any]) -> Optional[str]:
    messages = kwargs.get("messages") or []
    if not isinstance(messages, list):
        return None
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str):
                        return text
    return None


def _build_handler_class():
    """Build the ``HackAgentTrackingLogger`` class once litellm is importable."""
    CustomLogger = _try_import_custom_logger()
    if CustomLogger is None:
        return None

    class HackAgentTrackingLogger(CustomLogger):  # type: ignore[misc, valid-type]
        """Capture every HackAgent-owned ``litellm.completion`` call."""

        def log_pre_api_call(self, model, messages, kwargs):
            metadata = _extract_hackagent_metadata(kwargs)
            if metadata is None:
                return
            preview = ""
            for msg in reversed(messages or []):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    content = msg.get("content") or ""
                    preview = (content if isinstance(content, str) else "")[:120]
                    break
            _TRACKING_LOGGER.info(
                "litellm.pre",
                extra={
                    "hackagent_agent_id": metadata.get(HACKAGENT_AGENT_ID_KEY),
                    "hackagent_adapter_type": metadata.get(HACKAGENT_ADAPTER_TYPE_KEY),
                    "litellm_model": model,
                    "prompt_preview": preview,
                },
            )

        def log_success_event(self, kwargs, response_obj, start_time, end_time):
            metadata = _extract_hackagent_metadata(kwargs)
            if metadata is None:
                return
            text = _extract_response_text(response_obj) or ""
            response_preview = text[:200] if text else ""
            duration_ms = None
            try:
                duration_ms = (end_time - start_time).total_seconds() * 1000
            except (AttributeError, TypeError):
                pass
            _TRACKING_LOGGER.info(
                "litellm.success",
                extra={
                    "hackagent_agent_id": metadata.get(HACKAGENT_AGENT_ID_KEY),
                    "hackagent_adapter_type": metadata.get(HACKAGENT_ADAPTER_TYPE_KEY),
                    "litellm_model": kwargs.get("model"),
                    "litellm_call_id": kwargs.get("litellm_call_id"),
                    "response_preview": response_preview,
                    "response_cost": kwargs.get("response_cost"),
                    "duration_ms": duration_ms,
                    "prompt_preview": _last_user_message(kwargs),
                },
            )

        async def async_log_success_event(
            self, kwargs, response_obj, start_time, end_time
        ):
            self.log_success_event(kwargs, response_obj, start_time, end_time)

        def log_failure_event(self, kwargs, response_obj, start_time, end_time):
            metadata = _extract_hackagent_metadata(kwargs)
            if metadata is None:
                return
            duration_ms = None
            try:
                duration_ms = (end_time - start_time).total_seconds() * 1000
            except (AttributeError, TypeError):
                pass
            _TRACKING_LOGGER.warning(
                "litellm.failure",
                extra={
                    "hackagent_agent_id": metadata.get(HACKAGENT_AGENT_ID_KEY),
                    "hackagent_adapter_type": metadata.get(HACKAGENT_ADAPTER_TYPE_KEY),
                    "litellm_model": kwargs.get("model"),
                    "litellm_call_id": kwargs.get("litellm_call_id"),
                    "exception_repr": repr(kwargs.get("exception", response_obj)),
                    "duration_ms": duration_ms,
                    "prompt_preview": _last_user_message(kwargs),
                },
            )

        async def async_log_failure_event(
            self, kwargs, response_obj, start_time, end_time
        ):
            self.log_failure_event(kwargs, response_obj, start_time, end_time)

    return HackAgentTrackingLogger


def ensure_registered() -> bool:
    """Register the tracking logger on ``litellm.callbacks`` exactly once.

    Idempotent — safe to call from every ``AgentRouter.__init__``.
    Returns ``True`` when registration is in effect (either because we
    just registered or because we already had).
    """
    global _REGISTERED, _LOGGER_INSTANCE
    if _REGISTERED:
        return True

    handler_cls = _build_handler_class()
    if handler_cls is None:
        _TRACKING_LOGGER.debug(
            "litellm.integrations.custom_logger.CustomLogger unavailable; "
            "skipping HackAgentTrackingLogger registration."
        )
        return False

    try:
        import litellm
    except ImportError:
        return False

    instance = handler_cls()
    callbacks = list(getattr(litellm, "callbacks", None) or [])
    # Guard against re-adding ourselves if the user already imported us
    # in another module.
    already = any(getattr(cb, "__class__", None) is handler_cls for cb in callbacks)
    if not already:
        callbacks.append(instance)
        litellm.callbacks = callbacks

    _LOGGER_INSTANCE = instance
    _REGISTERED = True
    return True


def get_instance() -> Optional[Any]:
    """Return the singleton logger instance (mainly for tests)."""
    return _LOGGER_INSTANCE


def _reset_for_tests() -> None:
    """Reset the singleton state — only used by the unit tests."""
    global _REGISTERED, _LOGGER_INSTANCE
    _REGISTERED = False
    _LOGGER_INSTANCE = None
