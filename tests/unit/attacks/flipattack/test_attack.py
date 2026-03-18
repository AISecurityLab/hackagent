# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.flipattack.attack import (
    FlipAttack,
    _recursive_update,
)


class _DummyStepTracker:
    @contextmanager
    def track_step(self, *_args, **_kwargs):
        yield

    def add_step_metadata(self, *_args, **_kwargs):
        pass


class _DummyCoordinator:
    def __init__(self):
        self.goal_tracker = None
        self.has_goal_tracking = False

    def initialize_goals_from_pipeline_data(self, *_args, **_kwargs):
        pass

    def enrich_with_result_ids(self, results):
        return results

    def finalize_all_goals(self, *_args, **_kwargs):
        pass

    def log_summary(self):
        pass

    def finalize_pipeline(self, *_args, **_kwargs):
        pass

    def finalize_on_error(self, *_args, **_kwargs):
        pass


class TestRecursiveUpdate(unittest.TestCase):
    def test_nested_merge(self):
        dst = {"a": {"b": 1}, "x": 0}
        src = {"a": {"c": 2}, "y": 3}
        _recursive_update(dst, src)
        self.assertEqual(dst["a"]["b"], 1)
        self.assertEqual(dst["a"]["c"], 2)
        self.assertEqual(dst["y"], 3)

    def test_internal_key_passed_by_reference(self):
        obj = MagicMock()
        dst = {"_tracker": None}
        _recursive_update(dst, {"_tracker": obj})
        self.assertIs(dst["_tracker"], obj)


class TestFlipAttack(unittest.TestCase):
    def test_requires_client(self):
        with self.assertRaises(ValueError):
            FlipAttack(config={}, client=None, agent_router=MagicMock())

    def test_requires_agent_router(self):
        with self.assertRaises(ValueError):
            FlipAttack(config={}, client=MagicMock(), agent_router=None)

    def test_invalid_flip_mode_raises(self):
        with self.assertRaises(ValueError):
            FlipAttack(
                config={
                    "output_dir": "./logs/runs",
                    "flipattack_params": {"flip_mode": "BAD"},
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

    def test_run_empty_goals(self):
        attack = FlipAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.run([]), [])

    @patch("hackagent.attacks.techniques.flipattack.attack.evaluation.execute")
    @patch("hackagent.attacks.techniques.flipattack.attack.generation.execute")
    def test_run_pipeline(self, mock_generation, mock_evaluation):
        attack = FlipAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )

        coordinator = _DummyCoordinator()

        def _init_coord(*_args, **_kwargs):
            attack.tracker = _DummyStepTracker()
            return coordinator

        mock_generation.return_value = [
            {
                "goal": "g1",
                "prompt": "p1",
                "response": "r1",
            }
        ]
        mock_evaluation.return_value = [{"goal": "g1", "best_score": 1.0}]

        with patch.object(attack, "_initialize_coordinator", side_effect=_init_coord):
            out = attack.run(["g1"])

        self.assertEqual(len(out), 1)
        mock_generation.assert_called_once()
        mock_evaluation.assert_called_once()


if __name__ == "__main__":
    unittest.main()
