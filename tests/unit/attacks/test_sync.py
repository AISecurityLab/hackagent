# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for hackagent.attacks.evaluator.sync module."""

import logging
import unittest
from unittest.mock import MagicMock, patch

from hackagent.attacks.evaluator.sync import (
    _evaluate_row,
    sync_evaluation_to_server,
    update_single_result,
)


class TestUpdateSingleResult(unittest.TestCase):
    """Test update_single_result function."""

    @patch("hackagent.attacks.evaluator.sync.result_partial_update")
    def test_successful_update(self, mock_update):
        """Test successful result update returns True."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_update.sync_detailed.return_value = mock_response

        mock_client = MagicMock()
        result = update_single_result(
            result_id="550e8400-e29b-41d4-a716-446655440000",
            success=True,
            evaluation_notes="Jailbreak detected",
            client=mock_client,
        )

        self.assertTrue(result)
        mock_update.sync_detailed.assert_called_once()

    @patch("hackagent.attacks.evaluator.sync.result_partial_update")
    def test_failed_update_returns_false(self, mock_update):
        """Test failed API call returns False."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.content = b"Server error"
        mock_update.sync_detailed.return_value = mock_response

        mock_client = MagicMock()
        result = update_single_result(
            result_id="550e8400-e29b-41d4-a716-446655440000",
            success=False,
            evaluation_notes="Failed",
            client=mock_client,
        )

        self.assertFalse(result)

    @patch("hackagent.attacks.evaluator.sync.result_partial_update")
    def test_exception_returns_false(self, mock_update):
        """Test exception during update returns False."""
        mock_update.sync_detailed.side_effect = Exception("Network error")

        mock_client = MagicMock()
        result = update_single_result(
            result_id="550e8400-e29b-41d4-a716-446655440000",
            success=True,
            evaluation_notes="Test",
            client=mock_client,
        )

        self.assertFalse(result)

    @patch("hackagent.attacks.evaluator.sync.result_partial_update")
    def test_uses_custom_logger(self, mock_update):
        """Test that custom logger is used when provided."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_update.sync_detailed.return_value = mock_response

        custom_logger = logging.getLogger("test_sync")
        mock_client = MagicMock()

        result = update_single_result(
            result_id="550e8400-e29b-41d4-a716-446655440000",
            success=True,
            evaluation_notes="Test",
            client=mock_client,
            logger=custom_logger,
        )

        self.assertTrue(result)

    @patch("hackagent.attacks.evaluator.sync.result_partial_update")
    def test_success_true_uses_successful_jailbreak(self, mock_update):
        """Test that success=True maps to SUCCESSFUL_JAILBREAK."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_update.sync_detailed.return_value = mock_response

        mock_client = MagicMock()
        update_single_result(
            result_id="550e8400-e29b-41d4-a716-446655440000",
            success=True,
            evaluation_notes="Jailbreak",
            client=mock_client,
        )

        # Check PatchedResultRequest was constructed correctly
        call_kwargs = mock_update.sync_detailed.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
        from hackagent.api.models import EvaluationStatusEnum

        self.assertEqual(
            body.evaluation_status, EvaluationStatusEnum.SUCCESSFUL_JAILBREAK
        )

    @patch("hackagent.attacks.evaluator.sync.result_partial_update")
    def test_success_false_uses_failed_jailbreak(self, mock_update):
        """Test that success=False maps to FAILED_JAILBREAK."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_update.sync_detailed.return_value = mock_response

        mock_client = MagicMock()
        update_single_result(
            result_id="550e8400-e29b-41d4-a716-446655440000",
            success=False,
            evaluation_notes="No jailbreak",
            client=mock_client,
        )

        call_kwargs = mock_update.sync_detailed.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs[1].get("body")
        from hackagent.api.models import EvaluationStatusEnum

        self.assertEqual(body.evaluation_status, EvaluationStatusEnum.FAILED_JAILBREAK)


class TestEvaluateRow(unittest.TestCase):
    """Test _evaluate_row helper function."""

    def setUp(self):
        """Set up default judge keys."""
        self.judge_keys = [
            {
                "key": "eval_jb",
                "explanation": "explanation_jb",
                "label": "JailbreakBench",
            },
            {"key": "eval_hb", "explanation": "explanation_hb", "label": "HarmBench"},
            {"key": "eval_nj", "explanation": "explanation_nj", "label": "Nuanced"},
        ]

    def test_jailbreak_success(self):
        """Test row with jailbreak success (eval_jb=1)."""
        row = {"eval_jb": 1, "explanation_jb": "Detected jailbreak"}
        success, notes = _evaluate_row(row, self.judge_keys)
        self.assertTrue(success)
        self.assertIn("JailbreakBench: 1", notes)
        self.assertIn("Detected jailbreak", notes)

    def test_all_judges_fail(self):
        """Test row where all judges report failure."""
        row = {"eval_jb": 0, "eval_hb": 0, "eval_nj": 0}
        success, notes = _evaluate_row(row, self.judge_keys)
        self.assertFalse(success)

    def test_one_judge_succeeds(self):
        """Test row where at least one judge reports success."""
        row = {"eval_jb": 0, "eval_hb": 1, "eval_nj": 0}
        success, notes = _evaluate_row(row, self.judge_keys)
        self.assertTrue(success)

    def test_no_judge_keys_in_row(self):
        """Test row with no known judge keys falls back to generic success."""
        row = {"success": True, "evaluation_notes": "Generic success"}
        success, notes = _evaluate_row(row, self.judge_keys)
        self.assertTrue(success)
        self.assertIn("Generic success", notes)

    def test_no_judge_keys_no_success(self):
        """Test row with no judge keys and no success key."""
        row = {"other_data": "value"}
        success, notes = _evaluate_row(row, self.judge_keys)
        self.assertFalse(success)
        self.assertEqual(notes, "No evaluation scores available")

    def test_generic_success_false(self):
        """Test fallback to generic success=False."""
        row = {"success": False, "evaluation_notes": "No jailbreak"}
        success, notes = _evaluate_row(row, self.judge_keys)
        self.assertFalse(success)

    def test_multiple_judges_with_explanations(self):
        """Test notes contain all judge results."""
        row = {
            "eval_jb": 1,
            "explanation_jb": "JB detected",
            "eval_hb": 0,
            "explanation_hb": "HB safe",
        }
        success, notes = _evaluate_row(row, self.judge_keys)
        self.assertTrue(success)
        self.assertIn("JailbreakBench", notes)
        self.assertIn("HarmBench", notes)


class TestSyncEvaluationToServer(unittest.TestCase):
    """Test sync_evaluation_to_server function."""

    def test_no_client_returns_zero(self):
        """Test with no client returns 0."""
        count = sync_evaluation_to_server(
            evaluated_data=[{"result_id": "test"}],
            client=None,
        )
        self.assertEqual(count, 0)

    def test_no_result_ids_returns_zero(self):
        """Test with no result_id values returns 0."""
        mock_client = MagicMock()
        count = sync_evaluation_to_server(
            evaluated_data=[{"other": "data"}],
            client=mock_client,
        )
        self.assertEqual(count, 0)

    def test_empty_data_returns_zero(self):
        """Test with empty data list returns 0."""
        mock_client = MagicMock()
        count = sync_evaluation_to_server(
            evaluated_data=[],
            client=mock_client,
        )
        self.assertEqual(count, 0)

    @patch("hackagent.attacks.evaluator.sync.update_single_result")
    def test_syncs_best_per_result_id(self, mock_update):
        """Test that best evaluation per result_id is synced."""
        mock_update.return_value = True

        mock_client = MagicMock()
        evaluated_data = [
            {"result_id": "r1", "eval_jb": 0},
            {"result_id": "r1", "eval_jb": 1, "explanation_jb": "Jailbreak"},
            {"result_id": "r2", "eval_jb": 0},
        ]

        count = sync_evaluation_to_server(
            evaluated_data=evaluated_data,
            client=mock_client,
        )

        # Should update 2 unique result_ids
        self.assertEqual(count, 2)
        self.assertEqual(mock_update.call_count, 2)

    @patch("hackagent.attacks.evaluator.sync.update_single_result")
    def test_success_wins_over_failure(self, mock_update):
        """Test that successful evaluation overwrites failed one."""
        mock_update.return_value = True

        mock_client = MagicMock()
        evaluated_data = [
            {"result_id": "r1", "eval_jb": 0},
            {"result_id": "r1", "eval_jb": 1},  # success should win
        ]

        sync_evaluation_to_server(
            evaluated_data=evaluated_data,
            client=mock_client,
        )

        # The update call should have success=True
        call_args = mock_update.call_args
        self.assertTrue(call_args[0][1])  # success argument

    @patch("hackagent.attacks.evaluator.sync.update_single_result")
    def test_counts_only_successful_updates(self, mock_update):
        """Test that count only includes successful API updates."""
        mock_update.side_effect = [True, False]

        mock_client = MagicMock()
        evaluated_data = [
            {"result_id": "r1", "eval_jb": 1},
            {"result_id": "r2", "eval_jb": 0},
        ]

        count = sync_evaluation_to_server(
            evaluated_data=evaluated_data,
            client=mock_client,
        )

        self.assertEqual(count, 1)

    @patch("hackagent.attacks.evaluator.sync.update_single_result")
    def test_custom_judge_keys(self, mock_update):
        """Test sync with custom judge key mappings."""
        mock_update.return_value = True

        mock_client = MagicMock()
        custom_keys = [
            {"key": "my_eval", "explanation": "my_expl", "label": "MyJudge"},
        ]
        evaluated_data = [
            {"result_id": "r1", "my_eval": 1, "my_expl": "Custom judge says yes"},
        ]

        count = sync_evaluation_to_server(
            evaluated_data=evaluated_data,
            client=mock_client,
            judge_keys=custom_keys,
        )

        self.assertEqual(count, 1)

    @patch("hackagent.attacks.evaluator.sync.update_single_result")
    def test_uses_custom_logger(self, mock_update):
        """Test that custom logger is used."""
        mock_update.return_value = True

        custom_logger = logging.getLogger("test_sync_eval")
        mock_client = MagicMock()
        evaluated_data = [
            {"result_id": "r1", "eval_jb": 1},
        ]

        count = sync_evaluation_to_server(
            evaluated_data=evaluated_data,
            client=mock_client,
            logger=custom_logger,
        )

        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
