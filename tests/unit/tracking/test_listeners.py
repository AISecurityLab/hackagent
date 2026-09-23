# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.tracking.listeners import BusListener, Fanout


class _Recorder:
    def __init__(self) -> None:
        self.events = []

    def on_event(self, kind, **payload):
        self.events.append((kind, payload))


class _Boom:
    def on_event(self, kind, **payload):
        raise RuntimeError("listener down")


class TestFanout(unittest.TestCase):
    def test_delivers_to_every_listener(self):
        first = _Recorder()
        second = _Recorder()
        fanout = Fanout([first])
        fanout.add(second)
        fanout.emit("step_started", step_name="eval")
        self.assertEqual(first.events, [("step_started", {"step_name": "eval"})])
        self.assertEqual(second.events, first.events)

    def test_one_failure_does_not_stop_the_rest(self):
        keeper = _Recorder()
        fanout = Fanout([_Boom(), keeper])
        fanout.emit("log", message="hi")
        self.assertEqual(keeper.events, [("log", {"message": "hi"})])


class _Bus:
    def __init__(self) -> None:
        self.events = []

    def emit(self, kind, **payload):
        self.events.append((kind, payload))


class TestBusListener(unittest.TestCase):
    def test_forwards_to_emit(self):
        bus = _Bus()
        BusListener(bus).on_event("goal_started", goal_index=0)
        self.assertEqual(bus.events, [("goal_started", {"goal_index": 0})])

    def test_ignores_a_bus_without_emit(self):
        BusListener(object()).on_event("log", message="hi")


if __name__ == "__main__":
    unittest.main()
