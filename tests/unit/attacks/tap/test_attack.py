# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.tap.attack import TAPAttack
from tests.fakes import RecordingCoordinator, RecordingStepTracker


class TestTAPAttack(unittest.TestCase):
    def test_requires_client(self):
        with self.assertRaises(ValueError):
            TAPAttack(config={}, client=None, agent_router=MagicMock())

    def test_requires_agent_router(self):
        with self.assertRaises(ValueError):
            TAPAttack(config={}, client=MagicMock(), agent_router=None)

    def test_validate_config_rejects_invalid_depth(self):
        with self.assertRaises(ValueError):
            TAPAttack(
                config={"output_dir": "./logs/runs", "tap_params": {"depth": 0}},
                client=MagicMock(),
                agent_router=MagicMock(),
            )

    def test_get_pipeline_steps(self):
        attack = TAPAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        steps = attack._get_pipeline_steps()
        self.assertEqual(len(steps), 2)
        self.assertIn("Generation", steps[0]["name"])
        self.assertIn("Evaluation", steps[1]["name"])

    def test_run_empty_goals(self):
        attack = TAPAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.run([]), [])

    @patch("hackagent.attacks.techniques.tap.attack.evaluation.execute")
    @patch("hackagent.attacks.techniques.tap.attack.generation.execute")
    def test_run_pipeline(self, mock_generation, mock_evaluation):
        attack = TAPAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )

        coordinator = RecordingCoordinator()

        def _init_coord(*_args, **_kwargs):
            attack.tracker = RecordingStepTracker()
            return coordinator

        mock_generation.return_value = [{"goal": "g1", "best_prompt": "p1"}]
        mock_evaluation.return_value = [{"goal": "g1", "best_score": 1}]

        with patch.object(attack, "_initialize_coordinator", side_effect=_init_coord):
            out = attack.run(["g1"])

        self.assertEqual(len(out), 1)
        mock_generation.assert_called_once()
        mock_evaluation.assert_called_once()
        from hackagent.attacks.types import AttackResult

        self.assertIsInstance(out[0], AttackResult)
        self.assertEqual(out[0].goal, "g1")


if __name__ == "__main__":
    unittest.main()
