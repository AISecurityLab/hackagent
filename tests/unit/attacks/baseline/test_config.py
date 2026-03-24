# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.attacks.techniques.baseline.config import (
    DEFAULT_TEMPLATE_CONFIG,
    TemplateAttackConfig,
)


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


if __name__ == "__main__":
    unittest.main()
