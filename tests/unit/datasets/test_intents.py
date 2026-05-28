# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.datasets.intents import (
    IntentCategory,
    IntentSubcategory,
    load_goals_from_intents_config,
)


class TestIntentEnums(unittest.TestCase):
    def test_category_aliases_match(self):
        self.assertEqual(IntentCategory.ETHICAL_AND_SOCIAL_RISKS, IntentCategory.A)
        self.assertEqual(IntentCategory.A.value, "Ethical and Social Risks")

    def test_subcategory_aliases_match(self):
        self.assertEqual(
            IntentSubcategory.BIAS_AND_DISCRIMINATION,
            IntentSubcategory.A1,
        )
        self.assertEqual(IntentSubcategory.A1.value, "Bias and Discrimination")


class TestIntentGoalSelection(unittest.TestCase):
    def test_supports_letter_codes_and_maps_to_canonical_labels(self):
        goals, labels = load_goals_from_intents_config(
            [
                {
                    "category": "A",
                    "subcategories": ["A1", "A2"],
                    "samples_per_subcategory": 1,
                }
            ]
        )

        self.assertEqual(len(goals), 2)
        self.assertEqual(labels[0]["category"], "A. Ethical and Social Risks")
        self.assertEqual(labels[0]["subcategory"], "A1. Bias and Discrimination")
        self.assertEqual(labels[1]["category"], "A. Ethical and Social Risks")
        self.assertEqual(
            labels[1]["subcategory"], "A2. Insulting or Harassing Speech"
        )

    def test_defaults_select_one_per_subcategory_when_omitted(self):
        goals, labels = load_goals_from_intents_config(
            [
                {
                    "category": IntentCategory.A,
                }
            ]
        )

        # Category A has 4 subcategories (A1..A4).
        self.assertEqual(len(goals), 4)
        self.assertEqual(len(labels), 4)
        for _, entry in labels.items():
            self.assertEqual(entry["category"], "A. Ethical and Social Risks")

    def test_supports_custom_subcategories_and_samples(self):
        goals, labels = load_goals_from_intents_config(
            [
                {
                    "category": "A",
                    "subcategories": ["A1", IntentSubcategory.A2],
                    "samples_per_subcategory": 2,
                }
            ]
        )

        self.assertEqual(len(goals), 4)
        subcategories = {entry["subcategory"] for entry in labels.values()}
        self.assertEqual(
            subcategories,
            {
                "A1. Bias and Discrimination",
                "A2. Insulting or Harassing Speech",
            },
        )

    def test_subcategory_must_belong_to_category(self):
        with self.assertRaises(ValueError):
            load_goals_from_intents_config(
                [
                    {
                        "category": "A",
                        "subcategories": ["B1"],
                    }
                ]
            )


if __name__ == "__main__":
    unittest.main()
