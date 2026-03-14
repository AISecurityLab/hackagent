# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for HuggingFace dataset provider."""

import unittest
from unittest.mock import MagicMock, patch


class TestHuggingFaceDatasetProvider(unittest.TestCase):
    """Test HuggingFaceDatasetProvider functionality."""

    def test_init_requires_path(self):
        """Test that initialization requires a path."""
        # Need to patch the import check
        with patch(
            "hackagent.datasets.providers.huggingface._check_datasets_available",
            return_value=True,
        ):
            from hackagent.datasets.providers.huggingface import (
                HuggingFaceDatasetProvider,
            )

            with self.assertRaises(ValueError) as context:
                HuggingFaceDatasetProvider({})

            self.assertIn("path", str(context.exception).lower())

    @patch("hackagent.datasets.providers.huggingface._check_datasets_available")
    def test_init_checks_datasets_available(self, mock_check):
        """Test that initialization checks for datasets library."""
        mock_check.return_value = False

        from hackagent.datasets.providers.huggingface import HuggingFaceDatasetProvider

        with self.assertRaises(ImportError) as context:
            HuggingFaceDatasetProvider({"path": "test/dataset"})

        self.assertIn("datasets", str(context.exception).lower())

    @patch("hackagent.datasets.providers.huggingface._check_datasets_available")
    def test_load_goals_extracts_from_field(self, mock_check):
        """Test that goals are extracted from the specified field."""
        mock_check.return_value = True

        # Mock the datasets module
        with patch.dict("sys.modules", {"datasets": MagicMock()}):
            import sys

            mock_datasets = sys.modules["datasets"]

            # Mock dataset
            mock_dataset = MagicMock()
            mock_dataset.__iter__ = MagicMock(
                return_value=iter(
                    [
                        {"prompt": "Goal 1", "other": "data"},
                        {"prompt": "Goal 2", "other": "data"},
                        {"prompt": "Goal 3", "other": "data"},
                    ]
                )
            )
            mock_dataset.__len__ = MagicMock(return_value=3)
            mock_datasets.load_dataset.return_value = mock_dataset

            from hackagent.datasets.providers.huggingface import (
                HuggingFaceDatasetProvider,
            )

            provider = HuggingFaceDatasetProvider(
                {
                    "path": "test/dataset",
                    "goal_field": "prompt",
                    "split": "test",
                }
            )

            goals = provider.load_goals()

            self.assertEqual(len(goals), 3)
            self.assertEqual(goals[0], "Goal 1")
            self.assertEqual(goals[1], "Goal 2")
            self.assertEqual(goals[2], "Goal 3")

    @patch("hackagent.datasets.providers.huggingface._check_datasets_available")
    def test_load_goals_with_limit(self, mock_check):
        """Test that limit parameter works correctly."""
        mock_check.return_value = True

        with patch.dict("sys.modules", {"datasets": MagicMock()}):
            import sys

            mock_datasets = sys.modules["datasets"]

            # Mock dataset with many records
            records = [{"prompt": f"Goal {i}"} for i in range(100)]
            mock_dataset = MagicMock()
            mock_dataset.__iter__ = MagicMock(return_value=iter(records))
            mock_dataset.__len__ = MagicMock(return_value=100)
            mock_datasets.load_dataset.return_value = mock_dataset

            from hackagent.datasets.providers.huggingface import (
                HuggingFaceDatasetProvider,
            )

            provider = HuggingFaceDatasetProvider(
                {
                    "path": "test/dataset",
                    "goal_field": "prompt",
                }
            )

            goals = provider.load_goals(limit=10)

            self.assertEqual(len(goals), 10)

    @patch("hackagent.datasets.providers.huggingface._check_datasets_available")
    def test_load_goals_uses_fallback_fields(self, mock_check):
        """Test that fallback fields are used when primary field is missing."""
        mock_check.return_value = True

        with patch.dict("sys.modules", {"datasets": MagicMock()}):
            import sys

            mock_datasets = sys.modules["datasets"]

            # Records with different field names
            mock_dataset = MagicMock()
            mock_dataset.__iter__ = MagicMock(
                return_value=iter(
                    [
                        {"input": "Found via input"},
                        {"text": "Found via text"},
                    ]
                )
            )
            mock_dataset.__len__ = MagicMock(return_value=2)
            mock_datasets.load_dataset.return_value = mock_dataset

            from hackagent.datasets.providers.huggingface import (
                HuggingFaceDatasetProvider,
            )

            provider = HuggingFaceDatasetProvider(
                {
                    "path": "test/dataset",
                    "goal_field": "missing_field",
                    "fallback_fields": ["input", "text"],
                }
            )

            goals = provider.load_goals()

            self.assertEqual(len(goals), 2)
            self.assertEqual(goals[0], "Found via input")
            self.assertEqual(goals[1], "Found via text")

    @patch("hackagent.datasets.providers.huggingface._check_datasets_available")
    def test_load_goals_with_shuffle(self, mock_check):
        """Test that shuffle parameter is passed to dataset."""
        mock_check.return_value = True

        with patch.dict("sys.modules", {"datasets": MagicMock()}):
            import sys

            mock_datasets = sys.modules["datasets"]

            mock_dataset = MagicMock()
            mock_dataset.__iter__ = MagicMock(return_value=iter([{"prompt": "Goal"}]))
            mock_dataset.__len__ = MagicMock(return_value=1)
            mock_dataset.shuffle = MagicMock(return_value=mock_dataset)
            mock_datasets.load_dataset.return_value = mock_dataset

            from hackagent.datasets.providers.huggingface import (
                HuggingFaceDatasetProvider,
            )

            provider = HuggingFaceDatasetProvider(
                {
                    "path": "test/dataset",
                    "goal_field": "prompt",
                }
            )

            provider.load_goals(shuffle=True, seed=42)

            mock_dataset.shuffle.assert_called_once_with(seed=42)

    @patch("hackagent.datasets.providers.huggingface._check_datasets_available")
    def test_get_metadata(self, mock_check):
        """Test that metadata is returned correctly."""
        mock_check.return_value = True

        with patch.dict("sys.modules", {"datasets": MagicMock()}):
            import sys

            mock_datasets = sys.modules["datasets"]

            mock_dataset = MagicMock()
            mock_dataset.__iter__ = MagicMock(return_value=iter([{"prompt": "Goal"}]))
            mock_dataset.__len__ = MagicMock(return_value=1)
            mock_datasets.load_dataset.return_value = mock_dataset

            from hackagent.datasets.providers.huggingface import (
                HuggingFaceDatasetProvider,
            )

            provider = HuggingFaceDatasetProvider(
                {
                    "path": "test/dataset",
                    "goal_field": "prompt",
                    "split": "test",
                }
            )

            provider.load_goals()
            metadata = provider.get_metadata()

            self.assertEqual(metadata["provider"], "huggingface")
            self.assertEqual(metadata["path"], "test/dataset")
            self.assertEqual(metadata["split"], "test")
            self.assertEqual(metadata["total_samples"], 1)
            self.assertEqual(metadata["goals_loaded"], 1)

    @patch("hackagent.datasets.providers.huggingface._check_datasets_available")
    def test_load_dataset_with_config_name(self, mock_check):
        """Test that dataset config name is passed correctly."""
        mock_check.return_value = True

        with patch.dict("sys.modules", {"datasets": MagicMock()}):
            import sys

            mock_datasets = sys.modules["datasets"]

            mock_dataset = MagicMock()
            mock_dataset.__iter__ = MagicMock(return_value=iter([{"q": "Goal"}]))
            mock_dataset.__len__ = MagicMock(return_value=1)
            mock_datasets.load_dataset.return_value = mock_dataset

            from hackagent.datasets.providers.huggingface import (
                HuggingFaceDatasetProvider,
            )

            provider = HuggingFaceDatasetProvider(
                {
                    "path": "cais/wmdp",
                    "name": "wmdp-bio",  # Config name
                    "goal_field": "question",
                    "split": "test",
                }
            )

            provider.load_goals()

            # Verify load_dataset was called with name parameter
            mock_datasets.load_dataset.assert_called_once()
            call_kwargs = mock_datasets.load_dataset.call_args[1]
            self.assertEqual(call_kwargs["name"], "wmdp-bio")


if __name__ == "__main__":
    unittest.main()
