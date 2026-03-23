# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
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


if __name__ == "__main__":
    unittest.main()
