# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.attacks.techniques.static_template.config import (
    DEFAULT_TEMPLATE_CONFIG,
    TemplateAttackConfig,
)
from hackagent.attacks.generator import AttackTemplates


class TestDefaultTemplateConfig(unittest.TestCase):
    def test_has_required_keys(self):
        required = [
            "output_dir",
            "template_categories",
            "templates_per_category",
            "n_samples_per_template",
            "objective",
            "evaluator_type",
            "min_response_length",
            "deduplicate_responses",
        ]
        for key in required:
            self.assertIn(key, DEFAULT_TEMPLATE_CONFIG)

    def test_default_objective(self):
        self.assertEqual(DEFAULT_TEMPLATE_CONFIG["objective"], "jailbreak")

    def test_defaults_only_select_supported_categories(self):
        cfg = TemplateAttackConfig()
        self.assertEqual(
            cfg.template_categories, DEFAULT_TEMPLATE_CONFIG["template_categories"]
        )
        self.assertTrue(
            set(cfg.template_categories) <= set(AttackTemplates.get_all_categories())
        )
        self.assertEqual(cfg.batch_size, 0)
        self.assertEqual(cfg.batch_size, DEFAULT_TEMPLATE_CONFIG["batch_size"])


class TestTemplateAttackConfig(unittest.TestCase):
    def test_from_dict_filters_unknown_keys(self):
        cfg = TemplateAttackConfig.from_dict(
            {
                "output_dir": "./tmp",
                "templates_per_category": 2,
                "unknown_key": "ignored",
            }
        )
        self.assertEqual(cfg.output_dir, "./tmp")
        self.assertEqual(cfg.templates_per_category, 2)
        self.assertFalse(hasattr(cfg, "unknown_key"))

    def test_to_dict_roundtrip(self):
        cfg = TemplateAttackConfig.from_dict({"timeout": 99})
        d = cfg.to_dict()
        self.assertIn("timeout", d)
        self.assertEqual(d["timeout"], 99)

    def test_template_parameters_survive_roundtrip(self):
        parameters = {
            "goal_translated": "Résume la météo",
            "goal_foreign": "Riassumi il meteo",
        }
        cfg = TemplateAttackConfig.from_dict(
            {
                "template_categories": ["multi_language"],
                "template_parameters": parameters,
                "batch_size": 5,
            }
        )
        self.assertEqual(cfg.to_dict()["template_parameters"], parameters)
        self.assertEqual(cfg.batch_size, 5)

    def test_invalid_template_selection_fails_validation(self):
        cases = [
            ({"template_categories": ["unknown"]}, "Unknown template category"),
            ({"template_categories": []}, "non-empty list"),
            ({"template_categories": "encoding"}, "list"),
            ({"template_categories": ["multi_language"]}, "goal_translated"),
            (
                {
                    "template_categories": ["multi_language"],
                    "template_parameters": {"goal_translated": "Résume la météo"},
                },
                "goal_foreign",
            ),
            ({"template_parameters": {"goal": "replacement"}}, "reserved"),
            ({"template_parameters": {"template": "replacement"}}, "reserved"),
            ({"template_parameters": None}, "dictionary"),
        ]
        for config, message in cases:
            with self.subTest(config=config):
                with self.assertRaisesRegex(ValueError, message):
                    TemplateAttackConfig.from_dict(config)

    def test_unknown_category_assignment_is_validated(self):
        cfg = TemplateAttackConfig()
        with self.assertRaisesRegex(ValueError, "Unknown template category"):
            cfg.template_categories = ["unknown"]


if __name__ == "__main__":
    unittest.main()
