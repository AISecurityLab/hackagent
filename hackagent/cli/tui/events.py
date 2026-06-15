# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Structured event bus for the TUI.

Replaces ad-hoc log-string parsing. Attack techniques, trackers, and
adapters emit typed events; TUI widgets subscribe and render them directly.

Events are delivered synchronously on the emitting thread. Subscribers that
need to update Textual widgets should wrap their callback in
``app.call_from_thread`` themselves; the bus does not assume a Textual app.
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# Event type constants. Using plain strings (not an Enum) keeps the bus
# friendly to ad-hoc emitters and to JSON serialization.
EVENT_STEP_STARTED = "step_started"
EVENT_STEP_ENDED = "step_ended"
EVENT_GOAL_STARTED = "goal_started"
EVENT_GOAL_FINALIZED = "goal_finalized"
EVENT_TOOL_CALL = "tool_call"
EVENT_TOOL_RESULT = "tool_result"
EVENT_LLM_REQUEST = "llm_request"
EVENT_LLM_RESPONSE = "llm_response"
EVENT_HTTP_REQUEST = "http_request"
EVENT_EVALUATION = "evaluation"
EVENT_PROGRESS = "progress"

ALL_EVENT_TYPES = (
    EVENT_STEP_STARTED,
    EVENT_STEP_ENDED,
    EVENT_GOAL_STARTED,
    EVENT_GOAL_FINALIZED,
    EVENT_TOOL_CALL,
    EVENT_TOOL_RESULT,
    EVENT_LLM_REQUEST,
    EVENT_LLM_RESPONSE,
    EVENT_HTTP_REQUEST,
    EVENT_EVALUATION,
    EVENT_PROGRESS,
)


@dataclass(frozen=True)
class TUIEvent:
    """A single bus event.

    ``event_type`` is one of the ``EVENT_*`` constants. ``payload`` is the
    structured data — its shape depends on the event type. ``timestamp`` is
    wall-clock seconds since the epoch, set automatically.
    """

    event_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


Subscriber = Callable[[TUIEvent], None]


class TUIEventBus:
    """Thread-safe pub/sub event bus.

    Subscribers register per event type (or for all events). Emitters call
    :meth:`emit` from any thread; subscriber callbacks run synchronously on
    the emitting thread. Exceptions raised by subscribers are logged and
    swallowed so a misbehaving subscriber cannot break the attack.
    """

    _ALL = "__all__"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: Dict[str, List[Subscriber]] = {}
        self._logger = logging.getLogger("hackagent.cli.tui.events")

    def subscribe(
        self,
        callback: Subscriber,
        event_type: Optional[str] = None,
    ) -> None:
        """Register a subscriber.

        Args:
            callback: Function called with each matching :class:`TUIEvent`.
            event_type: Specific event type to subscribe to. If ``None``,
                the subscriber receives every event.
        """
        key = event_type or self._ALL
        with self._lock:
            self._subscribers.setdefault(key, []).append(callback)

    def unsubscribe(
        self,
        callback: Subscriber,
        event_type: Optional[str] = None,
    ) -> None:
        """Remove a previously registered subscriber. No-op if not found."""
        key = event_type or self._ALL
        with self._lock:
            subs = self._subscribers.get(key)
            if not subs:
                return
            try:
                subs.remove(callback)
            except ValueError:
                pass

    def emit(self, event_type: str, **payload: Any) -> None:
        """Emit an event to all matching subscribers.

        Args:
            event_type: One of the ``EVENT_*`` constants. Custom types are
                allowed but will only be seen by ``subscribe(..., None)``
                catch-all subscribers and by subscribers using the exact
                same string.
            **payload: Structured event data; merged into ``TUIEvent.payload``.
        """
        import time

        event = TUIEvent(
            event_type=event_type,
            payload=dict(payload),
            timestamp=time.time(),
        )

        # Snapshot the subscriber list under lock, then dispatch outside
        # the lock so a slow subscriber cannot block other emitters.
        with self._lock:
            specific = list(self._subscribers.get(event_type, ()))
            catch_all = list(self._subscribers.get(self._ALL, ()))

        for cb in specific + catch_all:
            try:
                cb(event)
            except Exception:
                self._logger.debug(
                    "TUI event subscriber raised; ignoring", exc_info=True
                )

    def clear(self) -> None:
        """Remove every subscriber. Useful between attack runs."""
        with self._lock:
            self._subscribers.clear()
