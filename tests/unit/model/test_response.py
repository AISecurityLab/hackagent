from litellm import ModelResponse as LiteLLMResponse
import pytest

from hackagent.models import ModelResponse


def test_normalizes_litellm_model_response():
    raw_response = LiteLLMResponse(
        id="chatcmpl-123",
        model="openai/gpt-4o",
        created=123456,
        system_fingerprint="fp_123",
        choices=[
            {
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "reasoning_content": "I should call the tool.",
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "lookup",
                                "arguments": '{"query":"value"}',
                            },
                        }
                    ],
                },
            }
        ],
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )
    raw_response._hidden_params = {"response_cost": 0.001}

    response = ModelResponse.from_value(raw_response)

    assert response.text == "I should call the tool."
    assert response.reasoning_content == "I should call the tool."
    assert response.tool_calls[0]["function"]["name"] == "lookup"
    assert response.usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    assert response.finish_reason == "tool_calls"
    assert response.model == "openai/gpt-4o"
    assert response.response_id == "chatcmpl-123"
    assert response.created == 123456
    assert response.system_fingerprint == "fp_123"
    assert response.metadata["response_cost"] == 0.001
    assert response.raw_response is raw_response


def test_normalizes_litellm_response_metadata():
    raw_response = LiteLLMResponse(
        id="chatcmpl-123",
        model="openai/gpt-test",
        system_fingerprint="fp_test",
        choices=[
            {
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "reasoning_content": "I should call the lookup tool.",
                    "tool_calls": [
                        {
                            "id": "call-123",
                            "type": "function",
                            "function": {
                                "name": "lookup",
                                "arguments": '{"query":"test"}',
                            },
                        }
                    ],
                },
            }
        ],
        usage={
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    )
    setattr(raw_response, "response_ms", 42.5)
    raw_response._hidden_params = {"response_cost": 0.001}
    raw_response._response_headers = {"x-request-id": "request-123"}

    response = ModelResponse.from_litellm(raw_response)

    assert response.text == "I should call the lookup tool."
    assert response.reasoning == "I should call the lookup tool."
    assert response.tool_calls[0]["function"]["name"] == "lookup"
    assert response.usage == {
        "completion_tokens": 5,
        "prompt_tokens": 10,
        "total_tokens": 15,
    }
    assert response.finish_reason == "tool_calls"
    assert response.model == "openai/gpt-test"
    assert response.response_id == "chatcmpl-123"
    assert response.metadata["response_ms"] == 42.5
    assert response.metadata["system_fingerprint"] == "fp_test"
    assert response.metadata["hidden_params"] == {"response_cost": 0.001}
    assert response.metadata["response_headers"] == {"x-request-id": "request-123"}
    assert response.raw_response is raw_response


def test_prefers_litellm_message_content_over_reasoning():
    raw_response = LiteLLMResponse(
        choices=[
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "Final answer",
                    "reasoning_content": "Private reasoning",
                },
            }
        ]
    )

    response = ModelResponse.from_value(raw_response)

    assert response.text == "Final answer"
    assert response.reasoning == "Private reasoning"


def test_normalizes_openai_style_response_mapping():
    raw_response = {
        "id": "chatcmpl-456",
        "model": "gpt-test",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Hello"},
            }
        ],
        "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
    }

    response = ModelResponse.from_value(raw_response)

    assert response.text == "Hello"
    assert response.finish_reason == "stop"
    assert response.model == "gpt-test"
    assert response.response_id == "chatcmpl-456"
    assert response.usage == {
        "prompt_tokens": 2,
        "completion_tokens": 1,
        "total_tokens": 3,
    }


def test_custom_provider_errors_and_guardrails_normalize_to_native_fields():
    failure = ModelResponse.from_value(
        {
            "status_code": 429,
            "error_message": "unavailable",
            "error_category": "rate_limit",
        }
    )
    assert not failure.ok
    assert failure.error.status_code == 429
    assert failure.metadata["error"]["category"] == "rate_limit"
    blocked = ModelResponse.from_value(
        {
            "agent_specific_data": {
                "guardrail": True,
                "side": "after",
                "categories": ["test"],
                "reasoning": "blocked",
            }
        }
    )
    assert not blocked.ok
    assert blocked.error is None
    assert blocked.guardrail.side == "after"


def test_rejects_stream_iterators_as_completed_responses():
    with pytest.raises(TypeError, match="list_iterator"):
        ModelResponse.from_value(iter(["chunk"]))
