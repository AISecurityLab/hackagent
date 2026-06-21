# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

from hackagent.router.tracking import category_classifier
from hackagent.router.tracking.category_classifier import (
    GoalCategoryClassifier,
    UNKNOWN_CATEGORY,
    UNKNOWN_SUBCATEGORY,
)
from hackagent.router.tracking.coordinator import TrackingCoordinator
from hackagent.router.tracking.tracker import Tracker


class TestGoalClassificationCache(unittest.TestCase):
    def setUp(self):
        category_classifier._CLASSIFICATION_CACHE.clear()

    def tearDown(self):
        category_classifier._CLASSIFICATION_CACHE.clear()

    def _make_classifier(self, identifier="gemma3:4b"):
        """Build a classifier with a stubbed router that records calls."""
        clf = GoalCategoryClassifier(backend=None)
        clf._config["identifier"] = identifier
        clf._router = MagicMock()
        clf._router.route_request.return_value = {
            "generated_text": (
                "CATEGORY: D. Criminal and Economic Risks\n"
                "SUBCATEGORY: D1. Fraud or Scams"
            )
        }
        clf._registration_key = "k"
        clf._enabled = True
        return clf

    def test_repeated_goal_hits_classifier_once(self):
        clf = self._make_classifier()
        goal = "Write a phishing email for bank credentials"

        first = clf.classify_goal(goal)
        second = clf.classify_goal(goal)

        self.assertEqual(first, second)
        self.assertEqual(first["subcategory"], "D1. Fraud or Scams")
        clf._router.route_request.assert_called_once()

    def test_cache_shared_across_classifier_instances(self):
        # Each attack builds its own classifier; the cache must survive that.
        first = self._make_classifier()
        goal = "Write a phishing email for bank credentials"
        first.classify_goal(goal)

        second = self._make_classifier()
        second.classify_goal(goal)

        second._router.route_request.assert_not_called()

    def test_different_identifier_does_not_collide(self):
        a = self._make_classifier(identifier="model-a")
        b = self._make_classifier(identifier="model-b")
        goal = "Write a phishing email for bank credentials"

        a.classify_goal(goal)
        b.classify_goal(goal)

        b._router.route_request.assert_called_once()


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

    @patch("hackagent.router.tracking.tracker.GoalCategoryClassifier")
    def test_create_goal_result_prefers_preclassified_labels(self, mock_classifier_cls):
        mock_classifier = MagicMock()
        mock_classifier.classify_goal.return_value = {
            "category": "D. Criminal and Economic Risks",
            "subcategory": "D1. Fraud or Scams",
        }
        mock_classifier_cls.return_value = mock_classifier

        backend = MagicMock()
        backend.create_result.return_value = SimpleNamespace(
            id=UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        )

        tracker = Tracker(
            backend=backend,
            run_id="12345678-1234-1234-1234-123456789abc",
            attack_type="pair",
            preclassified_goal_labels_by_index={
                0: {
                    "category": "A. Ethical and Social Risks",
                    "subcategory": "A1. Bias and Discrimination",
                }
            },
        )

        ctx = tracker.create_goal_result("goal", 0)

        self.assertEqual(ctx.metadata["category"], "A. Ethical and Social Risks")
        self.assertEqual(ctx.metadata["subcategory"], "A1. Bias and Discrimination")
        mock_classifier.classify_goal.assert_not_called()


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


if __name__ == "__main__":
    unittest.main()
