# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Base class for agents driven through a locally installed CLI.

A CLI agent (Claude Code, Codex, Hermes) serves no HTTP endpoint. Each
instance registers a per-instance :class:`litellm.CustomLLM` handler under a
unique provider name; the handler shells out to the CLI. Requests still flow
through ``litellm.completion`` and are captured by the HackAgent LiteLLM
callbacks like every other provider.

Subclasses set the class attributes, read their own options in
:meth:`SubprocessCLIAgent._configure`, and build the CLI handler in
:meth:`SubprocessCLIAgent._build_handler`.
"""

from __future__ import annotations

import shutil
from abc import abstractmethod
from typing import Any, ClassVar, Dict, List, Optional

from hackagent.models import envelope as _envelope
from hackagent.models.adapters.base import (
    AdapterConfigurationError,
    Agent,
    get_litellm,
)


def last_user_text(messages: List[Dict[str, Any]]) -> Optional[str]:
    """Return the text of the last user message in ``messages``."""
    for msg in reversed(messages or []):
        if (msg or {}).get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):  # OpenAI-style content parts
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str):
                        return text
    return None


class SubprocessCLIAgent(Agent):
    """An agent that answers each turn by running a local CLI."""

    #: Human-readable product name used in messages ("Claude Code").
    LABEL: ClassVar[str]
    #: Prefix of the per-instance LiteLLM provider name.
    PROVIDER_PREFIX: ClassVar[str]
    #: Executable looked up on ``PATH`` when no ``binary`` is configured.
    DEFAULT_BINARY: ClassVar[str]
    #: How to install the CLI, shown when the binary is missing.
    INSTALL_HINT: ClassVar[str]
    #: Default per-turn timeout in seconds.
    DEFAULT_TIMEOUT: ClassVar[int] = 300
    #: API key passed to LiteLLM; the CLIs handle their own authentication.
    LITELLM_API_KEY: ClassVar[Optional[str]] = None

    def __init__(self, id: str, config: Dict[str, Any]):
        if "name" not in config:
            raise AdapterConfigurationError(
                f"Missing required configuration key 'name' (the {self.LABEL} "
                f"model) for {type(self).__name__}: {id}"
            )

        super().__init__(id, config)
        self._init_generation_params()

        self.name: str = config["name"]
        self.model_name = self.name  # for the base ``Agent`` envelope helpers
        self.binary: str = config.get("binary") or self.DEFAULT_BINARY
        self.cwd: Optional[str] = config.get("cwd")
        self.timeout: int = int(config.get("timeout", self.DEFAULT_TIMEOUT))
        self.extra_args: List[str] = list(config.get("extra_args") or [])
        self._configure(config)

        # A missing binary fails loudly here instead of mid-attack.
        if shutil.which(self.binary) is None:
            raise AdapterConfigurationError(
                f"{self.LABEL} executable '{self.binary}' was not found on PATH. "
                f"{self.INSTALL_HINT} or set the 'binary' config to its full path."
            )

        self._provider_name = f"{self.PROVIDER_PREFIX}_{id}"
        self.litellm_model = f"{self._provider_name}/{self.name}"
        self.api_base_url: Optional[str] = config.get("endpoint", "http://localhost")
        self.actual_api_key: Optional[str] = self.LITELLM_API_KEY
        self.default_thinking = None
        self.default_tools = None
        self.default_tool_choice = None
        self.default_extra_body = None

        self._register_custom_provider()

        self.logger.info(
            f"{type(self).__name__} '{self.id}' registered as LiteLLM provider "
            f"'{self._provider_name}' (binary={self.binary}, model={self.name})"
        )

    def _configure(self, config: Dict[str, Any]) -> None:
        """Read adapter-specific options from ``config``."""

    @abstractmethod
    def _build_handler(self) -> Any:
        """Return the :class:`litellm.CustomLLM` that runs the CLI."""

    def _register_custom_provider(self) -> None:
        litellm, available = get_litellm()
        if not available:
            raise AdapterConfigurationError(
                f"litellm is required for {type(self).__name__} but is not installed."
            )

        handler = self._build_handler()
        provider = self._provider_name
        # Replace any stale entry for this provider name (e.g. when an agent
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

    def _complete(self, litellm: Any, messages: List[Dict[str, Any]]) -> Any:
        """Run one turn through LiteLLM. Raises on failure."""
        return litellm.completion(model=self.litellm_model, messages=messages)

    def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send one CLI turn via ``litellm.completion`` and wrap the reply."""
        is_valid, prompt_text, messages = self._validate_request(request_data)
        if not is_valid:
            return self._build_error_response(
                error_message=(
                    "Request data must include either 'messages' or 'prompt' field."
                ),
                status_code=400,
                raw_request=request_data,
            )
        if not messages:
            messages = self._prompt_to_messages(prompt_text)  # type: ignore[arg-type]

        litellm, available = get_litellm()
        if not available:
            return self._build_error_response(
                error_message="litellm is not installed",
                status_code=500,
                raw_request=request_data,
            )

        try:
            response = self._complete(litellm, messages)
        except Exception as exc:
            self.logger.exception(
                f"{self.LABEL} dispatch failed for agent {self.id}: {exc}"
            )
            return self._build_error_response(
                error_message=(
                    f"{self.ADAPTER_TYPE} error ({type(exc).__name__}): {exc}"
                ),
                status_code=500,
                raw_request=request_data,
            )

        text = _envelope.extract_text_from_response(
            response, model_name=self.litellm_model
        )
        if isinstance(text, str) and text.startswith("[GENERATION_ERROR:"):
            return self._build_error_response(
                error_message=f"{self.ADAPTER_TYPE} generation error: {text}",
                status_code=500,
                raw_request=request_data,
            )

        return self._build_success_response(
            processed_response=text,
            raw_request=request_data,
            raw_response_body=response,
            agent_specific_data=_envelope.build_agent_specific_data(
                model_name=self.litellm_model,
                invoked_parameters={"model": self.name},
            ),
        )
