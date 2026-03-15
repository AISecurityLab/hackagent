# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for shared evaluation_sync module."""

import logging
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from hackagent.attacks.evaluator.sync import (
    update_single_result,
    sync_evaluation_to_server,
    _evaluate_row,
)


@pytest.fixture
def logger():
    return logging.getLogger("test.evaluation_sync")


@pytest.fixture
def mock_client():
    return MagicMock()


class TestEvaluateRow:
    """Tests for the _evaluate_row helper."""

    def test_success_from_generic_key(self):
        row = {"success": True, "evaluation_notes": "it worked"}
        success, notes = _evaluate_row(row, judge_keys=[])
        assert success is True
        assert notes == "it worked"

    def test_failure_from_generic_key(self):
        row = {"success": False, "evaluation_notes": "it failed"}
        success, notes = _evaluate_row(row, judge_keys=[])
        assert success is False

    def test_success_from_judge_keys(self):
        row = {"eval_jb": 1, "eval_hb": 0, "eval_nj": 0}
        judge_keys = [
            {
                "key": "eval_jb",
                "explanation": "explanation_jb",
                "label": "JailbreakBench",
            },
            {"key": "eval_hb", "explanation": "explanation_hb", "label": "HarmBench"},
            {"key": "eval_nj", "explanation": "explanation_nj", "label": "Nuanced"},
        ]
        success, notes = _evaluate_row(row, judge_keys=judge_keys)
        assert success is True
        assert "JailbreakBench" in notes

    def test_failure_from_judge_keys_all_zero(self):
        row = {"eval_jb": 0, "eval_hb": 0, "eval_nj": 0}
        judge_keys = [
            {
                "key": "eval_jb",
                "explanation": "explanation_jb",
                "label": "JailbreakBench",
            },
            {"key": "eval_hb", "explanation": "explanation_hb", "label": "HarmBench"},
            {"key": "eval_nj", "explanation": "explanation_nj", "label": "Nuanced"},
        ]
        success, notes = _evaluate_row(row, judge_keys=judge_keys)
        assert success is False

    def test_judge_keys_with_missing_keys(self):
        row = {"eval_jb": 1}
        judge_keys = [
            {
                "key": "eval_jb",
                "explanation": "explanation_jb",
                "label": "JailbreakBench",
            },
            {"key": "eval_hb", "explanation": "explanation_hb", "label": "HarmBench"},
        ]
        success, notes = _evaluate_row(row, judge_keys=judge_keys)
        assert success is True

    def test_no_keys_returns_false(self):
        row = {"other_field": "value"}
        success, notes = _evaluate_row(row, judge_keys=[])
        assert success is False


class TestUpdateSingleResult:
    """Tests for the update_single_result function."""

    def test_successful_update(self, mock_client, logger):
        result_id = str(uuid4())

        result = update_single_result(
            result_id, True, "success notes", mock_client, logger
        )
        assert result is True
        mock_client.update_result.assert_called_once()

    def test_failed_update_status_code(self, mock_client, logger):
        mock_client.update_result.side_effect = Exception("400 bad request")
        result_id = str(uuid4())

        result = update_single_result(
            result_id, True, "success notes", mock_client, logger
        )
        assert result is False

    def test_exception_returns_false(self, mock_client, logger):
        mock_client.update_result.side_effect = Exception("connection error")
        result_id = str(uuid4())

        result = update_single_result(result_id, True, "notes", mock_client, logger)
        assert result is False


class TestSyncEvaluationToServer:
    """Tests for the sync_evaluation_to_server function."""

    def test_empty_data(self, mock_client, logger):
        count = sync_evaluation_to_server([], mock_client, logger)
        assert count == 0

    def test_no_result_ids(self, mock_client, logger):
        data = [{"success": True, "evaluation_notes": "ok"}]
        count = sync_evaluation_to_server(data, mock_client, logger)
        assert count == 0

    def test_aggregates_best_per_result_id(self, mock_client, logger):
        """Multiple rows with same result_id: best (success) should win."""
        rid = str(uuid4())
        data = [
            {"result_id": rid, "success": False, "evaluation_notes": "fail"},
            {"result_id": rid, "success": True, "evaluation_notes": "pass"},
        ]

        count = sync_evaluation_to_server(data, mock_client, logger)
        assert count == 1
        # Should be called once with success=True (SUCCESSFUL_JAILBREAK)
        mock_client.update_result.assert_called_once()
        call_args = mock_client.update_result.call_args
        evaluation_status = call_args.kwargs.get("evaluation_status") or call_args[
            1
        ].get("evaluation_status")
        assert evaluation_status in (
            "SUCCESSFUL_JAILBREAK",
            "successful_jailbreak",
        )

    def test_judge_keys(self, mock_client, logger):
        """Rows with judge keys are evaluated using those keys."""
        rid = str(uuid4())
        data = [
            {"result_id": rid, "eval_jb": 1, "eval_hb": 0},
        ]

        judge_keys = [
            {
                "key": "eval_jb",
                "explanation": "explanation_jb",
                "label": "JailbreakBench",
            },
            {"key": "eval_hb", "explanation": "explanation_hb", "label": "HarmBench"},
        ]
        count = sync_evaluation_to_server(
            data, mock_client, logger, judge_keys=judge_keys
        )
        assert count == 1
