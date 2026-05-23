# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ``hackagent/router/envelope.py``."""

import logging
import unittest
from unittest.mock import MagicMock

from hackagent.router import envelope

logging.disable(logging.CRITICAL)


def _model_response(
    content: str = "",
    *,
    reasoning_content: str = None,
    reasoning: str = None,
    tool_calls=None,
):
    """Build a minimal mock of a litellm ``ModelResponse``."""
    response = MagicMock()
    choice = MagicMock()
    message = MagicMock()
    message.content = content
    message.reasoning_content = reasoning_content
    message.reasoning = reasoning
    message.tool_calls = tool_calls
    message.provider_specific_fields = None
    choice.message = message
    response.choices = [choice]
    return response


class TestStripThinkPrefix(unittest.TestCase):
    def test_removes_prefix_up_to_and_including_marker(self):
        self.assertEqual(
            envelope.strip_think_prefix("scratch</think>real answer"),
            "real answer",
        )

    def test_returns_unchanged_when_marker_absent(self):
        self.assertEqual(envelope.strip_think_prefix("plain text"), "plain text")

    def test_handles_non_string_gracefully(self):
        self.assertIs(envelope.strip_think_prefix(None), None)


class TestExtractTextFromResponse(unittest.TestCase):
    def test_returns_content_when_present(self):
        response = _model_response("hello world")
        self.assertEqual(envelope.extract_text_from_response(response), "hello world")

    def test_falls_back_to_reasoning_content(self):
        response = _model_response("", reasoning_content="reasoning trace")
        self.assertEqual(
            envelope.extract_text_from_response(response), "reasoning trace"
        )

    def test_falls_back_to_reasoning_attribute(self):
        response = _model_response("", reasoning="reasoning text")
        self.assertEqual(
            envelope.extract_text_from_response(response), "reasoning text"
        )

    def test_returns_empty_response_marker_when_nothing_usable(self):
        response = _model_response("")
        self.assertEqual(
            envelope.extract_text_from_response(response),
            "[GENERATION_ERROR: EMPTY_RESPONSE]",
        )

    def test_returns_unexpected_response_marker_when_response_malformed(self):
        bad = MagicMock()
        bad.choices = []
        self.assertEqual(
            envelope.extract_text_from_response(bad),
            "[GENERATION_ERROR: UNEXPECTED_RESPONSE]",
        )


class TestExtractToolCalls(unittest.TestCase):
    def test_returns_none_when_no_tool_calls(self):
        self.assertIsNone(envelope.extract_tool_calls(_model_response("hi")))

    def test_normalises_tool_call_shape(self):
        tc = MagicMock()
        tc.id = "call_1"
        tc.type = "function"
        tc.function.name = "do_thing"
        tc.function.arguments = '{"x": 1}'
        response = _model_response("", tool_calls=[tc])
        result = envelope.extract_tool_calls(response)
        self.assertEqual(
            result,
            [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "do_thing", "arguments": '{"x": 1}'},
                }
            ],
        )

    def test_returns_none_for_unstructured_response(self):
        self.assertIsNone(envelope.extract_tool_calls(MagicMock(choices=[])))


class TestResolveLitellmModel(unittest.TestCase):
    def test_no_prefix_returns_raw(self):
        self.assertEqual(envelope.resolve_litellm_model("gpt-4"), "gpt-4")

    def test_adds_prefix_when_provided(self):
        self.assertEqual(
            envelope.resolve_litellm_model("gpt-4", provider_prefix="openai"),
            "openai/gpt-4",
        )

    def test_preserves_existing_known_prefix(self):
        self.assertEqual(
            envelope.resolve_litellm_model("ollama/llama3", provider_prefix="openai"),
            "ollama/llama3",
        )


class TestBuildLitellmKwargs(unittest.TestCase):
    def _common(self):
        return dict(
            model="openai/gpt-4",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=100,
            temperature=0.7,
            top_p=0.9,
        )

    def test_minimal_kwargs(self):
        kwargs = envelope.build_litellm_kwargs(**self._common())
        self.assertEqual(kwargs["model"], "openai/gpt-4")
        self.assertEqual(kwargs["temperature"], 0.7)
        self.assertNotIn("api_base", kwargs)

    def test_attaches_api_base_and_key(self):
        kwargs = envelope.build_litellm_kwargs(
            api_base="http://host/v1", api_key="sk-x", **self._common()
        )
        self.assertEqual(kwargs["api_base"], "http://host/v1")
        self.assertEqual(kwargs["api_key"], "sk-x")

    def test_custom_endpoint_without_provider_prefix_falls_back_to_openai(self):
        common = self._common()
        common["model"] = "local-model"
        kwargs = envelope.build_litellm_kwargs(api_base="http://host:8000/v1", **common)
        self.assertEqual(kwargs.get("custom_llm_provider"), "openai")
        self.assertIn("extra_headers", kwargs)

    def test_thinking_payload_merged_in(self):
        kwargs = envelope.build_litellm_kwargs(
            thinking_payload={"reasoning_effort": "high"}, **self._common()
        )
        self.assertEqual(kwargs["reasoning_effort"], "high")

    def test_tools_and_choice_only_set_when_tools_present(self):
        # tool_choice provided but no tools — both omitted.
        kwargs = envelope.build_litellm_kwargs(tool_choice="auto", **self._common())
        self.assertNotIn("tools", kwargs)
        self.assertNotIn("tool_choice", kwargs)

        kwargs = envelope.build_litellm_kwargs(
            tools=[{"type": "function"}],
            tool_choice="auto",
            **self._common(),
        )
        self.assertEqual(kwargs["tool_choice"], "auto")

    def test_extra_kwargs_override_defaults(self):
        kwargs = envelope.build_litellm_kwargs(
            extra_kwargs={"temperature": 0.1, "custom": "x"}, **self._common()
        )
        self.assertEqual(kwargs["temperature"], 0.1)
        self.assertEqual(kwargs["custom"], "x")


class TestEnvelopeBuilders(unittest.TestCase):
    def test_success_strips_think_prefix(self):
        env = envelope.build_success_envelope(
            agent_id="a1",
            adapter_type="X",
            processed_response="scratch</think>final",
        )
        self.assertEqual(env["processed_response"], "final")
        self.assertEqual(env["generated_text"], "final")
        self.assertEqual(env["status_code"], 200)
        self.assertIsNone(env["error_message"])

    def test_success_attaches_model_name(self):
        env = envelope.build_success_envelope(
            agent_id="a1",
            adapter_type="X",
            processed_response="ok",
            model_name="gpt-4",
        )
        self.assertEqual(env["agent_specific_data"]["model_name"], "gpt-4")

    def test_error_default_status_500(self):
        env = envelope.build_error_envelope(
            agent_id="a1", adapter_type="X", error_message="boom"
        )
        self.assertEqual(env["status_code"], 500)
        self.assertEqual(env["error_message"], "boom")
        self.assertIsNone(env["processed_response"])

    def test_error_uses_supplied_status(self):
        env = envelope.build_error_envelope(
            agent_id="a1",
            adapter_type="X",
            error_message="bad",
            status_code=400,
        )
        self.assertEqual(env["status_code"], 400)


class TestBuildAgentSpecificData(unittest.TestCase):
    def test_merges_completion_metadata(self):
        data = envelope.build_agent_specific_data(
            model_name="gpt-4",
            invoked_parameters={"temperature": 0.7},
            completion_result={
                "usage": {"total_tokens": 12},
                "finish_reason": "stop",
                "tool_calls": [{"id": "c1"}],
            },
        )
        self.assertEqual(data["model_name"], "gpt-4")
        self.assertEqual(data["usage"], {"total_tokens": 12})
        self.assertEqual(data["finish_reason"], "stop")
        self.assertEqual(data["tool_calls"], [{"id": "c1"}])

    def test_extra_dict_overrides(self):
        data = envelope.build_agent_specific_data(
            model_name="m",
            invoked_parameters={},
            extra={"hackagent_call_id": "abc"},
        )
        self.assertEqual(data["hackagent_call_id"], "abc")


if __name__ == "__main__":
    unittest.main()
