# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Native ``Model`` base for agents driven through a locally installed CLI.

A CLI agent (Claude Code, Codex, Hermes) serves no HTTP endpoint. Each
instance registers a per-instance :class:`litellm.CustomLLM` handler under a
unique provider name whose ``completion`` shells out to the CLI, so the call
still flows through ``litellm.completion`` and comes back as a
:class:`ModelResponse` like every other backend.

Subclasses set the class attributes, read their own options in
:meth:`_configure`, and build the CLI handler in :meth:`_build_handler`.
"""

from __future__ import annotations

import asyncio
import shutil
from abc import abstractmethod
from typing import Any, ClassVar, Dict, List, Mapping, Optional, Sequence
from uuid import uuid4

from hackagent.core.contracts import ModelSpec
from hackagent.core.logging import get_logger
from hackagent.models.model import Model
from hackagent.models.response import ModelResponse


class CLIConfigurationError(Exception):
    """A CLI backend was configured wrongly (missing binary, model, litellm)."""


class CLIInteractionError(Exception):
    """A CLI backend failed while producing a response (timeout, bad exit)."""


def _litellm() -> Optional[Any]:
    """Import litellm lazily; return the module or ``None`` when missing."""
    try:
        import litellm

        return litellm
    except ImportError:
        return None


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


class SubprocessCLIModel(Model):
    """A :class:`Model` that answers each turn by running a local CLI."""

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

    def __init__(self, spec: ModelSpec) -> None:
        config = self._config_from_spec(spec)
        name = config.get("name")
        if not name:
            raise CLIConfigurationError(
                f"Missing required configuration key 'name' (the {self.LABEL} "
                f"model) for {type(self).__name__}."
            )

        self.spec = spec
        self.id = uuid4().hex
        self.logger = get_logger(f"hackagent.models.completions.{self.LABEL}.{self.id}")
        self.name: str = str(name)
        self.binary: str = config.get("binary") or self.DEFAULT_BINARY
        self.cwd: Optional[str] = config.get("cwd")
        self.timeout: int = int(config.get("timeout") or self.DEFAULT_TIMEOUT)
        self.extra_args: List[str] = list(config.get("extra_args") or [])
        self._configure(config)

        # A missing binary fails loudly here instead of mid-attack.
        if shutil.which(self.binary) is None:
            raise CLIConfigurationError(
                f"{self.LABEL} executable '{self.binary}' was not found on PATH. "
                f"{self.INSTALL_HINT} or set the 'binary' config to its full path."
            )

        self._provider_name = f"{self.PROVIDER_PREFIX}_{self.id}"
        self.litellm_model = f"{self._provider_name}/{self.name}"
        self.actual_api_key: Optional[str] = self.LITELLM_API_KEY
        self._register_custom_provider()

        self.logger.info(
            f"{type(self).__name__} '{self.id}' registered as LiteLLM provider "
            f"'{self._provider_name}' (binary={self.binary}, model={self.name})"
        )

    @staticmethod
    def _config_from_spec(spec: ModelSpec) -> Dict[str, Any]:
        """Flatten a spec into the config dict the CLI backends read."""
        config: Dict[str, Any] = dict(spec.extra)
        config["name"] = spec.identifier
        if spec.endpoint:
            config["endpoint"] = spec.endpoint
        for field in ("max_tokens", "temperature", "top_p", "timeout", "thinking"):
            value = getattr(spec, field, None)
            if value is not None:
                config[field] = value
        return config

    def _configure(self, config: Dict[str, Any]) -> None:
        """Read backend-specific options from ``config``."""

    @abstractmethod
    def _build_handler(self) -> Any:
        """Return the :class:`litellm.CustomLLM` that runs the CLI."""

    def _register_custom_provider(self) -> None:
        litellm = _litellm()
        if litellm is None:
            raise CLIConfigurationError(
                f"litellm is required for {type(self).__name__} but is not installed."
            )

        handler = self._build_handler()
        provider = self._provider_name
        # Replace any stale entry for this provider name (e.g. when a backend
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

    def _call(self, litellm: Any, messages: List[Dict[str, Any]]) -> Any:
        """Run one turn through LiteLLM. Raises on failure."""
        return litellm.completion(model=self.litellm_model, messages=messages)

    def complete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        litellm = _litellm()
        if litellm is None:
            return ModelResponse.failed(RuntimeError("litellm is not installed"))
        try:
            response = self._call(litellm, [dict(message) for message in messages])
        except Exception as exc:
            self.logger.exception(
                f"{self.LABEL} dispatch failed for backend {self.id}: {exc}"
            )
            return ModelResponse.failed(exc)
        return ModelResponse.from_value(response)

    async def acomplete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        return await asyncio.to_thread(self.complete, messages, **overrides)


__all__ = [
    "CLIConfigurationError",
    "CLIInteractionError",
    "SubprocessCLIModel",
    "last_user_text",
]
