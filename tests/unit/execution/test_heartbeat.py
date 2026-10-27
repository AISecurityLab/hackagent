# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the background run heartbeat."""

import threading
import time
from uuid import uuid4

from hackagent.orchestrator.execution.heartbeat import RunHeartbeat
from hackagent.storage import ExecutorRejected


class FakeStore:
    def __init__(self, results):
        self._results = list(results)
        self.calls = 0
        self.called = threading.Event()

    def heartbeat_run(self, run_id):
        self.calls += 1
        self.called.set()
        result = self._results.pop(0) if len(self._results) > 1 else self._results[0]
        if isinstance(result, Exception):
            raise result
        return result


def _wait(event, timeout=2.0):
    return event.wait(timeout)


def test_sets_cancel_when_server_requests():
    store = FakeStore([False, True])
    changes = []
    hb = RunHeartbeat(store, uuid4(), interval_s=0.01)
    hb.on_change = lambda: changes.append(1)
    with hb:
        assert _wait(hb.cancel_requested)
        assert not hb.rejected.is_set()
    assert changes == [1]


def test_sets_rejected_on_401():
    store = FakeStore([ExecutorRejected("401")])
    changes = []
    hb = RunHeartbeat(store, uuid4(), interval_s=0.01)
    hb.on_change = lambda: changes.append(1)
    with hb:
        assert _wait(hb.rejected)
        time.sleep(0.05)
        calls = store.calls
        time.sleep(0.05)
        assert store.calls == calls  # the thread stopped
    assert not hb.cancel_requested.is_set()
    assert changes == [1]


def test_stops_on_exit():
    store = FakeStore([False])
    with RunHeartbeat(store, uuid4(), interval_s=0.01):
        assert _wait(store.called)
    calls = store.calls
    time.sleep(0.05)
    assert store.calls == calls


def test_keeps_beating_after_a_network_error():
    store = FakeStore([RuntimeError("boom"), True])
    with RunHeartbeat(store, uuid4(), interval_s=0.01) as hb:
        assert _wait(hb.cancel_requested)
        assert not hb.rejected.is_set()


def test_on_change_fires_once_per_event():
    store = FakeStore([True])
    changes = []
    hb = RunHeartbeat(store, uuid4(), interval_s=0.01)
    hb.on_change = lambda: changes.append(1)
    with hb:
        assert _wait(hb.cancel_requested)
        time.sleep(0.1)
    assert changes == [1]


def test_a_late_answer_after_exit_signals_nothing():
    """A heartbeat in flight when the run ends must not report a rejection."""
    answering = threading.Event()
    release = threading.Event()

    class SlowStore:
        def heartbeat_run(self, run_id):
            answering.set()
            release.wait(2.0)
            raise ExecutorRejected("403")

    changes = []
    hb = RunHeartbeat(SlowStore(), uuid4(), interval_s=0.01)
    hb.on_change = lambda: changes.append(1)
    thread_exit = threading.Thread(target=lambda: hb.__exit__(None, None, None))
    hb.__enter__()
    assert _wait(answering)
    thread_exit.start()
    time.sleep(0.05)  # __exit__ has set the stop flag and is joining
    release.set()
    thread_exit.join(2.0)
    assert not hb.rejected.is_set()
    assert changes == []
