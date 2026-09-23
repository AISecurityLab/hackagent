# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Model access: connect to a model or agent and call it.

``connect(spec)`` returns an :class:`~hackagent.core.contracts.LLM`. It
needs no storage backend and registers nothing. :class:`Guarded` adds
guardrails, and :class:`ModelFactory` builds role models with credentials
from :class:`~hackagent.core.settings.Settings`.
"""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "connect": "hackagent.models.client",
    "EnvelopeLLM": "hackagent.models.client",
    "ModelClient": "hackagent.models.client",
    "ModelFactory": "hackagent.models.factory",
    "spec_from_config": "hackagent.models.factory",
    "Guarded": "hackagent.models.guardrail",
    "GuardrailResult": "hackagent.models.guardrail",
    "GuardrailSpec": "hackagent.models.guardrail",
    "LLMGuardrail": "hackagent.models.guardrail",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    # Lazy, so importing a leaf such as ``models.envelope`` does not load
    # every adapter.
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(module), name)
