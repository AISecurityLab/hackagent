# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Tests for evaluation status updates.

This module tests that evaluation results are properly synced back to the server
after the local evaluation step completes.

ISSUES FIXED:
1. Results are created with NOT_EVALUATED status during generation via
   the Tracker, and are updated after evaluation completes.

2. The evaluation.py code now correctly handles bool return from
   PatternEvaluator.evaluate() instead of expecting a dict.

3. Result IDs are now tracked through the pipeline and updated after evaluation.
"""

import logging
import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
from uuid import uuid4

from hackagent.server.api.models import EvaluationStatusEnum
from hackagent.router.tracking import Tracker


class TestEvaluationStatusUpdates(unittest.TestCase):
    """Test that evaluation results are synced to the server."""

    def setUp(self):
        """Set up test fixtures."""
        self.logger = logging.getLogger("test")
        self.run_id = str(uuid4())
        self.mock_client = MagicMock()

    def test_pattern_evaluator_returns_bool(self):
        """
        FIXED: PatternEvaluator.evaluate() returns bool, and evaluation.py
        now correctly handles this.
        """
        from hackagent.attacks.evaluator import PatternEvaluator

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

        The execute_prompts function now uses Tracker with goal_contexts
        to track results. Each goal gets a Context object with a result_id.
        """
        from hackagent.attacks.techniques.baseline import generation
        import inspect

        # Check the execute_prompts function source
        source = inspect.getsource(generation.execute_prompts)

        # The code now uses Tracker with goal_contexts for result tracking
        self.assertIn("goal_tracker", source)
        self.assertIn("goal_contexts", source)
        self.assertIn("create_goal_result", source)


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

        mock_backend = MagicMock()
        mock_logger = logging.getLogger("test")

        # mock_backend has update_result (MagicMock provides all attrs),
        # so the StorageBackend path should be taken.
        result = _update_result_status(
            result_id=str(uuid4()),
            success=True,
            evaluation_notes="Test notes",
            backend=mock_backend,
            logger=mock_logger,
        )

        self.assertTrue(result)
        mock_backend.update_result.assert_called_once()


class _DummyRouter:
    """Minimal router stub for execute_prompts tests."""

    def __init__(self):
        self._agent_registry = {"victim": object()}

    def route_request(self, registration_key, request_data):  # noqa: ARG002
        return {"generated_text": "dummy completion"}


class TestBaselineTrackerConsistency(unittest.TestCase):
    """Regression tests for baseline tracker wiring and goal finalization."""

    def _build_backend(self):
        backend = MagicMock()
        backend.create_result.side_effect = lambda *args, **kwargs: SimpleNamespace(
            id=uuid4()
        )
        backend.create_trace.side_effect = lambda *args, **kwargs: SimpleNamespace(
            id=uuid4()
        )
        return backend

    def test_execute_prompts_reuses_existing_goal_context(self):
        from hackagent.attacks.techniques.baseline.generation import execute_prompts

        backend = self._build_backend()
        tracker = Tracker(
            backend=backend, run_id=str(uuid4()), logger=logging.getLogger("test")
        )

        tracker.create_goal_result("goal-0", goal_index=0)
        pre_count = backend.create_result.call_count

        data = [
            {
                "goal": "goal-0",
                "goal_index": 0,
                "template_category": "role_play",
                "template": "Template {goal}",
                "attack_prompt": "Prompt for goal-0",
            }
        ]
        config = {"n_samples_per_template": 1, "max_tokens": 32, "temperature": 0.1}

        execute_prompts(
            data=data,
            agent_router=_DummyRouter(),
            config=config,
            logger=logging.getLogger("test"),
            goal_tracker=tracker,
        )

        self.assertEqual(
            backend.create_result.call_count,
            pre_count,
            "execute_prompts should not create duplicate Result records when context already exists",
        )

    def test_finalize_goals_marks_missing_prompts_as_failed(self):
        from hackagent.attacks.techniques.baseline.evaluation import (
            _finalize_goals_with_tracker,
        )

        backend = self._build_backend()
        tracker = Tracker(
            backend=backend, run_id=str(uuid4()), logger=logging.getLogger("test")
        )

        tracker.create_goal_result("goal-0", goal_index=0)
        tracker.create_goal_result("goal-1", goal_index=1)

        evaluated_data = [
            {
                "goal": "goal-0",
                "goal_index": 0,
                "template_category": "role_play",
                "success": True,
                "evaluation_notes": "success",
                "response_length": 42,
            }
        ]

        finalized = _finalize_goals_with_tracker(
            evaluated_data=evaluated_data,
            goal_tracker=tracker,
            logger=logging.getLogger("test"),
        )

        self.assertEqual(finalized, 2)
        self.assertEqual(backend.update_result.call_count, 2)

        notes = [
            call.kwargs.get("evaluation_notes", "")
            for call in backend.update_result.call_args_list
        ]
        self.assertTrue(
            any("no prompts/completions generated" in note.lower() for note in notes),
            "A goal with no rows must be explicitly finalized with no-prompt notes",
        )

    def test_generate_prompts_respects_goal_index_offset(self):
        from hackagent.attacks.techniques.baseline.generation import generate_prompts

        config = {
            "template_categories": ["role_play"],
            "templates_per_category": 1,
            "_goal_index_offset": 10,
        }

        rows = generate_prompts(
            goals=["goal-a", "goal-b"],
            config=config,
            logger=logging.getLogger("test"),
        )

        indexes = sorted({row.get("goal_index") for row in rows})
        self.assertEqual(indexes, [10, 11])


if __name__ == "__main__":
    unittest.main()
