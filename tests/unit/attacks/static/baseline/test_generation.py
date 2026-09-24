# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the Baseline attack generation module."""

import logging
import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.static.baseline import generation
from hackagent.attacks.techniques.static.baseline.generation import (
    _safe_goal_index,
    _safe_positive_int,
    execute,
)


def _router(responses=None, side_effect=None):
    """Build a router stub whose registry has a single registration key."""
    router = MagicMock()
    router._agent_registry = {"target-key": object()}
    if side_effect is not None:
        router.route_request.side_effect = side_effect
    else:
        router.route_request.return_value = responses
    return router


class TestSafeConverters(unittest.TestCase):
    def test_safe_goal_index_parses_int_like_values(self):
        self.assertEqual(_safe_goal_index(5), 5)
        self.assertEqual(_safe_goal_index("7"), 7)
        self.assertEqual(_safe_goal_index(3.9), 3)

    def test_safe_goal_index_falls_back_on_garbage(self):
        self.assertEqual(_safe_goal_index(None), -1)
        self.assertEqual(_safe_goal_index("abc"), -1)
        self.assertEqual(_safe_goal_index(object(), fallback=42), 42)

    def test_safe_positive_int_keeps_positive_values(self):
        self.assertEqual(_safe_positive_int(4, 16), 4)
        self.assertEqual(_safe_positive_int("8", 16), 8)

    def test_safe_positive_int_rejects_non_positive_and_garbage(self):
        self.assertEqual(_safe_positive_int(0, 16), 16)
        self.assertEqual(_safe_positive_int(-3, 16), 16)
        self.assertEqual(_safe_positive_int(None, 16), 16)
        self.assertEqual(_safe_positive_int("many", 16), 16)


class TestExecute(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("test.baseline.generation")
        self.logger.addHandler(logging.NullHandler())

    def test_sends_each_goal_verbatim_and_preserves_order(self):
        goals = ["goal one", "goal two", "goal three"]
        router = _router(
            side_effect=lambda registration_key, request_data: {
                "generated_text": "reply:" + request_data["messages"][0]["content"]
            }
        )

        results = execute(goals, router, {}, self.logger)

        self.assertEqual([r["goal"] for r in results], goals)
        self.assertEqual([r["goal_index"] for r in results], [0, 1, 2])
        # The baseline attack applies no transformation: prompt == goal.
        self.assertEqual([r["attack_prompt"] for r in results], goals)
        self.assertEqual(results[1]["completion"], "reply:goal two")
        self.assertEqual(results[1]["response_length"], len("reply:goal two"))
        self.assertNotIn("error", results[0])

    def test_request_payload_uses_configured_sampling_parameters(self):
        router = _router({"generated_text": "ok"})

        execute(["g"], router, {"max_tokens": 77, "temperature": 0.9}, self.logger)

        router.route_request.assert_called_once_with(
            registration_key="target-key",
            request_data={
                "messages": [{"role": "user", "content": "g"}],
                "max_tokens": 77,
                "temperature": 0.9,
            },
        )

    def test_sampling_parameters_default_when_absent(self):
        router = _router({"generated_text": "ok"})

        execute(["g"], router, {}, self.logger)

        request_data = router.route_request.call_args.kwargs["request_data"]
        self.assertEqual(request_data["max_tokens"], 1024)
        self.assertEqual(request_data["temperature"], 0.0)

    def test_goal_index_offset_shifts_reported_indices(self):
        router = _router({"generated_text": "ok"})

        results = execute(["a", "b"], router, {"_goal_index_offset": 10}, self.logger)

        self.assertEqual([r["goal_index"] for r in results], [10, 11])

    def test_invalid_goal_index_offset_falls_back_to_zero(self):
        router = _router({"generated_text": "ok"})

        results = execute(["a"], router, {"_goal_index_offset": "oops"}, self.logger)

        self.assertEqual(results[0]["goal_index"], 0)

    def test_guardrail_response_is_flagged(self):
        router = _router({"adapter_type": "guardrail", "generated_text": "blocked"})

        results = execute(["a"], router, {}, self.logger)

        self.assertTrue(results[0]["guardrail_blocked"])
        self.assertNotIn("error", results[0])

    def test_adapter_error_without_completion_is_recorded(self):
        router = _router({"error_message": "upstream 500"})

        results = execute(["a"], router, {}, self.logger)

        self.assertEqual(results[0]["error"], "upstream 500")
        self.assertEqual(results[0]["completion"], "")
        self.assertEqual(results[0]["response_length"], 0)

    def test_adapter_error_alongside_completion_is_not_an_error_row(self):
        router = _router({"generated_text": "partial", "error": "warned"})

        results = execute(["a"], router, {}, self.logger)

        self.assertNotIn("error", results[0])
        self.assertEqual(results[0]["completion"], "partial")

    def test_router_exception_produces_error_row(self):
        router = _router(side_effect=RuntimeError("connection refused"))

        results = execute(["a", "b"], router, {}, self.logger)

        self.assertEqual(len(results), 2)
        for row in results:
            self.assertEqual(row["error"], "connection refused")
            self.assertEqual(row["completion"], "")
            self.assertEqual(row["response_length"], 0)
            self.assertEqual(row["attack_prompt"], row["goal"])

    def test_non_dict_response_still_extracts_completion(self):
        router = _router("plain string reply")

        results = execute(["a"], router, {}, self.logger)

        self.assertEqual(results[0]["completion"], "plain string reply")
        self.assertNotIn("guardrail_blocked", results[0])


class TestExecuteTracking(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("test.baseline.generation.tracking")
        self.logger.addHandler(logging.NullHandler())

    def _tracker(self, existing_ctx=None):
        tracker = MagicMock()
        tracker.get_goal_context.return_value = existing_ctx
        tracker.create_goal_result.side_effect = lambda **kwargs: (
            f"ctx-{kwargs['goal_index']}"
        )
        return tracker

    def test_explicit_tracker_creates_contexts_and_traces(self):
        tracker = self._tracker()
        router = _router({"generated_text": "ok"})

        execute(["a", "b"], router, {}, self.logger, goal_tracker=tracker)

        created = [
            call.kwargs["goal_index"]
            for call in tracker.create_goal_result.call_args_list
        ]
        self.assertEqual(created, [0, 1])
        self.assertEqual(
            tracker.create_goal_result.call_args_list[0].kwargs["initial_metadata"],
            {"attack_type": "Baseline"},
        )
        self.assertEqual(tracker.add_interaction_trace.call_count, 2)
        trace = tracker.add_interaction_trace.call_args_list[0].kwargs
        self.assertEqual(trace["step_name"], "Baseline: Direct Request")
        self.assertEqual(trace["request"], {"prompt": "a"})
        self.assertEqual(trace["metadata"], {"response_length": 2})

    def test_existing_goal_context_is_reused(self):
        tracker = self._tracker(existing_ctx="already-there")
        router = _router({"generated_text": "ok"})

        execute(["a"], router, {}, self.logger, goal_tracker=tracker)

        tracker.create_goal_result.assert_not_called()
        self.assertEqual(
            tracker.add_interaction_trace.call_args.kwargs["ctx"], "already-there"
        )

    def test_tracker_is_read_from_config_when_not_passed(self):
        tracker = self._tracker()
        router = _router({"generated_text": "ok"})

        execute(["a"], router, {"_tracker": tracker}, self.logger)

        tracker.create_goal_result.assert_called_once()

    def test_tracker_is_constructed_from_run_id_and_backend(self):
        router = _router({"generated_text": "ok"})
        backend = MagicMock()
        bus = MagicMock()
        classifier = {"model": "judge"}

        with patch.object(generation, "Tracker") as tracker_cls:
            tracker_cls.return_value = self._tracker()
            execute(
                ["a"],
                router,
                {
                    "_run_id": "run-1",
                    "_backend": backend,
                    "category_classifier": classifier,
                    "_tui_event_bus": bus,
                },
                self.logger,
            )

        tracker_cls.assert_called_once()
        kwargs = tracker_cls.call_args.kwargs
        self.assertIs(kwargs["backend"], backend)
        self.assertEqual(kwargs["run_id"], "run-1")
        self.assertEqual(kwargs["attack_type"], "Baseline")
        self.assertEqual(kwargs["category_classifier_config"], classifier)
        self.assertIs(kwargs["event_bus"], bus)

    def test_legacy_client_key_also_constructs_tracker(self):
        router = _router({"generated_text": "ok"})
        client = MagicMock()

        with patch.object(generation, "Tracker") as tracker_cls:
            tracker_cls.return_value = self._tracker()
            execute(["a"], router, {"_run_id": "run-1", "_client": client}, self.logger)

        self.assertIs(tracker_cls.call_args.kwargs["backend"], client)

    def test_missing_tracking_context_warns_and_skips_tracking(self):
        router = _router({"generated_text": "ok"})
        logger = MagicMock()

        with patch.object(generation, "Tracker") as tracker_cls:
            results = execute(["a"], router, {}, logger)

        tracker_cls.assert_not_called()
        logger.warning.assert_called_once()
        self.assertEqual(len(results), 1)

    def test_failures_are_traced_as_custom_error_steps(self):
        tracker = self._tracker()
        router = _router(side_effect=RuntimeError("boom"))

        execute(["a" * 500], router, {}, self.logger, goal_tracker=tracker)

        tracker.add_interaction_trace.assert_not_called()
        trace = tracker.add_custom_trace.call_args.kwargs
        self.assertEqual(trace["step_name"], "Execution Error")
        self.assertEqual(trace["content"]["error"], "boom")
        # The goal is truncated before it reaches the trace payload.
        self.assertEqual(len(trace["content"]["goal"]), 200)


class TestExecuteConcurrency(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("test.baseline.generation.pool")
        self.logger.addHandler(logging.NullHandler())

    def test_worker_count_is_bounded_by_goal_count_and_batch_size(self):
        router = _router({"generated_text": "ok"})

        with patch.object(generation, "ThreadPoolExecutor") as pool_cls:
            pool = pool_cls.return_value.__enter__.return_value
            pool.map.side_effect = lambda fn, it: [fn(i) for i in it]
            execute(["a", "b", "c"], router, {"batch_size": 2}, self.logger)

        self.assertEqual(pool_cls.call_args.kwargs["max_workers"], 2)

    def test_invalid_batch_size_falls_back_to_default(self):
        router = _router({"generated_text": "ok"})

        with patch.object(generation, "ThreadPoolExecutor") as pool_cls:
            pool = pool_cls.return_value.__enter__.return_value
            pool.map.side_effect = lambda fn, it: [fn(i) for i in it]
            execute(["a", "b"], router, {"batch_size": 0}, self.logger)

        # min(len(goals), 16) with the fallback batch size.
        self.assertEqual(pool_cls.call_args.kwargs["max_workers"], 2)


if __name__ == "__main__":
    unittest.main()
