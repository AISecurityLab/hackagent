# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Ollama adapter built on top of LiteLLM.

LiteLLM ships with an ``ollama_chat`` provider that targets a local or
remote Ollama server's ``/api/chat`` endpoint, so we no longer have to
hand-roll the HTTP calls. This adapter just pins the provider prefix,
normalises the endpoint URL the way the previous direct adapter did, and
translates the unified ``thinking`` knob into Ollama's ``think`` parameter.
"""

import os
from hackagent.logger import get_logger
from typing import Any, Dict, List, Optional

from .base import AdapterConfigurationError
from .litellm import LiteLLMAgent


class OllamaConfigurationError(AdapterConfigurationError):
    """Custom exception for Ollama adapter configuration issues."""

    pass


logger = get_logger(__name__)


class OllamaAgent(LiteLLMAgent):
    """
    Adapter for an Ollama server.

    Configuration:
        - ``name``: Ollama model tag (e.g. ``"llama3"``, ``"mistral"``).
        - ``endpoint`` (optional): Ollama base URL. Defaults to
          ``$OLLAMA_BASE_URL`` if set, otherwise ``http://localhost:11434``.
          API-path suffixes such as ``/api/chat`` are stripped automatically
          so users can paste their browser URL.
        - ``thinking`` (optional): see :class:`LiteLLMAgent` for the
          accepted shapes. Translated into Ollama's native ``think`` field.
        - ``top_k`` / ``num_ctx`` / ``stream`` (optional): forwarded as
          Ollama generation options.
    """

    ADAPTER_TYPE = "OllamaAgent"
    PROVIDER_PREFIX = "ollama_chat"
    DEFAULT_ENDPOINT = "http://localhost:11434"

    def __init__(self, id: str, config: Dict[str, Any]):
        # Resolve and normalise the endpoint before delegating to the base.
        effective_endpoint = config.get("endpoint") or os.environ.get(
            "OLLAMA_BASE_URL", self.DEFAULT_ENDPOINT
        )
        effective_endpoint = self._normalize_endpoint(effective_endpoint)
        config = {**config, "endpoint": effective_endpoint}

        try:
            super().__init__(id, config)
        except AdapterConfigurationError as e:
            raise OllamaConfigurationError(str(e)) from e

        # Ollama-specific generation options that LiteLLM forwards via
        # ``optional_params`` (any extra kwarg passed to
        # ``litellm.completion`` for the ``ollama_chat`` provider).
        self.default_top_k = self._get_config_key("top_k")
        self.default_num_ctx = self._get_config_key("num_ctx")
        self.default_stream = self._get_config_key("stream", False)

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> str:
        """Strip trailing slash and Ollama API path suffixes from ``endpoint``."""
        endpoint = endpoint.rstrip("/")
        for suffix in ("/api/generate", "/api/chat", "/api/tags", "/api/show", "/api"):
            if endpoint.endswith(suffix):
                endpoint = endpoint[: -len(suffix)]
                break
        return endpoint

    # ---- request shaping ------------------------------------------------

    def _get_completion_parameters(
        self, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Inject Ollama-specific defaults (top_k, num_ctx, stream)."""
        params = super()._get_completion_parameters(request_data)
        if "top_k" not in params and self.default_top_k is not None:
            params["top_k"] = self.default_top_k
        if "num_ctx" not in params and self.default_num_ctx is not None:
            params["num_ctx"] = self.default_num_ctx
        if "stream" not in params and self.default_stream:
            params["stream"] = self.default_stream
        return params

    def _get_excluded_request_keys(self) -> set:
        base = super()._get_excluded_request_keys()
        return base | {"top_k", "num_ctx", "stream", "system"}

    def _apply_thinking(self, litellm_params: Dict[str, Any], thinking: Any) -> None:
        """Translate ``thinking`` into Ollama's native ``think`` field.

        Ollama accepts a boolean (``true``/``false``) or a reasoning level
        such as ``"low"``/``"medium"``/``"high"`` depending on the model.
        Dicts and ints are coerced into the most reasonable boolean.
        """
        if thinking is None:
            return
        if isinstance(thinking, bool):
            litellm_params["think"] = thinking
        elif isinstance(thinking, str):
            litellm_params["think"] = thinking
        elif isinstance(thinking, int):
            litellm_params["think"] = thinking > 0
        elif isinstance(thinking, dict):
            kind = (thinking.get("type") or "").lower()
            if kind == "disabled":
                litellm_params["think"] = False
            else:
                litellm_params["think"] = True
        else:
            litellm_params["think"] = bool(thinking)

    # ---- diagnostics passthroughs (kept for callers/tests) --------------

    def list_models(self) -> List[Dict[str, Any]]:
        """Return models reported by ``GET {endpoint}/api/tags``."""
        import requests

        try:
            response = requests.get(f"{self.api_base_url}/api/tags", timeout=30)
            response.raise_for_status()
            return response.json().get("models", [])
        except Exception as e:
            self.logger.error(f"Failed to list Ollama models: {e}")
            return []

    def model_info(self) -> Dict[str, Any]:
        """Return ``POST {endpoint}/api/show`` payload for the current model."""
        import requests

        try:
            response = requests.post(
                f"{self.api_base_url}/api/show",
                json={"name": self.model_name},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Failed to get model info for '{self.model_name}': {e}")
            return {}

    def is_available(self) -> bool:
        """True iff the configured model appears in ``/api/tags``."""
        try:
            models = self.list_models()
            if not self.model_name:
                return False
            base_model = self.model_name.split(":")[0]
            names: List[Optional[str]] = [m.get("name") for m in models]
            base_names = [(m.get("name") or "").split(":")[0] for m in models]
            return base_model in base_names or self.model_name in names
        except Exception:
            return False
