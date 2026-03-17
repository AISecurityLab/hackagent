# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.pair.attack import PAIRAttack


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


if __name__ == "__main__":
    unittest.main()
