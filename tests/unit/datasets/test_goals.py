# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for hackagent.datasets.goals.resolve_goals."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from hackagent.datasets.goals import resolve_goals


class TestResolveGoals(unittest.TestCase):
    def test_explicit_goals_preserve_index_order(self):
        resolved = resolve_goals(goals=["a", "b", "c"])

        self.assertEqual([goal.text for goal in resolved], ["a", "b", "c"])
        self.assertEqual([goal.index for goal in resolved], [0, 1, 2])
        self.assertTrue(all(goal.labels == {} for goal in resolved))
        self.assertTrue(all(goal.extra == {} for goal in resolved))

    def test_no_source_raises_value_error(self):
        with self.assertRaises(ValueError) as context:
            resolve_goals()

        message = str(context.exception).lower()
        self.assertIn("goals", message)
        self.assertIn("dataset", message)
        self.assertIn("intents", message)

    def test_plain_string_goals_raises_value_error(self):
        with self.assertRaises(ValueError) as context:
            resolve_goals(goals="not a list")

        self.assertIn("list", str(context.exception).lower())

    def test_empty_goals_raises_value_error(self):
        with self.assertRaises(ValueError) as context:
            resolve_goals(goals=[])

        self.assertIn("empty", str(context.exception).lower())

    def test_non_string_goal_items_raise_value_error(self):
        with self.assertRaises(ValueError) as context:
            resolve_goals(goals=["ok", 1])

        self.assertIn("list of strings", str(context.exception).lower())

    @patch("hackagent.datasets.goals.load_goals_from_intents_config")
    def test_intents_map_labels_by_index(self, mock_load_intents):
        mock_load_intents.return_value = (
            ["intent-a", "intent-b"],
            {
                0: {"category": "A. Ethical", "subcategory": "A1. Bias"},
                1: {"category": "A. Ethical", "subcategory": "A2. Insult"},
            },
        )

        resolved = resolve_goals(intents=[{"category": "A"}])

        mock_load_intents.assert_called_once_with([{"category": "A"}])
        self.assertEqual([goal.text for goal in resolved], ["intent-a", "intent-b"])
        self.assertEqual(
            resolved[0].labels,
            {"category": "A. Ethical", "subcategory": "A1. Bias"},
        )
        self.assertEqual(
            resolved[1].labels,
            {"category": "A. Ethical", "subcategory": "A2. Insult"},
        )
        self.assertEqual(resolved[0].extra, {})

    @patch("hackagent.datasets.goals.load_goals_and_extra_fields_from_config")
    def test_dataset_map_extra_by_index(self, mock_load_dataset):
        mock_load_dataset.return_value = (
            ["dataset-a", "dataset-b"],
            {0: {"category": "cat-a"}, 1: {"category": "cat-b"}},
        )

        resolved = resolve_goals(dataset={"preset": "agentharm", "limit": 2})

        mock_load_dataset.assert_called_once_with({"preset": "agentharm", "limit": 2})
        self.assertEqual([goal.text for goal in resolved], ["dataset-a", "dataset-b"])
        self.assertEqual(resolved[0].extra, {"category": "cat-a"})
        self.assertEqual(resolved[1].extra, {"category": "cat-b"})
        self.assertEqual(resolved[0].labels, {})

    @patch("hackagent.datasets.goals.load_goals_and_extra_fields_from_config")
    def test_string_dataset_means_preset(self, mock_load_dataset):
        mock_load_dataset.return_value = (["preset-goal"], {})

        resolved = resolve_goals(dataset="agentharm")

        mock_load_dataset.assert_called_once_with({"preset": "agentharm"})
        self.assertEqual(resolved[0].text, "preset-goal")
        self.assertEqual(resolved[0].index, 0)

    @patch("hackagent.datasets.goals.load_goals_from_intents_config")
    def test_intents_loader_errors_are_wrapped(self, mock_load_intents):
        mock_load_intents.side_effect = RuntimeError("bad intents")

        with self.assertRaises(ValueError) as context:
            resolve_goals(intents=[{"category": "A"}])

        self.assertIn("Failed to load goals from intents", str(context.exception))
        self.assertIn("bad intents", str(context.exception))

    @patch("hackagent.datasets.goals.load_goals_and_extra_fields_from_config")
    def test_dataset_loader_errors_are_wrapped(self, mock_load_dataset):
        mock_load_dataset.side_effect = RuntimeError("missing preset")

        with self.assertRaises(ValueError) as context:
            resolve_goals(dataset={"preset": "missing"})

        self.assertIn("Failed to load goals from dataset", str(context.exception))
        self.assertIn("missing preset", str(context.exception))

    @patch("hackagent.datasets.goals.load_goals_and_extra_fields_from_config")
    def test_empty_dataset_result_raises(self, mock_load_dataset):
        mock_load_dataset.return_value = ([], {})

        with self.assertRaises(ValueError) as context:
            resolve_goals(dataset={"preset": "empty"})

        self.assertIn("empty", str(context.exception).lower())

    @patch("hackagent.datasets.goals.logger")
    @patch("hackagent.datasets.goals.load_goals_from_intents_config")
    @patch("hackagent.datasets.goals.load_goals_and_extra_fields_from_config")
    def test_precedence_goals_over_intents_and_dataset(
        self,
        mock_load_dataset,
        mock_load_intents,
        mock_logger,
    ):
        resolved = resolve_goals(
            goals=["direct"],
            intents=[{"category": "A"}],
            dataset={"preset": "agentharm"},
        )

        self.assertEqual([goal.text for goal in resolved], ["direct"])
        mock_load_intents.assert_not_called()
        mock_load_dataset.assert_not_called()
        mock_logger.warning.assert_called_once()
        warning = (
            mock_logger.warning.call_args.args[0]
            % mock_logger.warning.call_args.args[1:]
        )
        self.assertIn("goals", warning)
        self.assertIn("intents", warning)
        self.assertIn("dataset", warning)

    @patch("hackagent.datasets.goals.logger")
    @patch("hackagent.datasets.goals.load_goals_from_intents_config")
    @patch("hackagent.datasets.goals.load_goals_and_extra_fields_from_config")
    def test_precedence_intents_over_dataset(
        self,
        mock_load_dataset,
        mock_load_intents,
        mock_logger,
    ):
        mock_load_intents.return_value = (
            ["from-intents"],
            {0: {"category": "A. Ethical", "subcategory": "A1. Bias"}},
        )

        resolved = resolve_goals(
            intents=[{"category": "A"}],
            dataset={"preset": "agentharm"},
        )

        self.assertEqual([goal.text for goal in resolved], ["from-intents"])
        mock_load_intents.assert_called_once()
        mock_load_dataset.assert_not_called()
        mock_logger.warning.assert_called_once()
        warning = (
            mock_logger.warning.call_args.args[0]
            % mock_logger.warning.call_args.args[1:]
        )
        self.assertIn("intents", warning)
        self.assertIn("dataset", warning)
        self.assertIn("ignoring", warning.lower())


if __name__ == "__main__":
    unittest.main()
