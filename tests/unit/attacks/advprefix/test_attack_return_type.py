# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit test asserting AdvPrefixAttack.run() returns List[AttackResult]."""

import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.advprefix.attack import AdvPrefixAttack
from hackagent.attacks.types import AttackResult


class TestAdvPrefixAttackReturnType(unittest.TestCase):
    def test_run_empty_goals_returns_empty_list(self):
        attack = AdvPrefixAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.run([]), [])

    def test_run_returns_list_of_attack_result(self):
        attack = AdvPrefixAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        coordinator = MagicMock()
        coordinator.has_goal_tracking = False
        coordinator.goal_tracker = None

        generation_output = [{"goal": "g1", "prompt": "p1"}]
        final_output = [{"goal": "g1", "prompt": "p1", "response": "r1"}]

        with (
            patch.object(attack, "_initialize_coordinator", return_value=coordinator),
            patch.object(
                attack,
                "_execute_pipeline",
                side_effect=[generation_output, final_output],
            ),
        ):
            results = attack.run(["g1"])

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], AttackResult)
        self.assertEqual(results[0].goal, "g1")


if __name__ == "__main__":
    unittest.main()
