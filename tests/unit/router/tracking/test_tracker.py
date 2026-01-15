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

"""Tests for StepTracker class."""

import json
import logging
import unittest
from unittest.mock import MagicMock, patch

from hackagent.models import EvaluationStatusEnum, StatusEnum
from hackagent.router.tracking.context import TrackingContext
from hackagent.router.tracking.tracker import StepTracker


class TestStepTrackerInitialization(unittest.TestCase):
    """Test StepTracker initialization."""

    def test_initialization(self):
        """Test StepTracker initialization with context."""
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=logging.Logger)
        context = TrackingContext(
            client=mock_client,
            run_id="run-123",
            parent_result_id="result-456",
            logger=mock_logger,
        )

        tracker = StepTracker(context)

        self.assertEqual(tracker.context, context)
        self.assertEqual(tracker.logger, mock_logger)


class TestStepTrackerTrackStep(unittest.TestCase):
    """Test track_step context manager."""

    def test_track_step_disabled_yields_none(self):
        """Test track_step yields None when tracking is disabled."""
        context = TrackingContext.create_disabled()
        tracker = StepTracker(context)

        with tracker.track_step("Test Step", "TEST_STEP") as trace_id:
            self.assertIsNone(trace_id)

    @patch("hackagent.router.tracking.tracker.result_trace_create")
    def test_track_step_creates_trace(self, mock_trace_create):
        """Test track_step creates a trace when enabled."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="12345678-1234-1234-1234-123456789abc",
            parent_result_id="87654321-4321-4321-4321-cba987654321",
        )
        tracker = StepTracker(context)

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.parsed = MagicMock(id="trace-id-123")
        mock_trace_create.sync_detailed.return_value = mock_response

        with tracker.track_step("Test Step", "TEST_STEP") as trace_id:
            self.assertEqual(trace_id, "trace-id-123")

        mock_trace_create.sync_detailed.assert_called_once()

    @patch("hackagent.router.tracking.tracker.result_trace_create")
    @patch("hackagent.router.tracking.tracker.result_partial_update")
    def test_track_step_handles_exception(self, mock_partial_update, mock_trace_create):
        """Test track_step handles exceptions and re-raises."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="12345678-1234-1234-1234-123456789abc",
            parent_result_id="87654321-4321-4321-4321-cba987654321",
        )
        tracker = StepTracker(context)

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.parsed = MagicMock(id="trace-id-123")
        mock_trace_create.sync_detailed.return_value = mock_response

        with self.assertRaises(ValueError):
            with tracker.track_step("Test Step", "TEST_STEP"):
                raise ValueError("Test error")

        # Should have attempted to update error status
        mock_partial_update.sync_detailed.assert_called()


class TestStepTrackerSanitizeConfig(unittest.TestCase):
    """Test _sanitize_config method."""

    def test_sanitize_config_removes_sensitive_keys(self):
        """Test that sensitive keys are redacted."""
        context = TrackingContext.create_disabled()
        tracker = StepTracker(context)

        config = {
            "api_key": "secret123",
            "api_token": "token456",
            "password": "pass789",
            "secret_value": "hidden",
            "normal_setting": "visible",  # Use a non-sensitive key name
            "model": "gpt-4",
        }

        sanitized = tracker._sanitize_config(config)

        self.assertEqual(sanitized["api_key"], "***REDACTED***")
        self.assertEqual(sanitized["api_token"], "***REDACTED***")
        self.assertEqual(sanitized["password"], "***REDACTED***")
        self.assertEqual(sanitized["secret_value"], "***REDACTED***")
        self.assertEqual(sanitized["normal_setting"], "visible")
        self.assertEqual(sanitized["model"], "gpt-4")

    def test_sanitize_config_nested(self):
        """Test that nested configs are also sanitized."""
        context = TrackingContext.create_disabled()
        tracker = StepTracker(context)

        config = {
            "outer_setting": "visible",
            "nested": {
                "api_key": "secret",
                "normal": "visible_nested",
            },
        }

        sanitized = tracker._sanitize_config(config)

        self.assertEqual(sanitized["outer_setting"], "visible")
        self.assertEqual(sanitized["nested"]["api_key"], "***REDACTED***")
        self.assertEqual(sanitized["nested"]["normal"], "visible_nested")

    def test_sanitize_config_case_insensitive(self):
        """Test that sensitive key detection is case-insensitive."""
        context = TrackingContext.create_disabled()
        tracker = StepTracker(context)

        config = {
            "API_KEY": "secret1",
            "ApiToken": "secret2",
            "PASSWORD": "secret3",
        }

        sanitized = tracker._sanitize_config(config)

        self.assertEqual(sanitized["API_KEY"], "***REDACTED***")
        self.assertEqual(sanitized["ApiToken"], "***REDACTED***")
        self.assertEqual(sanitized["PASSWORD"], "***REDACTED***")


class TestStepTrackerUpdateRunStatus(unittest.TestCase):
    """Test update_run_status method."""

    def test_update_run_status_disabled(self):
        """Test update_run_status returns False when disabled."""
        context = TrackingContext.create_disabled()
        tracker = StepTracker(context)

        result = tracker.update_run_status(StatusEnum.COMPLETED)

        self.assertFalse(result)

    @patch("hackagent.router.tracking.tracker.run_partial_update")
    def test_update_run_status_success(self, mock_run_update):
        """Test successful run status update."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="12345678-1234-1234-1234-123456789abc",
        )
        tracker = StepTracker(context)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_run_update.sync_detailed.return_value = mock_response

        result = tracker.update_run_status(StatusEnum.COMPLETED)

        self.assertTrue(result)
        mock_run_update.sync_detailed.assert_called_once()

    @patch("hackagent.router.tracking.tracker.run_partial_update")
    def test_update_run_status_invalid_uuid(self, mock_run_update):
        """Test update_run_status handles invalid UUID."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="invalid-uuid",
        )
        tracker = StepTracker(context)

        result = tracker.update_run_status(StatusEnum.COMPLETED)

        self.assertFalse(result)
        mock_run_update.sync_detailed.assert_not_called()

    @patch("hackagent.router.tracking.tracker.run_partial_update")
    def test_update_run_status_api_failure(self, mock_run_update):
        """Test update_run_status handles API failures."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="12345678-1234-1234-1234-123456789abc",
        )
        tracker = StepTracker(context)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.content = b"Server error"
        mock_run_update.sync_detailed.return_value = mock_response

        result = tracker.update_run_status(StatusEnum.COMPLETED)

        self.assertFalse(result)


class TestStepTrackerUpdateResultStatus(unittest.TestCase):
    """Test update_result_status method."""

    def test_update_result_status_disabled(self):
        """Test update_result_status returns False when disabled."""
        context = TrackingContext.create_disabled()
        tracker = StepTracker(context)

        result = tracker.update_result_status(EvaluationStatusEnum.PASSED_CRITERIA)

        self.assertFalse(result)

    @patch("hackagent.router.tracking.tracker.result_partial_update")
    def test_update_result_status_success(self, mock_result_update):
        """Test successful result status update."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="12345678-1234-1234-1234-123456789abc",
            parent_result_id="87654321-4321-4321-4321-cba987654321",
        )
        tracker = StepTracker(context)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_result_update.sync_detailed.return_value = mock_response

        result = tracker.update_result_status(
            EvaluationStatusEnum.PASSED_CRITERIA,
            evaluation_notes="Test notes",
            agent_specific_data={"key": "value"},
        )

        self.assertTrue(result)
        mock_result_update.sync_detailed.assert_called_once()

    @patch("hackagent.router.tracking.tracker.result_partial_update")
    def test_update_result_status_invalid_uuid(self, mock_result_update):
        """Test update_result_status handles invalid UUID."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="12345678-1234-1234-1234-123456789abc",
            parent_result_id="invalid-uuid",
        )
        tracker = StepTracker(context)

        result = tracker.update_result_status(EvaluationStatusEnum.PASSED_CRITERIA)

        self.assertFalse(result)
        mock_result_update.sync_detailed.assert_not_called()


class TestStepTrackerMetadataHelpers(unittest.TestCase):
    """Test metadata helper methods."""

    def test_add_step_metadata(self):
        """Test add_step_metadata adds metadata to context."""
        context = TrackingContext()
        tracker = StepTracker(context)

        tracker.add_step_metadata("items_processed", 100)
        tracker.add_step_metadata("success_rate", 0.95)

        self.assertEqual(context.metadata["step_metadata"]["items_processed"], 100)
        self.assertEqual(context.metadata["step_metadata"]["success_rate"], 0.95)

    def test_record_progress(self):
        """Test record_progress adds progress entries."""
        context = TrackingContext()
        tracker = StepTracker(context)

        tracker.record_progress("Processing batch 1/10", items=50, errors=0)
        tracker.record_progress("Processing batch 2/10", items=100, errors=1)

        progress_log = context.metadata["progress_log"]
        self.assertEqual(len(progress_log), 2)
        self.assertEqual(progress_log[0]["message"], "Processing batch 1/10")
        self.assertEqual(progress_log[0]["items"], 50)
        self.assertEqual(progress_log[1]["items"], 100)

    def test_record_progress_limits_entries(self):
        """Test record_progress keeps only last 20 entries."""
        context = TrackingContext()
        tracker = StepTracker(context)

        # Add 25 entries
        for i in range(25):
            tracker.record_progress(f"Entry {i}")

        progress_log = context.metadata["progress_log"]
        self.assertEqual(len(progress_log), 20)
        # Should keep the last 20 (entries 5-24)
        self.assertEqual(progress_log[0]["message"], "Entry 5")
        self.assertEqual(progress_log[-1]["message"], "Entry 24")


class TestStepTrackerExtractTraceId(unittest.TestCase):
    """Test _extract_trace_id method."""

    def test_extract_trace_id_from_parsed(self):
        """Test extracting trace ID from parsed response."""
        context = TrackingContext.create_disabled()
        tracker = StepTracker(context)

        mock_response = MagicMock()
        mock_response.parsed = MagicMock(id="trace-123")

        result = tracker._extract_trace_id(mock_response, "Test Step")

        self.assertEqual(result, "trace-123")

    def test_extract_trace_id_from_content(self):
        """Test extracting trace ID from raw content."""
        context = TrackingContext.create_disabled()
        tracker = StepTracker(context)

        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.content = json.dumps({"id": "trace-456"}).encode()

        result = tracker._extract_trace_id(mock_response, "Test Step")

        self.assertEqual(result, "trace-456")

    def test_extract_trace_id_not_found(self):
        """Test extract_trace_id returns None when ID not found."""
        context = TrackingContext.create_disabled()
        tracker = StepTracker(context)

        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.content = json.dumps({}).encode()

        result = tracker._extract_trace_id(mock_response, "Test Step")

        self.assertIsNone(result)


class TestStepTrackerHandleStepError(unittest.TestCase):
    """Test _handle_step_error method."""

    def test_handle_step_error_disabled(self):
        """Test _handle_step_error does nothing when disabled."""
        context = TrackingContext.create_disabled()
        tracker = StepTracker(context)

        # Should not raise
        tracker._handle_step_error("Test Step", "Test error")

    @patch("hackagent.router.tracking.tracker.result_partial_update")
    def test_handle_step_error_updates_result(self, mock_partial_update):
        """Test _handle_step_error updates result status."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="12345678-1234-1234-1234-123456789abc",
            parent_result_id="87654321-4321-4321-4321-cba987654321",
        )
        tracker = StepTracker(context)

        tracker._handle_step_error("Test Step", "Something went wrong")

        mock_partial_update.sync_detailed.assert_called_once()
        call_args = mock_partial_update.sync_detailed.call_args
        body = call_args.kwargs["body"]
        self.assertEqual(
            body.evaluation_status, EvaluationStatusEnum.ERROR_TEST_FRAMEWORK
        )
        self.assertIn("Test Step", body.evaluation_notes)
        self.assertIn("Something went wrong", body.evaluation_notes)


if __name__ == "__main__":
    unittest.main()
