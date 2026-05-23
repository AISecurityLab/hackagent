# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ``hackagent/router/provider_config.py``."""

import logging
import unittest

from hackagent.router.provider_config import (
    PROVIDER_CONFIGS,
    default_thinking_translator,
    get_provider_config,
    ollama_thinking_translator,
    openai_thinking_translator,
)
from hackagent.router.types import AgentTypeEnum

logging.disable(logging.CRITICAL)


class TestDefaultThinkingTranslator(unittest.TestCase):
    def test_none_returns_empty(self):
        self.assertEqual(default_thinking_translator(None), {})

    def test_dict_passes_through(self):
        self.assertEqual(
            default_thinking_translator({"budget_tokens": 1024}),
            {"thinking": {"budget_tokens": 1024}},
        )

    def test_string_becomes_reasoning_effort(self):
        self.assertEqual(
            default_thinking_translator("high"), {"reasoning_effort": "high"}
        )

    def test_true_becomes_enabled_dict(self):
        self.assertEqual(
            default_thinking_translator(True),
            {"thinking": {"type": "enabled"}},
        )

    def test_false_becomes_disabled_dict(self):
        self.assertEqual(
            default_thinking_translator(False),
            {"thinking": {"type": "disabled"}},
        )

    def test_int_becomes_budget(self):
        self.assertEqual(
            default_thinking_translator(2048),
            {"thinking": {"type": "enabled", "budget_tokens": 2048}},
        )


class TestOpenAIThinkingTranslator(unittest.TestCase):
    def test_reasoning_model_true_maps_to_medium(self):
        self.assertEqual(
            openai_thinking_translator(True, model_name="openai/o1-mini"),
            {"reasoning_effort": "medium"},
        )

    def test_reasoning_model_false_omits(self):
        self.assertEqual(openai_thinking_translator(False, model_name="openai/o3"), {})

    def test_reasoning_model_string_passes_through(self):
        self.assertEqual(
            openai_thinking_translator("low", model_name="o1"),
            {"reasoning_effort": "low"},
        )

    def test_reasoning_model_dict_effort_extracted(self):
        self.assertEqual(
            openai_thinking_translator({"reasoning_effort": "high"}, model_name="o3"),
            {"reasoning_effort": "high"},
        )

    def test_non_reasoning_falls_back_to_default(self):
        self.assertEqual(
            openai_thinking_translator(True, model_name="openai/gpt-4"),
            {"thinking": {"type": "enabled"}},
        )

    def test_none_returns_empty(self):
        self.assertEqual(openai_thinking_translator(None, model_name="o1"), {})


class TestOllamaThinkingTranslator(unittest.TestCase):
    def test_bool_passes_through_to_think(self):
        self.assertEqual(
            ollama_thinking_translator(True, model_name="llama3"),
            {"think": True},
        )
        self.assertEqual(
            ollama_thinking_translator(False, model_name="llama3"),
            {"think": False},
        )

    def test_str_passes_through_to_think(self):
        self.assertEqual(
            ollama_thinking_translator("low", model_name="llama3"),
            {"think": "low"},
        )

    def test_int_coerces_to_bool(self):
        self.assertEqual(
            ollama_thinking_translator(1, model_name="llama3"),
            {"think": True},
        )
        self.assertEqual(
            ollama_thinking_translator(0, model_name="llama3"),
            {"think": False},
        )

    def test_dict_disabled_type_maps_to_false(self):
        self.assertEqual(
            ollama_thinking_translator({"type": "disabled"}, model_name="llama3"),
            {"think": False},
        )

    def test_dict_enabled_type_maps_to_true(self):
        self.assertEqual(
            ollama_thinking_translator({"type": "enabled"}, model_name="llama3"),
            {"think": True},
        )

    def test_none_returns_empty(self):
        self.assertEqual(ollama_thinking_translator(None, model_name="llama3"), {})


class TestProviderConfigsTable(unittest.TestCase):
    def test_openai_config_present_and_correct(self):
        cfg = get_provider_config(AgentTypeEnum.OPENAI_SDK)
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.provider_prefix, "openai")
        self.assertEqual(cfg.adapter_label, "OpenAIAgent")
        self.assertIn("tools", cfg.extra_passthrough_keys)

    def test_ollama_config_present_and_correct(self):
        cfg = get_provider_config(AgentTypeEnum.OLLAMA)
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.provider_prefix, "ollama_chat")
        self.assertEqual(cfg.adapter_label, "OllamaAgent")
        self.assertIn("top_k", cfg.extra_passthrough_keys)
        self.assertIn("num_ctx", cfg.extra_passthrough_keys)

    def test_litellm_passthrough_has_no_prefix(self):
        cfg = get_provider_config(AgentTypeEnum.LITELLM)
        self.assertIsNotNone(cfg)
        self.assertIsNone(cfg.provider_prefix)

    def test_langchain_uses_default_passthrough(self):
        cfg = get_provider_config(AgentTypeEnum.LANGCHAIN)
        self.assertIsNotNone(cfg)
        self.assertIsNone(cfg.provider_prefix)

    def test_google_adk_not_in_lookup_table(self):
        # ADK still uses per-instance custom-LLM registration; it's not
        # in the static table yet. See LITELLM_ROUTER_REFACTOR_PLAN.md
        # Phase E for the move into router/providers/.
        self.assertIsNone(get_provider_config(AgentTypeEnum.GOOGLE_ADK))

    def test_unknown_agent_type_returns_none(self):
        self.assertIsNone(get_provider_config(AgentTypeEnum.UNKNOWN))

    def test_provider_configs_dict_is_complete(self):
        """All chat-completion agent types appear in the table."""
        expected = {
            AgentTypeEnum.LITELLM,
            AgentTypeEnum.OPENAI_SDK,
            AgentTypeEnum.OLLAMA,
            AgentTypeEnum.LANGCHAIN,
        }
        self.assertEqual(expected, set(PROVIDER_CONFIGS.keys()))


if __name__ == "__main__":
    unittest.main()
