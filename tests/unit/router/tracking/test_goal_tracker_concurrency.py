# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Concurrency coverage for goal-level trace tracking."""

import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

from hackagent.router.tracking.tracker import Context, Tracker


class _SlowFirstTraceBackend:
    """Backend that exposes writes being reordered without a context lock."""

    def __init__(self) -> None:
        self.persisted_sequences: list[int] = []

    def create_trace(self, result_id, sequence, step_type, content):
        if sequence == 1:
            time.sleep(0.05)
        self.persisted_sequences.append(sequence)
        return SimpleNamespace(id=uuid4())


class TestGoalTrackerConcurrency(unittest.TestCase):
    def test_parallel_trace_writes_keep_local_and_persisted_order(self):
        backend = _SlowFirstTraceBackend()
        tracker = Tracker(
            backend=backend,
            run_id=str(uuid4()),
            disable_goal_category_classifier=True,
        )
        ctx = Context(goal="goal", goal_index=0, result_id=str(uuid4()))
        start = threading.Barrier(2)

        def add_trace(index: int) -> None:
            start.wait(timeout=1)
            tracker.add_custom_trace(ctx, f"trace-{index}", {"index": index})

        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(add_trace, (1, 2)))

        self.assertEqual([trace["sequence"] for trace in ctx.traces], [1, 2])
        self.assertEqual(backend.persisted_sequences, [1, 2])
