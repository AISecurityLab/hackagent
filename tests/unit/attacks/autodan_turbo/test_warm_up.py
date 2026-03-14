import unittest
from unittest.mock import MagicMock, patch


_IMPORT_ERROR = None


try:
    from hackagent.attacks.techniques.autodan_turbo import warm_up
except Exception as exc:  # pragma: no cover - optional dependency guard
    warm_up = None
    _IMPORT_ERROR = exc


class _FakeStrategyLibrary:
    def __init__(self, *args, **kwargs):
        self.items = {}
        self.add_calls = 0
        self.loaded_path = None

    def load(self, _path):
        self.loaded_path = _path
        return None

    def all(self):
        return self.items

    def size(self):
        return len(self.items)

    def add(self, strategy):
        self.add_calls += 1
        self.items[strategy["Strategy"]] = strategy

    def embed(self, _text):
        return [0.1, 0.2]


@unittest.skipIf(warm_up is None, f"warm_up unavailable: {_IMPORT_ERROR}")
class TestWarmUp(unittest.TestCase):
    def setUp(self):
        self.config = {
            "autodan_turbo_params": {
                "epochs": 1,
                "break_score": 8.5,
                "warm_up_iterations": 1,
            },
            "attacker": {"model": "a"},
            "scorer": {"model": "s"},
            "summarizer": {"model": "z"},
        }

    def test_warm_up_system_contains_request(self):
        out = warm_up._warm_up_system("my req")
        self.assertIn("my req", out)

    @patch("hackagent.attacks.techniques.autodan_turbo.warm_up.emit_phase_trace")
    @patch("hackagent.attacks.techniques.autodan_turbo.warm_up.summarize_strategy")
    @patch("hackagent.attacks.techniques.autodan_turbo.warm_up.score_response")
    @patch("hackagent.attacks.techniques.autodan_turbo.warm_up.query_target")
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.warm_up.extract_jailbreak_prompt"
    )
    @patch("hackagent.attacks.techniques.autodan_turbo.warm_up.conditional_generate")
    @patch("hackagent.attacks.techniques.autodan_turbo.warm_up.init_routers")
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.warm_up.StrategyLibrary",
        _FakeStrategyLibrary,
    )
    def test_execute_runs_and_builds_library(
        self,
        mock_init_routers,
        mock_conditional,
        mock_extract,
        mock_query_target,
        mock_score,
        mock_summarize,
        _mock_trace,
    ):
        mock_init_routers.return_value = (
            MagicMock(),
            "a",
            MagicMock(),
            "s",
            MagicMock(),
            "z",
        )
        mock_conditional.return_value = "raw"
        mock_extract.return_value = "prompt"
        mock_query_target.return_value = "target_response"
        mock_score.return_value = (9.0, "assessment")
        mock_summarize.return_value = {"Strategy": "S", "Definition": "D"}

        agent_router = MagicMock()
        agent_router.backend_agent.id = "victim"

        lib, attack_log = warm_up.execute(
            goals=["goal-1"],
            config=self.config,
            client=MagicMock(),
            agent_router=agent_router,
            logger=MagicMock(),
        )

        self.assertEqual(len(attack_log), 1)
        self.assertGreaterEqual(lib.add_calls, 1)

    @patch("hackagent.attacks.techniques.autodan_turbo.warm_up.emit_phase_trace")
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.warm_up.summarize_strategy",
        return_value=None,
    )
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.warm_up.score_response",
        return_value=(1.0, "assessment"),
    )
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.warm_up.query_target",
        return_value="target_response",
    )
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.warm_up.extract_jailbreak_prompt",
        return_value="prompt",
    )
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.warm_up.conditional_generate",
        return_value="raw",
    )
    @patch("hackagent.attacks.techniques.autodan_turbo.warm_up.init_routers")
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.warm_up.StrategyLibrary",
        _FakeStrategyLibrary,
    )
    def test_execute_loads_library_path_and_uses_adapter_model_break(
        self,
        mock_init_routers,
        *_mocks,
    ):
        mock_init_routers.return_value = (
            MagicMock(),
            "a",
            MagicMock(),
            "s",
            MagicMock(),
            "z",
        )

        cfg = {
            **self.config,
            "autodan_turbo_params": {
                **self.config["autodan_turbo_params"],
                "strategy_library_path": "./tmp/lib.pkl",
            },
        }

        agent_router = MagicMock()
        agent_router.backend_agent.id = "victim"
        agent_router._agent_registry = {"victim": MagicMock(model_name="target-model")}

        lib, _attack_log = warm_up.execute(
            goals=["goal-1"],
            config=cfg,
            client=MagicMock(),
            agent_router=agent_router,
            logger=MagicMock(),
        )
        self.assertEqual(lib.loaded_path, "./tmp/lib.pkl")


if __name__ == "__main__":
    unittest.main()
