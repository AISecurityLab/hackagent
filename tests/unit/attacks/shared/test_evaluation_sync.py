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

"""Tests for shared evaluation_sync module."""

import logging
from unittest.mock import MagicMock, patch
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

    @patch("hackagent.attacks.evaluator.sync.result_partial_update")
    def test_successful_update(self, mock_api, mock_client, logger):
        mock_api.sync_detailed.return_value = MagicMock(status_code=200)
        result_id = str(uuid4())

        result = update_single_result(
            result_id, True, "success notes", mock_client, logger
        )
        assert result is True
        mock_api.sync_detailed.assert_called_once()

    @patch("hackagent.attacks.evaluator.sync.result_partial_update")
    def test_failed_update_status_code(self, mock_api, mock_client, logger):
        mock_api.sync_detailed.return_value = MagicMock(status_code=400)
        result_id = str(uuid4())

        result = update_single_result(
            result_id, True, "success notes", mock_client, logger
        )
        assert result is False

    @patch("hackagent.attacks.evaluator.sync.result_partial_update")
    def test_exception_returns_false(self, mock_api, mock_client, logger):
        mock_api.sync_detailed.side_effect = Exception("connection error")
        result_id = str(uuid4())

        result = update_single_result(result_id, True, "notes", mock_client, logger)
        assert result is False


class TestSyncEvaluationToServer:
    """Tests for the sync_evaluation_to_server function."""

    @patch("hackagent.attacks.evaluator.sync.result_partial_update")
    def test_empty_data(self, mock_api, mock_client, logger):
        count = sync_evaluation_to_server([], mock_client, logger)
        assert count == 0

    @patch("hackagent.attacks.evaluator.sync.result_partial_update")
    def test_no_result_ids(self, mock_api, mock_client, logger):
        data = [{"success": True, "evaluation_notes": "ok"}]
        count = sync_evaluation_to_server(data, mock_client, logger)
        assert count == 0

    @patch("hackagent.attacks.evaluator.sync.result_partial_update")
    def test_aggregates_best_per_result_id(self, mock_api, mock_client, logger):
        """Multiple rows with same result_id: best (success) should win."""
        mock_api.sync_detailed.return_value = MagicMock(status_code=200)

        rid = str(uuid4())
        data = [
            {"result_id": rid, "success": False, "evaluation_notes": "fail"},
            {"result_id": rid, "success": True, "evaluation_notes": "pass"},
        ]

        count = sync_evaluation_to_server(data, mock_client, logger)
        assert count == 1
        # Should be called once with success=True
        call_args = mock_api.sync_detailed.call_args
        body = (
            call_args[1]["body"] if "body" in call_args[1] else call_args.kwargs["body"]
        )
        assert body.evaluation_status.value in (
            "SUCCESSFUL_JAILBREAK",
            "successful_jailbreak",
        )

    @patch("hackagent.attacks.evaluator.sync.result_partial_update")
    def test_judge_keys(self, mock_api, mock_client, logger):
        """Rows with judge keys are evaluated using those keys."""
        mock_api.sync_detailed.return_value = MagicMock(status_code=200)

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
