# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for StepTracker class."""

import json
import logging
import unittest
from unittest.mock import MagicMock

from hackagent.server.api.models import EvaluationStatusEnum, StatusEnum
from hackagent.router.tracking.context import TrackingContext
from hackagent.router.tracking.step import StepTracker
from hackagent.router.tracking.utils import sanitize_for_json


class TestStepTrackerInitialization(unittest.TestCase):
    """Test StepTracker initialization."""

    def test_initialization(self):
        """Test StepTracker initialization with context."""
        mock_backend = MagicMock()
        mock_logger = MagicMock(spec=logging.Logger)
        context = TrackingContext(
            backend=mock_backend,
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

    def test_track_step_creates_trace(self):
        """Test track_step creates a trace when enabled."""
        mock_backend = MagicMock()
        context = TrackingContext(
            backend=mock_backend,
            run_id="12345678-1234-1234-1234-123456789abc",
            parent_result_id="87654321-4321-4321-4321-cba987654321",
        )
        tracker = StepTracker(context)

        mock_backend.create_trace.return_value = MagicMock(id="trace-id-123")

        with tracker.track_step("Test Step", "TEST_STEP") as trace_id:
            self.assertEqual(trace_id, "trace-id-123")

        self.assertEqual(mock_backend.create_trace.call_count, 2)

    def test_track_step_handles_exception(self):
        """Test track_step handles exceptions and re-raises."""
        mock_backend = MagicMock()
        context = TrackingContext(
            backend=mock_backend,
            run_id="12345678-1234-1234-1234-123456789abc",
            parent_result_id="87654321-4321-4321-4321-cba987654321",
        )
        tracker = StepTracker(context)

        mock_backend.create_trace.return_value = MagicMock(id="trace-id-123")

        with self.assertRaises(ValueError):
            with tracker.track_step("Test Step", "TEST_STEP"):
                raise ValueError("Test error")

        # Should have attempted to update error status
        mock_backend.update_result.assert_called()
        self.assertGreaterEqual(mock_backend.create_trace.call_count, 1)

    def test_track_step_records_metadata_and_progress(self):
        """Test that step metadata/progress logs are recorded in summary trace."""
        mock_backend = MagicMock()
        context = TrackingContext(
            backend=mock_backend,
            run_id="12345678-1234-1234-1234-123456789abc",
            parent_result_id="87654321-4321-4321-4321-cba987654321",
        )
        tracker = StepTracker(context)

        mock_backend.create_trace.return_value = MagicMock(id="trace-id-123")

        with tracker.track_step("Test Step", "TEST_STEP"):
            tracker.add_step_metadata("items_processed", 5)
            tracker.record_progress("Batch 1", items=5)

        self.assertEqual(mock_backend.create_trace.call_count, 2)
        summary_call = mock_backend.create_trace.call_args_list[1]
        summary_content = summary_call.kwargs["content"]

        self.assertIn("step_metadata", summary_content)
        self.assertIn("progress_log", summary_content)
        self.assertEqual(summary_content.get("status"), "completed")


class TestStepTrackerSanitizeConfig(unittest.TestCase):
    """Test sanitize_for_json utility (formerly StepTracker._sanitize_config)."""

    def test_sanitize_config_removes_sensitive_keys(self):
        """Test that sensitive keys are redacted."""
        config = {
            "api_key": "secret123",
            "api_token": "token456",
            "password": "pass789",
            "secret_value": "hidden",
            "normal_setting": "visible",  # Use a non-sensitive key name
            "model": "gpt-4",
        }

        sanitized = sanitize_for_json(config)

        self.assertEqual(sanitized["api_key"], "***REDACTED***")
        self.assertEqual(sanitized["api_token"], "***REDACTED***")
        self.assertEqual(sanitized["password"], "***REDACTED***")
        self.assertEqual(sanitized["secret_value"], "***REDACTED***")
        self.assertEqual(sanitized["normal_setting"], "visible")
        self.assertEqual(sanitized["model"], "gpt-4")

    def test_sanitize_config_nested(self):
        """Test that nested configs are also sanitized."""
        config = {
            "outer_setting": "visible",
            "nested": {
                "api_key": "secret",
                "normal": "visible_nested",
            },
        }

        sanitized = sanitize_for_json(config)

        self.assertEqual(sanitized["outer_setting"], "visible")
        self.assertEqual(sanitized["nested"]["api_key"], "***REDACTED***")
        self.assertEqual(sanitized["nested"]["normal"], "visible_nested")

    def test_sanitize_config_case_insensitive(self):
        """Test that sensitive key detection is case-insensitive."""
        config = {
            "API_KEY": "secret1",
            "ApiToken": "secret2",
            "PASSWORD": "secret3",
        }

        sanitized = sanitize_for_json(config)

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

    def test_update_run_status_success(self):
        """Test successful run status update."""
        mock_backend = MagicMock()
        context = TrackingContext(
            backend=mock_backend,
            run_id="12345678-1234-1234-1234-123456789abc",
        )
        tracker = StepTracker(context)

        result = tracker.update_run_status(StatusEnum.COMPLETED)

        self.assertTrue(result)
        mock_backend.update_run.assert_called_once()

    def test_update_run_status_invalid_uuid(self):
        """Test update_run_status handles invalid UUID."""
        mock_backend = MagicMock()
        context = TrackingContext(
            backend=mock_backend,
            run_id="invalid-uuid",
        )
        tracker = StepTracker(context)

        result = tracker.update_run_status(StatusEnum.COMPLETED)

        self.assertFalse(result)
        mock_backend.update_run.assert_not_called()

    def test_update_run_status_api_failure(self):
        """Test update_run_status handles API failures."""
        mock_backend = MagicMock()
        context = TrackingContext(
            backend=mock_backend,
            run_id="12345678-1234-1234-1234-123456789abc",
        )
        tracker = StepTracker(context)

        mock_backend.update_run.side_effect = Exception("Server error")

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

    def test_update_result_status_success(self):
        """Test successful result status update."""
        mock_backend = MagicMock()
        context = TrackingContext(
            backend=mock_backend,
            run_id="12345678-1234-1234-1234-123456789abc",
            parent_result_id="87654321-4321-4321-4321-cba987654321",
        )
        tracker = StepTracker(context)

        result = tracker.update_result_status(
            EvaluationStatusEnum.PASSED_CRITERIA,
            evaluation_notes="Test notes",
            agent_specific_data={"key": "value"},
        )

        self.assertTrue(result)
        mock_backend.update_result.assert_called_once()

    def test_update_result_status_invalid_uuid(self):
        """Test update_result_status handles invalid UUID."""
        mock_backend = MagicMock()
        context = TrackingContext(
            backend=mock_backend,
            run_id="12345678-1234-1234-1234-123456789abc",
            parent_result_id="invalid-uuid",
        )
        tracker = StepTracker(context)

        result = tracker.update_result_status(EvaluationStatusEnum.PASSED_CRITERIA)

        self.assertFalse(result)
        mock_backend.update_result.assert_not_called()


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
        """JSON fallback was removed: when parsed is None, result is None."""
        context = TrackingContext.create_disabled()
        tracker = StepTracker(context)

        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.content = json.dumps({"id": "trace-456"}).encode()

        result = tracker._extract_trace_id(mock_response, "Test Step")

        self.assertIsNone(result)

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

    def test_handle_step_error_updates_result(self):
        """Test _handle_step_error updates result status."""
        mock_backend = MagicMock()
        context = TrackingContext(
            backend=mock_backend,
            run_id="12345678-1234-1234-1234-123456789abc",
            parent_result_id="87654321-4321-4321-4321-cba987654321",
        )
        tracker = StepTracker(context)

        tracker._handle_step_error("Test Step", "Something went wrong")

        mock_backend.update_result.assert_called_once()
        call_args = mock_backend.update_result.call_args
        self.assertEqual(
            call_args.kwargs["evaluation_status"],
            EvaluationStatusEnum.ERROR_TEST_FRAMEWORK.value,
        )
        self.assertIn("Test Step", call_args.kwargs["evaluation_notes"])
        self.assertIn("Something went wrong", call_args.kwargs["evaluation_notes"])


if __name__ == "__main__":
    unittest.main()
