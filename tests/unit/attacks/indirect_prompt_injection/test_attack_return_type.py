# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit test asserting IndirectPromptInjectionAttack.run() returns List[AttackResult]."""

import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.indirect_prompt_injection.attack import (
    IndirectPromptInjectionAttack,
)
from hackagent.attacks.types import AttackResult


def _fake_create_router(backend, config, logger, router_name):
    return MagicMock(), f"{router_name}_key"


class TestIndirectPromptInjectionAttackReturnType(unittest.TestCase):
    def _make_attack(self):
        with patch(
            "hackagent.attacks.techniques.indirect_prompt_injection.attack.create_router",
            side_effect=_fake_create_router,
        ):
            attack = IndirectPromptInjectionAttack(
                config={"output_dir": "./logs/runs"},
                client=MagicMock(),
                agent_router=MagicMock(),
            )
        return attack

    def test_requires_client(self):
        with self.assertRaises(ValueError):
            IndirectPromptInjectionAttack(
                config={}, client=None, agent_router=MagicMock()
            )

    def test_requires_agent_router(self):
        with self.assertRaises(ValueError):
            IndirectPromptInjectionAttack(
                config={}, client=MagicMock(), agent_router=None
            )

    def test_run_returns_list_of_attack_result(self):
        attack = self._make_attack()

        coordinator = MagicMock()
        coordinator.has_goal_tracking = False
        coordinator.goal_tracker = None

        with (
            patch.object(attack, "_initialize_coordinator", return_value=coordinator),
            patch(
                "hackagent.attacks.techniques.indirect_prompt_injection.attack.parse_documents",
                return_value=[{"source": "doc1", "text": "some document text"}],
            ),
            patch.object(
                attack,
                "_run_single_goal",
                return_value={
                    "goal": "g1",
                    "evaluations": [{"classification": "SUCCESS"}],
                },
            ),
        ):
            results = attack.run(["g1"])

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], AttackResult)
        self.assertEqual(results[0].goal, "g1")

    def test_run_no_goals_raises(self):
        attack = self._make_attack()
        with self.assertRaises(ValueError):
            attack.run([])

    def test_run_no_documents_raises(self):
        attack = self._make_attack()
        with patch(
            "hackagent.attacks.techniques.indirect_prompt_injection.attack.parse_documents",
            return_value=[],
        ):
            with self.assertRaises(ValueError):
                attack.run(["g1"])


if __name__ == "__main__":
    unittest.main()
