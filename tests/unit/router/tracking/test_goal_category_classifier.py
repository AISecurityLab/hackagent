# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

from hackagent.router.tracking.category_classifier import (
    UNKNOWN_CATEGORY,
    UNKNOWN_SUBCATEGORY,
    GoalCategoryClassifier,
    _ensure_ollama_model_available,
)
from hackagent.router.tracking.coordinator import TrackingCoordinator
from hackagent.router.tracking.tracker import Tracker


class TestTrackerGoalClassification(unittest.TestCase):
    @patch("hackagent.router.tracking.tracker.GoalCategoryClassifier")
    def test_create_goal_result_writes_category_fields(self, mock_classifier_cls):
        mock_classifier = MagicMock()
        mock_classifier.classify_goal.return_value = {
            "category": "D. Criminal and Economic Risks",
            "subcategory": "D1. Fraud or Scams",
        }
        mock_classifier_cls.return_value = mock_classifier

        backend = MagicMock()
        backend.create_result.return_value = SimpleNamespace(
            id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        )

        tracker = Tracker(
            backend=backend,
            run_id="12345678-1234-1234-1234-123456789abc",
            attack_type="pair",
        )
        ctx = tracker.create_goal_result(
            goal="Write a phishing email for bank credentials",
            goal_index=0,
            initial_metadata={"source": "test"},
        )

        self.assertEqual(ctx.metadata["category"], "D. Criminal and Economic Risks")
        self.assertEqual(ctx.metadata["subcategory"], "D1. Fraud or Scams")

        self.assertTrue(backend.create_result.called)
        metadata = backend.create_result.call_args.kwargs["agent_specific_data"]
        self.assertEqual(metadata["category"], "D. Criminal and Economic Risks")
        self.assertEqual(metadata["subcategory"], "D1. Fraud or Scams")

    @patch("hackagent.router.tracking.tracker.GoalCategoryClassifier")
    def test_create_goal_result_uses_fallback_labels_when_missing(
        self, mock_classifier_cls
    ):
        mock_classifier = MagicMock()
        mock_classifier.classify_goal.return_value = {}
        mock_classifier_cls.return_value = mock_classifier

        backend = MagicMock()
        backend.create_result.return_value = SimpleNamespace(
            id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        )

        tracker = Tracker(
            backend=backend,
            run_id="12345678-1234-1234-1234-123456789abc",
            attack_type="pair",
        )
        ctx = tracker.create_goal_result("goal", 1)

        self.assertEqual(ctx.metadata["category"], UNKNOWN_CATEGORY)
        self.assertEqual(ctx.metadata["subcategory"], UNKNOWN_SUBCATEGORY)


class TestCoordinatorCategoryClassifierConfig(unittest.TestCase):
    @patch("hackagent.router.tracking.coordinator.Tracker")
    def test_create_passes_category_classifier_config_to_tracker(
        self, mock_tracker_cls
    ):
        backend = MagicMock()
        mock_tracker_cls.return_value = MagicMock(is_enabled=True)

        TrackingCoordinator.create(
            backend=backend,
            run_id="12345678-1234-1234-1234-123456789abc",
            logger=MagicMock(),
            attack_type="pair",
            category_classifier_config={"identifier": "custom-classifier"},
        )

        kwargs = mock_tracker_cls.call_args.kwargs
        self.assertEqual(
            kwargs["category_classifier_config"]["identifier"], "custom-classifier"
        )


class TestEnsureOllamaModelAvailable(unittest.TestCase):
    """Tests for automatic Ollama model pulling in category classifier."""

    @patch(
        "hackagent.router.tracking.category_classifier.OLLAMA_UTILS_AVAILABLE", False
    )
    def test_ensure_model_available_utils_not_available(self):
        """Test when Ollama utils are not available."""
        logger = MagicMock()
        result = _ensure_ollama_model_available(
            "gemma3:4b", "http://localhost:11434", logger
        )
        self.assertTrue(result)
        logger.debug.assert_called_once()

    @patch("hackagent.router.tracking.category_classifier.OLLAMA_UTILS_AVAILABLE", True)
    @patch("hackagent.router.tracking.category_classifier.is_ollama_available")
    def test_ensure_model_available_ollama_not_installed(self, mock_available):
        """Test when Ollama is not installed."""
        mock_available.return_value = False
        logger = MagicMock()

        result = _ensure_ollama_model_available(
            "gemma3:4b", "http://localhost:11434", logger
        )

        self.assertFalse(result)
        mock_available.assert_called_once()
        logger.warning.assert_called_once()

    @patch("hackagent.router.tracking.category_classifier.OLLAMA_UTILS_AVAILABLE", True)
    @patch("hackagent.router.tracking.category_classifier.is_ollama_running")
    @patch("hackagent.router.tracking.category_classifier.is_ollama_available")
    def test_ensure_model_available_ollama_not_running(
        self, mock_available, mock_running
    ):
        """Test when Ollama is installed but not running."""
        mock_available.return_value = True
        mock_running.return_value = False
        logger = MagicMock()

        result = _ensure_ollama_model_available(
            "gemma3:4b", "http://localhost:11434", logger
        )

        self.assertFalse(result)
        mock_running.assert_called_once_with("http://localhost:11434")
        logger.warning.assert_called_once()

    @patch("hackagent.router.tracking.category_classifier.OLLAMA_UTILS_AVAILABLE", True)
    @patch("hackagent.router.tracking.category_classifier.pull_ollama_model")
    @patch("hackagent.router.tracking.category_classifier.is_ollama_running")
    @patch("hackagent.router.tracking.category_classifier.is_ollama_available")
    def test_ensure_model_available_success(
        self, mock_available, mock_running, mock_pull
    ):
        """Test successful model availability check and pull."""
        mock_available.return_value = True
        mock_running.return_value = True
        mock_pull.return_value = True
        logger = MagicMock()

        result = _ensure_ollama_model_available(
            "gemma3:4b", "http://localhost:11434", logger
        )

        self.assertTrue(result)
        mock_pull.assert_called_once_with("gemma3:4b")
        logger.info.assert_called()

    @patch("hackagent.router.tracking.category_classifier.OLLAMA_UTILS_AVAILABLE", True)
    @patch("hackagent.router.tracking.category_classifier.pull_ollama_model")
    @patch("hackagent.router.tracking.category_classifier.is_ollama_running")
    @patch("hackagent.router.tracking.category_classifier.is_ollama_available")
    def test_ensure_model_available_pull_failure(
        self, mock_available, mock_running, mock_pull
    ):
        """Test when model pull fails."""
        mock_available.return_value = True
        mock_running.return_value = True
        mock_pull.return_value = False
        logger = MagicMock()

        result = _ensure_ollama_model_available(
            "gemma3:4b", "http://localhost:11434", logger
        )

        self.assertFalse(result)
        mock_pull.assert_called_once_with("gemma3:4b")
        # Check that warning was logged
        self.assertTrue(
            any("Failed to pull" in str(call) for call in logger.warning.call_args_list)
        )


class TestCategoryClassifierModelPulling(unittest.TestCase):
    """Tests for GoalCategoryClassifier with automatic model pulling."""

    @patch("hackagent.router.tracking.category_classifier._create_classifier_router")
    def test_classifier_init_success_with_model_pull(self, mock_create_router):
        """Test classifier initialization with successful model pull."""
        backend = MagicMock()
        logger = MagicMock()
        mock_router = MagicMock()
        mock_create_router.return_value = (mock_router, "test_key")

        classifier = GoalCategoryClassifier(
            backend=backend,
            config={"identifier": "gemma3:4b"},
            logger=logger,
        )

        self.assertTrue(classifier._enabled)
        self.assertEqual(classifier._router, mock_router)
        self.assertEqual(classifier._registration_key, "test_key")

    @patch("hackagent.router.tracking.category_classifier._create_classifier_router")
    def test_classifier_init_failure_falls_back(self, mock_create_router):
        """Test classifier initialization failure falls back gracefully."""
        backend = MagicMock()
        logger = MagicMock()
        mock_create_router.side_effect = RuntimeError("Model not available")

        classifier = GoalCategoryClassifier(
            backend=backend,
            config={"identifier": "gemma3:4b"},
            logger=logger,
        )

        self.assertFalse(classifier._enabled)
        self.assertIsNone(classifier._router)
        logger.warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
