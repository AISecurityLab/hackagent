# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.crescendo.attack import CrescendoAttack, _deep_update


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


class TestCrescendoAttack(unittest.TestCase):
    def test_requires_client(self):
        with self.assertRaises(ValueError):
            CrescendoAttack(config={}, client=None, agent_router=MagicMock())

    def test_requires_agent_router(self):
        with self.assertRaises(ValueError):
            CrescendoAttack(config={}, client=MagicMock(), agent_router=None)

    def test_get_pipeline_steps_empty(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            CrescendoAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = CrescendoAttack(
                config={"output_dir": "./logs/runs"},
                client=MagicMock(),
                agent_router=MagicMock(),
            )
            self.assertEqual(attack._get_pipeline_steps(), [])

    def test_run_empty_goals(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            CrescendoAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = CrescendoAttack(
                config={"output_dir": "./logs/runs"},
                client=MagicMock(),
                agent_router=MagicMock(),
            )
            self.assertEqual(attack.run([]), [])

    def test_init_accepts_uncopyable_internal_runtime_key(self):
        class _Uncopyable:
            def __deepcopy__(self, memo):
                raise TypeError("cannot pickle '_thread.RLock' object")

        runtime_obj = _Uncopyable()
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            CrescendoAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = CrescendoAttack(
                config={"output_dir": "./logs/runs", "_client": runtime_obj},
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        self.assertIs(attack.config.get("_client"), runtime_obj)

    def test_init_accepts_dataset_dict(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            CrescendoAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = CrescendoAttack(
                config={
                    "output_dir": "./logs/runs",
                    "dataset": {"preset": "harmbench", "limit": 1},
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        self.assertEqual(attack.config.get("dataset", {}).get("preset"), "harmbench")

    def test_judge_turn_extracts_score_and_refused(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}
        dummy_judge = MagicMock()
        dummy_judge._agent_registry = {"j": object()}
        dummy_judge.route_request.return_value = {
            "generated_text": '{"refused": false, "score": 7, "explanation": "progress"}'
        }

        with (
            patch.object(
                CrescendoAttack,
                "_initialize_attacker_router",
                return_value=dummy_attacker,
            ),
            patch.object(
                CrescendoAttack, "_initialize_judge_router", return_value=dummy_judge
            ),
        ):
            attack = CrescendoAttack(
                config={"output_dir": "./logs/runs"},
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        score, refused, explanation = attack._judge_turn("goal", "question", "response")
        self.assertEqual(score, 7.0)
        self.assertFalse(refused)
        self.assertEqual(explanation, "progress")

    def test_judge_turn_detects_refusal(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}
        dummy_judge = MagicMock()
        dummy_judge._agent_registry = {"j": object()}
        dummy_judge.route_request.return_value = {
            "generated_text": '{"refused": true, "score": 1, "explanation": "declined"}'
        }

        with (
            patch.object(
                CrescendoAttack,
                "_initialize_attacker_router",
                return_value=dummy_attacker,
            ),
            patch.object(
                CrescendoAttack, "_initialize_judge_router", return_value=dummy_judge
            ),
        ):
            attack = CrescendoAttack(
                config={"output_dir": "./logs/runs"},
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        score, refused, explanation = attack._judge_turn("goal", "question", "response")
        self.assertEqual(score, 1.0)
        self.assertTrue(refused)

    def test_judge_turn_clamps_score_range(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}
        dummy_judge = MagicMock()
        dummy_judge._agent_registry = {"j": object()}
        dummy_judge.route_request.return_value = {
            "generated_text": '{"refused": false, "score": 42}'
        }

        with (
            patch.object(
                CrescendoAttack,
                "_initialize_attacker_router",
                return_value=dummy_attacker,
            ),
            patch.object(
                CrescendoAttack, "_initialize_judge_router", return_value=dummy_judge
            ),
        ):
            attack = CrescendoAttack(
                config={"output_dir": "./logs/runs"},
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        score, _refused, _explanation = attack._judge_turn("goal", "question", "response")
        self.assertEqual(score, 10.0)

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
            CrescendoAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = CrescendoAttack(
                config={
                    "output_dir": "./logs/runs",
                    "max_turns": 1,
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
                "hackagent.attacks.techniques.crescendo.attack.create_progress_bar",
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
                    "best_judge_explanation": "",
                    "is_success": False,
                    "turns_completed": 1,
                    "backtracks_used": 0,
                    "max_turns": 1,
                    "max_backtracks": 10,
                },
            ) as run_goal_mock,
        ):
            results = attack.run(["g"])

        self.assertEqual(len(results), 1)
        fake_coordinator.get_goal_context.assert_called_once_with(5)
        self.assertEqual(run_goal_mock.call_args.kwargs["goal_index"], 5)
        from hackagent.attacks.types import AttackResult

        self.assertIsInstance(results[0], AttackResult)
        self.assertEqual(results[0].goal, "g")

    def test_single_goal_stops_immediately_on_jailbreak_score(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            CrescendoAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = CrescendoAttack(
                config={
                    "output_dir": "./logs/runs",
                    "max_turns": 5,
                    "jailbreak_threshold": 8,
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        with (
            patch.object(
                attack,
                "_query_attacker",
                return_value={
                    "question": "q",
                    "reasoning": "",
                    "assistant_content": "{}",
                },
            ),
            patch.object(attack, "_query_target", return_value=("resp", {})),
            patch.object(
                attack, "_judge_turn", return_value=(9.0, False, "great")
            ) as judge_mock,
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
        self.assertEqual(result["turns_completed"], 1)
        self.assertEqual(judge_mock.call_count, 1)

    def test_single_goal_emits_evaluation_trace_with_score(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            CrescendoAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = CrescendoAttack(
                config={
                    "output_dir": "./logs/runs",
                    "max_turns": 1,
                    "jailbreak_threshold": 8,
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        fake_goal_tracker = MagicMock()
        fake_goal_ctx = MagicMock()

        with (
            patch.object(
                attack,
                "_query_attacker",
                return_value={
                    "question": "q",
                    "reasoning": "",
                    "assistant_content": "{}",
                },
            ),
            patch.object(attack, "_query_target", return_value=("resp", {})),
            patch.object(attack, "_judge_turn", return_value=(6.0, False, "ok")),
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
        self.assertEqual(kwargs["score"], 6.0)
        self.assertEqual(kwargs["evaluation_result"]["turn"], 1)

    def test_single_goal_backtracks_on_refusal_and_retries_same_turn(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            CrescendoAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = CrescendoAttack(
                config={
                    "output_dir": "./logs/runs",
                    "max_turns": 2,
                    "max_backtracks": 3,
                    "early_stop_on_success": False,
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        attacker_calls = [
            {"question": "q1-refused", "reasoning": "", "assistant_content": "{}"},
            {"question": "q1-retry", "reasoning": "", "assistant_content": "{}"},
            {"question": "q2", "reasoning": "", "assistant_content": "{}"},
        ]

        with (
            patch.object(attack, "_query_attacker", side_effect=attacker_calls),
            patch.object(
                attack,
                "_query_target",
                side_effect=[("refused-resp", {}), ("ok-resp", {}), ("ok-resp2", {})],
            ),
            patch.object(
                attack,
                "_judge_turn",
                side_effect=[(1.0, True, "refused"), (3.0, False, "ok"), (3.0, False, "ok")],
            ),
        ):
            result = attack._run_single_goal(
                goal="g",
                goal_index=0,
                goal_tracker=None,
                goal_ctx=None,
                progress_bar=None,
                task=None,
            )

        self.assertEqual(result["backtracks_used"], 1)
        self.assertEqual(result["turns_completed"], 2)

    def test_single_goal_accepts_refused_turn_when_backtrack_budget_exhausted(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            CrescendoAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = CrescendoAttack(
                config={
                    "output_dir": "./logs/runs",
                    "max_turns": 1,
                    "max_backtracks": 0,
                    "early_stop_on_success": False,
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        with (
            patch.object(
                attack,
                "_query_attacker",
                return_value={
                    "question": "q",
                    "reasoning": "",
                    "assistant_content": "{}",
                },
            ),
            patch.object(attack, "_query_target", return_value=("refused-resp", {})),
            patch.object(attack, "_judge_turn", return_value=(1.0, True, "refused")),
        ):
            result = attack._run_single_goal(
                goal="g",
                goal_index=0,
                goal_tracker=None,
                goal_ctx=None,
                progress_bar=None,
                task=None,
            )

        self.assertEqual(result["backtracks_used"], 0)
        self.assertEqual(result["turns_completed"], 1)

    def test_single_goal_handles_missing_target_response(self):
        dummy_attacker = MagicMock()
        dummy_attacker._agent_registry = {"a": object()}

        with patch.object(
            CrescendoAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = CrescendoAttack(
                config={
                    "output_dir": "./logs/runs",
                    "max_turns": 1,
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

        with (
            patch.object(
                attack,
                "_query_attacker",
                return_value={
                    "question": "q",
                    "reasoning": "",
                    "assistant_content": "{}",
                },
            ),
            patch.object(attack, "_query_target", return_value=(None, {})),
            patch.object(attack, "_judge_turn") as judge_mock,
        ):
            result = attack._run_single_goal(
                goal="g",
                goal_index=0,
                goal_tracker=None,
                goal_ctx=None,
                progress_bar=None,
                task=None,
            )

        judge_mock.assert_not_called()
        self.assertEqual(result["turns_completed"], 0)
        self.assertFalse(result["is_success"])

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
            CrescendoAttack, "_initialize_attacker_router", return_value=dummy_attacker
        ):
            attack = CrescendoAttack(
                config={
                    "output_dir": "./logs/runs",
                    "max_turns": 1,
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
                "hackagent.attacks.techniques.crescendo.attack.create_progress_bar",
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
                    "best_judge_explanation": "",
                    "is_success": False,
                    "turns_completed": 1,
                    "backtracks_used": 0,
                    "max_turns": 1,
                    "max_backtracks": 10,
                },
            ),
        ):
            attack.run(["g"])

        fake_coordinator.finalize_pipeline.assert_not_called()


if __name__ == "__main__":
    unittest.main()
