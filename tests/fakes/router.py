# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Scripted stand-in for the ``route_request`` surface (``LLMRouter``)."""

from types import SimpleNamespace
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

Response = Dict[str, Any]
Script = Union[Iterable[Union[str, Response]], Callable[[Dict[str, Any]], Response]]


def text_response(text: Optional[str]) -> Response:
    """Build the success envelope ``route_request`` returns for ``text``."""
    return {
        "generated_text": text,
        "processed_response": text,
        "error_message": None,
    }


class FakeRouter:
    """Answers ``route_request`` from a script and records every request.

    ``script`` is either an iterable of responses (a plain string becomes a
    success envelope) consumed in order, or a callable mapping
    ``request_data`` to a response. With no script every call returns
    ``default``.
    """

    def __init__(
        self,
        script: Optional[Script] = None,
        *,
        default: str = "fake response",
        agent_id: str = "fake-agent-id",
        name: str = "fake-model",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._responder: Optional[Callable[[Dict[str, Any]], Response]] = None
        self._queue: List[Response] = []
        if callable(script):
            self._responder = script
        elif script is not None:
            self._queue = [
                text_response(r) if isinstance(r, str) else r for r in script
            ]
        self._default = default
        self.requests: List[Dict[str, Any]] = []
        self.backend_agent = SimpleNamespace(
            id=agent_id, name=name, metadata=metadata or {}, endpoint=None
        )
        self._agent_registry = {agent_id: SimpleNamespace(id=agent_id)}

    def route_request(
        self,
        registration_key: str,
        request_data: Dict[str, Any],
        raise_on_error: bool = False,
    ) -> Response:
        self.requests.append(request_data)
        if self._responder is not None:
            return self._responder(request_data)
        if self._queue:
            return self._queue.pop(0)
        return text_response(self._default)

    def get_agent_instance(self, registration_key: str) -> Any:
        return self._agent_registry.get(registration_key)
