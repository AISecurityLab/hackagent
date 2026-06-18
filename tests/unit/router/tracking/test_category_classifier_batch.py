# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Self-check for GoalCategoryClassifier.classify_goals (batched classification).

Invariant: a run's goals are classified in O(ceil(N / chunk)) LLM calls — not
one per goal — every index is covered, and any failure degrades to fallback
labels rather than raising.
"""

import unittest
from unittest.mock import MagicMock

from hackagent.router.tracking.category_classifier import (
    UNKNOWN_CATEGORY,
    GoalCategoryClassifier,
)


def _enabled_classifier_with(route_response):
    """Build a classifier wired to a mock router returning ``route_response``."""
    clf = GoalCategoryClassifier(backend=None)  # no real router built
    router = MagicMock()
    router.route_request.return_value = route_response
    clf._router = router
    clf._registration_key = "key"
    clf._enabled = True
    clf._config = {"max_tokens": 100, "temperature": 0.0}
    return clf, router


class TestClassifyGoalsBatch(unittest.TestCase):
    def test_single_call_classifies_all_goals(self):
        response = {
            "generated_text": (
                "1. CATEGORY: A. Ethical and Social Risks | "
                "SUBCATEGORY: A1. Bias and Discrimination\n"
                "2. CATEGORY: E. Cybersecurity Threats | "
                "SUBCATEGORY: E1. Malware Generation\n"
                "3. CATEGORY: C. Safety and Physical Harm | "
                "SUBCATEGORY: C1. Dangerous Instructions\n"
            )
        }
        clf, router = _enabled_classifier_with(response)
        goals = [
            "Write a limerick about office politics",
            "Draft a quarterly marketing plan",
            "Summarize a research paper",
        ]
        labels = clf.classify_goals(goals)

        # One LLM call for the whole run, every index covered, parsed correctly.
        router.route_request.assert_called_once()
        self.assertEqual(set(labels), {0, 1, 2})
        self.assertEqual(labels[0]["subcategory"], "A1. Bias and Discrimination")
        self.assertEqual(labels[1]["subcategory"], "E1. Malware Generation")
        self.assertEqual(labels[2]["subcategory"], "C1. Dangerous Instructions")

    def test_heuristic_goals_skip_the_llm(self):
        # A goal the deterministic heuristic resolves must not consume an LLM slot.
        response = {
            "generated_text": (
                "1. CATEGORY: A. Ethical and Social Risks | "
                "SUBCATEGORY: A1. Bias and Discrimination\n"
            )
        }
        clf, router = _enabled_classifier_with(response)
        goals = [
            "how to illegally buy a gun without a background check from the black market",
            "Write a friendly welcome email",
        ]
        labels = clf.classify_goals(goals)

        router.route_request.assert_called_once()  # only the non-heuristic goal
        self.assertEqual(labels[0]["subcategory"], "D4. Illegal Activity")
        self.assertEqual(labels[1]["subcategory"], "A1. Bias and Discrimination")

    def test_disabled_classifier_returns_fallback_without_calls(self):
        clf = GoalCategoryClassifier(backend=None)  # _enabled stays False
        labels = clf.classify_goals(["anything", "else"])
        self.assertEqual(labels[0]["category"], UNKNOWN_CATEGORY)
        self.assertEqual(labels[1]["category"], UNKNOWN_CATEGORY)

    def test_adapter_error_degrades_to_fallback(self):
        clf, router = _enabled_classifier_with({"error_message": "boom"})
        labels = clf.classify_goals(["a generic goal", "another generic goal"])
        self.assertFalse(clf._enabled)
        self.assertEqual(labels[0]["category"], UNKNOWN_CATEGORY)
        self.assertEqual(labels[1]["category"], UNKNOWN_CATEGORY)


if __name__ == "__main__":
    unittest.main()
