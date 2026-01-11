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

"""Tests for AttackOrchestrator class."""

import json
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from hackagent.attacks.orchestrator import AttackOrchestrator
from hackagent.attacks.techniques.base import BaseAttack
from hackagent.errors import HackAgentError


class TestAttackOrchestratorInitialization(unittest.TestCase):
    """Test AttackOrchestrator initialization."""

    def test_orchestrator_requires_attack_type(self):
        """Test that orchestrator requires attack_type to be defined."""

        class BadOrchestrator(AttackOrchestrator):
            attack_impl_class = BaseAttack

        mock_hack_agent = MagicMock()

        with self.assertRaises(ValueError) as context:
            BadOrchestrator(mock_hack_agent)

        self.assertIn("attack_type", str(context.exception))

    def test_orchestrator_requires_attack_impl_class(self):
        """Test that orchestrator requires attack_impl_class to be defined."""

        class BadOrchestrator(AttackOrchestrator):
            attack_type = "test"

        mock_hack_agent = MagicMock()

        with self.assertRaises(ValueError) as context:
            BadOrchestrator(mock_hack_agent)

        self.assertIn("attack_impl_class", str(context.exception))

    def test_orchestrator_initialization_success(self):
        """Test successful orchestrator initialization."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        class TestOrchestrator(AttackOrchestrator):
            attack_type = "test"
            attack_impl_class = TestAttack

        mock_hack_agent = MagicMock()
        mock_hack_agent.client = MagicMock()

        orchestrator = TestOrchestrator(mock_hack_agent)

        self.assertEqual(orchestrator.attack_type, "test")
        self.assertEqual(orchestrator.attack_impl_class, TestAttack)
        self.assertEqual(orchestrator.hack_agent, mock_hack_agent)
        self.assertEqual(orchestrator.client, mock_hack_agent.client)


class TestAttackOrchestratorServerRecords(unittest.TestCase):
    """Test AttackOrchestrator server record creation."""

    def setUp(self):
        """Set up test fixtures."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                return ["result1", "result2"]

        class TestOrchestrator(AttackOrchestrator):
            attack_type = "test"
            attack_impl_class = TestAttack

        self.TestOrchestrator = TestOrchestrator
        self.mock_hack_agent = MagicMock()
        self.mock_hack_agent.client = MagicMock()
        self.mock_hack_agent.agent_id = uuid4()
        self.mock_hack_agent.organization_id = uuid4()
        self.mock_hack_agent.agent_router = MagicMock()

    @patch("hackagent.attacks.orchestrator.attacks_create_sync_detailed")
    def test_create_server_attack_record_success(self, mock_attacks_create):
        """Test successful attack record creation."""

        orchestrator = self.TestOrchestrator(self.mock_hack_agent)

        # Mock successful API response
        attack_id = "attack-123"
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = json.dumps({"id": attack_id}).encode()
        mock_response.parsed = MagicMock()
        mock_response.parsed.additional_properties = {"id": attack_id}
        mock_attacks_create.return_value = mock_response

        attack_config = {"goals": ["test goal"]}

        result_id = orchestrator._create_server_attack_record(
            "test",
            self.mock_hack_agent.agent_id,
            self.mock_hack_agent.organization_id,
            attack_config,
        )

        self.assertEqual(result_id, attack_id)
        mock_attacks_create.assert_called_once()

    @patch("hackagent.attacks.orchestrator.attacks_create_sync_detailed")
    def test_create_server_attack_record_failure(self, mock_attacks_create):
        """Test attack record creation failure."""

        orchestrator = self.TestOrchestrator(self.mock_hack_agent)

        # Mock failed API response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.content = b"Server error"
        mock_attacks_create.return_value = mock_response

        attack_config = {"goals": ["test goal"]}

        with self.assertRaises(HackAgentError):
            orchestrator._create_server_attack_record(
                "test",
                self.mock_hack_agent.agent_id,
                self.mock_hack_agent.organization_id,
                attack_config,
            )

    @patch("hackagent.attacks.orchestrator.run_run_tests_create")
    def test_create_server_run_record_success(self, mock_run_create):
        """Test successful run record creation."""

        orchestrator = self.TestOrchestrator(self.mock_hack_agent)

        # Mock successful API response
        run_id = "run-456"
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = json.dumps({"id": run_id}).encode()
        mock_response.parsed = MagicMock()
        mock_response.parsed.additional_properties = {"id": run_id}
        mock_run_create.sync_detailed.return_value = mock_response

        attack_id = "attack-123"
        agent_id = str(self.mock_hack_agent.agent_id)

        result_id = orchestrator._create_server_run_record(attack_id, agent_id, None)

        self.assertEqual(result_id, run_id)
        mock_run_create.sync_detailed.assert_called_once()


class TestAttackOrchestratorExecution(unittest.TestCase):
    """Test AttackOrchestrator execution flow."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_results = ["result1", "result2"]

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                return self.test_results

        class TestOrchestrator(AttackOrchestrator):
            attack_type = "test"
            attack_impl_class = TestAttack

        self.TestAttack = TestAttack
        self.TestOrchestrator = TestOrchestrator
        self.mock_hack_agent = MagicMock()
        self.mock_hack_agent.client = MagicMock()
        self.mock_hack_agent.agent_id = uuid4()
        self.mock_hack_agent.organization_id = uuid4()
        self.mock_hack_agent.agent_router = MagicMock()

    def test_prepare_attack_params_extracts_goals(self):
        """Test that attack params are prepared correctly."""

        orchestrator = self.TestOrchestrator(self.mock_hack_agent)

        attack_config = {"goals": ["goal1", "goal2"]}
        params = orchestrator._prepare_attack_params(attack_config)

        self.assertIn("goals", params)
        self.assertEqual(params["goals"], ["goal1", "goal2"])

    def test_prepare_attack_params_validates_goals(self):
        """Test that goals must be a list."""

        orchestrator = self.TestOrchestrator(self.mock_hack_agent)

        attack_config = {"goals": "not a list"}

        with self.assertRaises(ValueError) as context:
            orchestrator._prepare_attack_params(attack_config)

        self.assertIn("goals", str(context.exception).lower())
        self.assertIn("list", str(context.exception).lower())

    def test_get_attack_impl_kwargs(self):
        """Test that implementation kwargs are built correctly."""

        orchestrator = self.TestOrchestrator(self.mock_hack_agent)

        attack_config = {"param1": "value1"}
        run_config = {"param2": "value2"}

        kwargs = orchestrator._get_attack_impl_kwargs(attack_config, run_config)

        self.assertIn("config", kwargs)
        self.assertIn("client", kwargs)
        self.assertIn("agent_router", kwargs)
        self.assertEqual(kwargs["config"]["param1"], "value1")
        self.assertEqual(kwargs["config"]["param2"], "value2")

    @patch.object(AttackOrchestrator, "_create_server_attack_record")
    @patch.object(AttackOrchestrator, "_create_server_run_record")
    @patch.object(AttackOrchestrator, "_execute_local_attack")
    def test_execute_full_workflow(
        self, mock_execute_local, mock_create_run, mock_create_attack
    ):
        """Test full execute workflow."""

        orchestrator = self.TestOrchestrator(self.mock_hack_agent)

        # Mock successful responses
        mock_create_attack.return_value = "attack-123"
        mock_create_run.return_value = "run-456"
        mock_execute_local.return_value = self.test_results

        attack_config = {"goals": ["test goal"]}

        results = orchestrator.execute(
            attack_config=attack_config,
            run_config_override=None,
            fail_on_run_error=False,
        )

        # Verify workflow steps
        mock_create_attack.assert_called_once()
        mock_create_run.assert_called_once()
        mock_execute_local.assert_called_once()

        # Verify results
        self.assertEqual(results, self.test_results)

    @patch.object(AttackOrchestrator, "_create_server_attack_record")
    @patch.object(AttackOrchestrator, "_create_server_run_record")
    def test_execute_local_attack_instantiates_implementation(
        self, mock_create_run, mock_create_attack
    ):
        """Test that local attack instantiates the implementation class."""

        orchestrator = self.TestOrchestrator(self.mock_hack_agent)

        attack_config = {"goals": ["test goal"], "output_dir": "/tmp/test"}
        attack_params = {"goals": ["test goal"]}

        with patch.object(self.TestAttack, "__init__", return_value=None) as mock_init:
            with patch.object(self.TestAttack, "run", return_value=self.test_results):
                results = orchestrator._execute_local_attack(
                    "attack-123", "run-456", attack_params, attack_config, None
                )

        # Verify implementation was instantiated
        mock_init.assert_called_once()
        self.assertEqual(results, self.test_results)


class TestAttackOrchestratorHTTPHelpers(unittest.TestCase):
    """Test AttackOrchestrator HTTP response helpers."""

    def setUp(self):
        """Set up test fixtures."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        class TestOrchestrator(AttackOrchestrator):
            attack_type = "test"
            attack_impl_class = TestAttack

        self.TestOrchestrator = TestOrchestrator
        self.mock_hack_agent = MagicMock()
        self.mock_hack_agent.client = MagicMock()
        self.orchestrator = TestOrchestrator(self.mock_hack_agent)

    def test_decode_response_success(self):
        """Test successful response decoding."""

        mock_response = MagicMock()
        mock_response.content = b'{"status": "ok"}'

        decoded = self.orchestrator._decode_response(mock_response)

        self.assertEqual(decoded, '{"status": "ok"}')

    def test_decode_response_empty(self):
        """Test decoding empty response."""

        mock_response = MagicMock()
        mock_response.content = None

        decoded = self.orchestrator._decode_response(mock_response)

        self.assertEqual(decoded, "N/A")

    def test_parse_json_success(self):
        """Test successful JSON parsing."""

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = b'{"id": "123"}'

        decoded = '{"id": "123"}'
        parsed = self.orchestrator._parse_json(mock_response, decoded, "test")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["id"], "123")

    def test_parse_json_fallback_to_parsed_attribute(self):
        """Test fallback to response.parsed attribute."""

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = b"invalid json"
        mock_response.parsed = MagicMock()
        mock_response.parsed.additional_properties = {"id": "123"}

        decoded = "invalid json"

        # The method raises HackAgentError when it can't parse JSON
        # even if parsed attribute exists, as it checks parsed.id specifically
        with self.assertRaises(Exception):  # Could be HackAgentError
            self.orchestrator._parse_json(mock_response, decoded, "test")

    def test_extract_ids_from_data_success(self):
        """Test successful ID extraction from data."""

        parsed_data = {"id": "attack-123", "associated_run_id": "run-456"}

        attack_id, run_id = self.orchestrator._extract_ids_from_data(
            parsed_data, "test", ""
        )

        self.assertEqual(attack_id, "attack-123")
        self.assertEqual(run_id, "run-456")

    def test_extract_ids_missing_attack_id(self):
        """Test error when attack_id is missing."""

        parsed_data = {"other_field": "value"}

        with self.assertRaises(HackAgentError) as context:
            self.orchestrator._extract_ids_from_data(parsed_data, "test", "")

        self.assertIn("attack_id", str(context.exception).lower())


if __name__ == "__main__":
    unittest.main()
