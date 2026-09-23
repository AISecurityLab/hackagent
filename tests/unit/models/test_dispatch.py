# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for sending requests through a connected model.

Chat types go through ``litellm.completion`` directly; adapter types
(ADK, CLI agents, web) go through the adapter's ``handle_request``. These
tests patch LiteLLM, so nothing leaves the process.
"""

import asyncio
import logging
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.models import dispatch
from hackagent.models.client import connect

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
    response.usage = MagicMock(model_dump=MagicMock(return_value={"total_tokens": 7}))
    response.model = "openai/gpt-4"
    return response


def _openai(identifier: str = "gpt-4"):
    return connect(ModelSpec(identifier=identifier, agent_type=AgentType.OPENAI_SDK))


class TestDispatchViaLiteLLM(unittest.TestCase):
    """The chat path goes through litellm.completion directly."""

    @patch("litellm.completion")
    def test_chat_request_goes_through_litellm_completion(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("hi there")
        client = _openai()

        response = client.send({"prompt": "hi"})

        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "hi there")
        self.assertEqual(response["adapter_type"], "OpenAIAgent")
        kwargs = mock_completion.call_args.kwargs
        self.assertEqual(kwargs["model"], "openai/gpt-4")
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "hi"}])

    @patch("litellm.completion")
    def test_missing_prompt_returns_400_envelope(self, mock_completion):
        response = _openai().send({"temperature": 0.5})
        self.assertEqual(response["status_code"], 400)
        self.assertIn(
            "Request data must include either 'messages' or 'prompt'",
            response["error_message"],
        )
        mock_completion.assert_not_called()

    @patch("litellm.completion")
    def test_litellm_exception_becomes_500_envelope(self, mock_completion):
        mock_completion.side_effect = RuntimeError("boom")
        response = _openai().send({"prompt": "hi"})
        self.assertEqual(response["status_code"], 500)
        self.assertIn("boom", response["error_message"])
        self.assertEqual(response["adapter_type"], "OpenAIAgent")

    @patch("litellm.completion")
    def test_thinking_translation_applied(self, mock_completion):
        """Per-request ``thinking`` is translated by the ProviderConfig."""
        mock_completion.return_value = _make_litellm_response("ok")
        _openai("o1-mini").send({"prompt": "hi", "thinking": True})
        kwargs = mock_completion.call_args.kwargs
        self.assertEqual(kwargs.get("reasoning_effort"), "medium")

    @patch("litellm.completion")
    def test_ollama_thinking_false_is_translated_to_think_false(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("no")
        client = connect(
            ModelSpec(
                identifier="qwen3.5:9b",
                endpoint="http://127.0.0.1:11434",
                agent_type=AgentType.OLLAMA,
            )
        )
        client.send({"prompt": "Answer yes or no", "thinking": False})
        self.assertEqual(mock_completion.call_args.kwargs["think"], False)

    @patch("litellm.completion")
    def test_dispatch_attaches_hackagent_metadata_namespace(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("ok")
        client = _openai()
        client.send({"prompt": "hi"})
        metadata = mock_completion.call_args.kwargs.get("metadata")
        ha = metadata.get("hackagent")
        self.assertEqual(ha["id"], client.instance_id)
        self.assertEqual(ha["adapter_type"], "OpenAIAgent")
        self.assertNotIn("hackagent_agent_id", metadata)

    @patch("litellm.completion")
    def test_caller_metadata_outside_hackagent_namespace_preserved(
        self, mock_completion
    ):
        mock_completion.return_value = _make_litellm_response("ok")
        client = _openai()
        client.send(
            {"prompt": "hi", "metadata": {"trace_id": "xyz", "user_id": "alice"}}
        )
        metadata = mock_completion.call_args.kwargs.get("metadata")
        self.assertEqual(metadata["trace_id"], "xyz")
        self.assertEqual(metadata["user_id"], "alice")
        self.assertEqual(metadata["hackagent"]["id"], client.instance_id)

    @patch("litellm.completion")
    def test_caller_hackagent_namespace_wins_on_collision(self, mock_completion):
        mock_completion.return_value = _make_litellm_response("ok")
        _openai().send(
            {
                "prompt": "hi",
                "metadata": {"hackagent": {"id": "override", "custom": "x"}},
            }
        )
        ha = mock_completion.call_args.kwargs.get("metadata")["hackagent"]
        self.assertEqual(ha["id"], "override")
        self.assertEqual(ha["custom"], "x")
        self.assertEqual(ha["adapter_type"], "OpenAIAgent")

    @patch("litellm.completion")
    def test_response_cost_and_call_id_surface_in_envelope(self, mock_completion):
        response = _make_litellm_response("ok")
        response._hidden_params = {
            "response_cost": 0.000123,
            "litellm_call_id": "call-abc",
        }
        mock_completion.return_value = response

        env = _openai().send({"prompt": "hi"})

        self.assertEqual(env["status_code"], 200)
        agent_data = env["agent_specific_data"]
        self.assertAlmostEqual(agent_data["response_cost"], 0.000123)
        self.assertEqual(agent_data["litellm_call_id"], "call-abc")

    @patch("litellm.completion")
    def test_response_cost_absent_when_not_in_hidden_params(self, mock_completion):
        response = _make_litellm_response("ok")
        if hasattr(response, "_hidden_params"):
            del response._hidden_params
        mock_completion.return_value = response

        env = _openai().send({"prompt": "hi"})
        self.assertNotIn("response_cost", env["agent_specific_data"])

    @patch("litellm.acompletion", new_callable=AsyncMock)
    def test_async_chat_request_matches_sync_envelope(self, mock_acompletion):
        mock_acompletion.return_value = _make_litellm_response("async reply")

        response = asyncio.run(_openai().asend({"prompt": "hi"}))

        self.assertEqual(response["status_code"], 200)
        self.assertEqual(response["generated_text"], "async reply")
        self.assertEqual(response["adapter_type"], "OpenAIAgent")
        mock_acompletion.assert_awaited_once()


def _adk():
    return connect(
        ModelSpec(
            identifier="my_app",
            endpoint="http://fake-adk.com",
            agent_type=AgentType.GOOGLE_ADK,
            extra={"user_id": "alice"},
        )
    )


class TestDispatchADKBypassesLiteLLM(unittest.TestCase):
    """ADK requests flow through the adapter's handle_request."""

    def test_adk_uses_adapter_handle_request_not_litellm(self):
        client = _adk()
        client.adapter.handle_request = MagicMock(
            return_value={"status_code": 200, "generated_text": "adk reply"}
        )

        with patch("litellm.completion") as mock_completion:
            response = client.send({"prompt": "hi"})

        self.assertEqual(response["generated_text"], "adk reply")
        client.adapter.handle_request.assert_called_once()
        mock_completion.assert_not_called()

    def test_async_adk_uses_adapter_handle_request(self):
        client = _adk()
        client.adapter.handle_request = MagicMock(
            return_value={"generated_text": "adk reply"}
        )

        response = asyncio.run(client.asend({"prompt": "hi"}))

        self.assertEqual(response["generated_text"], "adk reply")
        client.adapter.handle_request.assert_called_once_with({"prompt": "hi"})

    def test_adk_user_id_comes_from_the_spec(self):
        self.assertEqual(_adk().adapter.user_id, "alice")

    def test_adk_without_user_id_uses_the_default(self):
        client = connect(
            ModelSpec(
                identifier="my_app",
                endpoint="http://fake-adk.com",
                agent_type=AgentType.GOOGLE_ADK,
            )
        )
        self.assertEqual(client.adapter.user_id, dispatch.DEFAULT_ADK_USER_ID)

    def test_adapter_exception_becomes_error_envelope(self):
        client = _adk()
        client.adapter.handle_request = MagicMock(side_effect=RuntimeError("down"))

        response = client.send({"prompt": "hi"})

        self.assertEqual(response["status_code"], 500)
        self.assertEqual(response["error_category"], "AdapterException")
        self.assertIn("down", response["error_message"])


class TestBuildAdapter(unittest.TestCase):
    def test_unsupported_agent_type_raises(self):
        with self.assertRaisesRegex(ValueError, "Unsupported agent type"):
            connect(ModelSpec(identifier="x", agent_type=AgentType.MCP))

    def test_adapter_config_carries_spec_fields_and_extra(self):
        config = dispatch.adapter_config(
            ModelSpec(
                identifier="m",
                endpoint="http://h/v1",
                api_key="sk-1",
                max_tokens=50,
                temperature=0.0,
                extra={"top_k": 3},
            )
        )
        self.assertEqual(
            config,
            {
                "name": "m",
                "endpoint": "http://h/v1",
                "api_key": "sk-1",
                "max_tokens": 50,
                "temperature": 0.0,
                "top_k": 3,
            },
        )

    def test_api_key_env_is_read_at_connect_time(self):
        with patch.dict("os.environ", {"MY_KEY": "from-env"}):
            spec = ModelSpec(identifier="m", api_key_env="MY_KEY")
            self.assertEqual(dispatch.resolve_api_key(spec), "from-env")
        self.assertIsNone(dispatch.resolve_api_key(spec))


if __name__ == "__main__":
    unittest.main()
