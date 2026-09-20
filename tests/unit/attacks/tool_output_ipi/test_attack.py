# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for ToolOutputIPIAttack wiring."""

import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.registry import ATTACK_REGISTRY, ToolOutputIPIOrchestrator
from hackagent.attacks.techniques.tool_output_ipi.attack import ToolOutputIPIAttack
from hackagent.attacks.types import AttackResult
from hackagent.cli.commands.attack.catalog import ATTACK_CATALOG
from hackagent.cli.tui.attack_specs import get_attack_config_spec


class TestRegistryAndDiscovery(unittest.TestCase):
    def test_registry_entry(self):
        self.assertIn("tool_output_ipi", ATTACK_REGISTRY)
        self.assertIs(ATTACK_REGISTRY["tool_output_ipi"], ToolOutputIPIOrchestrator)
        self.assertEqual(ToolOutputIPIOrchestrator.attack_type, "tool_output_ipi")
        self.assertIs(ToolOutputIPIOrchestrator.attack_impl_class, ToolOutputIPIAttack)

    def test_catalog_entry(self):
        self.assertIn("tool_output_ipi", ATTACK_CATALOG)
        self.assertIn("OPI", ATTACK_CATALOG["tool_output_ipi"]["description"])

    def test_tui_spec(self):
        # Importing specs package registers modules
        import hackagent.cli.tui.attack_specs.specs  # noqa: F401

        spec = get_attack_config_spec("tool_output_ipi")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.technique_key, "tool_output_ipi")


class TestAttackValidation(unittest.TestCase):
    def test_requires_client_and_router(self):
        with self.assertRaises(ValueError):
            ToolOutputIPIAttack(config={}, client=None, agent_router=MagicMock())
        with self.assertRaises(ValueError):
            ToolOutputIPIAttack(config={}, client=MagicMock(), agent_router=None)

    def test_rejects_bad_mode(self):
        with self.assertRaises(ValueError):
            ToolOutputIPIAttack(
                config={"tool_output_ipi_params": {"mode": "nope"}},
                client=MagicMock(),
                agent_router=MagicMock(),
            )

    def test_run_empty_goals(self):
        attack = ToolOutputIPIAttack(
            config={},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.run(goals=[]), [])

    def test_run_returns_attack_results(self):
        attack = ToolOutputIPIAttack(
            config={"tool_output_ipi_params": {"max_attempts": 1}},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        coordinator = MagicMock()
        coordinator.has_goal_tracking = False
        coordinator.goal_tracker = None

        with (
            patch.object(attack, "_initialize_coordinator", return_value=coordinator),
            patch.object(
                attack,
                "_execute_pipeline",
                side_effect=[
                    [
                        {
                            "goal": "g",
                            "prompt": "benign",
                            "response": "r",
                            "success": True,
                            "best_score": 10.0,
                        }
                    ],
                    [
                        {
                            "goal": "g",
                            "prompt": "benign",
                            "response": "r",
                            "success": True,
                            "best_score": 10.0,
                        }
                    ],
                ],
            ),
        ):
            results = attack.run(goals=["g"])

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], AttackResult)
        coordinator.finalize_all_goals.assert_called()
        coordinator.finalize_pipeline.assert_called()


if __name__ == "__main__":
    unittest.main()
