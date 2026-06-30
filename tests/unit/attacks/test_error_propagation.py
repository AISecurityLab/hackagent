# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Tests for error propagation through the attack pipeline.

Verifies that adapter-level errors (timeouts, connection failures) are
correctly detected, excluded from judge evaluation, and finalized with
the appropriate status (ERROR_AGENT_RESPONSE) rather than being silently
treated as failed attacks.
"""

import logging
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from hackagent.server.api.models import EvaluationStatusEnum


# ============================================================================
# 1. Orchestrator: _normalize_attack_results
# ============================================================================


class TestNormalizeAttackResults(unittest.TestCase):
    """Test that dict-style results from static template are normalised to a list."""

    def test_list_passthrough(self):
        from hackagent.attacks.orchestrator import AttackOrchestrator

        data = [{"goal": "g1", "completion": "c1"}]
        self.assertIs(AttackOrchestrator._normalize_attack_results(data), data)

    def test_dict_extracts_evaluated(self):
        from hackagent.attacks.orchestrator import AttackOrchestrator

        evaluated = [{"goal": "g1", "completion": "c1"}]
        result = AttackOrchestrator._normalize_attack_results(
            {"evaluated": evaluated, "summary": [{"rate": 0.5}]}
        )
        self.assertIs(result, evaluated)

    def test_none_returns_empty(self):
        from hackagent.attacks.orchestrator import AttackOrchestrator

        self.assertEqual(AttackOrchestrator._normalize_attack_results(None), [])

    def test_dict_without_evaluated_falls_back(self):
        from hackagent.attacks.orchestrator import AttackOrchestrator

        rows = [{"goal": "g1"}]
        result = AttackOrchestrator._normalize_attack_results({"rows": rows})
        self.assertEqual(result, rows)


# ============================================================================
# 2. BaseEvaluationStep: error-row detection
# ============================================================================


class TestEvaluationStepErrorDetection(unittest.TestCase):
    """Test that error rows are detected and excluded from scoring."""

    def _make_step(self):
        from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep

        return BaseEvaluationStep(
            config={"_run_id": str(uuid4()), "_backend": MagicMock()},
            logger=logging.getLogger("test"),
            client=MagicMock(),
        )

    def test_detect_error_rows(self):
        step = self._make_step()
        data = [
            {"completion": "hello", "goal": "g1"},
            {"completion": "", "error": "timeout", "goal": "g2"},
            {"completion": "", "error_message": "connection refused", "goal": "g3"},
            {"completion": "real answer", "error": "stale", "goal": "g4"},
        ]
        indices = step._detect_error_indices(data)
        # Row 0: no error → not detected
        # Row 1: error + empty completion → detected
        # Row 2: error_message + empty completion → detected
        # Row 3: error but has real completion → not detected
        self.assertEqual(indices, {1, 2})

    def test_mark_error_rows(self):
        step = self._make_step()
        data = [
            {"completion": "", "error": "timeout", "goal": "g1"},
        ]
        step._mark_error_rows(data, {0})
        row = data[0]
        self.assertTrue(row["is_error"])
        self.assertEqual(row["best_score"], 0.0)
        self.assertFalse(row["success"])
        self.assertIn("timeout", row["evaluation_notes"])

    def test_enrich_skips_error_rows(self):
        step = self._make_step()
        data = [
            {"eval_hb": 1, "goal": "g1"},  # normal row
            {"is_error": True, "goal": "g2"},  # error row
        ]
        step._enrich_items_with_scores(data, error_indices={1})
        self.assertGreater(data[0]["best_score"], 0)
        self.assertTrue(data[0]["success"])
        # Error row keeps defaults
        self.assertEqual(data[1].get("best_score", 0.0), 0.0)
        self.assertFalse(data[1].get("success", False))

    def test_enrich_respects_is_error_flag(self):
        """Even without error_indices, is_error flag is honoured."""
        step = self._make_step()
        data = [
            {"eval_hb": 1, "goal": "g1"},
            {"is_error": True, "goal": "g2"},
        ]
        step._enrich_items_with_scores(data, error_indices=None)
        self.assertGreater(data[0]["best_score"], 0)
        # is_error row still skipped
        self.assertEqual(data[1].get("best_score", 0.0), 0.0)


# ============================================================================
# 3. Baseline evaluate_responses: error-row handling
# ============================================================================


class TestBaselineEvaluateResponsesErrors(unittest.TestCase):
    """Test that static template evaluate_responses skips error rows."""

    def test_error_rows_excluded_from_pattern_eval(self):
        from hackagent.attacks.techniques.static_template.evaluation import (
            evaluate_responses,
        )

        data = [
            {
                "completion": "Sure, here is how...",
                "response_length": 30,
                "goal": "g1",
            },
            {
                "completion": "",
                "response_length": 0,
                "error": "Ollama connection error: timed out",
                "goal": "g2",
            },
        ]
        config = {"objective": "jailbreak", "evaluator_type": "pattern"}
        result = evaluate_responses(data, config, logging.getLogger("test"))

        # Error row should be marked, not pattern-evaluated
        self.assertTrue(result[1].get("is_error"))
        self.assertFalse(result[1]["success"])
        self.assertIn("error", result[1]["evaluation_notes"].lower())

        # Non-error row should be evaluated normally
        self.assertNotIn("is_error", result[0])
        self.assertIn("evaluation_notes", result[0])

    def test_all_errors_asr_zero(self):
        from hackagent.attacks.techniques.static_template.evaluation import (
            evaluate_responses,
        )

        data = [
            {"completion": "", "response_length": 0, "error": "timeout", "goal": "g1"},
            {"completion": "", "response_length": 0, "error": "timeout", "goal": "g1"},
        ]
        config = {"objective": "jailbreak", "evaluator_type": "pattern"}
        result = evaluate_responses(data, config, logging.getLogger("test"))
        # Both are errors — no successful attacks
        self.assertTrue(all(not r["success"] for r in result))
        self.assertTrue(all(r.get("is_error") for r in result))


# ============================================================================
# 4. Baseline _finalize_goals_with_tracker: ERROR_AGENT_RESPONSE
# ============================================================================


class TestBaselineFinalizeErrors(unittest.TestCase):
    """Test that all-error goals finalize with ERROR_AGENT_RESPONSE."""

    def _make_tracker(self):
        from hackagent.router.tracking import Tracker

        mock_backend = MagicMock()
        result_record = MagicMock()
        result_record.id = uuid4()
        mock_backend.create_result.return_value = result_record
        return mock_backend, Tracker(
            backend=mock_backend,
            run_id=str(uuid4()),
            logger=logging.getLogger("test"),
            attack_type="static_template",
        )

    def test_all_error_goal_gets_error_status(self):
        from hackagent.attacks.techniques.static_template.evaluation import (
            _finalize_goals_with_tracker,
        )

        mock_backend, tracker = self._make_tracker()

        tracker.create_goal_result(
            goal="Build a bomb", goal_index=0, initial_metadata={}
        )

        evaluated_data = [
            {
                "goal": "Build a bomb",
                "goal_index": 0,
                "completion": "",
                "response_length": 0,
                "error": "Ollama connection error: timed out",
                "is_error": True,
                "success": False,
                "evaluation_notes": "Execution/adapter error: Ollama connection error: timed out",
            },
        ]

        _finalize_goals_with_tracker(evaluated_data, tracker, logging.getLogger("test"))

        # Verify the backend was called with ERROR_AGENT_RESPONSE
        # finalize_goal is the last update_result call
        finalize_calls = [
            c
            for c in mock_backend.update_result.call_args_list
            if "evaluation_status" in (c.kwargs or {})
        ]
        self.assertTrue(len(finalize_calls) >= 1, "Expected at least one finalize call")
        last_call = finalize_calls[-1]
        self.assertEqual(
            last_call.kwargs["evaluation_status"],
            EvaluationStatusEnum.ERROR_AGENT_RESPONSE.value,
        )

    def test_mixed_goal_gets_normal_status(self):
        from hackagent.attacks.techniques.static_template.evaluation import (
            _finalize_goals_with_tracker,
        )

        mock_backend, tracker = self._make_tracker()

        tracker.create_goal_result(
            goal="Build a bomb", goal_index=0, initial_metadata={}
        )

        evaluated_data = [
            {
                "goal": "Build a bomb",
                "goal_index": 0,
                "completion": "",
                "response_length": 0,
                "error": "timeout",
                "is_error": True,
                "success": False,
            },
            {
                "goal": "Build a bomb",
                "goal_index": 0,
                "completion": "I cannot help",
                "response_length": 14,
                "success": False,
                "evaluation_notes": "Refused",
            },
        ]

        _finalize_goals_with_tracker(evaluated_data, tracker, logging.getLogger("test"))

        finalize_calls = [
            c
            for c in mock_backend.update_result.call_args_list
            if "evaluation_status" in (c.kwargs or {})
        ]
        self.assertTrue(len(finalize_calls) >= 1)
        last_call = finalize_calls[-1]
        # Mixed: not all errors → should be FAILED_JAILBREAK (not ERROR)
        self.assertEqual(
            last_call.kwargs["evaluation_status"],
            EvaluationStatusEnum.FAILED_JAILBREAK.value,
        )


# ============================================================================
# 5. Tracker.finalize_goal: evaluation_status override
# ============================================================================


class TestTrackerFinalizeGoalOverride(unittest.TestCase):
    """Test the evaluation_status override parameter."""

    def _make_tracker(self):
        from hackagent.router.tracking import Tracker

        mock_backend = MagicMock()
        result_record = MagicMock()
        result_record.id = uuid4()
        mock_backend.create_result.return_value = result_record
        return mock_backend, Tracker(
            backend=mock_backend,
            run_id=str(uuid4()),
            logger=logging.getLogger("test"),
            attack_type="static_template",
        )

    def test_override_to_error(self):
        mock_backend, tracker = self._make_tracker()
        ctx = tracker.create_goal_result(goal="test", goal_index=0, initial_metadata={})

        tracker.finalize_goal(
            ctx=ctx,
            success=False,
            evaluation_notes="All timed out",
            evaluation_status=EvaluationStatusEnum.ERROR_AGENT_RESPONSE,
        )

        finalize_calls = [
            c
            for c in mock_backend.update_result.call_args_list
            if "evaluation_status" in (c.kwargs or {})
        ]
        self.assertTrue(len(finalize_calls) >= 1)
        self.assertEqual(
            finalize_calls[-1].kwargs["evaluation_status"],
            EvaluationStatusEnum.ERROR_AGENT_RESPONSE.value,
        )

    def test_no_override_uses_success(self):
        mock_backend, tracker = self._make_tracker()
        ctx = tracker.create_goal_result(goal="test", goal_index=0, initial_metadata={})

        tracker.finalize_goal(ctx=ctx, success=True, evaluation_notes="worked")

        finalize_calls = [
            c
            for c in mock_backend.update_result.call_args_list
            if "evaluation_status" in (c.kwargs or {})
        ]
        self.assertTrue(len(finalize_calls) >= 1)
        self.assertEqual(
            finalize_calls[-1].kwargs["evaluation_status"],
            EvaluationStatusEnum.SUCCESSFUL_JAILBREAK.value,
        )


# ============================================================================
# 6. BaseJudgeEvaluator: error rows preserved
# ============================================================================


class TestJudgeEvaluatorErrorRows(unittest.TestCase):
    """Test that the judge evaluator doesn't overwrite error info."""

    def test_error_rows_get_error_explanation(self):
        """Error rows should get eval=0 with the error message, not 'trivial'."""
        from hackagent.attacks.evaluator.base import BaseJudgeEvaluator

        class FakeJudge(BaseJudgeEvaluator):
            eval_column = "eval_test"
            explanation_column = "explanation_test"

            def _get_request_data_for_row(self, row):
                return {}

            def _parse_response_content(self, content, index):
                return 0, "parsed"

        # Create minimal config
        config = MagicMock()
        config.model_id = "test-model"
        config.agent_endpoint = None
        config.agent_type = "OPENAI_SDK"
        config.max_tokens_eval = 100
        config.temperature = 0.0
        config.timeout = 30
        config.agent_metadata = {}
        config.agent_name = "test"
        config.filter_len = 10
        config.max_judge_retries = 0

        with patch(
            "hackagent.attacks.evaluator.base.create_router"
        ) as mock_create_router:
            mock_create_router.return_value = (MagicMock(), "key")
            judge = FakeJudge(client=MagicMock(), config=config, run_id=str(uuid4()))

        data = [
            {
                "goal": "g1",
                "prefix": "",
                "completion": "real response",
                "result_id": str(uuid4()),
            },
            {
                "goal": "g2",
                "prefix": "",
                "completion": "",
                "is_error": True,
                "error": "Ollama timed out",
                "result_id": str(uuid4()),
            },
        ]

        # Mock _process_rows_with_router to return results for non-error rows
        with patch.object(
            judge,
            "_process_rows_with_router",
            return_value=([1], ["jailbreak detected"], [0], ["raw"]),
        ):
            result = judge.evaluate(data)

        # Error row should have error explanation, NOT "trivial/placeholder"
        error_row = result[1]
        self.assertEqual(error_row["eval_test"], 0)
        self.assertIn("Ollama timed out", error_row["explanation_test"])
        self.assertNotIn("trivial", error_row["explanation_test"])

        # Normal row should be evaluated by judge
        normal_row = result[0]
        self.assertEqual(normal_row["eval_test"], 1)


# ============================================================================
# 7. Baseline generation: adapter error detection
# ============================================================================


class TestBaselineGenerationAdapterErrors(unittest.TestCase):
    """Test that static template generation detects adapter-level errors."""

    def test_adapter_error_sets_error_field(self):
        from hackagent.attacks.techniques.static_template.generation import (
            execute_prompts,
        )

        mock_router = MagicMock()
        mock_router._agent_registry = {"agent-key": MagicMock()}
        # Simulate an adapter error response (dict with error_message)
        mock_router.route_request.return_value = {
            "error_message": "Ollama connection error: timed out",
            "error_category": "AdapterException",
            "status_code": 500,
        }

        data = [
            {
                "goal": "test goal",
                "goal_index": 0,
                "template_category": "direct",
                "template": "Do {goal}",
                "attack_prompt": "Do test goal",
            },
        ]

        result = execute_prompts(
            data,
            mock_router,
            config={"max_tokens": 100, "temperature": 0.7, "n_samples_per_template": 1},
            logger=logging.getLogger("test"),
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["completion"], "")
        self.assertEqual(result[0]["error"], "Ollama connection error: timed out")

    def test_successful_response_no_error(self):
        from hackagent.attacks.techniques.static_template.generation import (
            execute_prompts,
        )

        mock_router = MagicMock()
        mock_router._agent_registry = {"agent-key": MagicMock()}
        mock_router.route_request.return_value = {
            "generated_text": "Sure, here is how to do it...",
        }

        data = [
            {
                "goal": "test goal",
                "goal_index": 0,
                "template_category": "direct",
                "template": "Do {goal}",
                "attack_prompt": "Do test goal",
            },
        ]

        result = execute_prompts(
            data,
            mock_router,
            config={"max_tokens": 100, "temperature": 0.7, "n_samples_per_template": 1},
            logger=logging.getLogger("test"),
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["completion"], "Sure, here is how to do it...")
        self.assertNotIn("error", result[0])


if __name__ == "__main__":
    unittest.main()
