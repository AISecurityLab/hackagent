# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for dataset registry and load_goals function."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hackagent.datasets.base import DatasetProvider
from hackagent.datasets.registry import (
    _PROVIDERS,
    get_provider,
    load_goals,
    load_goals_from_config,
    register_provider,
)


class TestProviderRegistry(unittest.TestCase):
    """Test provider registry functionality."""

    def test_builtin_providers_registered(self):
        """Test that built-in providers are registered."""
        self.assertIn("huggingface", _PROVIDERS)
        self.assertIn("hf", _PROVIDERS)  # Alias
        self.assertIn("file", _PROVIDERS)
        self.assertIn("local", _PROVIDERS)  # Alias

    def test_register_custom_provider(self):
        """Test registering a custom provider."""

        class CustomProvider(DatasetProvider):
            def load_goals(self, limit=None, **kwargs):
                return ["custom goal"]

            def get_metadata(self):
                return {"provider": "custom"}

        register_provider("custom", CustomProvider)

        self.assertIn("custom", _PROVIDERS)

        # Clean up
        del _PROVIDERS["custom"]

    def test_get_provider_returns_instance(self):
        """Test that get_provider returns a provider instance."""
        config = {"path": "/tmp/test.json", "goal_field": "goal"}

        provider = get_provider("file", config)

        self.assertIsInstance(provider, DatasetProvider)

    def test_get_provider_unknown_raises_error(self):
        """Test that unknown provider raises ValueError."""
        with self.assertRaises(ValueError) as context:
            get_provider("unknown_provider", {})

        self.assertIn("Unknown dataset provider", str(context.exception))

    def test_get_provider_case_insensitive(self):
        """Test that provider lookup is case insensitive."""
        config = {"path": "/tmp/test.json", "goal_field": "goal"}

        provider1 = get_provider("file", config)
        provider2 = get_provider("FILE", config)
        provider3 = get_provider("File", config)

        self.assertEqual(type(provider1), type(provider2))
        self.assertEqual(type(provider1), type(provider3))


class TestLoadGoals(unittest.TestCase):
    """Test load_goals function."""

    def test_load_goals_requires_preset_or_provider(self):
        """Test that either preset or provider must be specified."""
        with self.assertRaises(ValueError) as context:
            load_goals()

        self.assertIn("preset", str(context.exception).lower())
        self.assertIn("provider", str(context.exception).lower())

    def test_load_goals_from_file(self):
        """Test loading goals from a local file."""
        data = [
            {"goal": "File goal 1"},
            {"goal": "File goal 2"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            goals = load_goals(
                provider="file",
                path=temp_path,
                goal_field="goal",
            )

            self.assertEqual(len(goals), 2)
            self.assertEqual(goals[0], "File goal 1")
        finally:
            Path(temp_path).unlink()

    def test_load_goals_with_limit(self):
        """Test that limit parameter works."""
        data = [{"goal": f"Goal {i}"} for i in range(10)]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            goals = load_goals(
                provider="file",
                path=temp_path,
                goal_field="goal",
                limit=3,
            )

            self.assertEqual(len(goals), 3)
        finally:
            Path(temp_path).unlink()

    @patch("hackagent.datasets.registry.get_preset")
    @patch("hackagent.datasets.registry.get_provider")
    def test_load_goals_from_preset(self, mock_get_provider, mock_get_preset):
        """Test loading goals using a preset."""
        # Setup mocks
        mock_get_preset.return_value = {
            "provider": "huggingface",
            "path": "test/dataset",
            "goal_field": "prompt",
        }

        mock_provider = MagicMock()
        mock_provider.load_goals.return_value = ["preset goal 1", "preset goal 2"]
        mock_get_provider.return_value = mock_provider

        goals = load_goals(preset="test_preset", limit=10)

        mock_get_preset.assert_called_once_with("test_preset")
        mock_get_provider.assert_called_once()
        mock_provider.load_goals.assert_called_once()
        self.assertEqual(goals, ["preset goal 1", "preset goal 2"])

    @patch("hackagent.datasets.registry.get_preset")
    @patch("hackagent.datasets.registry.get_provider")
    def test_load_goals_preset_overrides(self, mock_get_provider, mock_get_preset):
        """Test that explicit arguments override preset values."""
        mock_get_preset.return_value = {
            "provider": "huggingface",
            "path": "original/path",
            "goal_field": "original_field",
            "split": "original_split",
        }

        mock_provider = MagicMock()
        mock_provider.load_goals.return_value = ["goal"]
        mock_get_provider.return_value = mock_provider

        load_goals(
            preset="test",
            path="override/path",
            goal_field="override_field",
            split="override_split",
        )

        # Check that provider was called with overridden config
        call_args = mock_get_provider.call_args
        config = call_args[0][1]  # Second positional argument is config

        self.assertEqual(config["path"], "override/path")
        self.assertEqual(config["goal_field"], "override_field")
        self.assertEqual(config["split"], "override_split")


class TestLoadGoalsFromConfig(unittest.TestCase):
    """Test load_goals_from_config function."""

    def test_load_from_config_dict(self):
        """Test loading goals from a configuration dictionary."""
        data = [{"objective": "Config goal"}]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            config = {
                "provider": "file",
                "path": temp_path,
                "goal_field": "objective",
            }

            goals = load_goals_from_config(config)

            self.assertEqual(len(goals), 1)
            self.assertEqual(goals[0], "Config goal")
        finally:
            Path(temp_path).unlink()

    @patch("hackagent.datasets.registry.get_preset")
    @patch("hackagent.datasets.registry.get_provider")
    def test_load_from_config_with_preset(self, mock_get_provider, mock_get_preset):
        """Test loading from config that specifies a preset."""
        mock_get_preset.return_value = {
            "provider": "huggingface",
            "path": "test/dataset",
            "goal_field": "prompt",
        }

        mock_provider = MagicMock()
        mock_provider.load_goals.return_value = ["goal"]
        mock_get_provider.return_value = mock_provider

        config = {
            "preset": "agentharm",
            "limit": 50,
        }

        goals = load_goals_from_config(config)

        mock_get_preset.assert_called_once_with("agentharm")
        self.assertEqual(goals, ["goal"])


if __name__ == "__main__":
    unittest.main()
