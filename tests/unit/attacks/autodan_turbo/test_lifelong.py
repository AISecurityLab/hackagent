import unittest
from unittest.mock import MagicMock, patch


_IMPORT_ERROR = None


try:
    from hackagent.attacks.techniques.autodan_turbo import lifelong
except Exception as exc:  # pragma: no cover - optional dependency guard
    lifelong = None
    _IMPORT_ERROR = exc


class _FakeStrategyLibrary:
    def __init__(self):
        self.add_calls = 0

    def size(self):
        return 1

    def retrieve(self, _query):
        return True, [{"Strategy": "S", "Definition": "D", "Example": "e"}]

    def all(self):
        return {"S": {"Strategy": "S", "Definition": "D"}}

    def embed(self, _text):
        return [0.1, 0.2]

    def add(self, _strategy):
        self.add_calls += 1


class _FakeTrackerContext:
    def __init__(self, metadata):
        self.is_finalized = True
        self.final_success = True
        self.metadata = metadata


class _FakeTracker:
    def __init__(self, metadata):
        self.ctx = _FakeTrackerContext(metadata)

    def get_goal_context_by_goal(self, _goal):
        return self.ctx

    def get_goal_context(self, _goal_idx):
        return self.ctx


@unittest.skipIf(lifelong is None, f"lifelong unavailable: {_IMPORT_ERROR}")
class TestLifelong(unittest.TestCase):
    def setUp(self):
        self.config = {
            "autodan_turbo_params": {
                "epochs": 1,
                "break_score": 1.5,
                "lifelong_iterations": 1,
            },
            "attacker": {"model": "a"},
            "scorer": {"model": "s"},
            "summarizer": {"model": "z"},
        }

    def test_build_system_with_empty_strategy_falls_back_warmup(self):
        s = lifelong._build_system("goal", [], True)
        self.assertIn("goal", s)

    def test_build_system_with_valid_single_and_invalid_list(self):
        valid_one = lifelong._build_system(
            "goal", [{"Strategy": "S", "Definition": "D", "Example": "e"}], True
        )
        self.assertIn("most effective solution", valid_one)

        valid_many = lifelong._build_system(
            "goal",
            [{"Strategy": "S1"}, {"Strategy": "S2"}],
            True,
        )
        self.assertIn("most effective solutions", valid_many)

        invalid_list = lifelong._build_system(
            "goal",
            [{"Strategy": "S1"}, {"Strategy": "S2"}],
            False,
        )
        self.assertIn("not effective", invalid_list)

    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.emit_phase_trace")
    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.summarize_strategy")
    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.score_response")
    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.query_target")
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.lifelong.extract_jailbreak_prompt"
    )
    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.conditional_generate")
    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.init_routers")
    def test_execute_returns_result(
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
        mock_score.return_value = (2.0, "assessment")
        mock_summarize.return_value = {"Strategy": "S", "Definition": "D"}

        agent_router = MagicMock()
        agent_router.backend_agent.id = "victim"
        lib = _FakeStrategyLibrary()

        out = lifelong.execute(
            goals=["goal-1"],
            config=self.config,
            client=MagicMock(),
            agent_router=agent_router,
            logger=MagicMock(),
            strategy_library=lib,
        )

        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["success"])
        self.assertGreaterEqual(lib.add_calls, 1)
        self.assertEqual(mock_score.call_args.kwargs["goal"], "goal-1")
        self.assertEqual(
            mock_score.call_args.kwargs["target_response"], "target_response"
        )

    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.emit_phase_trace")
    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.summarize_strategy")
    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.score_response")
    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.query_target")
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.lifelong.extract_jailbreak_prompt"
    )
    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.conditional_generate")
    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.init_routers")
    def test_execute_no_score_improvement_does_not_add_strategy(
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
        mock_score.return_value = (1.0, "assessment")
        mock_summarize.return_value = None

        agent_router = MagicMock()
        agent_router.backend_agent.id = "victim"
        lib = _FakeStrategyLibrary()

        out = lifelong.execute(
            goals=["goal-1"],
            config={
                "autodan_turbo_params": {
                    "epochs": 1,
                    "break_score": 9.0,
                    "lifelong_iterations": 1,
                },
                "attacker": {"model": "a"},
                "scorer": {"model": "s"},
                "summarizer": {"model": "z"},
            },
            client=MagicMock(),
            agent_router=agent_router,
            logger=MagicMock(),
            strategy_library=lib,
        )

        self.assertEqual(len(out), 1)
        self.assertEqual(lib.add_calls, 0)

    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.emit_phase_trace")
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.lifelong.summarize_strategy",
        return_value=None,
    )
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.lifelong.score_response",
        return_value=(1.0, "assessment"),
    )
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.lifelong.query_target",
        return_value="target_response",
    )
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.lifelong.extract_jailbreak_prompt",
        return_value="prompt",
    )
    @patch(
        "hackagent.attacks.techniques.autodan_turbo.lifelong.conditional_generate",
        return_value="raw",
    )
    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.init_routers")
    def test_execute_hits_retrieve_branch_after_first_epoch(
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

        class _Lib(_FakeStrategyLibrary):
            def __init__(self):
                super().__init__()
                self.retrieve_calls = 0

            def retrieve(self, query):
                self.retrieve_calls += 1
                return super().retrieve(query)

        lib = _Lib()
        agent_router = MagicMock()
        agent_router.backend_agent.id = "victim"
        agent_router._agent_registry = {"victim": MagicMock(model_name="target-model")}

        out = lifelong.execute(
            goals=["goal-1"],
            config={
                "autodan_turbo_params": {
                    "epochs": 2,
                    "break_score": 9.0,
                    "lifelong_iterations": 1,
                },
                "attacker": {"model": "a"},
                "scorer": {"model": "s"},
                "summarizer": {"model": "z"},
            },
            client=MagicMock(),
            agent_router=agent_router,
            logger=MagicMock(),
            strategy_library=lib,
        )

        self.assertEqual(len(out), 1)
        self.assertGreaterEqual(lib.retrieve_calls, 1)

    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.emit_phase_trace")
    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.conditional_generate")
    @patch("hackagent.attacks.techniques.autodan_turbo.lifelong.init_routers")
    def test_execute_skips_goal_already_finalized_in_warmup(
        self,
        mock_init_routers,
        mock_conditional,
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

        tracker = _FakeTracker(
            {
                "jailbreak_prompt": "warmup prompt",
                "target_response": "warmup response",
                "autodan_score": 9.2,
                "best_score": 9.2,
            }
        )
        agent_router = MagicMock()
        agent_router.backend_agent.id = "victim"
        lib = _FakeStrategyLibrary()

        out = lifelong.execute(
            goals=["goal-1"],
            config={
                **self.config,
                "_tracker": tracker,
            },
            client=MagicMock(),
            agent_router=agent_router,
            logger=MagicMock(),
            strategy_library=lib,
        )

        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["success"])
        self.assertEqual(out[0]["autodan_score"], 9.2)
        self.assertEqual(out[0]["prompt"], "warmup prompt")
        self.assertEqual(out[0]["response"], "warmup response")
        mock_conditional.assert_not_called()


if __name__ == "__main__":
    unittest.main()
