import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.pap.attack import (
    PAPAttack,
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


class TestPAPAttack(unittest.TestCase):
    def test_requires_client(self):
        with self.assertRaises(ValueError):
            PAPAttack(config={}, client=None, agent_router=MagicMock())

    def test_requires_agent_router(self):
        with self.assertRaises(ValueError):
            PAPAttack(config={}, client=MagicMock(), agent_router=None)

    def test_default_config_merge(self):
        attack = PAPAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertIn("pap_params", attack.config)
        self.assertEqual(attack.config["attack_type"], "pap")

    def test_user_config_overrides(self):
        attack = PAPAttack(
            config={
                "output_dir": "./logs/runs",
                "pap_params": {"techniques": "all", "attacker_temperature": 0.5},
            },
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.config["pap_params"]["techniques"], "all")
        self.assertAlmostEqual(attack.config["pap_params"]["attacker_temperature"], 0.5)
        # Defaults for non-overridden keys should remain
        self.assertEqual(attack.config["pap_params"]["attacker_max_tokens"], 1024)

    def test_run_empty_goals(self):
        attack = PAPAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.run([]), [])

    def test_validate_config_missing_attack_type(self):
        """Config without attack_type should fail after merge removes it."""
        # Default config always has attack_type, so we test an invalid techniques value
        with self.assertRaises(ValueError):
            PAPAttack(
                config={
                    "output_dir": "./logs/runs",
                    "pap_params": {"techniques": "invalid_value"},
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

    @patch("hackagent.attacks.techniques.pap.attack.evaluation.execute")
    @patch("hackagent.attacks.techniques.pap.attack.generation.execute")
    def test_run_pipeline(self, mock_gen, mock_eval):
        client = MagicMock()
        agent_router = MagicMock()
        attack = PAPAttack(
            config={"output_dir": "./logs/runs"},
            client=client,
            agent_router=agent_router,
        )

        coordinator = _DummyCoordinator()

        def _init_coord(*_args, **_kwargs):
            attack.tracker = _DummyStepTracker()
            return coordinator

        mock_gen.return_value = [
            {
                "goal": "test goal",
                "persuasive_prompt": "persuasive test",
                "response": "target response",
                "error": None,
                "technique": "Logical Appeal",
                "technique_index": 0,
                "best_score": 1.0,
                "success": True,
            }
        ]
        mock_eval.return_value = mock_gen.return_value

        with patch.object(attack, "_initialize_coordinator", side_effect=_init_coord):
            results = attack.run(["test goal"])

        mock_gen.assert_called_once()
        mock_eval.assert_called_once()
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
