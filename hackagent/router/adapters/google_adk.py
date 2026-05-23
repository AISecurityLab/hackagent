# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Google ADK (Agent Development Kit) adapter built on top of LiteLLM.

LiteLLM has no built-in provider for the ADK server protocol (POST /run
with sessions and events), so issue #379 routes ADK through LiteLLM by
registering a per-instance :class:`litellm.CustomLLM` handler under a
unique provider name. The HTTP transport against the deployed ADK server
lives in the lazily-defined ``_ADKCustomLLM`` class, while
:class:`ADKAgent` itself is a thin :class:`LiteLLMAgent` subclass that
registers the handler and asks LiteLLM to route through it.
"""

import json
import uuid
from hackagent.logger import get_logger
from typing import Any, Dict, List, Optional

import requests

from .base import (
    AdapterConfigurationError,
    AdapterInteractionError,
    AdapterResponseParsingError,
)
from .litellm import LiteLLMAgent, _get_litellm


logger = get_logger(__name__)


# --- Custom exceptions (kept for backwards compatibility) ---
class AgentConfigurationError(AdapterConfigurationError):
    """ADK adapter configuration issues."""

    pass


class AgentInteractionError(AdapterInteractionError):
    """Errors interacting with the ADK agent server."""

    pass


class ResponseParsingError(AdapterResponseParsingError):
    """Errors parsing the ADK server's event-list response."""

    pass


_ADK_PROVIDER_PREFIX = "hackagent_adk"


def _last_user_text(messages: List[Dict[str, Any]]) -> Optional[str]:
    """Return the text of the last user message in ``messages``."""
    for msg in reversed(messages or []):
        if (msg or {}).get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content
        # OpenAI-style content lists.
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str):
                        return text
    return None


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

    Defined as a function instead of a module-level class so this module
    keeps loading even when litellm is missing — the LiteLLMAgent base
    will raise a clear error before anyone tries to actually use ADK.
    """
    global _ADK_CUSTOM_LLM_CLASS
    if _ADK_CUSTOM_LLM_CLASS is not None:
        return _ADK_CUSTOM_LLM_CLASS

    from litellm import CustomLLM
    from litellm.types.utils import ModelResponse

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

        # ---- ADK transport (kept close to the previous implementation) ---

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
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                return
            except requests.exceptions.HTTPError as http_err:
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
                raise AgentInteractionError(
                    f"HTTP Error {status_code} creating session "
                    f"{session_id}: {response_text[:200]}"
                ) from http_err
            except requests.exceptions.RequestException as e:
                raise AgentInteractionError(
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
                response = requests.post(
                    url, headers=headers, json=payload, timeout=self.timeout
                )
            except requests.exceptions.Timeout as e:
                raise AgentInteractionError(f"Request timed out: {e}") from e
            except requests.exceptions.RequestException as e:
                raise AgentInteractionError(f"Request failed: {e}") from e

            response_body = response.text
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as http_err:
                raise AgentInteractionError(
                    f"HTTP Error: {response.status_code}"
                ) from http_err

            try:
                events = response.json()
            except (json.JSONDecodeError, ValueError) as parse_err:
                raise ResponseParsingError(
                    f"JSON parse failed: {parse_err}. Body: {response_body[:200]}"
                ) from parse_err

            if not isinstance(events, list):
                if isinstance(events, dict) and "detail" in events:
                    raise ResponseParsingError(
                        f"ADK returned detail message: {events['detail']}"
                    )
                raise ResponseParsingError(
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
            model_response: ModelResponse = (
                kwargs.get("model_response") or ModelResponse()
            )

            prompt_text = _last_user_text(messages)
            if not prompt_text:
                raise AgentInteractionError(
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

            # Stash ADK-specific bits where the outer adapter can find them.
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


class ADKAgent(LiteLLMAgent):
    """
    Adapter for a deployed Google ADK agent server.

    The request travels through LiteLLM via a per-instance
    :class:`CustomLLM` handler registered as
    ``hackagent_adk_<id>/<app_name>``. From the router's perspective this
    is just another LiteLLM agent.

    Required config:
        - ``name``: ADK app name (used as both the model string and the
          ``app_name`` in the request payload).
        - ``endpoint``: ADK server base URL.
        - ``user_id``: User ID for ADK sessions.

    Optional config:
        - ``timeout`` (seconds, default 120).
        - ``session_id``: sticky session ID; if unset a UUID is generated.
        - ``fresh_session_per_request`` (default True): if True, every
          request gets a brand-new session unless the caller supplies one.
    """

    ADAPTER_TYPE = "ADKAgent"

    def __init__(self, id: str, config: Dict[str, Any]):
        for key in ("name", "endpoint", "user_id"):
            if key not in config:
                raise AgentConfigurationError(
                    f"Missing required configuration key '{key}' for ADKAgent: {id}"
                )

        # Provider name is per-instance so each ADKAgent gets its own handler.
        # Set on self before super().__init__ runs so that the base's call to
        # _resolve_litellm_model (overridden below) sees the right value.
        self._provider_name = f"{_ADK_PROVIDER_PREFIX}_{id}"

        adk_endpoint = str(config["endpoint"]).strip("/")
        adk_user_id = config["user_id"]
        adk_app_name = config["name"]
        adk_timeout = int(config.get("timeout", 120))
        fresh = bool(config.get("fresh_session_per_request", True))
        session_id = config.get("session_id") or str(uuid.uuid4())

        # The base passes ``endpoint`` along to LiteLLM as ``api_base``; we
        # don't want that since our custom provider hits ADK directly.
        base_config = {k: v for k, v in config.items() if k != "endpoint"}
        super().__init__(id, base_config)

        self.endpoint = adk_endpoint
        self.user_id = adk_user_id
        self.name = adk_app_name
        self.timeout = adk_timeout
        self.fresh_session_per_request = fresh
        self.session_id = session_id

        self._register_custom_provider()

        self.logger.info(
            f"ADKAgent '{self.id}' registered as LiteLLM provider "
            f"'{self._provider_name}' targeting {self.endpoint} "
            f"(app={self.name}, session={self.session_id}, "
            f"fresh_session_per_request={self.fresh_session_per_request})"
        )

    def _register_custom_provider(self) -> None:
        litellm, available = _get_litellm()
        if not available:
            raise AgentConfigurationError(
                "litellm is required for ADKAgent but is not installed."
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
        # Replace any stale entry for this provider name (e.g. when an
        # ADKAgent with the same id is re-created during tests).
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

    def _resolve_litellm_model(self, raw_model: str) -> str:
        return f"{self._provider_name}/{raw_model}"

    # ---- forward ADK-specific request fields ----------------------------

    def _get_completion_parameters(
        self, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        params = super()._get_completion_parameters(request_data)
        session_id = request_data.get("session_id", request_data.get("adk_session_id"))
        if session_id:
            params["session_id"] = session_id
        if "initial_session_state" in request_data:
            params["initial_session_state"] = request_data["initial_session_state"]
        return params

    def _get_excluded_request_keys(self) -> set:
        base = super()._get_excluded_request_keys()
        return base | {"session_id", "adk_session_id", "initial_session_state"}

    def _build_agent_specific_data(
        self,
        completion_result: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        data = super()._build_agent_specific_data(completion_result, parameters)
        raw = completion_result.get("raw_response")
        adk_fields: Dict[str, Any] = {}
        try:
            adk_fields = (
                getattr(raw.choices[0].message, "provider_specific_fields", None) or {}
            )
        except (AttributeError, IndexError, TypeError):
            adk_fields = {}
        events = adk_fields.get("adk_events_list")
        if events is not None:
            data["adk_events_list"] = events
        if "adk_session_id" in adk_fields:
            data["adk_session_id"] = adk_fields["adk_session_id"]
        return data
