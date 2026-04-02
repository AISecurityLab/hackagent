# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.attacks.techniques.config import ConfigBase, default_config_base


class TestSharedConfigDefaults(unittest.TestCase):
    def test_default_category_classifier_block(self):
        cfg = default_config_base()

        self.assertIn("category_classifier", cfg)
        classifier = cfg["category_classifier"]

        self.assertEqual(classifier["agent_type"], "OLLAMA")
        self.assertEqual(classifier["endpoint"], "http://localhost:11434")
        self.assertEqual(classifier["max_tokens"], 100)
        self.assertEqual(classifier["identifier"], "gemma3:4b")

    def test_typed_config_includes_category_classifier(self):
        typed = ConfigBase()
        dumped = typed.model_dump()

        self.assertIn("category_classifier", dumped)
        self.assertEqual(dumped["category_classifier"]["identifier"], "gemma3:4b")


if __name__ == "__main__":
    unittest.main()
