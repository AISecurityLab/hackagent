# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for file-based dataset provider."""

import json
import tempfile
import unittest
from pathlib import Path

from hackagent.datasets.providers.file import FileDatasetProvider


class TestFileDatasetProvider(unittest.TestCase):
    """Test FileDatasetProvider functionality."""

    def test_init_requires_path(self):
        """Test that initialization requires a path."""
        with self.assertRaises(ValueError) as context:
            FileDatasetProvider({})

        self.assertIn("path", str(context.exception).lower())

    def test_load_json_array(self):
        """Test loading goals from a JSON array file."""
        data = [
            {"goal": "Test goal 1"},
            {"goal": "Test goal 2"},
            {"goal": "Test goal 3"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            provider = FileDatasetProvider(
                {
                    "path": temp_path,
                    "goal_field": "goal",
                }
            )

            goals = provider.load_goals()

            self.assertEqual(len(goals), 3)
            self.assertEqual(goals[0], "Test goal 1")
            self.assertEqual(goals[1], "Test goal 2")
            self.assertEqual(goals[2], "Test goal 3")
        finally:
            Path(temp_path).unlink()

    def test_load_json_with_data_key(self):
        """Test loading JSON with a 'data' wrapper key."""
        data = {
            "data": [
                {"prompt": "Goal A"},
                {"prompt": "Goal B"},
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            provider = FileDatasetProvider(
                {
                    "path": temp_path,
                    "goal_field": "prompt",
                }
            )

            goals = provider.load_goals()

            self.assertEqual(len(goals), 2)
            self.assertEqual(goals[0], "Goal A")
        finally:
            Path(temp_path).unlink()

    def test_load_jsonl(self):
        """Test loading goals from a JSONL file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"objective": "JSONL goal 1"}\n')
            f.write('{"objective": "JSONL goal 2"}\n')
            f.write('{"objective": "JSONL goal 3"}\n')
            temp_path = f.name

        try:
            provider = FileDatasetProvider(
                {
                    "path": temp_path,
                    "goal_field": "objective",
                }
            )

            goals = provider.load_goals()

            self.assertEqual(len(goals), 3)
            self.assertEqual(goals[0], "JSONL goal 1")
        finally:
            Path(temp_path).unlink()

    def test_load_csv(self):
        """Test loading goals from a CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("id,goal,category\n")
            f.write("1,CSV goal 1,test\n")
            f.write("2,CSV goal 2,test\n")
            temp_path = f.name

        try:
            provider = FileDatasetProvider(
                {
                    "path": temp_path,
                    "goal_field": "goal",
                }
            )

            goals = provider.load_goals()

            self.assertEqual(len(goals), 2)
            self.assertEqual(goals[0], "CSV goal 1")
            self.assertEqual(goals[1], "CSV goal 2")
        finally:
            Path(temp_path).unlink()

    def test_load_txt(self):
        """Test loading goals from a plain text file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Plain text goal 1\n")
            f.write("Plain text goal 2\n")
            f.write("\n")  # Empty line should be skipped
            f.write("Plain text goal 3\n")
            temp_path = f.name

        try:
            provider = FileDatasetProvider(
                {
                    "path": temp_path,
                }
            )

            goals = provider.load_goals()

            self.assertEqual(len(goals), 3)
            self.assertEqual(goals[0], "Plain text goal 1")
            self.assertEqual(goals[2], "Plain text goal 3")
        finally:
            Path(temp_path).unlink()

    def test_limit_parameter(self):
        """Test that limit parameter works correctly."""
        data = [{"goal": f"Goal {i}"} for i in range(10)]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            provider = FileDatasetProvider(
                {
                    "path": temp_path,
                    "goal_field": "goal",
                }
            )

            goals = provider.load_goals(limit=5)

            self.assertEqual(len(goals), 5)
        finally:
            Path(temp_path).unlink()

    def test_shuffle_parameter(self):
        """Test that shuffle parameter works."""
        data = [{"goal": f"Goal {i}"} for i in range(100)]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            provider = FileDatasetProvider(
                {
                    "path": temp_path,
                    "goal_field": "goal",
                }
            )

            # Load with shuffle and seed for reproducibility
            goals1 = provider.load_goals(shuffle=True, seed=42)
            goals2 = provider.load_goals(shuffle=True, seed=42)
            goals3 = provider.load_goals(shuffle=False)

            # Same seed should give same order
            self.assertEqual(goals1, goals2)
            # Shuffled should differ from unshuffled (highly likely with 100 items)
            self.assertNotEqual(goals1, goals3)
        finally:
            Path(temp_path).unlink()

    def test_fallback_fields(self):
        """Test that fallback fields are used when primary field is missing."""
        data = [
            {"input": "Found via input"},
            {"prompt": "Found via prompt"},
            {"text": "Found via text"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            provider = FileDatasetProvider(
                {
                    "path": temp_path,
                    "goal_field": "missing_field",
                    "fallback_fields": ["input", "prompt", "text"],
                }
            )

            goals = provider.load_goals()

            self.assertEqual(len(goals), 3)
            self.assertEqual(goals[0], "Found via input")
            self.assertEqual(goals[1], "Found via prompt")
            self.assertEqual(goals[2], "Found via text")
        finally:
            Path(temp_path).unlink()

    def test_file_not_found(self):
        """Test that FileNotFoundError is raised for missing files."""
        provider = FileDatasetProvider(
            {
                "path": "/nonexistent/path/to/file.json",
                "goal_field": "goal",
            }
        )

        with self.assertRaises(FileNotFoundError):
            provider.load_goals()

    def test_unsupported_format(self):
        """Test that unsupported file formats raise ValueError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
            f.write("<data></data>")
            temp_path = f.name

        try:
            provider = FileDatasetProvider(
                {
                    "path": temp_path,
                    "goal_field": "goal",
                }
            )

            with self.assertRaises(ValueError) as context:
                provider.load_goals()

            self.assertIn("Unsupported file format", str(context.exception))
        finally:
            Path(temp_path).unlink()

    def test_get_metadata(self):
        """Test that metadata is returned correctly."""
        data = [{"goal": "Test"}]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            provider = FileDatasetProvider(
                {
                    "path": temp_path,
                    "goal_field": "goal",
                }
            )

            # Load to populate metadata
            provider.load_goals()
            metadata = provider.get_metadata()

            self.assertEqual(metadata["provider"], "file")
            self.assertEqual(metadata["total_samples"], 1)
            self.assertEqual(metadata["goals_loaded"], 1)
        finally:
            Path(temp_path).unlink()


if __name__ == "__main__":
    unittest.main()
