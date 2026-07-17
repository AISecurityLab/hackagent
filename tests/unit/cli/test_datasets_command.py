# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the `hackagent datasets` CLI commands."""

import json
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from hackagent.cli.commands.datasets import datasets
from hackagent.cli.main import cli
from hackagent.datasets.presets import PRESETS


class TestDatasetsCommand(unittest.TestCase):
    """Test browse/sample behavior for the datasets CLI group."""

    def setUp(self) -> None:
        self.runner = CliRunner()
        self.known_preset = next(iter(PRESETS.keys()))

    def test_datasets_registered_on_main_cli(self):
        result = self.runner.invoke(cli, ["datasets", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("list", result.output)
        self.assertIn("show", result.output)
        self.assertIn("sample", result.output)

    def test_list_shows_presets(self):
        result = self.runner.invoke(datasets, ["list"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(self.known_preset, result.output)
        self.assertIn("Dataset Presets", result.output)

    def test_list_json_output(self):
        result = self.runner.invoke(datasets, ["list", "--json"])
        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.output)
        self.assertIsInstance(payload, list)
        self.assertGreater(len(payload), 0)
        self.assertIn("name", payload[0])
        self.assertIn("provider", payload[0])
        names = {item["name"] for item in payload}
        self.assertIn(self.known_preset, names)

    def test_list_filter_by_query(self):
        result = self.runner.invoke(
            datasets, ["list", "--query", self.known_preset, "--json"]
        )
        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.output)
        self.assertTrue(all(self.known_preset in item["name"] for item in payload))

    def test_list_filter_no_matches(self):
        result = self.runner.invoke(
            datasets, ["list", "--query", "definitely-not-a-real-preset-xyz"]
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("No dataset presets matched", result.output)

    def test_show_preset_details(self):
        result = self.runner.invoke(datasets, ["show", self.known_preset])
        self.assertEqual(result.exit_code, 0)
        self.assertIn(self.known_preset, result.output)
        self.assertIn("provider", result.output)
        self.assertIn("goal_field", result.output)

    def test_show_json_output(self):
        result = self.runner.invoke(datasets, ["show", self.known_preset, "--json"])
        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.output)
        self.assertIn("provider", payload)
        self.assertIn("goal_field", payload)

    def test_show_unknown_preset_fails(self):
        result = self.runner.invoke(datasets, ["show", "not-a-real-preset"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Unknown preset", result.output)

    def test_sample_loads_goals(self):
        fake_goals = ["goal one", "goal two"]
        with patch(
            "hackagent.datasets.load_goals",
            return_value=fake_goals,
        ) as mock_load:
            result = self.runner.invoke(
                datasets, ["sample", self.known_preset, "--limit", "2"]
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("goal one", result.output)
        self.assertIn("goal two", result.output)
        mock_load.assert_called_once_with(
            preset=self.known_preset,
            limit=2,
            shuffle=False,
            seed=None,
        )

    def test_sample_json_output(self):
        fake_goals = ["alpha", "beta"]
        with patch("hackagent.datasets.load_goals", return_value=fake_goals):
            result = self.runner.invoke(
                datasets,
                ["sample", self.known_preset, "--limit", "2", "--json"],
            )

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.output)
        self.assertEqual(payload["preset"], self.known_preset)
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["goals"], fake_goals)

    def test_sample_invalid_limit(self):
        result = self.runner.invoke(
            datasets, ["sample", self.known_preset, "--limit", "0"]
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--limit must be at least 1", result.output)

    def test_sample_unknown_preset_fails_before_load(self):
        with patch("hackagent.datasets.load_goals") as mock_load:
            result = self.runner.invoke(datasets, ["sample", "not-a-real-preset"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Unknown preset", result.output)
        mock_load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
