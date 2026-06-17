# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.static_template.attack import StaticTemplateAttack


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

    def finalize_pipeline(self, *_args, **_kwargs):
        pass

    def finalize_on_error(self, *_args, **_kwargs):
        pass


class TestStaticTemplateAttack(unittest.TestCase):
    def test_requires_client(self):
        with self.assertRaises(ValueError):
            StaticTemplateAttack(config={}, client=None, agent_router=MagicMock())

    def test_requires_agent_router(self):
        with self.assertRaises(ValueError):
            StaticTemplateAttack(config={}, client=MagicMock(), agent_router=None)

    def test_get_pipeline_steps(self):
        attack = StaticTemplateAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        steps = attack._get_pipeline_steps()
        self.assertEqual(len(steps), 2)
        self.assertIn("Generation", steps[0]["name"])
        self.assertIn("Evaluation", steps[1]["name"])

    def test_run_empty_goals(self):
        attack = StaticTemplateAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.run([]), {"evaluated": [], "summary": []})

    @patch("hackagent.attacks.techniques.static_template.attack.evaluation.execute")
    @patch("hackagent.attacks.techniques.static_template.attack.generation.execute")
    def test_run_pipeline(self, mock_generation, mock_evaluation):
        attack = StaticTemplateAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )

        coordinator = _DummyCoordinator()

        def _init_coord(*_args, **_kwargs):
            attack.tracker = _DummyStepTracker()
            return coordinator

        mock_generation.return_value = [
            {"goal": "g1", "prompt": "p1", "response": "r1"}
        ]
        mock_evaluation.return_value = {
            "evaluated": [{"goal": "g1", "success": True}],
            "summary": [{"success_rate": 1.0}],
        }

        with patch.object(attack, "_initialize_coordinator", side_effect=_init_coord):
            out = attack.run(["g1"])

        self.assertIn("evaluated", out)
        self.assertIn("summary", out)
        mock_generation.assert_called_once()
        mock_evaluation.assert_called_once()


if __name__ == "__main__":
    unittest.main()
