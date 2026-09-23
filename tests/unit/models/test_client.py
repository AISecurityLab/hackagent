# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for ModelClient, connect() and the envelope -> Completion mapping."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch

from hackagent.core.contracts import (
    LLM,
    AgentType,
    Message,
    ModelSpec,
    ToolCall,
)
from hackagent.models import connect
from hackagent.models.envelope import request_from_messages, to_completion


def _response(content="ok"):
    message = MagicMock(
        content=content,
        tool_calls=None,
        reasoning_content=None,
        reasoning=None,
        provider_specific_fields=None,
    )
    response = MagicMock()
    response.choices = [MagicMock(message=message, finish_reason="stop")]
    response.usage = MagicMock(
        model_dump=MagicMock(
            return_value={"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}
        )
    )
    response.model = "openai/gpt-4"
    response._hidden_params = {"response_cost": 0.5, "litellm_call_id": "c-1"}
    return response


def _client(**spec):
    spec.setdefault("identifier", "gpt-4")
    return connect(ModelSpec(**spec))


class TestConnect:
    def test_client_implements_the_llm_protocol(self):
        assert isinstance(_client(), LLM)

    def test_connect_needs_no_storage_and_does_no_io(self):
        with patch("litellm.completion") as completion:
            client = _client(max_tokens=10)
        completion.assert_not_called()
        assert client.describe().max_tokens == 10

    def test_each_client_gets_its_own_instance_id(self):
        assert _client().instance_id != _client().instance_id

    def test_explicit_instance_id(self):
        client = connect(ModelSpec(identifier="m"), instance_id="fixed")
        assert client.instance_id == "fixed"


class TestComplete:
    @patch("litellm.completion")
    def test_complete_returns_a_completion(self, mock_completion):
        mock_completion.return_value = _response("hello")

        completion = _client().complete("hi", max_tokens=5)

        assert completion.ok
        assert completion.text == "hello"
        assert completion.finish_reason == "stop"
        assert completion.provider_model == "openai/gpt-4"
        assert completion.usage.total_tokens == 7
        assert completion.invoked_parameters["max_tokens"] == 5
        assert completion.extra["response_cost"] == 0.5
        assert completion.extra["litellm_call_id"] == "c-1"
        assert mock_completion.call_args.kwargs["messages"] == [
            {"role": "user", "content": "hi"}
        ]

    @patch("litellm.completion", side_effect=RuntimeError("boom"))
    def test_errors_are_values_not_exceptions(self, _mock):
        completion = _client().complete("hi")
        assert not completion.ok
        assert "boom" in completion.error.message
        assert completion.error.status_code == 500
        assert completion.text is None

    @patch("litellm.acompletion", new_callable=AsyncMock)
    def test_acomplete(self, mock_acompletion):
        mock_acompletion.return_value = _response("async")
        assert asyncio.run(_client().acomplete("hi")).text == "async"

    def test_messages_are_sent_in_openai_shape(self):
        request = request_from_messages(
            [
                Message(role="system", content="sys"),
                Message(
                    role="assistant",
                    tool_calls=[ToolCall(id="t1", name="f", arguments="{}")],
                ),
                Message(role="tool", content="42", tool_call_id="t1"),
            ],
            {"temperature": 0},
        )
        assert request == {
            "temperature": 0,
            "messages": [
                {"role": "system", "content": "sys"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "t1",
                            "type": "function",
                            "function": {"name": "f", "arguments": "{}"},
                        }
                    ],
                },
                {"role": "tool", "content": "42", "tool_call_id": "t1"},
            ],
        }


class TestWithParams:
    @patch("litellm.completion")
    def test_params_apply_when_the_request_does_not_set_them(self, mock_completion):
        mock_completion.return_value = _response()
        client = _client(max_tokens=4096).with_params(max_tokens=64)

        client.send({"prompt": "a"})
        assert mock_completion.call_args.kwargs["max_tokens"] == 64

        client.send({"prompt": "b", "max_tokens": 8})
        assert mock_completion.call_args.kwargs["max_tokens"] == 8

    @patch("litellm.completion")
    def test_original_client_is_untouched(self, mock_completion):
        mock_completion.return_value = _response()
        base = _client(max_tokens=4096)
        scoped = base.with_params(max_tokens=64)

        base.send({"prompt": "a"})

        assert mock_completion.call_args.kwargs["max_tokens"] == 4096
        assert scoped.adapter is base.adapter
        assert base.adapter.default_max_tokens == 4096
        assert base.params == {}

    @patch("litellm.completion")
    def test_parallel_runs_with_different_params_do_not_race(self, mock_completion):
        seen = []

        def _record(**kwargs):
            seen.append((kwargs["messages"][0]["content"], kwargs["max_tokens"]))
            return _response()

        mock_completion.side_effect = _record
        base = _client(max_tokens=4096)
        runs = {f"run-{n}": base.with_params(max_tokens=n) for n in range(1, 9)}

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda item: item[1].send({"prompt": item[0]}), runs.items()))

        assert sorted(seen) == sorted((name, int(name[4:])) for name in runs)

    def test_describe_includes_params(self):
        spec = _client(max_tokens=10).with_params(max_tokens=64, seed=7).describe()
        assert spec.max_tokens == 64
        assert spec.extra["seed"] == 7


class TestToCompletion:
    def test_guardrail_envelope(self):
        completion = to_completion(
            {
                "processed_response": None,
                "raw_response_status": 200,
                "agent_specific_data": {
                    "guardrail": "before_guardrail_blocked",
                    "side": "before",
                    "message": "blocked",
                    "categories": ["harm"],
                    "reasoning": "why",
                },
                "error_message": None,
            }
        )
        assert not completion.ok
        assert completion.error is None
        assert completion.guardrail.side == "before"
        assert completion.guardrail.categories == ["harm"]

    def test_tool_calls(self):
        completion = to_completion(
            {
                "processed_response": "",
                "agent_specific_data": {
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {"name": "lookup", "arguments": '{"q": 1}'},
                        }
                    ]
                },
            }
        )
        assert completion.tool_calls == [
            ToolCall(id="c1", name="lookup", arguments='{"q": 1}')
        ]

    def test_error_category_is_kept(self):
        completion = to_completion(
            {
                "error_message": "nope",
                "error_category": "AdapterException",
                "status_code": 500,
            }
        )
        assert completion.error.category == "AdapterException"
        assert completion.error.status_code == 500

    def test_adapter_agent_type_is_described(self):
        client = connect(
            ModelSpec(
                identifier="my_app",
                endpoint="http://adk",
                agent_type=AgentType.GOOGLE_ADK,
            )
        )
        assert client.describe().agent_type is AgentType.GOOGLE_ADK
