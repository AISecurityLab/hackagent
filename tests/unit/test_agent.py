# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for HackAgent class (hackagent/agent.py)."""

import unittest
from unittest.mock import MagicMock, patch

import httpx

from hackagent.errors import HackAgentError
from hackagent.router.types import AgentTypeEnum


class TestHackAgentInitialization(unittest.TestCase):
    """Test HackAgent initialization."""

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def test_basic_initialization(
        self, mock_resolve_type, mock_resolve_token, mock_router
    ):
        """Test basic HackAgent initialization."""
        from hackagent.agent import HackAgent

        agent = HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
        )

        self.assertIsNotNone(agent.client)
        self.assertIsNotNone(agent.router)
        mock_router.assert_called_once()

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def test_default_base_url(self, mock_resolve_type, mock_resolve_token, mock_router):
        """Test default base_url is used when not provided."""
        from hackagent.agent import HackAgent

        agent = HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
        )

        self.assertEqual(agent.client.base_url, "https://api.hackagent.dev")

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def test_custom_base_url(self, mock_resolve_type, mock_resolve_token, mock_router):
        """Test custom base_url."""
        from hackagent.agent import HackAgent

        agent = HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
            base_url="https://custom.api.com",
        )

        self.assertEqual(agent.client.base_url, "https://custom.api.com")

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def test_default_timeout_is_120_seconds(
        self, mock_resolve_type, mock_resolve_token, mock_router
    ):
        """Test that the remote client defaults to a bounded 120s timeout,
        instead of hanging indefinitely on a misbehaving endpoint."""
        from hackagent.agent import HackAgent

        agent = HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
        )

        self.assertEqual(agent.client.timeout, httpx.Timeout(120.0))

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def test_custom_timeout_is_passed_to_client(
        self, mock_resolve_type, mock_resolve_token, mock_router
    ):
        """Test that an explicit timeout value reaches the AuthenticatedClient."""
        from hackagent.agent import HackAgent

        agent = HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
            timeout=5.0,
        )

        self.assertEqual(agent.client.timeout, httpx.Timeout(5.0))

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def test_explicit_none_timeout_disables_it(
        self, mock_resolve_type, mock_resolve_token, mock_router
    ):
        """Test that passing timeout=None explicitly still opts out of the
        default, preserving the previous unbounded-wait behavior."""
        from hackagent.agent import HackAgent

        agent = HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
            timeout=None,
        )

        self.assertIsNone(agent.client.timeout)

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def test_attack_strategies_lazy_loaded(
        self, mock_resolve_type, mock_resolve_token, mock_router
    ):
        """Test attack strategies are None initially (lazy-loaded)."""
        from hackagent.agent import HackAgent

        agent = HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
        )

        self.assertIsNone(agent._attack_strategies)

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def test_with_metadata(self, mock_resolve_type, mock_resolve_token, mock_router):
        """Test initialization with metadata."""
        from hackagent.agent import HackAgent

        metadata = {"key": "value"}
        HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
            metadata=metadata,
        )

        # metadata should be passed to the router
        call_kwargs = mock_router.call_args
        self.assertEqual(call_kwargs.kwargs.get("metadata"), metadata)

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def test_target_config_is_merged_into_router_defaults(
        self, mock_resolve_type, mock_resolve_token, mock_router
    ):
        """Test target_config becomes the router-owned victim request default."""
        from hackagent.agent import HackAgent

        HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
            target_config={"max_tokens": 321, "temperature": 0.2},
            adapter_operational_config={"name": "demo-model", "temperature": 0.4},
            metadata={"label": "demo"},
        )

        call_kwargs = mock_router.call_args.kwargs
        self.assertEqual(call_kwargs["adapter_operational_config"]["max_tokens"], 321)
        self.assertEqual(call_kwargs["adapter_operational_config"]["temperature"], 0.4)
        self.assertEqual(call_kwargs["metadata"]["temperature"], 0.2)
        self.assertEqual(call_kwargs["metadata"]["label"], "demo")

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def test_constructor_thinking_is_forwarded_for_ollama(
        self, mock_resolve_type, mock_resolve_token, mock_router
    ):
        """Constructor thinking is forwarded only when target type is OLLAMA."""
        from hackagent.agent import HackAgent

        mock_resolve_type.return_value = AgentTypeEnum.OLLAMA

        HackAgent(
            endpoint="http://localhost:11434",
            api_key="test-key",
            thinking=False,
        )

        call_kwargs = mock_router.call_args.kwargs
        self.assertIn("thinking", call_kwargs["adapter_operational_config"])
        self.assertFalse(call_kwargs["adapter_operational_config"]["thinking"])

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def test_constructor_thinking_is_ignored_for_non_ollama(
        self, mock_resolve_type, mock_resolve_token, mock_router
    ):
        """Constructor thinking is stripped for non-OLLAMA target types."""
        from hackagent.agent import HackAgent

        mock_resolve_type.return_value = AgentTypeEnum.OPENAI_SDK

        HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
            thinking=False,
        )

        call_kwargs = mock_router.call_args.kwargs
        self.assertNotIn("thinking", call_kwargs["adapter_operational_config"])


class TestHackAgentAttackStrategies(unittest.TestCase):
    """Test HackAgent.attack_strategies lazy loading."""

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def test_attack_strategies_loaded_on_access(
        self, mock_resolve_type, mock_resolve_token, mock_router
    ):
        """Test that attack_strategies are loaded on first access."""
        from hackagent.agent import HackAgent

        agent = HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
        )

        strategies = agent.attack_strategies

        self.assertIn("advprefix", strategies)
        self.assertIn("static_template", strategies)
        self.assertIn("pair", strategies)

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def test_attack_strategies_cached(
        self, mock_resolve_type, mock_resolve_token, mock_router
    ):
        """Test that attack_strategies are cached after first access."""
        from hackagent.agent import HackAgent

        agent = HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
        )

        strategies1 = agent.attack_strategies
        strategies2 = agent.attack_strategies

        self.assertIs(strategies1, strategies2)


class TestHackAgentHack(unittest.TestCase):
    """Test HackAgent.hack method."""

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def setUp(self, mock_resolve_type, mock_resolve_token, mock_router):
        """Set up HackAgent for hack tests."""
        from hackagent.agent import HackAgent

        self.agent = HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
        )

        # Mock the router's backend_agent
        mock_backend = MagicMock()
        mock_backend.name = "test-agent"
        mock_backend.id = "agent-123"
        mock_backend.agent_type = "litellm"
        self.agent.router.backend_agent = mock_backend

    def test_hack_missing_attack_type_raises(self):
        """Test that missing attack_type raises HackAgentError."""
        with self.assertRaises(HackAgentError) as ctx:
            self.agent.hack(attack_config={})
        self.assertIn("attack_type", str(ctx.exception))

    def test_hack_unsupported_attack_type_raises(self):
        """Test that unsupported attack_type raises HackAgentError."""
        with self.assertRaises(HackAgentError) as ctx:
            self.agent.hack(attack_config={"attack_type": "nonexistent"})
        self.assertIn("Unsupported", str(ctx.exception))

    def test_hack_delegates_to_strategy(self):
        """Test that hack delegates to the correct strategy."""
        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = [{"result": "test"}]
        self.agent._attack_strategies = {"test_attack": mock_strategy}

        result = self.agent.hack(
            attack_config={"attack_type": "test_attack", "goals": ["test"]}
        )

        mock_strategy.execute.assert_called_once()
        self.assertEqual(result, [{"result": "test"}])

    def test_hack_passes_run_config_override(self):
        """Test that run_config_override is passed to strategy."""
        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = []
        self.agent._attack_strategies = {"test_attack": mock_strategy}

        run_config = {"custom": "override"}
        self.agent.hack(
            attack_config={"attack_type": "test_attack"},
            run_config_override=run_config,
        )

        call_kwargs = mock_strategy.execute.call_args.kwargs
        self.assertEqual(call_kwargs["run_config_override"], run_config)

    def test_hack_passes_fail_on_run_error(self):
        """Test that fail_on_run_error is passed to strategy."""
        mock_strategy = MagicMock()
        mock_strategy.execute.return_value = []
        self.agent._attack_strategies = {"test_attack": mock_strategy}

        self.agent.hack(
            attack_config={"attack_type": "test_attack"},
            fail_on_run_error=False,
        )

        call_kwargs = mock_strategy.execute.call_args.kwargs
        self.assertFalse(call_kwargs["fail_on_run_error"])

    def test_hack_wraps_value_error(self):
        """Test that ValueError is wrapped in HackAgentError."""
        mock_strategy = MagicMock()
        mock_strategy.execute.side_effect = ValueError("Bad config")
        self.agent._attack_strategies = {"test_attack": mock_strategy}

        with self.assertRaises(HackAgentError) as ctx:
            self.agent.hack(attack_config={"attack_type": "test_attack"})
        self.assertIn("Configuration error", str(ctx.exception))

    def test_hack_wraps_runtime_error(self):
        """Test that RuntimeError is wrapped in HackAgentError."""
        mock_strategy = MagicMock()
        mock_strategy.execute.side_effect = RuntimeError("Something broke")
        self.agent._attack_strategies = {"test_attack": mock_strategy}

        with self.assertRaises(HackAgentError) as ctx:
            self.agent.hack(attack_config={"attack_type": "test_attack"})
        self.assertIn("unexpected runtime error", str(ctx.exception).lower())

    def test_hack_wraps_backend_runtime_error(self):
        """Test backend-specific RuntimeErrors are wrapped."""
        mock_strategy = MagicMock()
        mock_strategy.execute.side_effect = RuntimeError(
            "Failed to create backend agent"
        )
        self.agent._attack_strategies = {"test_attack": mock_strategy}

        with self.assertRaises(HackAgentError) as ctx:
            self.agent.hack(attack_config={"attack_type": "test_attack"})
        self.assertIn("Backend agent operation failed", str(ctx.exception))

    def test_hack_wraps_generic_exception(self):
        """Test that generic exceptions are wrapped in HackAgentError."""
        mock_strategy = MagicMock()
        mock_strategy.execute.side_effect = Exception("Unknown error")
        self.agent._attack_strategies = {"test_attack": mock_strategy}

        with self.assertRaises(HackAgentError):
            self.agent.hack(attack_config={"attack_type": "test_attack"})

    def test_hack_reraises_hackagent_error(self):
        """Test that HackAgentError is re-raised as-is."""
        mock_strategy = MagicMock()
        mock_strategy.execute.side_effect = HackAgentError("Direct error")
        self.agent._attack_strategies = {"test_attack": mock_strategy}

        with self.assertRaises(HackAgentError) as ctx:
            self.agent.hack(attack_config={"attack_type": "test_attack"})
        self.assertEqual(str(ctx.exception), "Direct error")


class TestHackAgentHackChain(unittest.TestCase):
    """Test HackAgent.hack_chain method."""

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def setUp(self, mock_resolve_type, mock_resolve_token, mock_router):
        """Set up HackAgent for hack_chain tests."""
        from hackagent.agent import HackAgent

        self.agent = HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
        )

        mock_backend = MagicMock()
        mock_backend.name = "test-agent"
        mock_backend.id = "agent-123"
        mock_backend.agent_type = "litellm"
        self.agent.router.backend_agent = mock_backend

    def test_hack_chain_empty_attacks_raises(self):
        """Test that an empty attacks list raises HackAgentError."""
        with self.assertRaises(HackAgentError):
            self.agent.hack_chain(attacks=[])

    def test_hack_chain_missing_attack_type_raises(self):
        """Test that a chain step missing attack_type raises HackAgentError."""
        with self.assertRaises(HackAgentError):
            self.agent.hack_chain(attacks=[{}], goals=["do the bad thing"])

    def test_hack_chain_defaults_to_jailbreak_campaign_when_attacks_omitted(self):
        """attacks=None (the default) resolves to the Jailbreak evaluation
        campaign's primary attacks, in campaign order: h4rm3l -> TAP -> PAIR."""
        with patch.object(self.agent, "hack") as mock_hack:
            mock_hack.return_value = [{"goal": "goal-a", "is_success": False}]

            self.agent.hack_chain(goals=["goal-a"])

            called_attack_types = [
                call.kwargs["attack_config"]["attack_type"]
                for call in mock_hack.call_args_list
            ]
            self.assertEqual(called_attack_types, ["h4rm3l", "tap", "pair"])

    def test_hack_chain_explicit_attacks_override_default_campaign(self):
        """Passing an explicit attacks list bypasses the campaign default."""
        with patch.object(self.agent, "hack") as mock_hack:
            mock_hack.return_value = [{"goal": "goal-a", "is_success": True}]

            self.agent.hack_chain(
                attacks=[{"attack_type": "baseline"}], goals=["goal-a"]
            )

            called_attack_types = [
                call.kwargs["attack_config"]["attack_type"]
                for call in mock_hack.call_args_list
            ]
            self.assertEqual(called_attack_types, ["baseline"])

    def test_hack_chain_stops_on_first_success(self):
        """A goal that succeeds at step 1 is never retried at step 2."""
        with patch.object(self.agent, "hack") as mock_hack:
            mock_hack.return_value = [{"goal": "goal-a", "is_success": True}]

            result = self.agent.hack_chain(
                attacks=[{"attack_type": "pair"}, {"attack_type": "tap"}],
                goals=["goal-a"],
            )

            mock_hack.assert_called_once()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["chain_attack_type"], "pair")
            self.assertEqual(result[0]["chain_step"], 0)

    def test_hack_chain_escalates_mitigated_goal_to_next_attack(self):
        """A goal mitigated at step 1 is retried at step 2."""
        with patch.object(self.agent, "hack") as mock_hack:
            mock_hack.side_effect = [
                [{"goal": "goal-a", "is_success": False}],
                [{"goal": "goal-a", "is_success": True}],
            ]

            result = self.agent.hack_chain(
                attacks=[{"attack_type": "pair"}, {"attack_type": "tap"}],
                goals=["goal-a"],
            )

            self.assertEqual(mock_hack.call_count, 2)
            second_call_config = mock_hack.call_args_list[1].kwargs["attack_config"]
            self.assertEqual(second_call_config["goals"], ["goal-a"])
            self.assertEqual(second_call_config["attack_type"], "tap")

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["chain_attack_type"], "tap")
            self.assertEqual(result[0]["chain_step"], 1)

    def test_hack_chain_keeps_last_attempt_for_fully_mitigated_goal(self):
        """A goal mitigated by every attack keeps the last step's rows."""
        with patch.object(self.agent, "hack") as mock_hack:
            mock_hack.side_effect = [
                [{"goal": "goal-a", "is_success": False}],
                [{"goal": "goal-a", "is_success": False}],
            ]

            result = self.agent.hack_chain(
                attacks=[{"attack_type": "pair"}, {"attack_type": "tap"}],
                goals=["goal-a"],
            )

            self.assertEqual(mock_hack.call_count, 2)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["chain_attack_type"], "tap")
            self.assertFalse(result[0]["is_success"])

    def test_hack_chain_skips_remaining_steps_when_all_goals_resolved(self):
        """No further hack() calls happen once every goal has succeeded."""
        with patch.object(self.agent, "hack") as mock_hack:
            mock_hack.return_value = [
                {"goal": "goal-a", "is_success": True},
                {"goal": "goal-b", "is_success": True},
            ]

            self.agent.hack_chain(
                attacks=[
                    {"attack_type": "pair"},
                    {"attack_type": "tap"},
                    {"attack_type": "bon"},
                ],
                goals=["goal-a", "goal-b"],
            )

            mock_hack.assert_called_once()

    def test_hack_chain_mixed_goals_partition_correctly(self):
        """Only mitigated goals are forwarded; resolved ones are excluded."""
        with patch.object(self.agent, "hack") as mock_hack:
            mock_hack.side_effect = [
                [
                    {"goal": "goal-a", "is_success": True},
                    {"goal": "goal-b", "is_success": False},
                ],
                [{"goal": "goal-b", "is_success": True}],
            ]

            result = self.agent.hack_chain(
                attacks=[{"attack_type": "pair"}, {"attack_type": "tap"}],
                goals=["goal-a", "goal-b"],
            )

            second_call_config = mock_hack.call_args_list[1].kwargs["attack_config"]
            self.assertEqual(second_call_config["goals"], ["goal-b"])

            by_goal = {row["goal"]: row for row in result}
            self.assertEqual(by_goal["goal-a"]["chain_attack_type"], "pair")
            self.assertEqual(by_goal["goal-b"]["chain_attack_type"], "tap")

    def test_hack_chain_resolves_goals_from_first_step_dataset(self):
        """When goals aren't passed explicitly, they're inferred from step 0 results."""
        with patch.object(self.agent, "hack") as mock_hack:
            mock_hack.return_value = [{"goal": "goal-a", "is_success": True}]

            result = self.agent.hack_chain(
                attacks=[{"attack_type": "pair", "dataset": {"preset": "advbench"}}],
            )

            first_call_config = mock_hack.call_args_list[0].kwargs["attack_config"]
            self.assertNotIn("goals", first_call_config)
            self.assertEqual(first_call_config["dataset"], {"preset": "advbench"})
            self.assertEqual(len(result), 1)

    def test_hack_chain_escalate_only_mitigated_false_runs_every_attack_on_every_goal(
        self,
    ):
        """With escalate_only_mitigated=False, all goals go to every attack
        regardless of outcome, and results from every step are kept."""
        with patch.object(self.agent, "hack") as mock_hack:
            mock_hack.side_effect = [
                [
                    {"goal": "goal-a", "is_success": True},
                    {"goal": "goal-b", "is_success": False},
                ],
                [
                    {"goal": "goal-a", "is_success": False},
                    {"goal": "goal-b", "is_success": True},
                ],
            ]

            result = self.agent.hack_chain(
                attacks=[{"attack_type": "pair"}, {"attack_type": "tap"}],
                goals=["goal-a", "goal-b"],
                escalate_only_mitigated=False,
            )

            # Both steps run against both goals (no escalation-based filtering).
            self.assertEqual(mock_hack.call_count, 2)
            second_call_config = mock_hack.call_args_list[1].kwargs["attack_config"]
            self.assertEqual(set(second_call_config["goals"]), {"goal-a", "goal-b"})

            # Rows from *both* steps are kept for *both* goals — nothing
            # dropped or overwritten, unlike the default escalation mode.
            self.assertEqual(len(result), 4)
            by_goal_and_step = {(r["goal"], r["chain_attack_type"]) for r in result}
            self.assertEqual(
                by_goal_and_step,
                {
                    ("goal-a", "pair"),
                    ("goal-a", "tap"),
                    ("goal-b", "pair"),
                    ("goal-b", "tap"),
                },
            )

    def test_hack_chain_escalate_only_mitigated_true_is_default(self):
        """escalate_only_mitigated defaults to True (fallback-ladder behavior)."""
        with patch.object(self.agent, "hack") as mock_hack:
            mock_hack.side_effect = [
                [{"goal": "goal-a", "is_success": False}],
                [{"goal": "goal-a", "is_success": True}],
            ]

            result = self.agent.hack_chain(
                attacks=[{"attack_type": "pair"}, {"attack_type": "tap"}],
                goals=["goal-a"],
            )

            self.assertEqual(mock_hack.call_count, 2)
            # Only the final (successful) attempt's row is kept.
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["chain_attack_type"], "tap")

    def test_hack_chain_keeps_unmatched_goal_instead_of_dropping_it(self):
        """A goal a step returns no row for (e.g. it errored) has no evidence
        of success, so it stays in the chain and keeps its last known rows
        from the previous step, rather than being dropped."""
        with patch.object(self.agent, "hack") as mock_hack:
            mock_hack.side_effect = [
                [
                    {"goal": "goal-a", "is_success": False},
                    {"goal": "goal-b", "is_success": False},
                ],
                # Step 2 only returns a row for goal-a; goal-b is absent.
                [{"goal": "goal-a", "is_success": True}],
            ]

            result = self.agent.hack_chain(
                attacks=[{"attack_type": "pair"}, {"attack_type": "tap"}],
                goals=["goal-a", "goal-b"],
            )

            second_call_config = mock_hack.call_args_list[1].kwargs["attack_config"]
            self.assertEqual(set(second_call_config["goals"]), {"goal-a", "goal-b"})

            by_goal = {row["goal"]: row for row in result}
            self.assertEqual(by_goal["goal-a"]["chain_attack_type"], "tap")
            # goal-b never got a matching row back, so it falls back to its
            # last known (step 1) rows rather than being dropped or errored.
            self.assertEqual(by_goal["goal-b"]["chain_attack_type"], "pair")


if __name__ == "__main__":
    unittest.main()
