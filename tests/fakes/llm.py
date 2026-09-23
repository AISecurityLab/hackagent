# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Scripted stand-in for a connected model (``LLM``)."""

from typing import Any, Callable, Dict, Iterable, List, Optional, Union

from hackagent.core.contracts import AgentType, ModelSpec
from hackagent.models.client import EnvelopeLLM
from tests.fakes.router import text_response

Response = Dict[str, Any]
Script = Union[Iterable[Union[str, Response]], Callable[[Dict[str, Any]], Response]]


class FakeLLM(EnvelopeLLM):
    """Answers every call from a script and records each request.

    ``script`` is either an iterable of responses (a plain string becomes a
    success envelope) consumed in order, or a callable mapping the request
    dict to an envelope. With no script every call returns ``default``.
    ``with_params`` returns a fake that shares the script and the recorded
    requests, and merges the parameters into each request.
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
            identifier="fake-model", agent_type=AgentType.OPENAI_SDK
        )
        self.instance_id = instance_id
        self.adapter = object()
        self.params = dict(params or {})
        if _shared is None:
            responder = script if callable(script) else None
            queue = (
                []
                if script is None or callable(script)
                else [text_response(r) if isinstance(r, str) else r for r in script]
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

    def send(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        request = {**self.params, **request_data}
        self.requests.append(request)
        if self._shared["responder"] is not None:
            return self._shared["responder"](request)
        if self._shared["queue"]:
            return self._shared["queue"].pop(0)
        return text_response(self._shared["default"])

    async def asend(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.send(request_data)
