# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Scripted models and a minimal campaign for campaign tests."""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Callable
from typing import Any, Mapping, Sequence

from hackagent.core.contracts import Goal, LLMError
from hackagent.models import Model, ModelConfig, ModelResponse

Reply = Callable[[Sequence[Mapping[str, Any]]], "str | ModelResponse"]


class ScriptedModel(Model):
    """Answers with ``reply(messages)`` and records every request."""

    def __init__(self, reply: Reply | str = "ok") -> None:
        self.reply = reply if callable(reply) else (lambda _messages: reply)
        self.requests: list[list[dict[str, Any]]] = []

    def complete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        return asyncio.run(self.acomplete(messages, **overrides))

    async def acomplete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        self.requests.append([dict(message) for message in messages])
        value = self.reply(messages)
        return value if isinstance(value, ModelResponse) else ModelResponse(text=value)


def failure(message: str = "boom") -> ModelResponse:
    return ModelResponse(text="", error=LLMError(message=message, category="APIError"))


class FakeBuilder:
    """Stands in for ``build_model``: one scripted model per model name."""

    def __init__(self, models: Mapping[str, ScriptedModel] | None = None) -> None:
        self.models = dict(models or {})
        self.built: list[tuple[str, int]] = []

    def __call__(self, config: ModelConfig, *, retries: int = 0) -> ScriptedModel:
        self.built.append((config.name, retries))
        return self.models.setdefault(config.name, ScriptedModel())


def goals(*texts: str) -> Callable[[Any], list[Goal]]:
    return lambda _dataset: [
        Goal(text=text, index=index) for index, text in enumerate(texts)
    ]


def model(name: str, endpoint: str = "http://127.0.0.1:8000/v1") -> dict[str, Any]:
    return {
        "name": name,
        "connection": {"provider": "vllm", "type": "OPENAI_SDK", "endpoint": endpoint},
        "generation": {"max_tokens": 64, "temperature": 0.0},
    }


BASE: dict[str, Any] = {
    "version": 1,
    "campaign": {"name": "test-campaign"},
    "dataset": {"preset": "harmbench"},
    "target": model("target"),
    "attacks": [{"name": "baseline"}],
    "evaluation": {
        "judges": [
            {
                **model("judge", "http://127.0.0.1:8001/v1"),
                "scoring": {"type": "harmbench"},
            }
        ],
    },
    "execution": {"output": {"formats": ["json", "jsonl"]}},
}


def campaign(**sections: Any) -> dict[str, Any]:
    """``BASE`` with top-level sections replaced (``execution`` is merged)."""
    values = copy.deepcopy(BASE)
    execution = sections.pop("execution", {})
    values.update(copy.deepcopy(sections))
    values["execution"] = {**values["execution"], **execution}
    return values
