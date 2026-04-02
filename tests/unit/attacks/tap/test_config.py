# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.attacks.techniques.tap.config import (
    DEFAULT_TAP_CONFIG,
    TapConfig,
    TapParams,
)


class TestDefaultTapConfig(unittest.TestCase):
    def test_required_keys_present(self):
        required = [
            "attack_type",
            "tap_params",
            "attacker",
            "category_classifier",
            "judge",
            "target_str",
            "output_dir",
        ]
        for key in required:
            self.assertIn(key, DEFAULT_TAP_CONFIG)

    def test_default_attack_type(self):
        self.assertEqual(DEFAULT_TAP_CONFIG["attack_type"], "tap")


class TestTapParams(unittest.TestCase):
    def test_defaults(self):
        p = TapParams()
        self.assertEqual(p.depth, 3)
        self.assertEqual(p.width, 4)
        self.assertEqual(p.branching_factor, 3)


class TestTapConfig(unittest.TestCase):
    def test_from_dict_parses_tap_params(self):
        cfg = TapConfig.from_dict({"tap_params": {"depth": 2, "width": 1}})
        self.assertEqual(cfg.tap_params.depth, 2)
        self.assertEqual(cfg.tap_params.width, 1)

    def test_to_dict_contains_tap_params(self):
        d = TapConfig().to_dict()
        self.assertIn("tap_params", d)
        self.assertIn("depth", d["tap_params"])


if __name__ == "__main__":
    unittest.main()
