# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The :class:`~hackagent.core.contracts.LLM` implementation and ``connect``."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional, Sequence, Union

from hackagent.core.contracts import Completion, Message, ModelSpec
from hackagent.models import dispatch
from hackagent.models import envelope as _envelope
from hackagent.models.adapters import litellm_callbacks as _callbacks

#: Call parameters that map onto a :class:`ModelSpec` field in ``describe``.
_SPEC_PARAMS = ("max_tokens", "temperature", "top_p", "timeout", "thinking")


class EnvelopeLLM:
    """An :class:`LLM` whose calls go through a response envelope.

    Subclasses implement :meth:`send` and :meth:`asend`, which take a request
    dict and return the envelope; ``complete`` and ``acomplete`` convert it
    into a :class:`Completion`. The techniques still call ``send`` (through
    ``attacks.shared.llm_router``) until they move to ``complete``.
    """

    instance_id: str
    adapter: Any

    def send(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    async def asend(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def with_params(self, **params: Any) -> "EnvelopeLLM":
        raise NotImplementedError

    def describe(self) -> ModelSpec:
        raise NotImplementedError

    def complete(
        self, messages: Union[str, Sequence[Message]], **params: Any
    ) -> Completion:
        request = _envelope.request_from_messages(messages, params)
        return _envelope.to_completion(self.send(request))

    async def acomplete(
        self, messages: Union[str, Sequence[Message]], **params: Any
    ) -> Completion:
        request = _envelope.request_from_messages(messages, params)
        return _envelope.to_completion(await self.asend(request))


class ModelClient(EnvelopeLLM):
    """One connected model or agent. Build it with :func:`connect`.

    ``with_params`` returns a new client sharing the same adapter, with
    call parameters that apply whenever a request does not set them. The
    adapter itself is never mutated, so run-scoped parameters are safe
    under parallel goals.
    """

    def __init__(
        self,
        spec: ModelSpec,
        adapter: Any,
        *,
        instance_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._spec = spec
        self.adapter = adapter
        self.instance_id = instance_id
        self._params: Dict[str, Any] = dict(params or {})

    def __repr__(self) -> str:
        return (
            f"ModelClient({self._spec.agent_type.value}:{self._spec.identifier}, "
            f"id={self.instance_id})"
        )

    @property
    def params(self) -> Dict[str, Any]:
        """The parameters set with :meth:`with_params`."""
        return dict(self._params)

    def with_params(self, **params: Any) -> "ModelClient":
        return ModelClient(
            self._spec,
            self.adapter,
            instance_id=self.instance_id,
            params={**self._params, **params},
        )

    def describe(self) -> ModelSpec:
        """The spec this client was connected with, plus its parameters."""
        if not self._params:
            return self._spec
        update: Dict[str, Any] = {}
        extra = dict(self._spec.extra)
        for key, value in self._params.items():
            if key in _SPEC_PARAMS:
                update[key] = value
            else:
                extra[key] = value
        update["extra"] = extra
        return self._spec.model_copy(update=update)

    def _request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._params:
            return request_data
        return {**self._params, **request_data}

    def send(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        return dispatch.send(
            self.adapter,
            self._spec.agent_type,
            self._request(request_data),
            instance_id=self.instance_id,
        )

    async def asend(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        return await dispatch.asend(
            self.adapter,
            self._spec.agent_type,
            self._request(request_data),
            instance_id=self.instance_id,
        )


def connect(spec: ModelSpec, *, instance_id: Optional[str] = None) -> ModelClient:
    """Connect to the model ``spec`` describes. Does no network I/O.

    Args:
        spec: The model to reach. ADK agents read ``user_id`` from
            ``spec.extra``.
        instance_id: Identifies this client in logs and in the LiteLLM
            provider names the adapters register. Defaults to a random id.

    Raises:
        ValueError: If the agent type is unsupported or the adapter rejects
            the spec.
    """
    _callbacks.ensure_registered()
    instance_id = instance_id or uuid.uuid4().hex
    adapter = dispatch.build_adapter(spec, instance_id=instance_id)
    return ModelClient(spec, adapter, instance_id=instance_id)


__all__ = ["EnvelopeLLM", "ModelClient", "connect"]
