# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ``hackagent/router/_chat_registration.py``."""

import logging
import os
import unittest
from unittest.mock import patch

from hackagent.router._chat_registration import _ChatRegistration
from hackagent.router.provider_config import get_provider_config
from hackagent.router.types import AgentTypeEnum

logging.disable(logging.CRITICAL)


def _build(agent_type: AgentTypeEnum, config) -> _ChatRegistration:
    return _ChatRegistration(
        id="reg-id",
        agent_type=agent_type,
        provider_config=get_provider_config(agent_type),
        config=config,
    )


class TestOpenAIRegistration(unittest.TestCase):
    def test_basic_openai_attributes(self):
        reg = _build(AgentTypeEnum.OPENAI_SDK, {"name": "gpt-4"})
        self.assertEqual(reg.model_name, "gpt-4")
        self.assertEqual(reg.litellm_model, "openai/gpt-4")
        self.assertEqual(reg.ADAPTER_TYPE, "OpenAIAgent")
        # OpenAI's default temperature is historically 1.0.
        self.assertEqual(reg.default_temperature, 1.0)

    def test_custom_endpoint_without_api_key_uses_placeholder(self):
        reg = _build(
            AgentTypeEnum.OPENAI_SDK,
            {"name": "gpt-4", "endpoint": "https://proxy/v1"},
        )
        self.assertEqual(reg.api_base_url, "https://proxy/v1")
        self.assertEqual(reg.actual_api_key, "not-required")

    def test_custom_endpoint_defaults_model_name_to_default(self):
        reg = _build(AgentTypeEnum.OPENAI_SDK, {"endpoint": "https://example.com/v1"})
        self.assertEqual(reg.model_name, "default")

    @patch.dict(os.environ, {"CUSTOM_API_KEY": "sk-test"})
    def test_api_key_resolved_from_env(self):
        reg = _build(
            AgentTypeEnum.OPENAI_SDK,
            {"name": "gpt-4", "api_key": "CUSTOM_API_KEY"},
        )
        self.assertEqual(reg.actual_api_key, "sk-test")

    def test_preserves_existing_provider_prefix(self):
        reg = _build(AgentTypeEnum.OPENAI_SDK, {"name": "openai/gpt-4"})
        self.assertEqual(reg.litellm_model, "openai/gpt-4")


class TestOllamaRegistration(unittest.TestCase):
    def test_basic_ollama_attributes(self):
        reg = _build(AgentTypeEnum.OLLAMA, {"name": "llama3"})
        self.assertEqual(reg.litellm_model, "ollama_chat/llama3")
        self.assertEqual(reg.api_base_url, "http://localhost:11434")
        self.assertEqual(reg.ADAPTER_TYPE, "OllamaAgent")

    def test_endpoint_normalisation_strips_api_suffix(self):
        reg = _build(
            AgentTypeEnum.OLLAMA,
            {"name": "llama3", "endpoint": "http://host:11434/api/chat/"},
        )
        self.assertEqual(reg.api_base_url, "http://host:11434")

    @patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://env-ollama:11434"})
    def test_env_var_endpoint_fallback(self):
        reg = _build(AgentTypeEnum.OLLAMA, {"name": "llama3"})
        self.assertEqual(reg.api_base_url, "http://env-ollama:11434")

    def test_top_k_num_ctx_stream_recorded(self):
        reg = _build(
            AgentTypeEnum.OLLAMA,
            {
                "name": "llama3",
                "top_k": 40,
                "num_ctx": 8192,
                "stream": True,
            },
        )
        self.assertEqual(reg.default_top_k, 40)
        self.assertEqual(reg.default_num_ctx, 8192)
        self.assertTrue(reg.default_stream)


class TestLiteLLMRegistration(unittest.TestCase):
    def test_no_provider_prefix_when_litellm_passthrough(self):
        reg = _build(AgentTypeEnum.LITELLM, {"name": "ollama/llama3"})
        self.assertEqual(reg.litellm_model, "ollama/llama3")
        self.assertEqual(reg.ADAPTER_TYPE, "LiteLLMAgent")

    def test_missing_name_raises(self):
        with self.assertRaises(ValueError):
            _build(AgentTypeEnum.LITELLM, {})


class TestRegistrationMutability(unittest.TestCase):
    """External code mutates ``adapter.default_max_tokens``; that must work."""

    def test_default_max_tokens_is_mutable(self):
        reg = _build(AgentTypeEnum.OPENAI_SDK, {"name": "gpt-4"})
        reg.default_max_tokens = 500
        self.assertEqual(reg.default_max_tokens, 500)


if __name__ == "__main__":
    unittest.main()
