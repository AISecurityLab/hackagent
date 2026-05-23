# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for the OpenAI agent adapter.

Issue #379 moved every chat-completion adapter onto LiteLLM, so these
tests exercise the OpenAI adapter by patching ``litellm.completion``
rather than the OpenAI SDK directly.
"""

import logging
import os
import unittest
from unittest.mock import MagicMock, patch

from hackagent.router.adapters.openai import (
    OpenAIAgent,
    OpenAIConfigurationError,
)

logging.disable(logging.CRITICAL)


def _make_litellm_response(content: str = "ok", *, tool_calls=None) -> MagicMock:
    """Build a minimal mock of a litellm ModelResponse."""
    response = MagicMock()
    choice = MagicMock()
    message = MagicMock()
    message.content = content
    message.tool_calls = tool_calls
    message.reasoning_content = None
    message.reasoning = None
    message.provider_specific_fields = None
    choice.message = message
    choice.finish_reason = "stop"
    response.choices = [choice]
    response.usage = MagicMock(model_dump=MagicMock(return_value={"total_tokens": 10}))
    response.model = "gpt-4"
    return response


class TestOpenAIAgentInit(unittest.TestCase):
    def test_init_success_with_required_config(self):
        adapter = OpenAIAgent(id="o1", config={"name": "gpt-4"})
        self.assertEqual(adapter.id, "o1")
        self.assertEqual(adapter.model_name, "gpt-4")
        # OpenAIAgent forces the openai/ provider prefix when none is set.
        self.assertEqual(adapter.litellm_model, "openai/gpt-4")
        self.assertIsNone(adapter.api_base_url)
        self.assertEqual(adapter.default_temperature, 1.0)

    def test_init_with_custom_endpoint(self):
        adapter = OpenAIAgent(
            id="o2",
            config={
                "name": "gpt-4",
                "endpoint": "https://custom.proxy/v1",
            },
        )
        self.assertEqual(adapter.api_base_url, "https://custom.proxy/v1")
        # When there's no API key, a placeholder is used so the underlying
        # OpenAI client doesn't choke.
        self.assertEqual(adapter.actual_api_key, "not-required")

    def test_init_with_custom_endpoint_defaults_model_name(self):
        adapter = OpenAIAgent(id="o3", config={"endpoint": "https://example.com/v1"})
        self.assertEqual(adapter.model_name, "default")

    @patch.dict(os.environ, {"CUSTOM_API_KEY": "sk-test"})
    def test_init_with_api_key_from_env(self):
        adapter = OpenAIAgent(
            id="o4",
            config={"name": "gpt-4", "api_key": "CUSTOM_API_KEY"},
        )
        self.assertEqual(adapter.actual_api_key, "sk-test")

    def test_init_with_generation_parameters(self):
        adapter = OpenAIAgent(
            id="o5",
            config={
                "name": "gpt-4",
                "max_tokens": 500,
                "temperature": 0.7,
                "tools": [{"type": "function", "function": {"name": "f"}}],
                "tool_choice": "auto",
            },
        )
        self.assertEqual(adapter.default_max_tokens, 500)
        self.assertEqual(adapter.default_temperature, 0.7)
        self.assertIsNotNone(adapter.default_tools)
        self.assertEqual(adapter.default_tool_choice, "auto")

    def test_init_missing_name_no_endpoint_raises(self):
        with self.assertRaises(OpenAIConfigurationError):
            OpenAIAgent(id="err", config={})

    def test_init_preserves_existing_provider_prefix(self):
        """A user-supplied ``openai/<model>`` shouldn't get double-prefixed."""
        adapter = OpenAIAgent(id="o6", config={"name": "openai/gpt-4"})
        self.assertEqual(adapter.litellm_model, "openai/gpt-4")


class TestOpenAIAgentHandleRequest(unittest.TestCase):
    def setUp(self):
        self.adapter = OpenAIAgent(
            id="oh1",
            config={"name": "gpt-4", "max_tokens": 100, "temperature": 0.8},
        )

    def test_missing_prompt_and_messages_returns_400(self):
        response = self.adapter.handle_request({"temperature": 0.5})
        self.assertEqual(response["status_code"], 400)
        self.assertIn(
            "Request data must include either 'messages' or 'prompt'",
            response["error_message"],
        )

    @patch("litellm.completion")
    def test_handle_request_with_prompt_success(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("Hello back")
        response = self.adapter.handle_request({"prompt": "Hi"})

        self.assertEqual(response["status_code"], 200)
        self.assertIsNone(response["error_message"])
        self.assertEqual(response["generated_text"], "Hello back")
        self.assertEqual(response["adapter_type"], "OpenAIAgent")
        kwargs = mock_completion.call_args.kwargs
        self.assertEqual(kwargs["model"], "openai/gpt-4")
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "Hi"}])

    @patch("litellm.completion")
    def test_handle_request_with_messages_success(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("Hi!")
        messages = [
            {"role": "system", "content": "be helpful"},
            {"role": "user", "content": "ping"},
        ]
        response = self.adapter.handle_request({"messages": messages})

        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "Hi!")
        kwargs = mock_completion.call_args.kwargs
        self.assertEqual(kwargs["messages"], messages)

    @patch("litellm.completion")
    def test_handle_request_with_tool_calls(self, mock_completion):
        tool = MagicMock()
        tool.id = "call_1"
        tool.type = "function"
        tool.function.name = "get_weather"
        tool.function.arguments = '{"loc": "SF"}'
        mock_completion.return_value = _make_litellm_response(
            "I'll call a tool", tool_calls=[tool]
        )

        response = self.adapter.handle_request(
            {
                "prompt": "weather?",
                "tools": [{"type": "function", "function": {"name": "x"}}],
                "tool_choice": "auto",
            }
        )

        self.assertEqual(response["status_code"], 200)
        tcs = response["agent_specific_data"]["tool_calls"]
        self.assertEqual(len(tcs), 1)
        self.assertEqual(tcs[0]["function"]["name"], "get_weather")
        kwargs = mock_completion.call_args.kwargs
        self.assertIn("tools", kwargs)
        self.assertEqual(kwargs["tool_choice"], "auto")

    @patch("litellm.completion")
    def test_parameter_overrides_apply(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("ok")
        self.adapter.handle_request(
            {"prompt": "go", "max_tokens": 200, "temperature": 0.5}
        )
        kwargs = mock_completion.call_args.kwargs
        self.assertEqual(kwargs["max_tokens"], 200)
        self.assertEqual(kwargs["temperature"], 0.5)

    @patch("litellm.completion")
    def test_handle_request_api_error(self, mock_completion):
        mock_completion.side_effect = RuntimeError("boom")
        response = self.adapter.handle_request({"prompt": "Hi"})
        self.assertEqual(response["status_code"], 500)
        self.assertIn("boom", response["error_message"])


class TestOpenAIAgentThinking(unittest.TestCase):
    """Issue #379 — verify the unified thinking knob translates correctly."""

    @patch("litellm.completion")
    def test_thinking_true_on_reasoning_model_sets_reasoning_effort(
        self, mock_completion
    ):
        mock_completion.return_value = _make_litellm_response("hi")
        adapter = OpenAIAgent(id="r1", config={"name": "o1-mini", "thinking": True})
        adapter.handle_request({"prompt": "hello"})
        kwargs = mock_completion.call_args.kwargs
        self.assertEqual(kwargs.get("reasoning_effort"), "medium")
        self.assertNotIn("thinking", kwargs)

    @patch("litellm.completion")
    def test_thinking_false_on_reasoning_model_omits_effort(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("hi")
        adapter = OpenAIAgent(id="r2", config={"name": "o3", "thinking": False})
        adapter.handle_request({"prompt": "hello"})
        kwargs = mock_completion.call_args.kwargs
        self.assertNotIn("reasoning_effort", kwargs)
        self.assertNotIn("thinking", kwargs)

    @patch("litellm.completion")
    def test_thinking_string_passes_through_as_effort(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("hi")
        adapter = OpenAIAgent(id="r3", config={"name": "o1"})
        adapter.handle_request({"prompt": "hello", "thinking": "high"})
        self.assertEqual(
            mock_completion.call_args.kwargs.get("reasoning_effort"), "high"
        )

    @patch("litellm.completion")
    def test_thinking_on_non_reasoning_model_passes_through_generically(
        self, mock_completion
    ):
        mock_completion.return_value = _make_litellm_response("hi")
        adapter = OpenAIAgent(id="r4", config={"name": "gpt-4"})
        adapter.handle_request({"prompt": "hello", "thinking": True})
        kwargs = mock_completion.call_args.kwargs
        # Non-reasoning OpenAI models get the generic LiteLLM thinking dict.
        self.assertEqual(kwargs.get("thinking"), {"type": "enabled"})


if __name__ == "__main__":
    unittest.main()
