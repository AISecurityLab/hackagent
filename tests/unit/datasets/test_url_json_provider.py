# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for URL JSON dataset provider."""

import json
import unittest
from unittest.mock import patch

from hackagent.datasets.providers.url_json import UrlJsonDatasetProvider


class _MockHTTPResponse:
    """Simple HTTP response context manager for urllib mocks."""

    def __init__(self, payload: str):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._payload.encode("utf-8")


class TestUrlJsonDatasetProvider(unittest.TestCase):
    """Test UrlJsonDatasetProvider functionality."""

    def test_init_requires_url(self):
        """Test that initialization fails when url is missing."""
        with self.assertRaises(ValueError) as context:
            UrlJsonDatasetProvider({})

        self.assertIn("url", str(context.exception).lower())

    def test_load_goals_from_url_and_cache_dataset(self):
        """Test loading goals from URL and reusing cached dataset."""
        payload = json.dumps(
            [
                {"query": "Goal 1"},
                {"query": "Goal 2"},
            ]
        )

        with patch(
            "hackagent.datasets.providers.url_json.urllib.request.urlopen",
            return_value=_MockHTTPResponse(payload),
        ) as mock_urlopen:
            provider = UrlJsonDatasetProvider(
                {
                    "url": "https://example.com/dataset.json",
                    "goal_field": "query",
                }
            )

            first = provider.load_goals(limit=1)
            second = provider.load_goals()

            self.assertEqual(first, ["Goal 1"])
            self.assertEqual(second, ["Goal 1", "Goal 2"])
            mock_urlopen.assert_called_once()

            metadata = provider.get_metadata()
            self.assertEqual(metadata["provider"], "url_json")
            self.assertEqual(metadata["total_samples"], 2)
            self.assertEqual(metadata["goals_loaded"], 2)

    def test_load_goals_supports_wrapped_json_payload(self):
        """Test loading from JSON objects wrapped under common list keys."""
        payload = json.dumps(
            {
                "records": [
                    {"query": "Record goal 1"},
                    {"query": "Record goal 2"},
                ]
            }
        )

        with patch(
            "hackagent.datasets.providers.url_json.urllib.request.urlopen",
            return_value=_MockHTTPResponse(payload),
        ):
            provider = UrlJsonDatasetProvider(
                {
                    "url": "https://example.com/wrapped.json",
                    "goal_field": "query",
                }
            )

            goals = provider.load_goals()
            self.assertEqual(goals, ["Record goal 1", "Record goal 2"])

    def test_load_goals_with_extra_fields_and_return_dicts(self):
        """Test returning goals as dictionaries with additional metadata."""
        payload = json.dumps(
            [
                {
                    "query": "Goal 1",
                    "category": "credential-exposure",
                    "jailbreak_method": "role-play",
                },
                {
                    "query": "Goal 2",
                    "category": "tool-misuse",
                    "jailbreak_method": "obfuscation",
                },
            ]
        )

        with patch(
            "hackagent.datasets.providers.url_json.urllib.request.urlopen",
            return_value=_MockHTTPResponse(payload),
        ):
            provider = UrlJsonDatasetProvider(
                {
                    "url": "https://example.com/agenthazard.json",
                    "goal_field": "query",
                    "extra_fields": ["category", "jailbreak_method"],
                }
            )

            goals = provider.load_goals(return_dicts=True)

            self.assertEqual(
                goals,
                [
                    {
                        "goal": "Goal 1",
                        "category": "credential-exposure",
                        "jailbreak_method": "role-play",
                    },
                    {
                        "goal": "Goal 2",
                        "category": "tool-misuse",
                        "jailbreak_method": "obfuscation",
                    },
                ],
            )
            self.assertEqual(
                provider.get_extra_data(),
                [
                    {
                        "category": "credential-exposure",
                        "jailbreak_method": "role-play",
                    },
                    {
                        "category": "tool-misuse",
                        "jailbreak_method": "obfuscation",
                    },
                ],
            )

    def test_load_goals_shuffle_uses_seed_and_shuffle(self):
        """Test shuffle path uses random.seed and random.shuffle."""
        payload = json.dumps(
            [
                {"query": "Goal A"},
                {"query": "Goal B"},
            ]
        )

        with (
            patch(
                "hackagent.datasets.providers.url_json.urllib.request.urlopen",
                return_value=_MockHTTPResponse(payload),
            ),
            patch("hackagent.datasets.providers.url_json.random.seed") as mock_seed,
            patch(
                "hackagent.datasets.providers.url_json.random.shuffle"
            ) as mock_shuffle,
        ):
            provider = UrlJsonDatasetProvider(
                {
                    "url": "https://example.com/shuffle.json",
                    "goal_field": "query",
                }
            )

            provider.load_goals(shuffle=True, seed=123)

            mock_seed.assert_called_once_with(123)
            mock_shuffle.assert_called_once()

    def test_load_goals_skips_invalid_records_with_warning(self):
        """Test records without goal fields are skipped and warned."""
        payload = json.dumps(
            [
                {"query": "Goal 1"},
                {"no_goal": "skip me"},
            ]
        )

        with patch(
            "hackagent.datasets.providers.url_json.urllib.request.urlopen",
            return_value=_MockHTTPResponse(payload),
        ):
            provider = UrlJsonDatasetProvider(
                {
                    "url": "https://example.com/invalid.json",
                    "goal_field": "query",
                }
            )

            with patch.object(provider.logger, "warning") as mock_warning:
                goals = provider.load_goals()

            self.assertEqual(goals, ["Goal 1"])
            mock_warning.assert_called_once()

    def test_load_goals_raises_if_download_fails(self):
        """Test provider re-raises errors when URL fetch fails."""
        with patch(
            "hackagent.datasets.providers.url_json.urllib.request.urlopen",
            side_effect=RuntimeError("network error"),
        ):
            provider = UrlJsonDatasetProvider(
                {
                    "url": "https://example.com/fail.json",
                    "goal_field": "query",
                }
            )

            with patch.object(provider.logger, "error") as mock_error:
                with self.assertRaises(RuntimeError):
                    provider.load_goals()

            mock_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
