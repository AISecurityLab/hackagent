# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Integration tests for ``AgentRouter._dispatch_via_litellm``.

These exercise the post-#379 hot path end-to-end: a real
``AgentRouter`` is created, the call goes through ``litellm.completion``
against a real provider (OpenAI by default, OpenRouter on CI), and the
returned dict is validated against the envelope shape.

The old per-class integration tests (``test_litellm.py``,
``test_openai.py``, ``test_ollama.py``) were removed in Phase E.2c when
the corresponding adapter classes were deleted. This file replaces
that coverage at the level the router actually operates.

Skipped automatically when no ``OPENAI_API_KEY`` / ``OPENROUTER_API_KEY``
is configured — CI runs them when those env vars are present.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import pytest

from hackagent.router._chat_registration import _ChatRegistration
from hackagent.router.router import AgentRouter
from hackagent.router.tracking_logger import HACKAGENT_METADATA_KEY
from hackagent.router.types import AgentTypeEnum

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.openai_sdk
class TestRouterLiteLLMDispatchIntegration:
    """Hit a real OpenAI-compatible endpoint via ``AgentRouter.route_request``."""

    def test_router_dispatch_returns_standardised_envelope(
        self,
        skip_if_openai_unavailable,
        skip_if_no_hackagent_key,
        hackagent_api_base_url: str,
        hackagent_api_key: str,
        openai_config: Dict[str, Any],
        openai_base_url: str,
    ):
        from hackagent.server.client import AuthenticatedClient
        from hackagent.server.storage.remote import RemoteBackend

        backend = RemoteBackend(
            AuthenticatedClient(
                base_url=hackagent_api_base_url,
                token=hackagent_api_key,
                prefix="Bearer",
            )
        )

        # Use AgentTypeEnum.LITELLM so the model string carries the
        # provider prefix already supplied via openai_config["name"].
        router = AgentRouter(
            backend=backend,
            name=openai_config["name"],
            agent_type=AgentTypeEnum.OPENAI_SDK,
            endpoint=openai_base_url,
            metadata={"name": openai_config["name"]},
            adapter_operational_config=openai_config,
        )
        reg_key = str(router.backend_agent.id)

        # The registry should hold a _ChatRegistration (Phase E.2b).
        registration = router.get_agent_instance(reg_key)
        assert isinstance(registration, _ChatRegistration)

        response = router.route_request(
            reg_key,
            {
                "messages": [
                    {"role": "system", "content": "Reply with the single word OK."},
                    {"role": "user", "content": "Acknowledge."},
                ],
                "max_tokens": 16,
                "temperature": 0.0,
            },
        )

        # ---- envelope shape ----
        assert response["status_code"] == 200, response.get("error_message")
        assert response["error_message"] is None
        assert isinstance(response["processed_response"], str)
        assert response["processed_response"], "expected non-empty text"
        assert response["generated_text"] == response["processed_response"]
        assert response["agent_id"] == reg_key
        assert response["adapter_type"] == registration.ADAPTER_TYPE

        agent_data = response["agent_specific_data"]
        assert agent_data["model_name"] == registration.litellm_model
        # F.1 — usage + finish_reason should flow through.
        assert agent_data.get("usage"), "expected usage data from LiteLLM"
        assert "finish_reason" in agent_data

    def test_router_dispatch_supports_prompt_field(
        self,
        skip_if_openai_unavailable,
        skip_if_no_hackagent_key,
        hackagent_api_base_url: str,
        hackagent_api_key: str,
        openai_config: Dict[str, Any],
        openai_base_url: str,
    ):
        """Backwards-compatible ``prompt`` shorthand should still work."""
        from hackagent.server.client import AuthenticatedClient
        from hackagent.server.storage.remote import RemoteBackend

        backend = RemoteBackend(
            AuthenticatedClient(
                base_url=hackagent_api_base_url,
                token=hackagent_api_key,
                prefix="Bearer",
            )
        )
        router = AgentRouter(
            backend=backend,
            name=openai_config["name"],
            agent_type=AgentTypeEnum.OPENAI_SDK,
            endpoint=openai_base_url,
            metadata={"name": openai_config["name"]},
            adapter_operational_config=openai_config,
        )
        reg_key = str(router.backend_agent.id)

        response = router.route_request(
            reg_key,
            {"prompt": "Reply with the single word OK.", "max_tokens": 8},
        )
        assert response["status_code"] == 200, response.get("error_message")
        assert isinstance(response["processed_response"], str)

    def test_router_attaches_hackagent_metadata_namespace(
        self,
        skip_if_openai_unavailable,
        skip_if_no_hackagent_key,
        hackagent_api_base_url: str,
        hackagent_api_key: str,
        openai_config: Dict[str, Any],
        openai_base_url: str,
    ):
        """Phase F.2 — every dispatched call carries ``metadata['hackagent']``."""
        import litellm

        from hackagent.server.client import AuthenticatedClient
        from hackagent.server.storage.remote import RemoteBackend

        # Spy on litellm.completion to capture the kwargs without disabling it.
        captured: Dict[str, Any] = {}
        original_completion = litellm.completion

        def spy(**kwargs):
            captured.update(kwargs)
            return original_completion(**kwargs)

        backend = RemoteBackend(
            AuthenticatedClient(
                base_url=hackagent_api_base_url,
                token=hackagent_api_key,
                prefix="Bearer",
            )
        )
        router = AgentRouter(
            backend=backend,
            name=openai_config["name"],
            agent_type=AgentTypeEnum.OPENAI_SDK,
            endpoint=openai_base_url,
            metadata={"name": openai_config["name"]},
            adapter_operational_config=openai_config,
        )
        reg_key = str(router.backend_agent.id)

        litellm.completion = spy
        try:
            router.route_request(
                reg_key,
                {"prompt": "hi", "max_tokens": 8, "metadata": {"trace_id": "xyz"}},
            )
        finally:
            litellm.completion = original_completion

        metadata = captured.get("metadata")
        assert isinstance(metadata, dict), "router did not attach metadata"
        ha = metadata.get(HACKAGENT_METADATA_KEY)
        assert isinstance(ha, dict), "missing metadata['hackagent'] namespace"
        assert ha["id"] == reg_key
        assert ha["adapter_type"] == "OpenAIAgent"
        # Caller-supplied keys outside the namespace are preserved.
        assert metadata["trace_id"] == "xyz"
