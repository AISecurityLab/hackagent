# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The ``route_request`` surface the techniques call, over an LLM.

The techniques still call ``router.route_request(registration_key=...,
request_data=...)`` and read ``backend_agent`` and ``_agent_registry``.
:class:`LLMRouter` presents an :class:`~hackagent.models.EnvelopeLLM`
that way, with no storage behind it. It goes away once the techniques
call ``LLM.complete`` (Phase 5 of #640).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from hackagent.models.client import EnvelopeLLM, connect
from hackagent.models.factory import spec_from_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelInfo:
    """What the techniques read off ``router.backend_agent``."""

    id: str
    name: str
    agent_type: str
    endpoint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMRouter:
    """Routes ``route_request`` calls to one LLM.

    Args:
        llm: The model to call.
        agent: Identity to expose as ``backend_agent``; the target passes
            its Agent record. Defaults to one derived from the LLM's spec.
    """

    def __init__(self, llm: EnvelopeLLM, *, agent: Any = None) -> None:
        self.llm = llm
        self.registration_key = llm.instance_id
        if agent is None:
            spec = llm.describe()
            agent = ModelInfo(
                id=llm.instance_id,
                name=spec.identifier,
                agent_type=spec.agent_type.value,
                endpoint=spec.endpoint,
                metadata={"name": spec.identifier},
            )
        self.backend_agent = agent
        self._agent_registry = {self.registration_key: llm.adapter}

    def with_params(self, **params: Any) -> "LLMRouter":
        """A router over ``llm.with_params(...)`` with the same identity."""
        return LLMRouter(self.llm.with_params(**params), agent=self.backend_agent)

    def get_agent_instance(self, registration_key: str) -> Any:
        return self._agent_registry.get(registration_key)

    def _not_found(self, registration_key: str, request_data: Dict[str, Any]):
        message = f"Agent not found for key: {registration_key}"
        logger.error(message)
        return {
            "raw_request": request_data,
            "processed_response": None,
            "generated_text": None,
            "status_code": 404,
            "raw_response_status": 404,
            "raw_response_headers": None,
            "raw_response_body": None,
            "agent_specific_data": None,
            "error_message": message,
            "error_category": "AgentNotFound",
            "agent_id": registration_key,
            "adapter_type": "LLMRouter",
        }

    def route_request(
        self, registration_key: str, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send ``request_data`` and return the response envelope."""
        if registration_key != self.registration_key:
            return self._not_found(registration_key, request_data)
        return self.llm.send(request_data)

    async def route_request_async(
        self, registration_key: str, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Asynchronous :meth:`route_request`."""
        if registration_key != self.registration_key:
            return self._not_found(registration_key, request_data)
        return await self.llm.asend(request_data)


def connect_role(
    config: Dict[str, Any],
    *,
    name: Optional[str] = None,
    models: Any = None,
) -> Tuple[LLMRouter, str]:
    """Connect to the role model ``config`` describes.

    When *models* (an ``LLMFactory`` from ``ctx.models``) is provided, the
    role is built through ``models.for_role`` instead of a bare ``connect``.

    Returns the router and its registration key. The model uses only the
    credentials its config names.

    Raises:
        ValueError: If the config is invalid or the adapter rejects it.
    """
    spec = spec_from_config(config)
    llm = models.for_role(spec) if models is not None else connect(spec)
    router = LLMRouter(llm)
    logger.debug(
        "Role model '%s' ready (%s via %s, key %s)",
        name or spec.identifier,
        spec.identifier,
        spec.endpoint,
        router.registration_key,
    )
    return router, router.registration_key
