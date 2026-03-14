import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.bon.attack import (
    BoNAttack,
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
        # Should be a copy, not the same object
        self.assertIsNot(dst["data"], src_list)


class TestBoNAttack(unittest.TestCase):
    def test_requires_client(self):
        with self.assertRaises(ValueError):
            BoNAttack(config={}, client=None, agent_router=MagicMock())

    def test_requires_agent_router(self):
        with self.assertRaises(ValueError):
            BoNAttack(config={}, client=MagicMock(), agent_router=None)

    def test_default_config_merge(self):
        attack = BoNAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertIn("bon_params", attack.config)
        self.assertEqual(attack.config["attack_type"], "bon")

    def test_user_config_overrides(self):
        attack = BoNAttack(
            config={
                "output_dir": "./logs/runs",
                "bon_params": {"n_steps": 8, "sigma": 0.6},
            },
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.config["bon_params"]["n_steps"], 8)
        self.assertAlmostEqual(attack.config["bon_params"]["sigma"], 0.6)
        # Defaults for non-overridden keys should remain
        self.assertEqual(attack.config["bon_params"]["num_concurrent_k"], 5)

    def test_run_empty_goals(self):
        attack = BoNAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.run([]), [])

    def test_validate_config_missing_keys(self):
        with self.assertRaises(ValueError):
            BoNAttack(
                config={
                    "output_dir": "./logs/runs",
                    "bon_params": {"n_steps": 0},
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

    def test_validate_config_invalid_sigma(self):
        with self.assertRaises(ValueError):
            BoNAttack(
                config={
                    "output_dir": "./logs/runs",
                    "bon_params": {"sigma": 0.0},
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

    def test_get_pipeline_steps(self):
        attack = BoNAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        steps = attack._get_pipeline_steps()
        self.assertEqual(len(steps), 2)
        self.assertIn("Generation", steps[0]["name"])
        self.assertIn("Evaluation", steps[1]["name"])

    @patch("hackagent.attacks.techniques.bon.attack.evaluation.execute")
    @patch("hackagent.attacks.techniques.bon.attack.generation.execute")
    def test_run_pipeline(self, mock_gen, mock_eval):
        client = MagicMock()
        agent_router = MagicMock()
        attack = BoNAttack(
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
                "goal": "test",
                "augmented_prompt": "tset",
                "response": "ok",
                "error": None,
            }
        ]
        mock_eval.return_value = [
            {
                "goal": "test",
                "augmented_prompt": "tset",
                "response": "ok",
                "error": None,
                "best_score": 1.0,
            }
        ]

        with patch.object(attack, "_initialize_coordinator", side_effect=_init_coord):
            results = attack.run(["test"])

        mock_gen.assert_called_once()
        mock_eval.assert_called_once()
        self.assertEqual(len(results), 1)


if __name__ == "__main__":
    unittest.main()
