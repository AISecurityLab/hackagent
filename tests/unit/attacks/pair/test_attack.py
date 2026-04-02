# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.pair.attack import PAIRAttack, _deep_update


class TestDeepUpdate(unittest.TestCase):
    def test_nested_merge(self):
        dst = {"a": {"b": 1}, "x": 0}
        src = {"a": {"c": 2}, "y": 3}
        _deep_update(dst, src)
        self.assertEqual(dst["a"]["b"], 1)
        self.assertEqual(dst["a"]["c"], 2)
        self.assertEqual(dst["y"], 3)

    def test_internal_keys_by_reference(self):
        obj = MagicMock()
        dst = {"_client": None}
        _deep_update(dst, {"_client": obj})
        self.assertIs(dst["_client"], obj)

    def test_non_internal_values_are_deep_copied(self):
        src = {"data": [1, 2, 3]}
        dst = {"data": []}
        _deep_update(dst, src)
        self.assertEqual(dst["data"], [1, 2, 3])
        self.assertIsNot(dst["data"], src["data"])


class TestPAIRAttack(unittest.TestCase):
    def test_requires_client(self):
        with self.assertRaises(ValueError):
            PAIRAttack(config={}, client=None, agent_router=MagicMock())

    def test_requires_agent_router(self):
        with self.assertRaises(ValueError):
            PAIRAttack(config={}, client=MagicMock(), agent_router=None)

    def test_get_pipeline_steps_empty(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            PAIRAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = PAIRAttack(
                config={"output_dir": "./logs/runs"},
                client=MagicMock(),
                agent_router=MagicMock(),
            )
            self.assertEqual(attack._get_pipeline_steps(), [])

    def test_run_empty_goals(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            PAIRAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = PAIRAttack(
                config={"output_dir": "./logs/runs"},
                client=MagicMock(),
                agent_router=MagicMock(),
            )
            self.assertEqual(attack.run([]), [])

    def test_judge_response_extracts_rating(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}
        dummy_attacker.route_request.return_value = {"generated_text": "Rating: [[7]]"}

        with patch.object(
            PAIRAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = PAIRAttack(
                config={"output_dir": "./logs/runs"},
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        score = attack._judge_response("goal", "prompt", "response")
        self.assertEqual(score, 7)

    def test_judge_response_clamps_fallback_integer(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}
        dummy_attacker.route_request.return_value = {"generated_text": "Score: 42"}

        with patch.object(
            PAIRAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = PAIRAttack(
                config={"output_dir": "./logs/runs"},
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        score = attack._judge_response("goal", "prompt", "response")
        self.assertEqual(score, 10)

    def test_init_accepts_uncopyable_internal_runtime_key(self):
        class _Uncopyable:
            def __deepcopy__(self, memo):
                raise TypeError("cannot pickle '_thread.RLock' object")

        runtime_obj = _Uncopyable()
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            PAIRAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = PAIRAttack(
                config={"output_dir": "./logs/runs", "_client": runtime_obj},
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        self.assertIs(attack.config.get("_client"), runtime_obj)

    def test_init_accepts_dataset_dict(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            PAIRAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = PAIRAttack(
                config={
                    "output_dir": "./logs/runs",
                    "dataset": {"preset": "harmbench", "limit": 1},
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        self.assertEqual(attack.config.get("dataset", {}).get("preset"), "harmbench")

    def test_run_uses_global_goal_index_offset_for_tracking_context(self):
        class _DummyStepTracker:
            @contextmanager
            def track_step(self, *_args, **_kwargs):
                yield None

            def add_step_metadata(self, *_args, **_kwargs):
                return None

        class _DummyProgress:
            def update(self, *_args, **_kwargs):
                return None

        class _DummyProgressBar:
            @contextmanager
            def __call__(self, *_args, **_kwargs):
                yield (_DummyProgress(), object())

        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            PAIRAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = PAIRAttack(
                config={
                    "output_dir": "./logs/runs",
                    "n_iterations": 1,
                    "_goal_index_offset": 5,
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        attack.tracker = _DummyStepTracker()
        fake_goal_ctx = MagicMock()
        fake_goal_tracker = MagicMock()
        fake_coordinator = MagicMock()
        fake_coordinator.goal_tracker = fake_goal_tracker
        fake_coordinator.has_goal_tracking = True
        fake_coordinator.get_goal_context.return_value = fake_goal_ctx

        with (
            patch.object(
                attack, "_initialize_coordinator", return_value=fake_coordinator
            ),
            patch(
                "hackagent.attacks.techniques.pair.attack.create_progress_bar",
                new=_DummyProgressBar(),
            ),
            patch.object(
                attack,
                "_run_single_goal",
                return_value={
                    "goal": "g",
                    "goal_index": 5,
                    "best_prompt": "p",
                    "best_response": "r",
                    "best_score": 1,
                    "is_success": False,
                    "iterations_completed": 1,
                    "n_iterations": 1,
                },
            ) as run_goal_mock,
        ):
            results = attack.run(["g"])

        self.assertEqual(len(results), 1)
        fake_coordinator.get_goal_context.assert_called_once_with(5)
        self.assertEqual(run_goal_mock.call_args.kwargs["goal_index"], 5)

    def test_single_goal_stops_immediately_on_jailbreak_score(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            PAIRAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = PAIRAttack(
                config={
                    "output_dir": "./logs/runs",
                    "n_iterations": 5,
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        with (
            patch.object(attack, "_query_attacker", return_value="adv"),
            patch.object(
                attack, "_query_target_simple", return_value="target response"
            ),
            patch.object(attack, "_judge_response", return_value=8) as judge_mock,
        ):
            result = attack._run_single_goal(
                goal="g",
                goal_index=0,
                goal_tracker=None,
                goal_ctx=None,
                progress_bar=None,
                task=None,
            )

        self.assertTrue(result["is_success"])
        self.assertEqual(result["iterations_completed"], 1)
        self.assertEqual(judge_mock.call_count, 1)

    def test_single_goal_emits_iteration_evaluation_trace_with_score(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            PAIRAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = PAIRAttack(
                config={
                    "output_dir": "./logs/runs",
                    "n_iterations": 1,
                    "jailbreak_threshold": 8,
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        fake_goal_tracker = MagicMock()
        fake_goal_ctx = MagicMock()

        with (
            patch.object(attack, "_query_attacker", return_value="adv"),
            patch.object(attack, "_query_target_simple", return_value="resp"),
            patch.object(attack, "_judge_response", return_value=6),
        ):
            attack._run_single_goal(
                goal="g",
                goal_index=0,
                goal_tracker=fake_goal_tracker,
                goal_ctx=fake_goal_ctx,
                progress_bar=None,
                task=None,
            )

        fake_goal_tracker.add_evaluation_trace.assert_called_once()
        kwargs = fake_goal_tracker.add_evaluation_trace.call_args.kwargs
        self.assertEqual(kwargs["score"], 6)
        self.assertEqual(kwargs["evaluation_result"]["iteration"], 1)

    def test_query_target_simple_include_meta_exposes_requested_max_tokens(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            PAIRAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = PAIRAttack(
                config={"output_dir": "./logs/runs", "max_tokens": 1000},
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        attack.agent_router._agent_registry = {"k": object()}
        attack.agent_router.route_request.return_value = {
            "generated_text": "ok",
            "agent_specific_data": {
                "invoked_parameters": {"max_tokens": 1000, "temperature": 0.7},
                "finish_reason": "stop",
                "usage": {
                    "completion_tokens": 42,
                    "prompt_tokens": 100,
                    "total_tokens": 142,
                },
                "provider_model": "google/gemma-3-27b-it",
            },
        }

        content, meta = attack._query_target_simple("hello", include_meta=True)
        self.assertEqual(content, "ok")
        self.assertEqual(meta.get("requested_max_tokens"), 1000)
        self.assertEqual(meta.get("finish_reason"), "stop")

    def test_score_response_passes_original_goal_to_scorer(self):
        dummy_router = MagicMock()
        dummy_router._agent_registry = {"k": object()}

        with (
            patch.object(
                PAIRAttack, "_initialize_attacker_router", return_value=dummy_router
            ),
            patch.object(
                PAIRAttack, "_initialize_scorer_router", return_value=dummy_router
            ),
        ):
            attack = PAIRAttack(
                config={"output_dir": "./logs/runs"},
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        with patch(
            "hackagent.attacks.techniques.pair.attack.score_response",
            return_value=(8.0, "ok"),
        ) as mock_score:
            out = attack._score_response("ORIGINAL GOAL", "target reply")

        self.assertEqual(out, 8)
        self.assertEqual(mock_score.call_args.kwargs["goal"], "ORIGINAL GOAL")
        self.assertEqual(mock_score.call_args.kwargs["target_response"], "target reply")

    def test_single_goal_records_response_length_and_preview_truncation(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            PAIRAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = PAIRAttack(
                config={
                    "output_dir": "./logs/runs",
                    "n_iterations": 1,
                    "target_trace_response_max_chars": 20,
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        fake_goal_tracker = MagicMock()
        fake_goal_ctx = MagicMock()
        long_response = "x" * 75

        with (
            patch.object(attack, "_query_attacker", return_value="adv"),
            patch.object(
                attack, "_query_target_simple", return_value=(long_response, {})
            ),
            patch.object(attack, "_judge_response", return_value=2),
        ):
            attack._run_single_goal(
                goal="g",
                goal_index=0,
                goal_tracker=fake_goal_tracker,
                goal_ctx=fake_goal_ctx,
                progress_bar=None,
                task=None,
            )

        call_kwargs = fake_goal_tracker.add_interaction_trace.call_args.kwargs
        self.assertEqual(call_kwargs["response"], "x" * 20)
        self.assertEqual(call_kwargs["metadata"]["response_char_count"], 75)
        self.assertEqual(call_kwargs["metadata"]["response_preview_chars"], 20)
        self.assertTrue(call_kwargs["metadata"]["response_preview_truncated"])

    def test_run_suppresses_pipeline_status_updates_in_sub_run(self):
        class _DummyStepTracker:
            @contextmanager
            def track_step(self, *_args, **_kwargs):
                yield None

            def add_step_metadata(self, *_args, **_kwargs):
                return None

        class _DummyProgress:
            def update(self, *_args, **_kwargs):
                return None

        class _DummyProgressBar:
            @contextmanager
            def __call__(self, *_args, **_kwargs):
                yield (_DummyProgress(), object())

        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            PAIRAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = PAIRAttack(
                config={
                    "output_dir": "./logs/runs",
                    "n_iterations": 1,
                    "_suppress_run_status_updates": True,
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        attack.tracker = _DummyStepTracker()
        fake_goal_ctx = MagicMock()
        fake_goal_tracker = MagicMock()
        fake_coordinator = MagicMock()
        fake_coordinator.goal_tracker = fake_goal_tracker
        fake_coordinator.has_goal_tracking = True
        fake_coordinator.get_goal_context.return_value = fake_goal_ctx

        with (
            patch.object(
                attack, "_initialize_coordinator", return_value=fake_coordinator
            ),
            patch(
                "hackagent.attacks.techniques.pair.attack.create_progress_bar",
                new=_DummyProgressBar(),
            ),
            patch.object(
                attack,
                "_run_single_goal",
                return_value={
                    "goal": "g",
                    "goal_index": 0,
                    "best_prompt": "p",
                    "best_response": "r",
                    "best_score": 1,
                    "is_success": False,
                    "iterations_completed": 1,
                    "n_iterations": 1,
                },
            ),
        ):
            attack.run(["g"])

        fake_coordinator.finalize_pipeline.assert_not_called()


if __name__ == "__main__":
    unittest.main()
