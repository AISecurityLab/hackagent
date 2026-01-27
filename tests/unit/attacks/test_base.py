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

"""Tests for BaseAttack class and its infrastructure."""

import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.techniques.base import BaseAttack
from hackagent.models import StatusEnum, EvaluationStatusEnum


class TestBaseAttackInfrastructure(unittest.TestCase):
    """Test BaseAttack infrastructure methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.mock_agent_router = MagicMock()
        self.test_config = {
            "output_dir": "/tmp/test",
            "run_id": "00000000-0000-0000-0000-000000000001",
            "test_param": "value",
        }

    def test_baseattack_cannot_be_instantiated(self):
        """Test that BaseAttack is abstract and cannot be instantiated directly."""
        with self.assertRaises(TypeError) as context:
            BaseAttack(self.test_config, self.mock_client, self.mock_agent_router)

        self.assertIn("abstract", str(context.exception).lower())

    def test_config_validation_requires_dict(self):
        """Test that config must be a dictionary."""

        class MinimalAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        with self.assertRaises((ValueError, AttributeError)):
            MinimalAttack("not a dict", self.mock_client, self.mock_agent_router)

    def test_config_validation_requires_output_dir(self):
        """Test that output_dir is required in config."""

        class MinimalAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        invalid_config = {"run_id": "test"}

        with self.assertRaises(ValueError) as context:
            MinimalAttack(invalid_config, self.mock_client, self.mock_agent_router)

        self.assertIn("output_dir", str(context.exception).lower())

    @patch("hackagent.attacks.techniques.base.logging")
    def test_setup_logging_creates_console_handler(self, mock_logging_module):
        """Test that logging setup creates a console handler."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        mock_logger = MagicMock()
        mock_logger.handlers = []

        attack = TestAttack(self.test_config, self.mock_client, self.mock_agent_router)
        attack.logger = mock_logger
        attack._setup_logging()

        # Verify logger was configured
        mock_logger.setLevel.assert_called()

    @patch("hackagent.attacks.techniques.base.run_result_create")
    def test_create_parent_result_success(self, mock_result_create):
        """Test successful parent result creation."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        # Setup mock response
        mock_result_id = "result-123"
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.parsed = MagicMock()
        mock_response.parsed.id = mock_result_id
        mock_result_create.sync_detailed.return_value = mock_response

        attack = TestAttack(self.test_config, self.mock_client, self.mock_agent_router)
        result_id = attack._create_parent_result()

        self.assertEqual(result_id, mock_result_id)
        mock_result_create.sync_detailed.assert_called_once()

    @patch("hackagent.attacks.techniques.base.run_result_create")
    def test_create_parent_result_no_run_id(self, mock_result_create):
        """Test that parent result is not created without run_id."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        config_no_run_id = {"output_dir": "/tmp/test"}
        attack = TestAttack(config_no_run_id, self.mock_client, self.mock_agent_router)
        result_id = attack._create_parent_result()

        self.assertIsNone(result_id)
        mock_result_create.sync_detailed.assert_not_called()

    def test_prepare_input_sample_limits_size(self):
        """Test that input sample is limited to 5 items."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        attack = TestAttack(self.test_config, self.mock_client, self.mock_agent_router)

        large_list = [{"item": i} for i in range(10)]
        sample = attack._prepare_input_sample(large_list)

        self.assertEqual(len(sample), 5)
        self.assertEqual(sample[0]["item"], 0)
        self.assertEqual(sample[4]["item"], 4)

    def test_prepare_input_sample_handles_inf(self):
        """Test that infinity values are replaced with None."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        attack = TestAttack(self.test_config, self.mock_client, self.mock_agent_router)

        data_with_inf = [
            {"value": float("inf")},
            {"value": float("-inf")},
            {"value": 42},
        ]
        sample = attack._prepare_input_sample(data_with_inf)

        self.assertIsNone(sample[0]["value"])
        self.assertIsNone(sample[1]["value"])
        self.assertEqual(sample[2]["value"], 42)

    @patch("hackagent.attacks.techniques.base.StepTracker")
    @patch("hackagent.attacks.techniques.base.TrackingContext")
    def test_initialize_tracking_creates_tracker(
        self, mock_context_class, mock_tracker_class
    ):
        """Test that tracking is properly initialized."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        mock_context = MagicMock()
        mock_context_class.return_value = mock_context
        mock_tracker = MagicMock()
        mock_tracker_class.return_value = mock_tracker

        attack = TestAttack(self.test_config, self.mock_client, self.mock_agent_router)
        goals = ["goal1", "goal2"]
        metadata = {"key": "value"}

        tracker = attack._initialize_tracking("test_attack", goals, metadata)

        # Verify context was created with correct parameters
        mock_context_class.assert_called_once()
        mock_context.add_metadata.assert_any_call("attack_type", "test_attack")
        mock_context.add_metadata.assert_any_call("num_goals", 2)
        mock_context.add_metadata.assert_any_call("key", "value")

        # Verify tracker was created and status updated
        mock_tracker_class.assert_called_once_with(mock_context)
        mock_tracker.update_run_status.assert_called_once_with(StatusEnum.RUNNING)

        self.assertEqual(tracker, mock_tracker)


class TestBaseAttackPipelineExecution(unittest.TestCase):
    """Test BaseAttack pipeline execution framework."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.mock_agent_router = MagicMock()
        self.test_config = {
            "output_dir": "/tmp/test",
            "param1": "value1",
            "param2": "value2",
        }

    def test_build_step_args_includes_required_args(self):
        """Test that step arguments are built correctly."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        attack = TestAttack(self.test_config, self.mock_client, self.mock_agent_router)
        attack.logger = MagicMock()

        step_info = {
            "name": "Test Step",
            "required_args": ["logger", "client", "agent_router"],
            "config_keys": ["param1"],
            "input_data_arg_name": "input_data",
        }
        step_config = {"param1": "value1"}
        input_data = ["test", "data"]

        args = attack._build_step_args(step_info, step_config, input_data)

        self.assertIn("config", args)
        self.assertIn("logger", args)
        self.assertIn("client", args)
        self.assertIn("agent_router", args)
        self.assertIn("input_data", args)
        self.assertEqual(args["input_data"], input_data)
        self.assertEqual(args["client"], self.mock_client)

    @patch("hackagent.attacks.techniques.base.logging")
    def test_execute_pipeline_runs_all_steps(self, mock_logging):
        """Test that pipeline executes all steps in sequence."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        attack = TestAttack(self.test_config, self.mock_client, self.mock_agent_router)
        attack.logger = MagicMock()
        attack.tracker = MagicMock()
        attack.tracker.track_step = MagicMock()
        attack.tracker.track_step.return_value.__enter__ = MagicMock()
        attack.tracker.track_step.return_value.__exit__ = MagicMock()

        # Mock step functions
        step1_func = MagicMock(return_value="output1")
        step2_func = MagicMock(return_value="output2")

        pipeline_steps = [
            {
                "name": "Step 1",
                "function": step1_func,
                "step_type_enum": "GENERATION",
                "config_keys": ["param1"],
                "input_data_arg_name": "input_data",
                "required_args": [],
            },
            {
                "name": "Step 2",
                "function": step2_func,
                "step_type_enum": "EVALUATION",
                "config_keys": ["param2"],
                "input_data_arg_name": "input_data",
                "required_args": [],
            },
        ]

        initial_input = ["initial", "data"]
        result = attack._execute_pipeline(pipeline_steps, initial_input)

        # Verify both steps were called
        self.assertEqual(step1_func.call_count, 1)
        self.assertEqual(step2_func.call_count, 1)

        # Verify final output
        self.assertEqual(result, "output2")

    def test_finalize_pipeline_success(self):
        """Test pipeline finalization with successful results."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        attack = TestAttack(self.test_config, self.mock_client, self.mock_agent_router)
        attack.tracker = MagicMock()

        results = ["result1", "result2"]
        attack._finalize_pipeline(results)

        # Verify successful status was set
        attack.tracker.update_result_status.assert_called_once_with(
            EvaluationStatusEnum.PASSED_CRITERIA, "Pipeline completed successfully."
        )
        attack.tracker.update_run_status.assert_called_once_with(StatusEnum.COMPLETED)

    def test_finalize_pipeline_failure(self):
        """Test pipeline finalization with failed results."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        attack = TestAttack(self.test_config, self.mock_client, self.mock_agent_router)
        attack.tracker = MagicMock()

        results = []  # Empty results = failure
        attack._finalize_pipeline(results)

        # Verify failed status was set
        attack.tracker.update_result_status.assert_called_once()
        call_args = attack.tracker.update_result_status.call_args
        self.assertEqual(call_args[0][0], EvaluationStatusEnum.FAILED_CRITERIA)
        self.assertIsNotNone(call_args[0][1])  # Should have error notes

        attack.tracker.update_run_status.assert_called_once_with(StatusEnum.COMPLETED)

    def test_finalize_pipeline_custom_success_check(self):
        """Test pipeline finalization with custom success check."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        attack = TestAttack(self.test_config, self.mock_client, self.mock_agent_router)
        attack.tracker = MagicMock()

        results = {"status": "success", "count": 5}

        def custom_check(output):
            return output.get("count", 0) > 3

        attack._finalize_pipeline(results, custom_check)

        # Verify custom check was used (count > 3 = success)
        attack.tracker.update_result_status.assert_called_once_with(
            EvaluationStatusEnum.PASSED_CRITERIA, "Pipeline completed successfully."
        )


class TestBaseAttackKwargsHandling(unittest.TestCase):
    """Test BaseAttack handling of additional kwargs."""

    def test_kwargs_stored_as_attributes(self):
        """Test that additional kwargs are stored as instance attributes."""

        class TestAttack(BaseAttack):
            def _get_pipeline_steps(self):
                return []

            def run(self, **kwargs):
                pass

        config = {"output_dir": "/tmp/test"}
        client = MagicMock()
        agent_router = MagicMock()
        custom_router = MagicMock()

        attack = TestAttack(
            config,
            client,
            agent_router,
            custom_router=custom_router,
            extra_param="value",
        )

        # Verify kwargs were stored
        self.assertTrue(hasattr(attack, "custom_router"))
        self.assertEqual(attack.custom_router, custom_router)
        self.assertTrue(hasattr(attack, "extra_param"))
        self.assertEqual(attack.extra_param, "value")


if __name__ == "__main__":
    unittest.main()
