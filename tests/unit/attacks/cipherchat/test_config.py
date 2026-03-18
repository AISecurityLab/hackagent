# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for CipherChat config."""

import unittest

from hackagent.attacks.techniques.cipherchat.config import DEFAULT_CIPHERCHAT_CONFIG


class TestConfig(unittest.TestCase):
    def test_has_required_keys(self):
        required = [
            "attack_type",
            "cipherchat_params",
            "judges",
            "batch_size_judge",
            "output_dir",
            "batch_size",
            "goal_batch_size",
            "max_new_tokens_eval",
            "filter_len",
            "judge_request_timeout",
            "judge_temperature",
            "max_judge_retries",
        ]
        for key in required:
            self.assertIn(key, DEFAULT_CIPHERCHAT_CONFIG, f"Missing key: {key}")

    def test_attack_type_matches(self):
        self.assertEqual(DEFAULT_CIPHERCHAT_CONFIG["attack_type"], "cipherchat")

    def test_judges_is_list(self):
        self.assertIsInstance(DEFAULT_CIPHERCHAT_CONFIG["judges"], list)

    def test_params_is_dict(self):
        self.assertIsInstance(DEFAULT_CIPHERCHAT_CONFIG["cipherchat_params"], dict)

    def test_params_has_encode_method(self):
        params = DEFAULT_CIPHERCHAT_CONFIG["cipherchat_params"]
        self.assertIn("encode_method", params)
        self.assertEqual(params["encode_method"], "caesar")

    def test_params_has_expected_defaults(self):
        params = DEFAULT_CIPHERCHAT_CONFIG["cipherchat_params"]
        self.assertTrue(params.get("use_system_role"))
        self.assertTrue(params.get("use_demonstrations"))
        self.assertEqual(params.get("demonstration_toxicity"), "toxic")
        self.assertEqual(params.get("language"), "en")
        self.assertEqual(params.get("num_demonstrations"), 3)
        self.assertTrue(params.get("decode_response"))


if __name__ == "__main__":
    unittest.main()
