# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import unittest

from hackagent.attacks.techniques.flipattack.config import (
    DEFAULT_FLIPATTACK_CONFIG,
    FlipAttackConfig,
    FlipAttackParams,
)


class TestDefaultFlipAttackConfig(unittest.TestCase):
    def test_required_keys_present(self):
        required = [
            "attack_type",
            "flipattack_params",
            "goals",
            "output_dir",
            "start_step",
            "judges",
        ]
        for key in required:
            self.assertIn(key, DEFAULT_FLIPATTACK_CONFIG)

    def test_default_attack_type(self):
        self.assertEqual(DEFAULT_FLIPATTACK_CONFIG["attack_type"], "flipattack")


class TestFlipAttackParams(unittest.TestCase):
    def test_invalid_flip_mode_raises(self):
        with self.assertRaises(ValueError):
            FlipAttackParams(flip_mode="INVALID")


class TestFlipAttackConfig(unittest.TestCase):
    def test_from_dict_parses_nested_params(self):
        cfg = FlipAttackConfig.from_dict(
            {"flipattack_params": {"flip_mode": "FWO", "cot": True}}
        )
        self.assertEqual(cfg.flipattack_params.flip_mode, "FWO")
        self.assertTrue(cfg.flipattack_params.cot)

    def test_to_dict_contains_nested_params(self):
        d = FlipAttackConfig().to_dict()
        self.assertIn("flipattack_params", d)
        self.assertIn("flip_mode", d["flipattack_params"])


if __name__ == "__main__":
    unittest.main()
