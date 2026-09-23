# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tracker implements Events and writes through RunSink. RecordingEvents records the port."""

import logging
import unittest
from types import SimpleNamespace
from uuid import UUID, uuid4

from hackagent.attacks.ports import Events
from hackagent.core.contracts import EvalStatus, Goal
from hackagent.tracking.sink import RunSink
from hackagent.tracking.tracker import UNKNOWN_CATEGORY, UNKNOWN_SUBCATEGORY, Tracker
from tests.fakes.context import RecordingEvents, make_ctx


class RecordingSink:
    """In-memory RunSink. Records every write and serves scripted reads."""

    def __init__(self, existing_status: str = "") -> None:
        self.created = []
        self.updates = []
        self.traces = []
        self.runs = []
        self.existing_status = existing_status

    def create_result(
        self, run_id, goal, goal_index, request_payload, agent_specific_data
    ):
        record = SimpleNamespace(id=uuid4())
        self.created.append(
            {
                "run_id": run_id,
                "goal": goal,
                "goal_index": goal_index,
                "request_payload": request_payload,
                "agent_specific_data": agent_specific_data,
                "id": record.id,
            }
        )
        return record

    def update_result(self, result_id, **kwargs):
        self.updates.append({"result_id": result_id, **kwargs})
        return None

    def get_result(self, result_id):
        return SimpleNamespace(id=result_id, evaluation_status=self.existing_status)

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
        self.runs.append({"run_id": run_id, **kwargs})
        return None

    def get_run(self, run_id):
        return SimpleNamespace(id=run_id, status="RUNNING")


class _Recorder:
    def __init__(self) -> None:
        self.events = []

    def on_event(self, kind, **payload):
        self.events.append((kind, payload))


class _Boom:
    def on_event(self, kind, **payload):
        raise RuntimeError("listener down")


class TestRecordingEvents(unittest.TestCase):
    def test_records_the_events_port(self):
        events = RecordingEvents()
        goal = Goal(text="steal the key", index=0)

        with events.step("Evaluation", "eval"):
            with events.goal(goal):
                events.interaction(request={"prompt": "hi"}, response={"content": "no"})
                events.evaluation(score=10.0, explanation="jailbreak")
                events.trace(step_name="note", detail="kept")
                events.finalize(success=True, explanation="jailbreak")
        events.progress(1.0, "done")
        events.log("finished", level="info")

        self.assertEqual(
            [call[0] for call in events.calls],
            [
                "step",
                "goal",
                "interaction",
                "evaluation",
                "trace",
                "finalize",
                "progress",
                "log",
            ],
        )
        self.assertIsInstance(events, Events)
        ctx = make_ctx(events=events)
        self.assertIs(ctx.events, events)


class TestTrackerEvents(unittest.TestCase):
    def _tracker(self, **kwargs) -> tuple[Tracker, RecordingSink, _Recorder]:
        sink = kwargs.pop("sink", None) or RecordingSink()
        listener = _Recorder()
        tracker = Tracker(
            sink=sink,
            run_id=kwargs.pop("run_id", str(uuid4())),
            logger=logging.getLogger("test.tracking"),
            attack_type=kwargs.pop("attack_type", "pair"),
            listeners=[_Boom(), listener],
            **kwargs,
        )
        return tracker, sink, listener

    def test_tracker_satisfies_events_and_run_sink(self):
        tracker, sink, _listener = self._tracker()
        self.assertIsInstance(tracker, Events)
        self.assertIsInstance(sink, RunSink)
        ctx = make_ctx(events=tracker)
        self.assertIs(ctx.events, tracker)

    def test_goal_scope_owns_result_id_map(self):
        tracker, sink, listener = self._tracker()
        goal = Goal(text="steal the key", index=0)
        with tracker.goal(goal) as ctx:
            self.assertIsNotNone(tracker.result_id_for(goal))
            self.assertEqual(
                tracker.result_id_for(0), tracker.result_id_for("steal the key")
            )
            self.assertEqual(ctx.result_id, tracker.result_id_for(goal))
        self.assertEqual(tracker.result_id_for(goal), str(sink.created[0]["id"]))
        self.assertEqual(len(sink.created), 1)
        self.assertIsInstance(sink.created[0]["run_id"], UUID)
        self.assertEqual(
            sink.created[0]["agent_specific_data"]["category"], UNKNOWN_CATEGORY
        )
        self.assertEqual(
            sink.created[0]["agent_specific_data"]["subcategory"],
            UNKNOWN_SUBCATEGORY,
        )
        kinds = [kind for kind, _payload in listener.events]
        self.assertIn("goal_started", kinds)
        self.assertIn("trace_added", kinds)

    def test_repeated_goal_text_keeps_the_first_result_id(self):
        tracker, _sink, _listener = self._tracker()
        with tracker.goal(Goal(text="same", index=0)):
            first = tracker.result_id_for("same")
        with tracker.goal(Goal(text="same", index=1)):
            second = tracker.result_id_for(1)
        self.assertEqual(tracker.result_id_for("same"), first)
        self.assertNotEqual(second, first)
        self.assertEqual(tracker.result_id_for(Goal(text="same", index=0)), first)
        self.assertEqual(tracker.result_id_for(Goal(text="same", index=1)), second)

    def test_preclassified_labels_are_stored_and_classifier_config_is_ignored(self):
        tracker, sink, _listener = self._tracker(
            category_classifier_config={"identifier": "ignored"},
            preclassified_goal_labels_by_index={
                0: {"category": "A. Cat", "subcategory": "A1. Sub"},
            },
        )
        with tracker.goal(Goal(text="labelled", index=0)):
            pass
        data = sink.created[0]["agent_specific_data"]
        self.assertEqual(data["category"], "A. Cat")
        self.assertEqual(data["subcategory"], "A1. Sub")
        self.assertNotIn("identifier", data)

    def test_interaction_evaluation_and_finalize_write_through_sink(self):
        tracker, sink, listener = self._tracker()
        goal = Goal(text="steal the key", index=1)
        with tracker.goal(goal):
            tracker.interaction(request={"prompt": "hi"}, response={"content": "no"})
            tracker.evaluation(
                score=10.0, explanation="jailbreak", evaluator="harmbench"
            )
            tracker.trace(step_name="note", detail="kept")
            tracker.finalize(success=True, explanation="jailbreak")

        self.assertEqual([trace["sequence"] for trace in sink.traces], [1, 2, 3, 4])
        self.assertEqual(sink.traces[0]["content"]["goal"], "steal the key")
        interaction = sink.traces[1]["content"]
        self.assertEqual(interaction["request"], {"prompt": "hi"})
        self.assertEqual(interaction["response"], "no")
        self.assertEqual(sink.traces[2]["content"]["step_name"], "Evaluation")
        self.assertEqual(sink.traces[2]["content"]["score"], 10.0)
        self.assertEqual(sink.traces[3]["content"]["detail"], "kept")
        self.assertEqual(sink.updates[-1]["evaluation_status"], "SUCCESSFUL_JAILBREAK")
        self.assertEqual(sink.updates[-1]["evaluation_notes"], "jailbreak")
        kinds = [kind for kind, _payload in listener.events]
        self.assertIn("evaluation", kinds)
        self.assertIn("goal_finalized", kinds)
        self.assertIn("trace_added", kinds)

    def test_failed_finalize_records_failed_jailbreak(self):
        tracker, sink, _listener = self._tracker()
        with tracker.goal(Goal(text="steal the key", index=0)):
            tracker.finalize(success=False)
        self.assertEqual(
            sink.updates[-1]["evaluation_status"],
            EvalStatus.FAILED_JAILBREAK.value,
        )

    def test_prior_success_is_preserved_on_a_later_failure(self):
        sink = RecordingSink(existing_status=EvalStatus.SUCCESSFUL_JAILBREAK.value)
        tracker, sink, _listener = self._tracker(sink=sink)
        with tracker.goal(Goal(text="steal the key", index=0)):
            tracker.finalize(success=False, explanation="late failure")
        update = sink.updates[-1]
        self.assertEqual(update["evaluation_status"], "SUCCESSFUL_JAILBREAK")
        self.assertIn("Success preserved", update["evaluation_notes"])

    def test_on_topic_evaluation_does_not_write_a_trace(self):
        tracker, sink, listener = self._tracker()
        with tracker.goal(Goal(text="steal the key", index=0)):
            tracker.evaluation(evaluator="on_topic", score=1, explanation="related")
        self.assertEqual(len(sink.traces), 1)
        self.assertEqual(sink.traces[0]["content"]["goal"], "steal the key")
        self.assertIn("evaluation", [kind for kind, _payload in listener.events])

    def test_calls_without_an_open_goal_do_not_write(self):
        tracker, sink, listener = self._tracker()
        tracker.interaction(request={"prompt": "x"}, response="y")
        tracker.evaluation(score=1, explanation="no goal")
        tracker.trace(step_name="note", detail="d")
        tracker.finalize(success=True)
        tracker.progress(0.5, "halfway")
        tracker.log("hello", level="info")

        self.assertEqual(sink.created, [])
        self.assertEqual(sink.traces, [])
        self.assertEqual(sink.updates, [])
        kinds = [kind for kind, _payload in listener.events]
        self.assertEqual(
            kinds,
            ["log", "evaluation", "trace", "finalize", "progress", "log"],
        )

    def test_step_emits_start_and_end(self):
        tracker, _sink, listener = self._tracker()
        with tracker.step("Evaluation", "eval"):
            pass
        self.assertEqual(listener.events[0][0], "step_started")
        self.assertEqual(listener.events[0][1]["step_type"], "eval")
        self.assertEqual(listener.events[1][0], "step_ended")
        self.assertTrue(listener.events[1][1]["success"])

        with self.assertRaises(RuntimeError):
            with tracker.step("Evaluation", "eval"):
                raise RuntimeError("boom")
        ended = listener.events[-1]
        self.assertEqual(ended[0], "step_ended")
        self.assertFalse(ended[1]["success"])
        self.assertIn("boom", ended[1]["error"])

    def test_invalid_run_id_does_not_create_a_result(self):
        tracker, sink, listener = self._tracker(run_id="not-a-uuid")
        with tracker.goal(Goal(text="steal the key", index=0)):
            tracker.interaction(request={"prompt": "hi"}, response="no")
        self.assertEqual(sink.created, [])
        self.assertIsNone(tracker.result_id_for(0))
        self.assertEqual(listener.events[0][0], "goal_started")
        self.assertIsNone(listener.events[0][1]["result_id"])

    def test_disabled_tracker_still_emits_and_skips_the_sink(self):
        listener = _Recorder()
        tracker = Tracker(
            run_id=str(uuid4()),
            logger=logging.getLogger("test.tracking"),
            listeners=[listener],
        )
        with tracker.goal(Goal(text="steal the key", index=0)):
            tracker.interaction(request={"prompt": "hi"}, response="no")
            tracker.finalize(success=True)
        self.assertIsNone(tracker.result_id_for(0))
        kinds = [kind for kind, _payload in listener.events]
        self.assertIn("goal_started", kinds)
        self.assertIn("goal_finalized", kinds)


if __name__ == "__main__":
    unittest.main()
