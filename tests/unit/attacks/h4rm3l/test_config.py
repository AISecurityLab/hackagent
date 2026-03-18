# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for h4rm3l configuration."""

import unittest

from hackagent.attacks.techniques.h4rm3l.config import (
    DEFAULT_H4RM3L_CONFIG,
    H4rm3lConfig,
    H4rm3lParams,
    PRESET_PROGRAMS,
)


class TestDefaultConfig(unittest.TestCase):
    """Test DEFAULT_H4RM3L_CONFIG structure and defaults."""

    def test_has_required_keys(self):
        required = [
            "attack_type",
            "h4rm3l_params",
            "judges",
            "batch_size_judge",
            "goal_batch_size",
            "goal_batch_workers",
            "max_new_tokens_eval",
            "filter_len",
            "judge_request_timeout",
            "judge_temperature",
            "max_judge_retries",
            "goals",
            "output_dir",
            "start_step",
        ]
        for key in required:
            self.assertIn(key, DEFAULT_H4RM3L_CONFIG, f"Missing key: {key}")

    def test_attack_type_matches(self):
        self.assertEqual(DEFAULT_H4RM3L_CONFIG["attack_type"], "h4rm3l")

    def test_judges_is_list(self):
        self.assertIsInstance(DEFAULT_H4RM3L_CONFIG["judges"], list)
        self.assertGreater(len(DEFAULT_H4RM3L_CONFIG["judges"]), 0)

    def test_params_is_dict(self):
        self.assertIsInstance(DEFAULT_H4RM3L_CONFIG["h4rm3l_params"], dict)

    def test_params_defaults(self):
        params = DEFAULT_H4RM3L_CONFIG["h4rm3l_params"]
        self.assertEqual(params["program"], "refusal_suppression")
        self.assertEqual(params["syntax_version"], 2)
        self.assertNotIn("synthesis_model", params)

    def test_has_decorator_llm(self):
        self.assertIn("decorator_llm", DEFAULT_H4RM3L_CONFIG)
        self.assertIsInstance(DEFAULT_H4RM3L_CONFIG["decorator_llm"], dict)

    def test_default_goal_batch_workers(self):
        self.assertEqual(DEFAULT_H4RM3L_CONFIG["goal_batch_workers"], 1)


class TestPresetPrograms(unittest.TestCase):
    """Test PRESET_PROGRAMS catalogue."""

    def test_is_dict(self):
        self.assertIsInstance(PRESET_PROGRAMS, dict)

    def test_has_entries(self):
        self.assertGreater(len(PRESET_PROGRAMS), 0)

    def test_base64_refusal_suppression_present(self):
        self.assertIn("base64_refusal_suppression", PRESET_PROGRAMS)

    def test_identity_present(self):
        self.assertIn("identity", PRESET_PROGRAMS)

    def test_all_values_are_strings(self):
        for name, program in PRESET_PROGRAMS.items():
            with self.subTest(preset=name):
                self.assertIsInstance(program, str)
                self.assertTrue(len(program) > 0)

    def test_known_presets_exist(self):
        expected = [
            "refusal_suppression",
            "aim_refusal_suppression",
            "dan_style",
            "base64_refusal_suppression",
            "hex_mixin_dialog",
            "translate_zulu",
            "pap_logical_appeal",
            "payload_splitting",
            "wikipedia",
            "aim",
            "dan",
            "identity",
        ]
        for name in expected:
            with self.subTest(preset=name):
                self.assertIn(name, PRESET_PROGRAMS)


class TestH4rm3lParams(unittest.TestCase):
    """Test H4rm3lParams dataclass."""

    def test_defaults(self):
        p = H4rm3lParams()
        self.assertEqual(p.program, "refusal_suppression")
        self.assertEqual(p.syntax_version, 2)

    def test_custom_program(self):
        p = H4rm3lParams(program="IdentityDecorator()")
        self.assertEqual(p.program, "IdentityDecorator()")

    def test_invalid_syntax_version(self):
        with self.assertRaises(ValueError):
            H4rm3lParams(syntax_version=3)

    def test_syntax_version_0_invalid(self):
        with self.assertRaises(ValueError):
            H4rm3lParams(syntax_version=0)

    def test_valid_v1(self):
        p = H4rm3lParams(syntax_version=1)
        self.assertEqual(p.syntax_version, 1)

    def test_valid_v2(self):
        p = H4rm3lParams(syntax_version=2)
        self.assertEqual(p.syntax_version, 2)


class TestH4rm3lConfig(unittest.TestCase):
    """Test H4rm3lConfig dataclass."""

    def test_defaults(self):
        c = H4rm3lConfig()
        self.assertEqual(c.attack_type, "h4rm3l")
        self.assertEqual(c.goal_batch_workers, 1)
        self.assertIsInstance(c.h4rm3l_params, H4rm3lParams)

    def test_from_dict(self):
        d = {
            "attack_type": "h4rm3l",
            "h4rm3l_params": {"program": "identity", "syntax_version": 1},
            "goal_batch_workers": 4,
        }
        c = H4rm3lConfig.from_dict(d)
        self.assertEqual(c.h4rm3l_params.program, "identity")
        self.assertEqual(c.h4rm3l_params.syntax_version, 1)
        self.assertEqual(c.goal_batch_workers, 4)

    def test_to_dict_roundtrip(self):
        c = H4rm3lConfig()
        d = c.to_dict()
        self.assertEqual(d["attack_type"], "h4rm3l")
        self.assertIn("h4rm3l_params", d)
        self.assertIsInstance(d["h4rm3l_params"], dict)

    def test_from_dict_missing_params(self):
        """from_dict with no h4rm3l_params should use defaults."""
        c = H4rm3lConfig.from_dict({})
        self.assertEqual(c.h4rm3l_params.program, "refusal_suppression")

    def test_from_dict_ignores_legacy_synthesis_model(self):
        c = H4rm3lConfig.from_dict(
            {
                "h4rm3l_params": {
                    "program": "identity",
                    "syntax_version": 2,
                    "synthesis_model": "openai/gpt-4o-mini",
                }
            }
        )
        self.assertEqual(c.h4rm3l_params.program, "identity")
        self.assertEqual(c.h4rm3l_params.syntax_version, 2)


if __name__ == "__main__":
    unittest.main()
