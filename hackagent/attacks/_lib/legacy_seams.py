# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Legacy sibling imports still used by technique code.

Depth-0 packages import ``core`` and not each other. Techniques still
construct tracking coordinators, accept a storage ``Store`` on the obsolete
constructor, and build role models through ``LLMRouter``. Those imports live
only in this module, so the independence contract can forbid every other
sibling edge. New technique code uses :mod:`hackagent.attacks.ports` and
:mod:`hackagent.core`.
"""

from __future__ import annotations

from typing import Any

_TRACKING = frozenset({"Context", "StepTracker", "Tracker", "TrackingCoordinator"})
_MODELS = frozenset({"EnvelopeLLM", "connect", "spec_from_config"})

__all__ = sorted(_TRACKING | _MODELS | {"Store"})


def __getattr__(name: str) -> Any:
    if name in _TRACKING:
        from hackagent.tracking import (
            Context,
            StepTracker,
            Tracker,
            TrackingCoordinator,
        )

        namespace = {
            "Context": Context,
            "StepTracker": StepTracker,
            "Tracker": Tracker,
            "TrackingCoordinator": TrackingCoordinator,
        }
        globals().update(namespace)
        return namespace[name]
    if name == "Store":
        from hackagent.storage.store import Store

        globals()["Store"] = Store
        return Store
    if name in _MODELS:
        from hackagent.models.client import EnvelopeLLM, connect
        from hackagent.models.factory import spec_from_config

        namespace = {
            "EnvelopeLLM": EnvelopeLLM,
            "connect": connect,
            "spec_from_config": spec_from_config,
        }
        globals().update(namespace)
        return namespace[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
