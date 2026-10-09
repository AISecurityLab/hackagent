# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Scripted stand-in for a connected :class:`Model`."""

from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Union

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.models.model import Model
from hackagent.models.response import ModelResponse


def text_response(text: str) -> Dict[str, Any]:
    """The success envelope-shaped dict a scripted reply maps from."""
    return {"generated_text": text, "processed_response": text, "error_message": None}


Reply = Union[str, Dict[str, Any], ModelResponse]
Script = Union[Iterable[Reply], Callable[[Dict[str, Any]], Any]]


def _as_response(value: Any) -> ModelResponse:
    """Map a scripted reply (text, envelope dict, or response) to a response."""
    if isinstance(value, ModelResponse):
        return value
    if isinstance(value, str):
        return ModelResponse(text=value)
    return ModelResponse.from_value(value)


class FakeLLM(Model):
    """Answers every call from a script and records each request.

    ``script`` is either an iterable of replies (a plain string becomes a text
    response; an envelope-shaped dict maps onto a :class:`ModelResponse`)
    consumed in order, or a callable mapping the recorded request dict to a
    reply (it may raise, to exercise judge/guardrail error handling). With no
    script every call returns ``default``. ``with_params`` returns a fake that
    shares the script and the recorded requests, merging the parameters into
    each recorded request.
    """

    def __init__(
        self,
        script: Optional[Script] = None,
        *,
        default: str = "fake response",
        spec: Optional[ModelSpec] = None,
        instance_id: str = "fake-llm",
        params: Optional[Dict[str, Any]] = None,
        _shared: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.spec = spec or ModelSpec(
            identifier="fake-model", agent_type=AgentType.OPENAI
        )
        self.instance_id = instance_id
        self.params = dict(params or {})
        if _shared is None:
            responder = script if callable(script) else None
            queue = (
                []
                if script is None or callable(script)
                else [_as_response(reply) for reply in script]
            )
            _shared = {
                "responder": responder,
                "queue": queue,
                "default": default,
                "requests": [],
            }
        self._shared = _shared

    @property
    def requests(self) -> List[Dict[str, Any]]:
        return self._shared["requests"]

    def with_params(self, **params: Any) -> "FakeLLM":
        return FakeLLM(
            spec=self.spec,
            instance_id=self.instance_id,
            params={**self.params, **params},
            _shared=self._shared,
        )

    def describe(self) -> ModelSpec:
        return self.spec

    def _respond(self, request: Dict[str, Any]) -> ModelResponse:
        if self._shared["responder"] is not None:
            return _as_response(self._shared["responder"](request))
        if self._shared["queue"]:
            return self._shared["queue"].pop(0)
        return ModelResponse(text=self._shared["default"])

    def complete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        if isinstance(messages, str):
            payload: Dict[str, Any] = {"prompt": messages}
        else:
            payload = {"messages": [dict(message) for message in messages]}
        request = {**self.params, **payload, **overrides}
        self.requests.append(request)
        return self._respond(request)

    async def acomplete(
        self, messages: Sequence[Mapping[str, Any]], **overrides: Any
    ) -> ModelResponse:
        return self.complete(messages, **overrides)
