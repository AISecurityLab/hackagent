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
            HackAgent(
                _settings(api_key="test-key", base_url="https://api.hackagent.dev")
            )
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
        with patch("hackagent.models.connect.connect") as mock_connect:
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
        with patch("hackagent.models.connect.connect") as mock_connect:
            _target(
                endpoint="http://localhost:11434", agent_type="ollama", thinking=False
            )
        self.assertIs(mock_connect.call_args.args[0].thinking, False)

    def test_thinking_is_ignored_for_non_ollama(self):
        with patch("hackagent.models.connect.connect") as mock_connect:
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

    @patch("hackagent.orchestrator.campaign.legacy.run_as_campaign")
    def test_hack_delegates_to_runner(self, mock_run):
        """Test that hack delegates to the orchestrator runner."""
        mock_run.return_value = [{"result": "test"}]

        result = self.agent.hack(
            attack_config={"attack_type": "autodan_turbo", "goals": ["test"]}
        )

        mock_run.assert_called_once()
        self.assertEqual(result, [{"result": "test"}])
        self.assertIs(mock_run.call_args.args[0], self.agent)

    @patch("hackagent.orchestrator.campaign.legacy.run_as_campaign")
    def test_hack_passes_run_config_override(self, mock_run):
        """Test that run_config_override is passed to the runner."""
        mock_run.return_value = []
        run_config = {"custom": "override"}
        self.agent.hack(
            attack_config={"attack_type": "autodan_turbo"},
            run_config_override=run_config,
        )
        self.assertEqual(mock_run.call_args.kwargs["run_config_override"], run_config)

    @patch("hackagent.orchestrator.campaign.legacy.run_as_campaign")
    def test_hack_wraps_value_error(self, mock_run):
        """Test that ValueError is wrapped in HackAgentError."""
        mock_run.side_effect = ValueError("Bad config")
        with self.assertRaises(HackAgentError) as ctx:
            self.agent.hack(attack_config={"attack_type": "autodan_turbo"})
        self.assertIn("Configuration error", str(ctx.exception))

    @patch("hackagent.orchestrator.campaign.legacy.run_as_campaign")
    def test_hack_wraps_runtime_error(self, mock_run):
        """Test that RuntimeError is wrapped in HackAgentError."""
        mock_run.side_effect = RuntimeError("Something broke")
        with self.assertRaises(HackAgentError) as ctx:
            self.agent.hack(attack_config={"attack_type": "autodan_turbo"})
        self.assertIn("unexpected runtime error", str(ctx.exception).lower())

    @patch("hackagent.orchestrator.campaign.legacy.run_as_campaign")
    def test_hack_wraps_backend_runtime_error(self, mock_run):
        """Test backend-specific RuntimeErrors are wrapped."""
        mock_run.side_effect = RuntimeError("Failed to create backend agent")
        with self.assertRaises(HackAgentError) as ctx:
            self.agent.hack(attack_config={"attack_type": "autodan_turbo"})
        self.assertIn("Backend agent operation failed", str(ctx.exception))

    @patch("hackagent.orchestrator.campaign.legacy.run_as_campaign")
    def test_hack_wraps_generic_exception(self, mock_run):
        """Test that generic exceptions are wrapped in HackAgentError."""
        mock_run.side_effect = Exception("Unknown error")
        with self.assertRaises(HackAgentError):
            self.agent.hack(attack_config={"attack_type": "autodan_turbo"})

    @patch("hackagent.orchestrator.campaign.legacy.run_as_campaign")
    def test_hack_reraises_hackagent_error(self, mock_run):
        """Test that HackAgentError is re-raised as-is."""
        mock_run.side_effect = HackAgentError("Direct error")
        with self.assertRaises(HackAgentError) as ctx:
            self.agent.hack(attack_config={"attack_type": "autodan_turbo"})
        self.assertEqual(str(ctx.exception), "Direct error")


class TestHackAgentHackChain(unittest.TestCase):
    """``hack_chain`` validates its steps and hands one escalating campaign
    to the bridge. The escalation itself is covered against a scripted
    campaign in ``tests/unit/campaign/test_chain.py``."""

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
        """attacks=None resolves to the Jailbreak campaign's primary attacks,
        in campaign order: h4rm3l -> TAP -> PAIR, run as one campaign."""
        with patch(
            "hackagent.orchestrator.campaign.legacy.run_chain_as_campaign"
        ) as mock_run:
            mock_run.return_value = []

            self.agent.hack_chain(goals=["goal-a"])

            steps = [step["attack_type"] for step in mock_run.call_args.args[1]]
            self.assertEqual(steps, ["h4rm3l", "tap", "pair"])
            self.assertTrue(mock_run.call_args.kwargs["escalate"])

    def test_hack_chain_explicit_attacks_override_default_campaign(self):
        """Passing an explicit attacks list bypasses the campaign default."""
        with patch(
            "hackagent.orchestrator.campaign.legacy.run_chain_as_campaign"
        ) as mock_run:
            mock_run.return_value = []

            self.agent.hack_chain(
                attacks=[{"attack_type": "baseline"}], goals=["goal-a"]
            )

            steps = [step["attack_type"] for step in mock_run.call_args.args[1]]
            self.assertEqual(steps, ["baseline"])

    def test_hack_chain_forwards_escalation_and_goals_to_the_campaign(self):
        """The escalation toggle and goal pool reach the bridge unchanged."""
        with patch(
            "hackagent.orchestrator.campaign.legacy.run_chain_as_campaign"
        ) as mock_run:
            mock_run.return_value = []

            self.agent.hack_chain(
                attacks=[{"attack_type": "baseline"}],
                goals=["goal-a", "goal-b"],
                escalate_only_mitigated=False,
            )

            self.assertFalse(mock_run.call_args.kwargs["escalate"])
            self.assertEqual(mock_run.call_args.kwargs["goals"], ["goal-a", "goal-b"])

    def test_hack_chain_fail_on_run_error_stops_the_chain(self):
        """``fail_on_run_error`` maps to the campaign's stop-on-error."""
        with patch(
            "hackagent.orchestrator.campaign.legacy.run_chain_as_campaign"
        ) as mock_run:
            mock_run.return_value = []

            self.agent.hack_chain(
                attacks=[{"attack_type": "baseline"}],
                goals=["goal-a"],
                fail_on_run_error=True,
            )

            override = mock_run.call_args.kwargs["run_config_override"]
            self.assertEqual(override["on_error"], "stop")


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

    def test_guardrails_wrap_the_target(self):
        from hackagent.models.guardrail import GuardedModel, GuardrailSpec

        agent, _ = self._agent(
            after_guardrail={
                "identifier": "guard",
                "endpoint": "http://localhost:11434",
                "agent_type": "OLLAMA",
                "system_prompt": "be strict",
            }
        )

        self.assertIsInstance(agent.target, GuardedModel)
        self.assertIsNone(agent.target.before)
        self.assertEqual(agent.target.after.system_prompt, "be strict")
        self.assertIsInstance(agent.guardrails["after"], GuardrailSpec)
        self.assertEqual(agent.guardrails["after"].identifier, "guard")

    def test_no_guardrails_leaves_the_target_unwrapped(self):
        from hackagent.models.guardrail import GuardedModel
        from hackagent.models.model import Model

        agent, _ = self._agent()
        self.assertIsInstance(agent.target, Model)
        self.assertNotIsInstance(agent.target, GuardedModel)
        self.assertEqual(agent.guardrails, {})

    def test_unsupported_agent_type_is_rejected_before_registration(self):
        store = in_memory_store()
        with self.assertRaises(ValueError):
            _target(store=store, endpoint="http://x", agent_type="mcp")
        self.assertEqual(store.list_agents().items, [])


if __name__ == "__main__":
    unittest.main()
