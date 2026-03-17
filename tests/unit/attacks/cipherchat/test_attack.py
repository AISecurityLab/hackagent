# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for CipherChat attack class."""

import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.cipherchat.attack import (
    CipherChatAttack,
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

    def initialize_goals(self, *a, **kw):
        pass

    def initialize_goals_from_pipeline_data(self, *a, **kw):
        pass

    def enrich_with_result_ids(self, r):
        return r

    def finalize_all_goals(self, *a, **kw):
        pass

    def log_summary(self):
        pass

    def finalize_pipeline(self, *a, **kw):
        pass

    def finalize_on_error(self, *a, **kw):
        pass


class TestRecursiveUpdate(unittest.TestCase):
    def test_nested_merge(self):
        dst = {"a": {"b": 1}, "x": 0}
        src = {"a": {"c": 2}, "y": 3}
        _recursive_update(dst, src)
        self.assertEqual(dst["a"]["b"], 1)
        self.assertEqual(dst["a"]["c"], 2)
        self.assertEqual(dst["y"], 3)

    def test_internal_keys_by_reference(self):
        obj = MagicMock()
        dst = {"_tracker": None}
        _recursive_update(dst, {"_tracker": obj})
        self.assertIs(dst["_tracker"], obj)

    def test_deep_copy_non_internal(self):
        src_list = [1, 2, 3]
        dst = {"data": []}
        _recursive_update(dst, {"data": src_list})
        self.assertEqual(dst["data"], [1, 2, 3])
        self.assertIsNot(dst["data"], src_list)


class TestCipherChatAttack(unittest.TestCase):
    def test_requires_client(self):
        with self.assertRaises(ValueError):
            CipherChatAttack(config={}, client=None, agent_router=MagicMock())

    def test_requires_agent_router(self):
        with self.assertRaises(ValueError):
            CipherChatAttack(config={}, client=MagicMock(), agent_router=None)

    def test_default_config_merge(self):
        attack = CipherChatAttack(
            config={"output_dir": "./test"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.config["output_dir"], "./test")
        self.assertIn("cipherchat_params", attack.config)
        self.assertEqual(attack.config["attack_type"], "cipherchat")

    def test_user_config_overrides_params(self):
        attack = CipherChatAttack(
            config={
                "output_dir": "./logs/runs",
                "cipherchat_params": {
                    "encode_method": "morse",
                    "num_demonstrations": 5,
                },
            },
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        params = attack.config["cipherchat_params"]
        self.assertEqual(params["encode_method"], "morse")
        self.assertEqual(params["num_demonstrations"], 5)
        # Defaults for non-overridden keys should remain
        self.assertTrue(params["use_system_role"])

    def test_run_empty_goals(self):
        attack = CipherChatAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.run([]), [])

    def test_validate_config_invalid_encode_method(self):
        with self.assertRaises(ValueError):
            CipherChatAttack(
                config={
                    "output_dir": "./logs/runs",
                    "cipherchat_params": {"encode_method": "nonexistent"},
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

    def test_validate_config_invalid_toxicity(self):
        with self.assertRaises(ValueError):
            CipherChatAttack(
                config={
                    "output_dir": "./logs/runs",
                    "cipherchat_params": {"demonstration_toxicity": "bad_value"},
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

    def test_validate_config_invalid_language(self):
        with self.assertRaises(ValueError):
            CipherChatAttack(
                config={
                    "output_dir": "./logs/runs",
                    "cipherchat_params": {"language": "fr"},
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

    def test_validate_config_invalid_instruction_type(self):
        with self.assertRaises(ValueError):
            CipherChatAttack(
                config={
                    "output_dir": "./logs/runs",
                    "cipherchat_params": {"instruction_type": "Nonexistent_Category"},
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

    def test_get_pipeline_steps(self):
        attack = CipherChatAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        steps = attack._get_pipeline_steps()
        self.assertEqual(len(steps), 2)
        self.assertIn("Generation", steps[0]["name"])
        self.assertIn("Evaluation", steps[1]["name"])

    @patch("hackagent.attacks.techniques.cipherchat.attack.evaluation.execute")
    @patch("hackagent.attacks.techniques.cipherchat.attack.generation.execute")
    def test_run_pipeline(self, mock_gen, mock_eval):
        attack = CipherChatAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )

        coordinator = _DummyCoordinator()

        def _init_coord(*_args, **_kwargs):
            attack.tracker = _DummyStepTracker()
            return coordinator

        mock_gen.return_value = [
            {
                "goal": "test",
                "full_prompt": "encoded prompt",
                "response": "encoded resp",
                "decoded_response": "decoded resp",
                "error": None,
            }
        ]
        mock_eval.return_value = [
            {
                "goal": "test",
                "full_prompt": "encoded prompt",
                "response": "encoded resp",
                "decoded_response": "decoded resp",
                "error": None,
                "best_score": 1.0,
                "success": True,
            }
        ]

        with patch.object(attack, "_initialize_coordinator", side_effect=_init_coord):
            results = attack.run(["test"])

        mock_gen.assert_called_once()
        mock_eval.assert_called_once()
        self.assertEqual(len(results), 1)

    @patch("hackagent.attacks.techniques.cipherchat.attack.generation.execute")
    def test_run_no_generation_output(self, mock_gen):
        attack = CipherChatAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )

        coordinator = _DummyCoordinator()

        def _init_coord(*_args, **_kwargs):
            attack.tracker = _DummyStepTracker()
            return coordinator

        mock_gen.return_value = []

        with patch.object(attack, "_initialize_coordinator", side_effect=_init_coord):
            results = attack.run(["test"])

        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
