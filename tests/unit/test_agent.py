# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for HackAgent class (hackagent/agent.py)."""

import unittest
from unittest.mock import MagicMock, patch

from hackagent.errors import HackAgentError


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
        self.assertIsNotNone(agent.prompts)
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

        self.assertEqual(agent.client._base_url, "https://api.hackagent.dev")

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

        self.assertEqual(agent.client._base_url, "https://custom.api.com")

    @patch("hackagent.agent.AgentRouter")
    @patch("hackagent.agent.utils.resolve_api_token", return_value="test-token")
    @patch("hackagent.agent.utils.resolve_agent_type")
    def test_prompts_are_copy(self, mock_resolve_type, mock_resolve_token, mock_router):
        """Test prompts are a copy of DEFAULT_PROMPTS."""
        from hackagent.agent import HackAgent
        from hackagent.vulnerabilities.prompts import DEFAULT_PROMPTS

        agent = HackAgent(
            endpoint="http://localhost:8000",
            api_key="test-key",
        )

        # Should be equal but not the same object
        self.assertEqual(agent.prompts, DEFAULT_PROMPTS)
        self.assertIsNot(agent.prompts, DEFAULT_PROMPTS)

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
        self.assertIn("baseline", strategies)
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


if __name__ == "__main__":
    unittest.main()
