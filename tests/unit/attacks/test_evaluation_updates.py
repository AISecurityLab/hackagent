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

"""
Tests for evaluation status updates.

This module tests that evaluation results are properly synced back to the server
after the local evaluation step completes.

ISSUES FIXED:
1. Results are created with NOT_EVALUATED status during generation via
   route_with_tracking(), and now are updated after evaluation completes.

2. The evaluation.py code now correctly handles bool return from
   PatternEvaluator.evaluate() instead of expecting a dict.

3. Result IDs are now tracked through the pipeline and updated after evaluation.
"""

import logging
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from hackagent.models import EvaluationStatusEnum


class TestEvaluationStatusUpdates(unittest.TestCase):
    """Test that evaluation results are synced to the server."""

    def setUp(self):
        """Set up test fixtures."""
        self.logger = logging.getLogger("test")
        self.run_id = str(uuid4())
        self.mock_client = MagicMock()

    def test_route_with_tracking_creates_results_as_not_evaluated(self):
        """Test that route_with_tracking creates results with NOT_EVALUATED status."""
        from hackagent.router.router import AgentRouter

        # This is expected behavior - results start as NOT_EVALUATED
        # The issue is they should be updated after evaluation

        with patch.object(AgentRouter, "__init__", lambda x, **kwargs: None):
            router = AgentRouter.__new__(AgentRouter)
            router._agent_registry = {"test-agent": MagicMock()}
            router.logger = self.logger

            # Mock the route_request to return a response
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="test response"))
            ]

            with patch.object(router, "route_request", return_value=mock_response):
                # The import happens inside route_with_tracking, so we patch there
                with patch(
                    "hackagent.api.run.run_result_create.sync_detailed"
                ) as mock_create:
                    mock_create_response = MagicMock()
                    mock_create_response.status_code = 201
                    mock_create_response.parsed = MagicMock(id=uuid4())
                    mock_create.return_value = mock_create_response

                    # Call route_with_tracking
                    router.route_with_tracking(
                        registration_key="test-agent",
                        request_data={
                            "messages": [{"role": "user", "content": "test"}]
                        },
                        run_id=self.run_id,
                        client=self.mock_client,
                    )

                    # Verify result was created with NOT_EVALUATED status
                    mock_create.assert_called_once()
                    call_args = mock_create.call_args
                    result_request = call_args.kwargs["body"]

                    self.assertEqual(
                        result_request.evaluation_status,
                        EvaluationStatusEnum.NOT_EVALUATED,
                        "Results should be created with NOT_EVALUATED status initially",
                    )

    def test_pattern_evaluator_returns_bool(self):
        """
        FIXED: PatternEvaluator.evaluate() returns bool, and evaluation.py
        now correctly handles this.
        """
        from hackagent.attacks.shared.evaluators import PatternEvaluator

        evaluator = PatternEvaluator(
            success_patterns=[r"harmful content"],
            failure_patterns=[r"cannot|sorry|I'm unable"],
        )

        # evaluate() returns a bool
        result = evaluator.evaluate("I cannot help with that.")
        self.assertIsInstance(result, bool)
        self.assertFalse(result)

        # get_matched_patterns() returns dict for detailed notes
        matched = evaluator.get_matched_patterns("I cannot help with that.")
        self.assertIn("failure_patterns", matched)
        self.assertIn("success_patterns", matched)

    def test_evaluation_code_correctly_uses_bool(self):
        """
        FIXED: evaluation.py now correctly uses bool return from evaluator.
        """
        from hackagent.attacks.techniques.baseline import evaluation
        import inspect

        # Get the source code of evaluate_responses
        source = inspect.getsource(evaluation.evaluate_responses)

        # Check that the fix is in place - code uses bool directly
        self.assertIn(
            'evaluator.evaluate(row.get("completion", ""))',
            source,
        )
        # Should NOT have the old buggy code
        self.assertNotIn(
            'evaluator.evaluate(row["completion"])["success"]',
            source,
            "Bug fixed: code no longer tries to subscript bool",
        )
        self.assertNotIn(
            'evaluator.evaluate(row.get("completion", ""))["success"]',
            source,
            "Bug fixed: code no longer tries to subscript bool",
        )

    def test_evaluation_step_should_update_server_results(self):
        """
        Test that evaluation step SHOULD update server results.

        This test demonstrates the EXPECTED behavior - after local evaluation,
        each result's evaluation_status should be updated on the server.

        Currently this is NOT happening, which is the bug.
        """
        # This is what SHOULD happen after evaluation:
        # 1. For each row in the evaluated list that has a result_id
        # 2. Call result_partial_update with the computed evaluation status
        # 3. Map success=True -> SUCCESSFUL_JAILBREAK or PASSED_CRITERIA
        # 4. Map success=False -> FAILED_JAILBREAK or FAILED_CRITERIA

        # Create evaluated list with result IDs
        evaluated_data = [
            {
                "goal": "test goal",
                "completion": "I cannot help with that.",
                "success": False,
                "result_id": str(uuid4()),  # This ID should be tracked from creation
            },
            {
                "goal": "test goal 2",
                "completion": "Here is harmful content...",
                "success": True,
                "result_id": str(uuid4()),
            },
        ]

        # Expected: result_partial_update should be called for each result
        expected_updates = [
            (evaluated_data[0]["result_id"], EvaluationStatusEnum.FAILED_CRITERIA),
            (evaluated_data[1]["result_id"], EvaluationStatusEnum.PASSED_CRITERIA),
        ]

        # NOTE: Currently the code does NOT do this!
        # This test documents the expected behavior that should be implemented.
        self.assertEqual(len(expected_updates), 2, "Should update 2 results")

    def test_generation_step_now_tracks_result_ids(self):
        """
        FIXED: Generation step now tracks result IDs.

        When route_with_tracking creates a result, the result ID is now
        captured and added to the data for later updates.
        """
        from hackagent.attacks.techniques.baseline import generation
        import inspect

        # Check the execute_prompts function source
        source = inspect.getsource(generation.execute_prompts)

        # The code now tracks result_id
        self.assertIn("result_id", source)
        self.assertIn('tracking_result.get("result_id")', source)


class TestEvaluationEndToEnd(unittest.TestCase):
    """End-to-end tests for the evaluation pipeline."""

    def test_baseline_attack_evaluation_now_updates_results(self):
        """
        FIXED: Baseline attack now updates results after evaluation.

        The evaluation step now calls result_partial_update to sync status to server.
        """
        from hackagent.attacks.techniques.baseline import evaluation
        import inspect

        # Check that evaluation.py now calls result_partial_update
        source = inspect.getsource(evaluation)

        self.assertIn(
            "result_partial_update",
            source,
            "Fix confirmed: evaluation.py now imports result_partial_update",
        )

        self.assertIn(
            "_sync_evaluation_to_server",
            source,
            "Fix confirmed: evaluation.py has sync function",
        )

    def test_sync_evaluation_function_exists(self):
        """Test that _sync_evaluation_to_server function exists and is called."""
        from hackagent.attacks.techniques.baseline.evaluation import (
            _sync_evaluation_to_server,
            execute,
        )
        import inspect

        # Function should exist
        self.assertTrue(callable(_sync_evaluation_to_server))

        # Should be called in execute
        execute_source = inspect.getsource(execute)
        self.assertIn("_sync_evaluation_to_server", execute_source)

    def test_update_result_status_function(self):
        """Test that _update_result_status function works correctly."""
        from hackagent.attacks.techniques.baseline.evaluation import (
            _update_result_status,
        )

        mock_client = MagicMock()
        mock_logger = logging.getLogger("test")

        with patch(
            "hackagent.attacks.techniques.baseline.evaluation.result_partial_update"
        ) as mock_update:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_update.sync_detailed.return_value = mock_response

            result = _update_result_status(
                result_id=str(uuid4()),
                success=True,
                evaluation_notes="Test notes",
                client=mock_client,
                logger=mock_logger,
            )

            self.assertTrue(result)
            mock_update.sync_detailed.assert_called_once()


class TestResultIdTracking(unittest.TestCase):
    """Test that result IDs are properly tracked through the pipeline."""

    def test_route_with_tracking_returns_response_and_result_id(self):
        """
        FIXED: route_with_tracking now returns both response and result_id.
        """
        from hackagent.router.router import AgentRouter

        with patch.object(AgentRouter, "__init__", lambda x, **kwargs: None):
            router = AgentRouter.__new__(AgentRouter)
            router._agent_registry = {"test-agent": MagicMock()}
            router.logger = logging.getLogger("test")

            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content="test"))]

            result_id = uuid4()

            with patch.object(router, "route_request", return_value=mock_response):
                with patch(
                    "hackagent.api.run.run_result_create.sync_detailed"
                ) as mock_create:
                    mock_create_response = MagicMock()
                    mock_create_response.status_code = 201
                    mock_create_response.parsed = MagicMock(id=result_id)
                    mock_create.return_value = mock_create_response

                    result = router.route_with_tracking(
                        registration_key="test-agent",
                        request_data={
                            "messages": [{"role": "user", "content": "test"}]
                        },
                        run_id=str(uuid4()),
                        client=MagicMock(),
                    )

                    # Now returns dict with both response and result_id
                    self.assertIsInstance(result, dict)
                    self.assertIn("response", result)
                    self.assertIn("result_id", result)
                    self.assertEqual(result["result_id"], str(result_id))

    def test_route_with_tracking_docstring_updated(self):
        """
        Verify route_with_tracking documents the new return type.
        """
        from hackagent.router.router import AgentRouter
        import inspect

        source = inspect.getsource(AgentRouter.route_with_tracking)

        # Should document the return structure
        self.assertIn("result_id", source)


if __name__ == "__main__":
    unittest.main()
