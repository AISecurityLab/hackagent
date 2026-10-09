import asyncio
import threading
import time
from typing import Any, Mapping, Sequence
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from hackagent.models import (
    Model,
    ModelConnection,
    ModelGeneration,
    ModelResponse,
)
from hackagent.models.completions import LiteLLMModel
from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.models.connect import connect
from hackagent.models.guardrail import GuardedModel, ModelGuardrail
from hackagent.models.retry import RetryingModel


class BatchModel(Model):
    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        **overrides: Any,
    ) -> ModelResponse:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(0.01)
            return ModelResponse(text=str(messages[-1]["content"]))
        finally:
            with self.lock:
                self.active -= 1

    async def acomplete(
        self,
        messages: Sequence[Mapping[str, Any]],
        **overrides: Any,
    ) -> ModelResponse:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            return ModelResponse(text=str(messages[-1]["content"]))
        finally:
            self.active -= 1


def test_model_accepts_explicit_runtime_configuration():
    model = LiteLLMModel(
        "ollama_chat/llama3.2-vision",
        connection=ModelConnection(api_base="http://localhost:11434"),
        generation=ModelGeneration(max_tokens=512, temperature=0.4),
    )

    assert model.model == "ollama_chat/llama3.2-vision"
    assert model.connection.api_base == "http://localhost:11434"
    assert model.generation.max_tokens == 512


def test_connect_ollama_uses_litellm_without_sdk_clients():
    spec = ModelSpec(
        identifier="gemma3:4b",
        agent_type=AgentType.OLLAMA,
        endpoint="http://127.0.0.1:11545",
        thinking=False,
        max_tokens=512,
        temperature=0.6,
        extra={"provider": "ollama", "seed": 42},
    )
    model = connect(spec)
    with patch("litellm.completion", return_value="ok") as complete:
        result = model.complete([{"role": "user", "content": "test"}])
    assert result.ok
    assert complete.call_args.kwargs["model"] == "ollama_chat/gemma3:4b"
    assert complete.call_args.kwargs["api_base"] == spec.endpoint
    assert complete.call_args.kwargs["think"] is False
    assert complete.call_args.kwargs["seed"] == 42


def test_model_resolves_api_key_environment(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "secret")

    model = LiteLLMModel(
        "openai/gpt-4o",
        connection=ModelConnection(api_key_env="MODEL_API_KEY"),
    )

    with patch("litellm.completion", return_value="response") as completion:
        model.complete([{"role": "user", "content": "Hello"}])

    assert completion.call_args.kwargs["api_key"] == "secret"


def test_complete_preserves_multimodal_messages_and_applies_overrides():
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,x"}},
            ],
        }
    ]
    model = LiteLLMModel(
        "openai/gpt-4o",
        generation=ModelGeneration(temperature=0.2, max_tokens=100),
    )

    with patch("litellm.completion", return_value="response") as completion:
        result = model.complete(messages, temperature=0.7)

    assert result.text == "response"
    completion.assert_called_once_with(
        model="openai/gpt-4o",
        messages=messages,
        timeout=120.0,
        max_tokens=100,
        temperature=0.7,
    )


@pytest.mark.asyncio
async def test_acomplete_uses_litellm_async_completion():
    model = LiteLLMModel("anthropic/claude-sonnet-4")

    with patch("litellm.acompletion", new=AsyncMock(return_value="response")) as call:
        result = await model.acomplete([{"role": "user", "content": "Hello"}])

    assert result.text == "response"
    call.assert_awaited_once()


def test_missing_api_key_environment_fails_during_instantiation(monkeypatch):
    monkeypatch.delenv("MISSING_MODEL_API_KEY", raising=False)

    with pytest.raises(ValueError, match="MISSING_MODEL_API_KEY"):
        LiteLLMModel(
            "openai/gpt-4o",
            connection=ModelConnection(api_key_env="MISSING_MODEL_API_KEY"),
        )


def test_empty_api_key_environment_fails_during_instantiation(monkeypatch):
    monkeypatch.setenv("EMPTY_MODEL_API_KEY", "")

    with pytest.raises(ValueError, match="EMPTY_MODEL_API_KEY.*empty"):
        LiteLLMModel(
            "openai/gpt-4o",
            connection=ModelConnection(api_key_env="EMPTY_MODEL_API_KEY"),
        )


def test_generation_rejects_transport_fields():
    with pytest.raises(ValidationError, match="api_key"):
        ModelGeneration.model_validate({"api_key": "not-allowed"})

    with pytest.raises(ValidationError, match="timeout"):
        ModelGeneration(extra_kwargs={"timeout": 10})


def test_generation_allows_explicit_provider_options():
    model = LiteLLMModel(
        "ollama_chat/llama3.2",
        generation=ModelGeneration(extra_kwargs={"top_k": 40}),
    )

    with patch("litellm.completion", return_value="response") as completion:
        model.complete([{"role": "user", "content": "Hello"}])

    assert completion.call_args.kwargs["top_k"] == 40


def test_complete_rejects_streaming():
    model = LiteLLMModel("openai/gpt-4o")

    with pytest.raises(ValueError, match="Streaming is not supported"):
        model.complete([{"role": "user", "content": "Hello"}], stream=True)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_provider_failures_have_one_native_response_contract(asynchronous):
    model = LiteLLMModel("openai/test")
    method = "litellm.acompletion" if asynchronous else "litellm.completion"
    with patch(method, side_effect=RuntimeError("provider unavailable")):
        response = (
            asyncio.run(model.acomplete([{"role": "user", "content": "test"}]))
            if asynchronous
            else model.complete([{"role": "user", "content": "test"}])
        )
    assert not response.ok
    assert response.error.message == "provider unavailable"
    assert response.metadata["error"]["category"] == "RuntimeError"


def test_complete_batch_preserves_order_and_bounds_concurrency():
    model = BatchModel()
    requests = [[{"role": "user", "content": str(index)}] for index in range(5)]

    responses = model.complete_batch(requests, max_concurrency=2)

    assert [response.text for response in responses] == ["0", "1", "2", "3", "4"]
    assert model.max_active == 2


@pytest.mark.asyncio
async def test_acomplete_batch_preserves_order_and_bounds_concurrency():
    model = BatchModel()
    requests = [[{"role": "user", "content": str(index)}] for index in range(5)]

    responses = await model.acomplete_batch(requests, max_concurrency=3)

    assert [response.text for response in responses] == ["0", "1", "2", "3", "4"]
    assert model.max_active == 3


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("side", ["before", "after"])
def test_native_guardrails_withhold_content_without_retries(asynchronous, side):
    classifier = LiteLLMModel("openai/classifier")
    target = LiteLLMModel("openai/target")
    guarded = GuardedModel(target, **{side: ModelGuardrail(classifier)})
    retrying = RetryingModel(guarded, retries=2)
    classifier_response = (
        '{"safe": false, "categories": ["test"], "reasoning": "blocked"}'
    )
    responses = (
        [classifier_response]
        if asynchronous or side == "before"
        else ["target content", classifier_response]
    )
    method = "litellm.acompletion" if asynchronous else "litellm.completion"
    with patch("litellm.completion", side_effect=responses) as sync_call:
        if asynchronous:
            with patch(
                method, new=AsyncMock(return_value="target content")
            ) as async_call:
                result = asyncio.run(
                    retrying.acomplete([{"role": "user", "content": "test"}])
                )
            assert async_call.await_count == (0 if side == "before" else 1)
        else:
            result = retrying.complete([{"role": "user", "content": "test"}])
    assert sync_call.call_count == (1 if asynchronous or side == "before" else 2)
    assert not result.ok
    assert result.error is None
    assert result.guardrail.side == side
    assert result.guardrail.categories == ["test"]
    assert result.text == ""
    assert result.raw_response is None


@pytest.mark.parametrize(
    "values", [{"max_tokens": 0}, {"temperature": -1}, {"top_p": 2}]
)
def test_native_generation_reuses_shared_validation(values):
    with pytest.raises(ValidationError):
        ModelGeneration(**values)


def test_batch_rejects_invalid_concurrency():
    model = BatchModel()

    with pytest.raises(ValueError, match="at least 1"):
        model.complete_batch([], max_concurrency=0)


def test_model_config_options_reach_the_native_backend():
    from unittest.mock import patch

    from hackagent.models.build import build_model
    from hackagent.models.config import ModelConfig

    config = ModelConfig.model_validate(
        {
            "name": "sonnet",
            "connection": {"provider": "legacy", "type": "CLAUDE_CODE", "endpoint": ""},
            "options": {"binary": "/custom/claude", "max_turns": 3},
        }
    )
    with patch(
        "hackagent.models.completions.cli.shutil.which", return_value="/custom/claude"
    ):
        model = build_model(config)
    assert model.binary == "/custom/claude"
    assert model.max_turns == 3
