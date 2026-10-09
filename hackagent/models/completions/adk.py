# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Google ADK backend: proxy to an ADK server through a LiteLLM custom provider.

LiteLLM has no built-in provider for the ADK server protocol (``POST /run``
with sessions and events), so ADK is routed through LiteLLM by registering a
per-instance :class:`litellm.CustomLLM` handler under a unique provider name.
The HTTP transport against the deployed ADK server lives in the lazily-defined
``_ADKCustomLLM`` class, while :class:`ADKModel` registers the handler and
dispatches requests through ``litellm.completion``, returning a
:class:`ModelResponse` like every other backend.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from typing import Any, Dict, List, Mapping, Optional, Sequence

import httpx

from hackagent.core.contracts import ModelSpec
from hackagent.core.logging import get_logger
from hackagent.models.completions.cli import _litellm, last_user_text
from hackagent.models.model import Model
from hackagent.models.response import ModelResponse

logger = get_logger(__name__)


class ADKConfigurationError(Exception):
    """ADK backend configuration issues (missing name/endpoint/user_id)."""


class ADKInteractionError(Exception):
    """Errors interacting with the ADK agent server."""


class ADKResponseParsingError(Exception):
    """Errors parsing the ADK server's event-list response."""


_ADK_PROVIDER_PREFIX = "hackagent_adk"
#: ADK sessions need a user id; used when the spec does not carry one. Matches
#: the default the legacy dispatch layer applied.
DEFAULT_ADK_USER_ID = "hackagent"


def _extract_final_text(events: List[Dict[str, Any]]) -> Optional[str]:
    """Walk ``events`` newest-first and return the agent's final reply."""
    for event in reversed(events):
        actions = event.get("actions")
        if actions and isinstance(actions, dict) and actions.get("escalate"):
            error_msg = event.get(
                "error_message",
                "No specific message provided by agent for escalation.",
            )
            return f"Agent escalated: {error_msg}"

        content = event.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list) or not parts:
            continue
        first = parts[0]
        if not isinstance(first, dict):
            continue
        text = first.get("text")
        if isinstance(text, str) and text.strip():
            return text
    return None


_ADK_CUSTOM_LLM_CLASS = None


def _get_adk_custom_llm_class():
    """Lazily build the CustomLLM subclass once litellm is importable.

    Defined as a function instead of a module-level class so this module keeps
    loading even when litellm is missing — ``ADKModel`` raises a clear
    ``ADKConfigurationError`` from ``_register_custom_provider`` if someone
    actually tries to use it without litellm installed.
    """
    global _ADK_CUSTOM_LLM_CLASS
    if _ADK_CUSTOM_LLM_CLASS is not None:
        return _ADK_CUSTOM_LLM_CLASS

    from litellm import CustomLLM
    from litellm.types.utils import ModelResponse as LiteLLMModelResponse

    class _ADKCustomLLM(CustomLLM):
        """LiteLLM CustomLLM handler that proxies to an ADK server."""

        def __init__(
            self,
            *,
            endpoint: str,
            app_name: str,
            user_id: str,
            default_session_id: str,
            fresh_session_per_request: bool,
            timeout: int,
            log,
        ):
            super().__init__()
            self.endpoint = endpoint.rstrip("/")
            self.app_name = app_name
            self.user_id = user_id
            self.default_session_id = default_session_id
            self.fresh_session_per_request = fresh_session_per_request
            self.timeout = timeout
            self.logger = log

        # ---- ADK transport ------------------------------------------------

        def _create_session(
            self, session_id: str, initial_state: Optional[dict] = None
        ) -> None:
            url = (
                f"{self.endpoint}/apps/{self.app_name}/users/"
                f"{self.user_id}/sessions/{session_id}"
            )
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = initial_state or {}
            session_timeout = min(30, max(1, int(self.timeout)))
            try:
                response = httpx.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=session_timeout,
                )
                response.raise_for_status()
                return
            except httpx.HTTPStatusError as http_err:
                response_text = ""
                status_code = None
                if http_err.response is not None:
                    status_code = http_err.response.status_code
                    try:
                        response_text = http_err.response.text or ""
                    except Exception:
                        response_text = ""
                if status_code == 409:
                    return
                if (
                    status_code == 400
                    and "session already exists" in response_text.lower()
                ):
                    return
                raise ADKInteractionError(
                    f"HTTP Error {status_code} creating session "
                    f"{session_id}: {response_text[:200]}"
                ) from http_err
            except httpx.RequestError as e:
                raise ADKInteractionError(
                    f"Request failed creating session {session_id}: {e}"
                ) from e

        def _run(self, prompt_text: str, session_id: str) -> Dict[str, Any]:
            url = f"{self.endpoint}/run"
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = {
                "app_name": self.app_name,
                "user_id": self.user_id,
                "session_id": session_id,
                "new_message": {
                    "role": "user",
                    "parts": [{"text": prompt_text}],
                },
            }

            try:
                response = httpx.post(
                    url, headers=headers, json=payload, timeout=self.timeout
                )
            except httpx.TimeoutException as e:
                raise ADKInteractionError(f"Request timed out: {e}") from e
            except httpx.RequestError as e:
                raise ADKInteractionError(f"Request failed: {e}") from e

            response_body = response.text
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as http_err:
                raise ADKInteractionError(
                    f"HTTP Error: {response.status_code}"
                ) from http_err

            try:
                events = response.json()
            except (json.JSONDecodeError, ValueError) as parse_err:
                raise ADKResponseParsingError(
                    f"JSON parse failed: {parse_err}. Body: {response_body[:200]}"
                ) from parse_err

            if not isinstance(events, list):
                if isinstance(events, dict) and "detail" in events:
                    raise ADKResponseParsingError(
                        f"ADK returned detail message: {events['detail']}"
                    )
                raise ADKResponseParsingError(
                    "ADK response format unrecognized (not a list)."
                )

            return {
                "events": events,
                "raw_request": payload,
                "raw_response_body": response_body,
                "raw_response_headers": dict(response.headers),
                "status_code": response.status_code,
                "final_text": _extract_final_text(events),
            }

        # ---- LiteLLM CustomLLM API ---------------------------------------

        def completion(self, *args, **kwargs):
            """Translate a LiteLLM completion call into an ADK /run request."""
            messages = kwargs.get("messages") or []
            optional_params = kwargs.get("optional_params") or {}
            model_response: LiteLLMModelResponse = (
                kwargs.get("model_response") or LiteLLMModelResponse()
            )

            prompt_text = last_user_text(messages)
            if not prompt_text:
                raise ADKInteractionError(
                    "ADK adapter requires at least one user message with text content."
                )

            session_id = optional_params.get("session_id")
            if not session_id:
                session_id = (
                    str(uuid.uuid4())
                    if self.fresh_session_per_request
                    else self.default_session_id
                )
            initial_state = optional_params.get("initial_session_state")

            self.logger.info(
                f"🌐 ADK run for app '{self.app_name}' (session {session_id})"
            )
            self._create_session(session_id=session_id, initial_state=initial_state)
            result = self._run(prompt_text=prompt_text, session_id=session_id)

            final_text = result["final_text"] or ""
            model_response.choices[0].message.content = final_text  # type: ignore[attr-defined]
            try:
                model_response.choices[0].finish_reason = "stop"  # type: ignore[attr-defined]
            except Exception:
                pass
            model_response.model = (
                kwargs.get("model") or f"{_ADK_PROVIDER_PREFIX}/{self.app_name}"
            )

            # Stash ADK-specific bits where the outer backend can find them.
            try:
                model_response.choices[0].message.provider_specific_fields = {  # type: ignore[attr-defined]
                    "adk_events_list": result["events"],
                    "adk_session_id": session_id,
                    "adk_raw_response_body": result["raw_response_body"],
                    "adk_raw_request": result["raw_request"],
                    "adk_status_code": result["status_code"],
                }
            except Exception:
                pass
            return model_response

        async def acompletion(self, *args, **kwargs):
            """Async wrapper — run the sync ADK transport in a worker thread."""
            import asyncio

            return await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.completion(*args, **kwargs)
            )

    _ADK_CUSTOM_LLM_CLASS = _ADKCustomLLM
    return _ADKCustomLLM


class ADKModel(Model):
    """Native backend for a deployed Google ADK agent server.

    Each instance registers its own :class:`litellm.CustomLLM` handler under a
    unique provider name (``hackagent_adk_<id>``) so the call goes through
    ``litellm.completion`` like every other LiteLLM provider — even though
    LiteLLM has no built-in knowledge of the ADK ``POST /run`` + sessions +
    events protocol.

    Required config:
        - ``name``: ADK app name (used as both the model string and the
          ``app_name`` in the request payload).
        - ``endpoint``: ADK server base URL.
        - ``user_id``: User ID for ADK sessions (read from ``spec.extra``).

    Optional config:
        - ``timeout`` (seconds, default 120).
        - ``session_id``: sticky session ID; if unset a UUID is generated.
        - ``fresh_session_per_request`` (default True): if True, every request
          gets a brand-new session unless the caller supplies one.
    """

    def __init__(self, spec: ModelSpec) -> None:
        extra = dict(spec.extra)
        name = spec.identifier
        endpoint = spec.endpoint
        user_id = extra.get("user_id") or DEFAULT_ADK_USER_ID
        missing = [
            key for key, value in (("name", name), ("endpoint", endpoint)) if not value
        ]
        if missing:
            raise ADKConfigurationError(
                f"Missing required configuration key(s) {missing} for ADKModel."
            )

        self.spec = spec
        self.id = uuid.uuid4().hex
        self.logger = get_logger(f"hackagent.models.completions.ADK.{self.id}")
        self.name: str = str(name)
        self.endpoint: str = str(endpoint).strip("/")
        self.user_id: str = str(user_id)
        self.timeout: int = int(spec.timeout or extra.get("timeout") or 120)
        self.fresh_session_per_request: bool = bool(
            extra.get("fresh_session_per_request", True)
        )
        self.session_id: str = extra.get("session_id") or str(uuid.uuid4())

        self._provider_name = f"{_ADK_PROVIDER_PREFIX}_{self.id}"
        self.litellm_model = f"{self._provider_name}/{self.name}"
        self._register_custom_provider()

        self.logger.info(
            f"ADKModel '{self.id}' registered as LiteLLM provider "
            f"'{self._provider_name}' targeting {self.endpoint} "
            f"(app={self.name}, session={self.session_id}, "
            f"fresh_session_per_request={self.fresh_session_per_request})"
        )

    def _register_custom_provider(self) -> None:
        litellm = _litellm()
        if litellm is None:
            raise ADKConfigurationError(
                "litellm is required for ADKModel but is not installed."
            )

        handler_cls = _get_adk_custom_llm_class()
        handler = handler_cls(
            endpoint=self.endpoint,
            app_name=self.name,
            user_id=self.user_id,
            default_session_id=self.session_id,
            fresh_session_per_request=self.fresh_session_per_request,
            timeout=self.timeout,
            log=self.logger,
        )

        provider = self._provider_name
        # Replace any stale entry for this provider name (e.g. when an ADKModel
        # with the same id is re-created during tests).
        litellm.custom_provider_map = [
            entry
            for entry in litellm.custom_provider_map
            if entry.get("provider") != provider
        ]
        litellm.custom_provider_map.append(
            {"provider": provider, "custom_handler": handler}
        )
        if provider not in litellm._custom_providers:
            litellm._custom_providers.append(provider)

        self._custom_handler = handler

    def _adk_fields(self, response: Any) -> Dict[str, Any]:
        """Pull the ADK events/session the handler stashed on the reply."""
        try:
            fields = (
                getattr(response.choices[0].message, "provider_specific_fields", None)
                or {}
            )
        except (AttributeError, IndexError, TypeError):
            return {}
        captured: Dict[str, Any] = {}
        if fields.get("adk_events_list") is not None:
            captured["adk_events_list"] = fields["adk_events_list"]
        if "adk_session_id" in fields:
            captured["adk_session_id"] = fields["adk_session_id"]
        return captured

    def complete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        litellm = _litellm()
        if litellm is None:
            return ModelResponse.failed(RuntimeError("litellm is not installed"))

        # ``session_id`` / ``initial_session_state`` reach the custom handler
        # through LiteLLM's ``optional_params``. ``adk_session_id`` is a legacy
        # alias for the session id.
        session_id = overrides.get("session_id") or overrides.get("adk_session_id")
        initial_session_state = overrides.get("initial_session_state")
        kwargs: Dict[str, Any] = {
            "model": self.litellm_model,
            "messages": [dict(message) for message in messages],
        }
        if session_id:
            kwargs["session_id"] = session_id
        if initial_session_state is not None:
            kwargs["initial_session_state"] = initial_session_state

        try:
            response = litellm.completion(**kwargs)
        except Exception as exc:
            self.logger.exception(f"ADK dispatch failed for backend {self.id}: {exc}")
            return ModelResponse.failed(exc)

        result = ModelResponse.from_value(response)
        adk = self._adk_fields(response)
        if adk:
            result = replace(result, metadata={**result.metadata, **adk})
        return result

    async def acomplete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        import asyncio

        return await asyncio.to_thread(self.complete, messages, **overrides)


__all__ = [
    "ADKConfigurationError",
    "ADKInteractionError",
    "ADKModel",
    "ADKResponseParsingError",
]
