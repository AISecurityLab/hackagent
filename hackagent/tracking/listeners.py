# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Fan tracker events out to interfaces.

Interfaces subscribe with a listener. Tracking does not import them.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, Sequence, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class EventListener(Protocol):
    """One subscriber. ``kind`` is the event name; ``payload`` is its data."""

    def on_event(self, kind: str, **payload: Any) -> None: ...


class BusListener:
    """Adapt an object with ``emit(kind, **payload)`` (the TUI bus)."""

    def __init__(self, bus: Any) -> None:
        self._bus = bus

    def on_event(self, kind: str, **payload: Any) -> None:
        emit = getattr(self._bus, "emit", None)
        if emit is None:
            return
        emit(kind, **payload)


class Fanout:
    """Deliver each event to every listener. One failure does not stop the rest."""

    def __init__(self, listeners: Sequence[EventListener] | None = None) -> None:
        self._listeners: list[EventListener] = list(listeners or [])

    def add(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    def emit(self, kind: str, **payload: Any) -> None:
        for listener in list(self._listeners):
            try:
                listener.on_event(kind, **payload)
            except Exception:
                logger.debug("listener failed for %s", kind, exc_info=True)
