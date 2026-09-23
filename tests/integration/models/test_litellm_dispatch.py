# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Integration tests for the LiteLLM chat path of a connected model.

A model is connected with :func:`hackagent.models.connect`, the call goes
through ``litellm.completion`` against a real provider (OpenAI by default,
OpenRouter on CI), and the returned envelope and completion are validated.
Connecting needs no storage backend or HackAgent key.

Skipped automatically when no ``OPENAI_API_KEY`` / ``OPENROUTER_API_KEY``
is configured — CI runs them when those env vars are present.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import pytest

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.models import connect
from hackagent.models.adapters.litellm import _ChatRegistration
from hackagent.models.adapters.litellm_callbacks import HACKAGENT_METADATA_KEY

logger = logging.getLogger(__name__)


def _connect(openai_config: Dict[str, Any]):
    return connect(
        ModelSpec(
            identifier=openai_config["name"],
            endpoint=openai_config.get("endpoint"),
            agent_type=AgentType.OPENAI_SDK,
            api_key=openai_config.get("api_key"),
            max_tokens=openai_config.get("max_tokens"),
            temperature=openai_config.get("temperature"),
        )
    )


@pytest.mark.integration
@pytest.mark.openai_sdk
class TestLiteLLMDispatchIntegration:
    """Hit a real OpenAI-compatible endpoint through a connected model."""

    def test_dispatch_returns_standardised_envelope(
        self, skip_if_openai_unavailable, openai_config: Dict[str, Any]
    ):
        client = _connect(openai_config)
        assert isinstance(client.adapter, _ChatRegistration)

        response = client.send(
            {
                "messages": [
                    {"role": "system", "content": "Reply with the single word OK."},
                    {"role": "user", "content": "Acknowledge."},
                ],
                "max_tokens": 16,
                "temperature": 0.0,
            }
        )

        assert response["status_code"] == 200, response.get("error_message")
        assert response["error_message"] is None
        assert isinstance(response["processed_response"], str)
        assert response["processed_response"], "expected non-empty text"
        assert response["generated_text"] == response["processed_response"]
        assert response["agent_id"] == client.instance_id
        assert response["adapter_type"] == client.adapter.ADAPTER_TYPE

        agent_data = response["agent_specific_data"]
        assert agent_data["model_name"] == client.adapter.litellm_model
        assert agent_data.get("usage"), "expected usage data from LiteLLM"
        assert "finish_reason" in agent_data

    def test_complete_returns_a_completion(
        self, skip_if_openai_unavailable, openai_config: Dict[str, Any]
    ):
        completion = _connect(openai_config).complete(
            "Reply with the single word OK.", max_tokens=8
        )
        assert completion.ok, completion.error
        assert isinstance(completion.text, str)
        assert completion.usage is not None

    def test_dispatch_supports_prompt_field(
        self, skip_if_openai_unavailable, openai_config: Dict[str, Any]
    ):
        response = _connect(openai_config).send(
            {"prompt": "Reply with the single word OK.", "max_tokens": 8}
        )
        assert response["status_code"] == 200, response.get("error_message")
        assert isinstance(response["processed_response"], str)

    def test_dispatch_attaches_hackagent_metadata_namespace(
        self, skip_if_openai_unavailable, openai_config: Dict[str, Any]
    ):
        import litellm

        captured: Dict[str, Any] = {}
        original_completion = litellm.completion

        def spy(**kwargs):
            captured.update(kwargs)
            return original_completion(**kwargs)

        client = _connect(openai_config)
        litellm.completion = spy
        try:
            client.send(
                {"prompt": "hi", "max_tokens": 8, "metadata": {"trace_id": "xyz"}}
            )
        finally:
            litellm.completion = original_completion

        metadata = captured.get("metadata")
        assert isinstance(metadata, dict), "dispatch did not attach metadata"
        ha = metadata.get(HACKAGENT_METADATA_KEY)
        assert isinstance(ha, dict), "missing metadata['hackagent'] namespace"
        assert ha["id"] == client.instance_id
        assert ha["adapter_type"] == "OpenAIAgent"
        assert metadata["trace_id"] == "xyz"
