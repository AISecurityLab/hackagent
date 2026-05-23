# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for OllamaAgent.

Issue #379 moved the Ollama adapter onto LiteLLM (via the
``ollama_chat`` provider), so these tests patch ``litellm.completion``
rather than ``requests.post`` for the chat path. Utility methods such as
``list_models`` and ``model_info`` still talk to the Ollama HTTP API
directly and so still mock ``requests``.
"""

import logging
import os
import unittest
from unittest.mock import MagicMock, patch

import requests

from hackagent.router.adapters.ollama import (
    OllamaAgent,
    OllamaConfigurationError,
)

logging.disable(logging.CRITICAL)


def _make_litellm_response(content: str = "ok") -> MagicMock:
    response = MagicMock()
    choice = MagicMock()
    message = MagicMock()
    message.content = content
    message.tool_calls = None
    message.reasoning_content = None
    message.reasoning = None
    message.provider_specific_fields = None
    choice.message = message
    choice.finish_reason = "stop"
    response.choices = [choice]
    response.usage = MagicMock(model_dump=MagicMock(return_value={"total_tokens": 5}))
    response.model = "ollama_chat/llama3"
    return response


class TestOllamaAgentInit(unittest.TestCase):
    def test_init_success_minimal_config(self):
        adapter = OllamaAgent(id="ol1", config={"name": "llama3"})
        self.assertEqual(adapter.id, "ol1")
        self.assertEqual(adapter.model_name, "llama3")
        self.assertEqual(adapter.api_base_url, "http://localhost:11434")
        self.assertEqual(adapter.litellm_model, "ollama_chat/llama3")
        self.assertEqual(adapter.default_max_tokens, 100)

    def test_init_with_custom_endpoint(self):
        adapter = OllamaAgent(
            id="ol2",
            config={"name": "mistral", "endpoint": "http://host:11434"},
        )
        self.assertEqual(adapter.api_base_url, "http://host:11434")

    def test_init_normalizes_trailing_slash_and_api_suffix(self):
        adapter = OllamaAgent(
            id="ol3",
            config={
                "name": "llama3",
                "endpoint": "http://host:11434/api/chat/",
            },
        )
        self.assertEqual(adapter.api_base_url, "http://host:11434")

    @patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://env-ollama:11434"})
    def test_init_picks_up_env_var(self):
        adapter = OllamaAgent(id="ol4", config={"name": "llama3"})
        self.assertEqual(adapter.api_base_url, "http://env-ollama:11434")

    def test_init_missing_name_raises(self):
        with self.assertRaises(OllamaConfigurationError):
            OllamaAgent(id="err", config={})

    def test_init_preserves_existing_provider_prefix(self):
        """If the user supplies ``ollama/<model>`` it shouldn't be re-prefixed."""
        adapter = OllamaAgent(id="ol5", config={"name": "ollama/llama3"})
        self.assertEqual(adapter.litellm_model, "ollama/llama3")


class TestOllamaAgentHandleRequest(unittest.TestCase):
    def setUp(self):
        self.adapter = OllamaAgent(
            id="oh1",
            config={"name": "llama3", "max_tokens": 50, "temperature": 0.5},
        )

    def test_missing_prompt_and_messages_returns_400(self):
        response = self.adapter.handle_request({})
        self.assertEqual(response["status_code"], 400)
        self.assertIn(
            "Request data must include either 'messages' or 'prompt'",
            response["error_message"],
        )

    @patch("litellm.completion")
    def test_handle_request_with_prompt_success(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("Hello!")

        response = self.adapter.handle_request({"prompt": "Hi"})

        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "Hello!")
        kwargs = mock_completion.call_args.kwargs
        self.assertEqual(kwargs["model"], "ollama_chat/llama3")
        self.assertEqual(kwargs["api_base"], "http://localhost:11434")
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "Hi"}])

    @patch("litellm.completion")
    def test_handle_request_with_messages_success(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("ack")
        messages = [
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "go"},
        ]
        response = self.adapter.handle_request({"messages": messages})
        self.assertEqual(response["status_code"], 200)
        self.assertEqual(mock_completion.call_args.kwargs["messages"], messages)

    @patch("litellm.completion")
    def test_extra_generation_options_pass_through(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("hi")
        adapter = OllamaAgent(
            id="oh2",
            config={
                "name": "llama3",
                "top_k": 40,
                "num_ctx": 8192,
                "stream": True,
            },
        )
        adapter.handle_request({"prompt": "Hi"})
        kwargs = mock_completion.call_args.kwargs
        self.assertEqual(kwargs.get("top_k"), 40)
        self.assertEqual(kwargs.get("num_ctx"), 8192)
        self.assertEqual(kwargs.get("stream"), True)

    @patch("litellm.completion")
    def test_thinking_true_translates_to_think(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("yo")
        adapter = OllamaAgent(id="oh3", config={"name": "llama3", "thinking": True})
        adapter.handle_request({"prompt": "Hi"})
        kwargs = mock_completion.call_args.kwargs
        self.assertIs(kwargs.get("think"), True)
        self.assertNotIn("thinking", kwargs)

    @patch("litellm.completion")
    def test_thinking_false_translates_to_think_false(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("yo")
        adapter = OllamaAgent(id="oh4", config={"name": "llama3", "thinking": False})
        adapter.handle_request({"prompt": "Hi"})
        self.assertIs(mock_completion.call_args.kwargs.get("think"), False)

    @patch("litellm.completion")
    def test_thinking_request_overrides_config_default(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("yo")
        adapter = OllamaAgent(id="oh5", config={"name": "llama3", "thinking": False})
        adapter.handle_request({"prompt": "Hi", "thinking": True})
        self.assertIs(mock_completion.call_args.kwargs.get("think"), True)

    @patch("litellm.completion")
    def test_handle_request_api_error(self, mock_completion):
        mock_completion.side_effect = RuntimeError("connection refused")
        response = self.adapter.handle_request({"prompt": "Hi"})
        self.assertEqual(response["status_code"], 500)
        self.assertIn("connection refused", response["error_message"])


class TestOllamaAgentUtilities(unittest.TestCase):
    def setUp(self):
        self.adapter = OllamaAgent(id="util", config={"name": "llama3"})

    @patch("requests.get")
    def test_list_models_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "models": [{"name": "llama3"}, {"name": "mistral:latest"}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        models = self.adapter.list_models()
        self.assertEqual(len(models), 2)

    @patch("requests.get")
    def test_list_models_error_returns_empty_list(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("nope")
        self.assertEqual(self.adapter.list_models(), [])

    @patch("requests.post")
    def test_model_info_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"license": "mit"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp
        self.assertEqual(self.adapter.model_info(), {"license": "mit"})

    @patch("requests.post")
    def test_model_info_error_returns_empty_dict(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("nope")
        self.assertEqual(self.adapter.model_info(), {})

    @patch.object(OllamaAgent, "list_models")
    def test_is_available_true_when_model_present(self, mock_list):
        mock_list.return_value = [{"name": "llama3:latest"}]
        self.assertTrue(self.adapter.is_available())

    @patch.object(OllamaAgent, "list_models")
    def test_is_available_false_when_model_missing(self, mock_list):
        mock_list.return_value = [{"name": "mistral"}]
        self.assertFalse(self.adapter.is_available())


if __name__ == "__main__":
    unittest.main()
