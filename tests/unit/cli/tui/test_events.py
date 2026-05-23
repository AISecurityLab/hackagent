# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for :mod:`hackagent.cli.tui.events`."""

import threading
import time

import pytest

from hackagent.cli.tui.events import (
    EVENT_GOAL_FINALIZED,
    EVENT_GOAL_STARTED,
    EVENT_STEP_ENDED,
    EVENT_STEP_STARTED,
    EVENT_TOOL_CALL,
    TUIEvent,
    TUIEventBus,
)


class TestTUIEventBusBasics:
    """Smoke tests for emit/subscribe/unsubscribe."""

    def test_subscribe_specific_event_delivers_event(self) -> None:
        bus = TUIEventBus()
        received: list[TUIEvent] = []
        bus.subscribe(received.append, event_type=EVENT_STEP_STARTED)

        bus.emit(EVENT_STEP_STARTED, step_name="Attack")

        assert len(received) == 1
        assert received[0].event_type == EVENT_STEP_STARTED
        assert received[0].payload == {"step_name": "Attack"}
        assert received[0].timestamp > 0

    def test_subscribe_specific_event_filters_other_types(self) -> None:
        bus = TUIEventBus()
        received: list[TUIEvent] = []
        bus.subscribe(received.append, event_type=EVENT_GOAL_FINALIZED)

        bus.emit(EVENT_STEP_STARTED, step_name="Attack")
        bus.emit(EVENT_GOAL_FINALIZED, goal_index=0, success=True)

        assert len(received) == 1
        assert received[0].event_type == EVENT_GOAL_FINALIZED

    def test_catch_all_subscriber_receives_every_event(self) -> None:
        bus = TUIEventBus()
        received: list[TUIEvent] = []
        bus.subscribe(received.append)  # event_type=None

        bus.emit(EVENT_STEP_STARTED)
        bus.emit(EVENT_GOAL_STARTED, goal_index=0)
        bus.emit(EVENT_TOOL_CALL, tool_name="grep")

        assert [e.event_type for e in received] == [
            EVENT_STEP_STARTED,
            EVENT_GOAL_STARTED,
            EVENT_TOOL_CALL,
        ]

    def test_unsubscribe_stops_delivery(self) -> None:
        bus = TUIEventBus()
        received: list[TUIEvent] = []
        bus.subscribe(received.append, event_type=EVENT_STEP_STARTED)
        bus.unsubscribe(received.append, event_type=EVENT_STEP_STARTED)

        bus.emit(EVENT_STEP_STARTED, step_name="Attack")
        assert received == []

    def test_unsubscribe_unknown_is_noop(self) -> None:
        bus = TUIEventBus()
        # Not raising means the test passes.
        bus.unsubscribe(lambda e: None, event_type=EVENT_STEP_STARTED)
        bus.unsubscribe(lambda e: None)

    def test_clear_removes_all_subscribers(self) -> None:
        bus = TUIEventBus()
        received: list[TUIEvent] = []
        bus.subscribe(received.append, event_type=EVENT_STEP_STARTED)
        bus.subscribe(received.append)
        bus.clear()

        bus.emit(EVENT_STEP_STARTED)
        assert received == []


class TestTUIEventBusIsolation:
    """A misbehaving subscriber must not break the bus."""

    def test_subscriber_exception_does_not_propagate(self) -> None:
        bus = TUIEventBus()

        def bad(_event: TUIEvent) -> None:
            raise RuntimeError("boom")

        received: list[TUIEvent] = []
        bus.subscribe(bad, event_type=EVENT_STEP_STARTED)
        bus.subscribe(received.append, event_type=EVENT_STEP_STARTED)

        # Should NOT raise, and the second subscriber must still receive.
        bus.emit(EVENT_STEP_STARTED, step_name="ok")
        assert len(received) == 1

    def test_subscriber_exception_does_not_block_catchall(self) -> None:
        bus = TUIEventBus()
        received_catchall: list[TUIEvent] = []
        bus.subscribe(lambda _e: (_ for _ in ()).throw(ValueError("nope")))
        bus.subscribe(received_catchall.append)

        bus.emit(EVENT_TOOL_CALL, tool_name="grep")
        assert len(received_catchall) == 1


class TestTUIEventBusThreadSafety:
    """Concurrent emitters / subscribers shouldn't drop or duplicate events."""

    def test_concurrent_emits_deliver_all(self) -> None:
        bus = TUIEventBus()
        received: list[TUIEvent] = []
        lock = threading.Lock()

        def collect(event: TUIEvent) -> None:
            with lock:
                received.append(event)

        bus.subscribe(collect, event_type=EVENT_GOAL_FINALIZED)

        per_thread = 50
        threads = [
            threading.Thread(
                target=lambda i=i: [
                    bus.emit(EVENT_GOAL_FINALIZED, goal_index=i, n=k)
                    for k in range(per_thread)
                ]
            )
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(received) == 4 * per_thread

    def test_subscribe_during_emit_is_safe(self) -> None:
        """Adding a subscriber while emit() runs must not corrupt the list."""
        bus = TUIEventBus()
        received: list[TUIEvent] = []

        def subscriber_that_adds(_event: TUIEvent) -> None:
            received.append(_event)
            # Subscribe a no-op while we're in a dispatch — exercising the
            # snapshot-under-lock pattern the bus relies on.
            bus.subscribe(lambda _e: None, event_type=EVENT_STEP_ENDED)

        bus.subscribe(subscriber_that_adds, event_type=EVENT_STEP_ENDED)
        bus.emit(EVENT_STEP_ENDED, step_name="x")
        bus.emit(EVENT_STEP_ENDED, step_name="y")
        assert len(received) == 2


class TestTUIEventBusPayload:
    """Sanity checks on payload shape."""

    def test_payload_is_copied_per_event(self) -> None:
        bus = TUIEventBus()
        received: list[TUIEvent] = []
        bus.subscribe(received.append, event_type=EVENT_TOOL_CALL)

        # Caller can mutate kwargs without affecting delivered payload.
        kwargs = {"tool_name": "grep", "args": [1, 2, 3]}
        bus.emit(EVENT_TOOL_CALL, **kwargs)
        kwargs["tool_name"] = "mutated"

        assert received[0].payload["tool_name"] == "grep"

    def test_timestamp_is_monotonic_within_burst(self) -> None:
        bus = TUIEventBus()
        received: list[TUIEvent] = []
        bus.subscribe(received.append)

        for i in range(5):
            bus.emit(EVENT_STEP_STARTED, i=i)
            time.sleep(0.001)

        timestamps = [e.timestamp for e in received]
        assert timestamps == sorted(timestamps)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
