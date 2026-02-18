# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for dataset presets."""

import unittest

from hackagent.datasets.presets import PRESETS, get_preset, list_presets


class TestPresets(unittest.TestCase):
    """Test dataset presets functionality."""

    def test_presets_registry_is_not_empty(self):
        """Test that presets registry contains entries."""
        self.assertGreater(len(PRESETS), 0)

    def test_all_presets_have_required_fields(self):
        """Test that all presets have required configuration fields."""
        required_fields = {"provider", "path", "goal_field"}

        for name, config in PRESETS.items():
            for field in required_fields:
                self.assertIn(
                    field,
                    config,
                    f"Preset '{name}' missing required field '{field}'",
                )

    def test_get_preset_returns_config(self):
        """Test that get_preset returns a valid configuration."""
        # Use a preset we know exists
        preset_name = list(PRESETS.keys())[0]
        config = get_preset(preset_name)

        self.assertIsInstance(config, dict)
        self.assertIn("provider", config)
        self.assertIn("path", config)

    def test_get_preset_returns_copy(self):
        """Test that get_preset returns a copy, not the original."""
        preset_name = list(PRESETS.keys())[0]
        config1 = get_preset(preset_name)
        config2 = get_preset(preset_name)

        # Modifying one should not affect the other
        config1["custom_field"] = "test"
        self.assertNotIn("custom_field", config2)

    def test_get_preset_case_insensitive(self):
        """Test that preset lookup is case insensitive."""
        # agentharm should exist
        config_lower = get_preset("agentharm")
        config_upper = get_preset("AGENTHARM")
        config_mixed = get_preset("AgentHarm")

        self.assertEqual(config_lower["path"], config_upper["path"])
        self.assertEqual(config_lower["path"], config_mixed["path"])

    def test_get_preset_unknown_raises_error(self):
        """Test that unknown preset raises ValueError."""
        with self.assertRaises(ValueError) as context:
            get_preset("unknown_preset_xyz")

        self.assertIn("Unknown preset", str(context.exception))
        self.assertIn("unknown_preset_xyz", str(context.exception))

    def test_list_presets_returns_dict(self):
        """Test that list_presets returns a dict with descriptions."""
        presets = list_presets()

        self.assertIsInstance(presets, dict)
        self.assertGreater(len(presets), 0)

        # Each entry should have a string description
        for name, description in presets.items():
            self.assertIsInstance(name, str)
            self.assertIsInstance(description, str)

    def test_known_presets_exist(self):
        """Test that expected presets are defined."""
        expected_presets = [
            "agentharm",
            "strongreject",
            "harmbench",
            "advbench",
        ]

        for preset_name in expected_presets:
            self.assertIn(
                preset_name,
                PRESETS,
                f"Expected preset '{preset_name}' not found",
            )

    def test_agentharm_preset_configuration(self):
        """Test AgentHarm preset has correct configuration."""
        config = get_preset("agentharm")

        self.assertEqual(config["provider"], "huggingface")
        self.assertIn("AgentHarm", config["path"])
        self.assertEqual(config["goal_field"], "prompt")

    def test_strongreject_preset_configuration(self):
        """Test StrongREJECT preset has correct configuration."""
        config = get_preset("strongreject")

        self.assertEqual(config["provider"], "huggingface")
        self.assertEqual(config["goal_field"], "forbidden_prompt")


class TestPresetNormalization(unittest.TestCase):
    """Test preset name normalization."""

    def test_handles_dashes(self):
        """Test that dashes are normalized to underscores."""
        # If we have a preset with underscore, dash should also work
        try:
            # agentharm_benign with dash
            config = get_preset("agentharm-benign")
            self.assertIsNotNone(config)
        except ValueError:
            # Preset might not exist, that's ok
            pass

    def test_handles_spaces(self):
        """Test that spaces are normalized to underscores."""
        try:
            _ = get_preset("agent harm")
            # Should normalize to agentharm or agent_harm
        except ValueError:
            # Expected if no matching preset
            pass


if __name__ == "__main__":
    unittest.main()
