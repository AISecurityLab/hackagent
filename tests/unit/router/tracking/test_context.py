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

"""Tests for TrackingContext class."""

import logging
import unittest
from unittest.mock import MagicMock
from uuid import UUID

from hackagent.router.tracking.context import TrackingContext


class TestTrackingContextInitialization(unittest.TestCase):
    """Test TrackingContext initialization and defaults."""

    def test_default_initialization(self):
        """Test default TrackingContext initialization."""
        context = TrackingContext()

        self.assertIsNone(context.client)
        self.assertIsNone(context.run_id)
        self.assertIsNone(context.parent_result_id)
        self.assertIsNotNone(context.logger)
        self.assertEqual(context.sequence_counter, 0)
        self.assertEqual(context.metadata, {})

    def test_initialization_with_values(self):
        """Test TrackingContext initialization with all values."""
        mock_client = MagicMock()
        mock_logger = MagicMock(spec=logging.Logger)

        context = TrackingContext(
            client=mock_client,
            run_id="run-123",
            parent_result_id="result-456",
            logger=mock_logger,
            sequence_counter=5,
            metadata={"key": "value"},
        )

        self.assertEqual(context.client, mock_client)
        self.assertEqual(context.run_id, "run-123")
        self.assertEqual(context.parent_result_id, "result-456")
        self.assertEqual(context.logger, mock_logger)
        self.assertEqual(context.sequence_counter, 5)
        self.assertEqual(context.metadata, {"key": "value"})

    def test_default_logger_created(self):
        """Test that a default logger is created if not provided."""
        context = TrackingContext()

        self.assertIsInstance(context.logger, logging.Logger)


class TestTrackingContextIsEnabled(unittest.TestCase):
    """Test is_enabled property."""

    def test_is_enabled_false_when_client_none(self):
        """Test is_enabled returns False when client is None."""
        context = TrackingContext(
            client=None,
            run_id="run-123",
        )

        self.assertFalse(context.is_enabled)

    def test_is_enabled_false_when_run_id_none(self):
        """Test is_enabled returns False when run_id is None."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id=None,
        )

        self.assertFalse(context.is_enabled)

    def test_is_enabled_true_when_client_and_run_id_set(self):
        """Test is_enabled returns True when both client and run_id are set."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="run-123",
        )

        self.assertTrue(context.is_enabled)

    def test_is_enabled_true_without_parent_result_id(self):
        """Test is_enabled returns True even without parent_result_id."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="run-123",
            parent_result_id=None,
        )

        self.assertTrue(context.is_enabled)


class TestTrackingContextCanCreateResults(unittest.TestCase):
    """Test can_create_results property."""

    def test_can_create_results_false_when_not_enabled(self):
        """Test can_create_results returns False when tracking not enabled."""
        context = TrackingContext(
            client=None,
            run_id="run-123",
            parent_result_id="result-456",
        )

        self.assertFalse(context.can_create_results)

    def test_can_create_results_false_without_parent_result_id(self):
        """Test can_create_results returns False without parent_result_id."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="run-123",
            parent_result_id=None,
        )

        self.assertFalse(context.can_create_results)

    def test_can_create_results_true_when_fully_configured(self):
        """Test can_create_results returns True when fully configured."""
        mock_client = MagicMock()
        context = TrackingContext(
            client=mock_client,
            run_id="run-123",
            parent_result_id="result-456",
        )

        self.assertTrue(context.can_create_results)


class TestTrackingContextSequence(unittest.TestCase):
    """Test sequence counter functionality."""

    def test_increment_sequence(self):
        """Test increment_sequence increments and returns new value."""
        context = TrackingContext()

        self.assertEqual(context.sequence_counter, 0)

        result1 = context.increment_sequence()
        self.assertEqual(result1, 1)
        self.assertEqual(context.sequence_counter, 1)

        result2 = context.increment_sequence()
        self.assertEqual(result2, 2)
        self.assertEqual(context.sequence_counter, 2)

    def test_increment_sequence_from_initial_value(self):
        """Test increment_sequence works from a non-zero initial value."""
        context = TrackingContext(sequence_counter=10)

        result = context.increment_sequence()
        self.assertEqual(result, 11)


class TestTrackingContextUUIDConversion(unittest.TestCase):
    """Test UUID conversion methods."""

    def test_get_run_uuid_valid(self):
        """Test get_run_uuid with valid UUID string."""
        context = TrackingContext(run_id="12345678-1234-1234-1234-123456789abc")

        result = context.get_run_uuid()

        self.assertIsInstance(result, UUID)
        self.assertEqual(str(result), "12345678-1234-1234-1234-123456789abc")

    def test_get_run_uuid_none(self):
        """Test get_run_uuid returns None when run_id is None."""
        context = TrackingContext(run_id=None)

        result = context.get_run_uuid()

        self.assertIsNone(result)

    def test_get_run_uuid_invalid_format(self):
        """Test get_run_uuid returns None for invalid UUID format."""
        context = TrackingContext(run_id="invalid-uuid")

        result = context.get_run_uuid()

        self.assertIsNone(result)

    def test_get_result_uuid_valid(self):
        """Test get_result_uuid with valid UUID string."""
        context = TrackingContext(
            parent_result_id="12345678-1234-1234-1234-123456789abc"
        )

        result = context.get_result_uuid()

        self.assertIsInstance(result, UUID)
        self.assertEqual(str(result), "12345678-1234-1234-1234-123456789abc")

    def test_get_result_uuid_none(self):
        """Test get_result_uuid returns None when parent_result_id is None."""
        context = TrackingContext(parent_result_id=None)

        result = context.get_result_uuid()

        self.assertIsNone(result)

    def test_get_result_uuid_invalid_format(self):
        """Test get_result_uuid returns None for invalid UUID format."""
        context = TrackingContext(parent_result_id="invalid-uuid")

        result = context.get_result_uuid()

        self.assertIsNone(result)


class TestTrackingContextMetadata(unittest.TestCase):
    """Test metadata management."""

    def test_add_metadata(self):
        """Test adding metadata."""
        context = TrackingContext()

        context.add_metadata("key1", "value1")
        context.add_metadata("key2", {"nested": "data"})

        self.assertEqual(context.metadata["key1"], "value1")
        self.assertEqual(context.metadata["key2"], {"nested": "data"})

    def test_add_metadata_overwrites(self):
        """Test that add_metadata overwrites existing keys."""
        context = TrackingContext(metadata={"key": "original"})

        context.add_metadata("key", "updated")

        self.assertEqual(context.metadata["key"], "updated")

    def test_get_metadata_existing_key(self):
        """Test get_metadata returns value for existing key."""
        context = TrackingContext(metadata={"key": "value"})

        result = context.get_metadata("key")

        self.assertEqual(result, "value")

    def test_get_metadata_missing_key(self):
        """Test get_metadata returns None for missing key."""
        context = TrackingContext()

        result = context.get_metadata("nonexistent")

        self.assertIsNone(result)

    def test_get_metadata_with_default(self):
        """Test get_metadata returns default for missing key."""
        context = TrackingContext()

        result = context.get_metadata("nonexistent", "default_value")

        self.assertEqual(result, "default_value")


class TestTrackingContextCreateDisabled(unittest.TestCase):
    """Test create_disabled factory method."""

    def test_create_disabled(self):
        """Test create_disabled creates a disabled context."""
        context = TrackingContext.create_disabled()

        self.assertIsNone(context.client)
        self.assertIsNone(context.run_id)
        self.assertIsNone(context.parent_result_id)
        self.assertFalse(context.is_enabled)
        self.assertFalse(context.can_create_results)


if __name__ == "__main__":
    unittest.main()
