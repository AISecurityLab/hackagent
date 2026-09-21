# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for tool_output_ipi config."""

import unittest

from pydantic import ValidationError

from hackagent.attacks.techniques.tool_output_ipi.config import (
    DEFAULT_TOOL_OUTPUT_IPI_CONFIG,
    ToolOutputIPIConfig,
    ToolOutputIPIParams,
)


class TestToolOutputIPIParams(unittest.TestCase):
    def test_defaults(self):
        params = ToolOutputIPIParams()
        self.assertEqual(params.mode, "simulated")
        self.assertEqual(params.max_attempts, 3)
        self.assertFalse(params.use_attacker_llm)
        self.assertEqual(params.success_setting, "both")
        self.assertTrue(params.injection_template)

    def test_rejects_empty_template(self):
        with self.assertRaises(ValidationError):
            ToolOutputIPIParams(injection_template="  ")

    def test_rejects_bad_mode(self):
        with self.assertRaises(ValidationError):
            ToolOutputIPIParams(mode="offline")

    def test_rejects_max_attempts_below_one(self):
        with self.assertRaises(ValidationError):
            ToolOutputIPIParams(max_attempts=0)

    def test_rejects_bad_success_setting(self):
        with self.assertRaises(ValidationError):
            ToolOutputIPIParams(success_setting="maybe")

    def test_accepts_all_success_settings(self):
        for setting in ("direct_harm", "data_stealing", "both"):
            params = ToolOutputIPIParams(success_setting=setting)
            self.assertEqual(params.success_setting, setting)


class TestToolOutputIPIConfig(unittest.TestCase):
    def test_default_dict_has_attack_type(self):
        self.assertEqual(
            DEFAULT_TOOL_OUTPUT_IPI_CONFIG["attack_type"], "tool_output_ipi"
        )
        self.assertIn("tool_output_ipi_params", DEFAULT_TOOL_OUTPUT_IPI_CONFIG)

    def test_from_dict_roundtrip(self):
        cfg = ToolOutputIPIConfig.from_dict(
            {
                "attack_type": "tool_output_ipi",
                "tool_output_ipi_params": {"mode": "live", "max_attempts": 2},
            }
        )
        self.assertEqual(cfg.tool_output_ipi_params.mode, "live")
        self.assertEqual(cfg.tool_output_ipi_params.max_attempts, 2)
        dumped = cfg.to_dict()
        self.assertEqual(dumped["attack_type"], "tool_output_ipi")


if __name__ == "__main__":
    unittest.main()
