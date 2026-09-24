# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for the facade session and a bound target."""

import unittest
from unittest.mock import patch

from hackagent import HackAgent, Settings
from hackagent.core.errors import HackAgentError
from tests.fakes import in_memory_store


def _settings(**kwargs):
    kwargs.setdefault("api_key", "")
    kwargs.setdefault("db_path", ":memory:")
    kwargs.setdefault("env", {})
    kwargs.setdefault("config_path", "/nonexistent/hackagent/config.json")
    return Settings.resolve(**kwargs)


def _target(**kwargs):
    store = kwargs.pop("store", None) or in_memory_store()
    endpoint = kwargs.pop("endpoint", "http://localhost:8000")
    agent_type = kwargs.pop("agent_type", "openai-sdk")
    name = kwargs.pop("name", "test-agent")
    session = HackAgent(_settings(), backend=store)
    return session.target(endpoint, agent_type, name=name, **kwargs), store


class TestHackAgentSession(unittest.TestCase):
    def test_remote_session_defaults_to_a_120_second_timeout(self):
        with patch("hackagent.storage.remote.RemoteBackend.connect") as connect:
            HackAgent(_settings(api_key="test-key", base_url="https://api.hackagent.dev"))
        connect.assert_called_once()
        self.assertEqual(connect.call_args.kwargs["timeout"], 120.0)
        self.assertEqual(connect.call_args.args[1], "test-key")

    def test_custom_base_url_and_timeout_are_forwarded(self):
        with patch("hackagent.storage.remote.RemoteBackend.connect") as connect:
            HackAgent(
                _settings(api_key="test-key", base_url="https://custom.api.com"),
                timeout=15.0,
            )
        self.assertEqual(connect.call_args.args[0], "https://custom.api.com")
        self.assertEqual(connect.call_args.kwargs["timeout"], 15.0)

    def test_explicit_none_timeout_disables_it(self):
        with patch("hackagent.storage.remote.RemoteBackend.connect") as connect:
            HackAgent(_settings(api_key="test-key"), timeout=None)
        self.assertIsNone(connect.call_args.kwargs["timeout"])


class TestBoundTarget(unittest.TestCase):
    def test_metadata_is_stored_on_the_agent_record(self):
        target, _store = _target(metadata={"key": "value"})
        self.assertEqual(target.agent_record.metadata["key"], "value")

    def test_target_config_is_merged_into_the_spec(self):
        with patch("hackagent.models.client.connect") as mock_connect:
            target, _store = _target(
                target_config={"max_tokens": 321, "temperature": 0.2},
                adapter_operational_config={"name": "demo-model", "temperature": 0.4},
                metadata={"label": "demo"},
            )
        spec = mock_connect.call_args.args[0]
        self.assertEqual(spec.identifier, "demo-model")
        self.assertEqual(spec.max_tokens, 321)
        self.assertEqual(spec.temperature, 0.4)
        self.assertEqual(target.agent_record.metadata["label"], "demo")

    def test_thinking_is_forwarded_for_ollama(self):
        with patch("hackagent.models.client.connect") as mock_connect:
            _target(endpoint="http://localhost:11434", agent_type="ollama", thinking=False)
        self.assertIs(mock_connect.call_args.args[0].thinking, False)

    def test_thinking_is_ignored_for_non_ollama(self):
        with patch("hackagent.models.client.connect") as mock_connect:
            _target(thinking=False)
        self.assertIsNone(mock_connect.call_args.args[0].thinking)


class TestHackAgentHack(unittest.TestCase):
    """Test HackAgent.hack method."""

    def setUp(self):
        self.agent, self.store = _target()

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

    @patch("hackagent.orchestrator.runner.run")
    def test_hack_delegates_to_runner(self, mock_run):
        """Test that hack delegates to the orchestrator runner."""
        mock_run.return_value = [{"result": "test"}]

        result = self.agent.hack(
            attack_config={"attack_type": "baseline", "goals": ["test"]}
        )

        mock_run.assert_called_once()
        self.assertEqual(result, [{"result": "test"}])
        self.assertIs(mock_run.call_args.args[0], self.agent)

    @patch("hackagent.orchestrator.runner.run")
    def test_hack_passes_run_config_override(self, mock_run):
        """Test that run_config_override is passed to the runner."""
        mock_run.return_value = []
        run_config = {"custom": "override"}
        self.agent.hack(
            attack_config={"attack_type": "baseline"},
            run_config_override=run_config,
        )
        self.assertEqual(mock_run.call_args.kwargs["run_config_override"], run_config)

    @patch("hackagent.orchestrator.runner.run")
    def test_hack_passes_fail_on_run_error(self, mock_run):
        """Test that fail_on_run_error is passed to the runner."""
        mock_run.return_value = []
        self.agent.hack(
            attack_config={"attack_type": "baseline"},
            fail_on_run_error=False,
        )
        self.assertFalse(mock_run.call_args.kwargs["fail_on_run_error"])

    @patch("hackagent.orchestrator.runner.run")
    def test_hack_wraps_value_error(self, mock_run):
        """Test that ValueError is wrapped in HackAgentError."""
        mock_run.side_effect = ValueError("Bad config")
        with self.assertRaises(HackAgentError) as ctx:
            self.agent.hack(attack_config={"attack_type": "baseline"})
        self.assertIn("Configuration error", str(ctx.exception))

    @patch("hackagent.orchestrator.runner.run")
    def test_hack_wraps_runtime_error(self, mock_run):
        """Test that RuntimeError is wrapped in HackAgentError."""
        mock_run.side_effect = RuntimeError("Something broke")
        with self.assertRaises(HackAgentError) as ctx:
            self.agent.hack(attack_config={"attack_type": "baseline"})
        self.assertIn("unexpected runtime error", str(ctx.exception).lower())

    @patch("hackagent.orchestrator.runner.run")
    def test_hack_wraps_backend_runtime_error(self, mock_run):
        """Test backend-specific RuntimeErrors are wrapped."""
        mock_run.side_effect = RuntimeError("Failed to create backend agent")
        with self.assertRaises(HackAgentError) as ctx:
            self.agent.hack(attack_config={"attack_type": "baseline"})
        self.assertIn("Backend agent operation failed", str(ctx.exception))

    @patch("hackagent.orchestrator.runner.run")
    def test_hack_wraps_generic_exception(self, mock_run):
        """Test that generic exceptions are wrapped in HackAgentError."""
        mock_run.side_effect = Exception("Unknown error")
        with self.assertRaises(HackAgentError):
            self.agent.hack(attack_config={"attack_type": "baseline"})

    @patch("hackagent.orchestrator.runner.run")
    def test_hack_reraises_hackagent_error(self, mock_run):
        """Test that HackAgentError is re-raised as-is."""
        mock_run.side_effect = HackAgentError("Direct error")
        with self.assertRaises(HackAgentError) as ctx:
            self.agent.hack(attack_config={"attack_type": "baseline"})
        self.assertEqual(str(ctx.exception), "Direct error")


class TestHackAgentHackChain(unittest.TestCase):
    """Test HackAgent.hack_chain method."""

    def setUp(self):
        self.agent, self.store = _target()

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


class TestHackAgentTarget(unittest.TestCase):
    """The facade registers the target, and nothing else, as an Agent."""

    def _agent(self, **kwargs):
        guardrails = {}
        if "before_guardrail" in kwargs:
            guardrails["before"] = kwargs.pop("before_guardrail")
        if "after_guardrail" in kwargs:
            guardrails["after"] = kwargs.pop("after_guardrail")
        store = in_memory_store()
        return _target(
            store=store,
            endpoint="http://localhost:11434",
            agent_type="ollama",
            name="llama3",
            guardrails=guardrails or None,
            **kwargs,
        )

    def test_only_the_target_is_registered(self):
        agent, store = self._agent(
            before_guardrail={
                "identifier": "guard",
                "endpoint": "http://localhost:11434",
                "agent_type": "OLLAMA",
            }
        )

        agents = store.list_agents().items
        self.assertEqual([a.name for a in agents], ["llama3"])
        self.assertEqual(agent.router.registration_key, str(agent.agent_record.id))
        self.assertIs(agent.router.backend_agent, agent.agent_record)

    def test_guardrails_wrap_the_target(self):
        from hackagent.models.guardrail import Guarded, GuardrailSpec

        agent, _ = self._agent(
            after_guardrail={
                "identifier": "guard",
                "endpoint": "http://localhost:11434",
                "agent_type": "OLLAMA",
                "system_prompt": "be strict",
            }
        )

        self.assertIsInstance(agent.target, Guarded)
        self.assertIsNone(agent.target.before)
        self.assertEqual(agent.target.after.system_prompt, "be strict")
        self.assertIsInstance(agent.guardrails["after"], GuardrailSpec)
        self.assertEqual(agent.guardrails["after"].identifier, "guard")

    def test_no_guardrails_leaves_the_target_unwrapped(self):
        from hackagent.models.client import ModelClient

        agent, _ = self._agent()
        self.assertIsInstance(agent.target, ModelClient)
        self.assertEqual(agent.guardrails, {})

    def test_unsupported_agent_type_is_rejected_before_registration(self):
        store = in_memory_store()
        with self.assertRaises(ValueError):
            _target(store=store, endpoint="http://x", agent_type="mcp")
        self.assertEqual(store.list_agents().items, [])


if __name__ == "__main__":
    unittest.main()
