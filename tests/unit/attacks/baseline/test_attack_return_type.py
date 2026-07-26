# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit test asserting BaselineAttack.run() returns List[AttackResult]."""

import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.baseline.attack import BaselineAttack
from hackagent.attacks.types import AttackResult


class TestBaselineAttackReturnType(unittest.TestCase):
    def test_run_empty_goals_returns_empty_list(self):
        attack = BaselineAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.run([]), [])

    def test_run_returns_list_of_attack_result(self):
        attack = BaselineAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        coordinator = MagicMock()
        coordinator.goal_tracker = None

        with (
            patch.object(attack, "_initialize_coordinator", return_value=coordinator),
            patch.object(
                attack,
                "_execute_pipeline",
                return_value=[{"goal": "g1", "response": "r1"}],
            ),
        ):
            results = attack.run(["g1"])

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], AttackResult)
        self.assertEqual(results[0].goal, "g1")


if __name__ == "__main__":
    unittest.main()
