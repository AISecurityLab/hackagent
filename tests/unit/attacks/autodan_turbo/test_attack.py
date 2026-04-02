import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.autodan_turbo.attack import (
    AutoDANTurboAttack,
    _deep_update,
)


class _DummyStepTracker:
    @contextmanager
    def track_step(self, *_args, **_kwargs):
        yield


class _DummyCoordinator:
    def __init__(self):
        self.goal_tracker = None
        self.finalize_all_goals_calls = []

    def initialize_goals(self, *_args, **_kwargs):
        return None

    def enrich_with_result_ids(self, results):
        return results

    def finalize_all_goals(self, *args, **kwargs):
        self.finalize_all_goals_calls.append((args, kwargs))
        return None

    def log_summary(self):
        return None

    def finalize_pipeline(self, *_args, **_kwargs):
        return None

    def finalize_on_error(self, *_args, **_kwargs):
        return None


class TestAttackHelpers(unittest.TestCase):
    def test_deep_update(self):
        dst = {"a": {"b": 1}, "x": 0}
        src = {"a": {"c": 2}, "y": 3}
        _deep_update(dst, src)
        self.assertEqual(dst["a"]["b"], 1)
        self.assertEqual(dst["a"]["c"], 2)
        self.assertEqual(dst["y"], 3)


class TestAutoDANTurboAttack(unittest.TestCase):
    def test_init_requires_client_and_router(self):
        with self.assertRaises(ValueError):
            AutoDANTurboAttack(config={}, client=None, agent_router=MagicMock())
        with self.assertRaises(ValueError):
            AutoDANTurboAttack(config={}, client=MagicMock(), agent_router=None)

    def test_validate_config_errors(self):
        with self.assertRaises(ValueError):
            AutoDANTurboAttack(
                config={
                    "output_dir": "./logs/runs",
                    "autodan_turbo_params": {"epochs": 0},
                    "attacker": {"identifier": "x"},
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

    def test_get_pipeline_steps_is_empty(self):
        attack = AutoDANTurboAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack._get_pipeline_steps(), [])

    def test_run_with_no_goals_returns_empty(self):
        attack = AutoDANTurboAttack(
            config={"output_dir": "./logs/runs"},
            client=MagicMock(),
            agent_router=MagicMock(),
        )
        self.assertEqual(attack.run([]), [])

        with self.assertRaises(ValueError):
            AutoDANTurboAttack(
                config={
                    "output_dir": "./logs/runs",
                    "autodan_turbo_params": {"epochs": 1},
                    "attacker": {"identifier": ""},
                },
                client=MagicMock(),
                agent_router=MagicMock(),
            )

    @patch("hackagent.attacks.techniques.autodan_turbo.attack.emit_phase_trace")
    @patch("hackagent.attacks.techniques.autodan_turbo.attack.evaluation.execute")
    @patch("hackagent.attacks.techniques.autodan_turbo.attack.lifelong.execute")
    @patch("hackagent.attacks.techniques.autodan_turbo.attack.warm_up.execute")
    def test_run_pipeline(
        self,
        mock_warm_up,
        mock_lifelong,
        mock_eval,
        _mock_trace,
    ):
        client = MagicMock()
        agent_router = MagicMock()
        attack = AutoDANTurboAttack(
            config={"output_dir": "./logs/runs"},
            client=client,
            agent_router=agent_router,
        )

        coordinator = _DummyCoordinator()

        def _init_coord(*_args, **_kwargs):
            attack.tracker = _DummyStepTracker()
            return coordinator

        attack._initialize_coordinator = MagicMock(side_effect=_init_coord)

        strategy_lib = MagicMock()
        strategy_lib.size.return_value = 1
        mock_warm_up.return_value = (strategy_lib, [])
        base_results = [
            {"goal": "g", "prompt": "p", "response": "r", "score": 2.0, "success": True}
        ]
        mock_lifelong.return_value = base_results
        mock_eval.return_value = base_results

        out = attack.run(["g"])

        self.assertEqual(len(out), 1)
        self.assertEqual(mock_warm_up.call_count, 1)
        self.assertEqual(mock_lifelong.call_count, 1)
        self.assertEqual(mock_eval.call_count, 1)
        strategy_lib.save.assert_called_once()
        self.assertEqual(len(coordinator.finalize_all_goals_calls), 1)
        _args, finalize_kwargs = coordinator.finalize_all_goals_calls[0]
        scorer = finalize_kwargs.get("scorer")
        self.assertTrue(callable(scorer))
        self.assertTrue(scorer([{"success": True}]))
        self.assertFalse(scorer([{"success": False}]))

    @patch("hackagent.attacks.techniques.autodan_turbo.attack.emit_phase_trace")
    @patch("hackagent.attacks.techniques.autodan_turbo.attack.evaluation.execute")
    @patch("hackagent.attacks.techniques.autodan_turbo.attack.lifelong.execute")
    @patch("hackagent.attacks.techniques.autodan_turbo.attack.warm_up.execute")
    def test_run_sets_tracker_and_uses_metadata_target_name(
        self,
        mock_warm_up,
        mock_lifelong,
        mock_eval,
        _mock_trace,
    ):
        client = MagicMock()
        agent_router = MagicMock()
        agent_router._agent_registry = {}
        agent_router.backend_agent.id = "victim"
        agent_router.backend_agent.metadata = {"name": "meta-target"}

        attack = AutoDANTurboAttack(
            config={"output_dir": "./logs/runs"},
            client=client,
            agent_router=agent_router,
        )

        coordinator = _DummyCoordinator()
        coordinator.goal_tracker = MagicMock()

        def _init_coord(*_args, **_kwargs):
            attack.tracker = _DummyStepTracker()
            return coordinator

        attack._initialize_coordinator = MagicMock(side_effect=_init_coord)

        strategy_lib = MagicMock()
        strategy_lib.size.return_value = 1
        mock_warm_up.return_value = (strategy_lib, [])
        base_results = [
            {"goal": "g", "prompt": "p", "response": "r", "score": 2.0, "success": True}
        ]
        mock_lifelong.return_value = base_results
        mock_eval.return_value = base_results

        out = attack.run(["g"])
        self.assertEqual(len(out), 1)
        self.assertIn("_tracker", attack.config)

    @patch("hackagent.attacks.techniques.autodan_turbo.attack.emit_phase_trace")
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.attack.warm_up.execute",
        side_effect=RuntimeError("boom"),
    )
    def test_run_pipeline_error_finalizes(self, _mock_warm_up, _mock_trace):
        client = MagicMock()
        agent_router = MagicMock()
        attack = AutoDANTurboAttack(
            config={"output_dir": "./logs/runs"},
            client=client,
            agent_router=agent_router,
        )

        coordinator = _DummyCoordinator()

        def _init_coord(*_args, **_kwargs):
            attack.tracker = _DummyStepTracker()
            return coordinator

        attack._initialize_coordinator = MagicMock(side_effect=_init_coord)

        with self.assertRaises(RuntimeError):
            attack.run(["g"])


if __name__ == "__main__":
    unittest.main()
