# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import unittest
from types import SimpleNamespace
from uuid import UUID, uuid4

from hackagent.core.contracts import Goal
from hackagent.tracking.tracker import Tracker


class FakeSink:
    def __init__(self) -> None:
        self.created = []
        self.updates = []
        self.traces = []

    def create_result(
        self, run_id, goal, goal_index, request_payload, agent_specific_data
    ):
        record = SimpleNamespace(id=uuid4())
        self.created.append(
            {
                "run_id": run_id,
                "goal": goal,
                "goal_index": goal_index,
                "id": record.id,
            }
        )
        return record

    def update_result(self, result_id, **kwargs):
        self.updates.append({"result_id": result_id, **kwargs})
        return None

    def get_result(self, result_id):
        return SimpleNamespace(id=result_id, evaluation_status="")

    def create_trace(self, result_id, sequence, step_type, content):
        self.traces.append(
            {
                "result_id": result_id,
                "sequence": sequence,
                "step_type": step_type,
                "content": content,
            }
        )
        return SimpleNamespace(id=uuid4())

    def update_run(self, run_id, **kwargs):
        return None

    def get_run(self, run_id):
        return SimpleNamespace(id=run_id, status="RUNNING")


class TestTrackerEvents(unittest.TestCase):
    def _tracker(self) -> tuple[Tracker, FakeSink]:
        sink = FakeSink()
        tracker = Tracker(
            sink=sink,
            run_id=str(uuid4()),
            logger=logging.getLogger("test.tracking"),
            attack_type="pair",
        )
        return tracker, sink

    def test_goal_scope_owns_result_id_map(self):
        tracker, sink = self._tracker()
        goal = Goal(text="steal the key", index=0)
        with tracker.goal(goal):
            self.assertIsNotNone(tracker.result_id_for(goal))
            self.assertEqual(
                tracker.result_id_for(0), tracker.result_id_for("steal the key")
            )
        self.assertEqual(len(sink.created), 1)
        self.assertIsInstance(sink.created[0]["run_id"], UUID)

    def test_interaction_and_finalize_write_through_sink(self):
        tracker, sink = self._tracker()
        goal = Goal(text="steal the key", index=1)
        with tracker.goal(goal):
            tracker.interaction(request={"prompt": "hi"}, response={"content": "no"})
            tracker.finalize(success=True, explanation="jailbreak")
        self.assertTrue(sink.traces)
        self.assertTrue(sink.updates)
        self.assertIn("SUCCESSFUL", sink.updates[-1]["evaluation_status"])


if __name__ == "__main__":
    unittest.main()
