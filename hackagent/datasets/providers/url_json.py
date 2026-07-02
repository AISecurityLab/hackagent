# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""URL-based dataset provider for loading JSON datasets from the web."""

import json
import urllib.request
import random
from typing import Any, Dict, List, Optional, Union
from hackagent.logger import get_logger
from hackagent.datasets.base import DatasetProvider

logger = get_logger(__name__)


class UrlJsonDatasetProvider(DatasetProvider):
    """
    Provider to download and load JSON datasets directly from a URL into RAM.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        self.url = config.get("url")
        if not self.url:
            raise ValueError("URL is required in the configuration")

        self.goal_field = config.get("goal_field", "instruction")
        self.extra_fields = config.get("extra_fields", [])
        self.fallback_fields = config.get(
            "fallback_fields", ["prompt", "input", "text"]
        )

        # List to store additional metadata while maintaining backward compatibility
        self.last_extracted_extras: List[Dict[str, Any]] = []

        self._dataset = None
        self._metadata = {
            "provider": "url_json",
            "url": self.url,
            "goal_field": self.goal_field,
            "extra_fields": self.extra_fields,
        }

    def _load_dataset(self):
        """Lazily download and load the dataset from the specified URL."""
        if self._dataset is not None:
            return self._dataset

        self.logger.info(f"Downloading dataset into memory from: {self.url}")

        try:
            # Basic headers to avoid being blocked by servers
            req = urllib.request.Request(
                self.url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req) as response:
                raw_data = response.read().decode("utf-8")
                self._dataset = json.loads(raw_data)

            # If the downloaded JSON is a dictionary (e.g., {"data": [...]}), extract the list
            if isinstance(self._dataset, dict):
                for key in ["data", "samples", "records", "items"]:
                    if key in self._dataset and isinstance(self._dataset[key], list):
                        self._dataset = self._dataset[key]
                        break

            self._metadata["total_samples"] = len(self._dataset)
            return self._dataset

        except Exception as e:
            self.logger.error(f"Error loading dataset from {self.url}: {e}")
            raise

    def load_goals(
        self,
        limit: Optional[int] = None,
        shuffle: bool = False,
        seed: Optional[int] = None,
        return_dicts: bool = False,
        **kwargs,
    ) -> Union[List[str], List[Dict[str, Any]]]:
        """
        Load goals from the downloaded dataset.

        Args:
            limit: Maximum number of goals to return.
            shuffle: Whether to shuffle the dataset before selecting.
            seed: Random seed for shuffling.
            return_dicts: If True, returns a list of dictionaries with extra fields.
                          If False (default), returns a list of strings.
            **kwargs: Additional arguments.

        Returns:
            List of goal strings by default, or dictionaries if return_dicts=True.
        """
        dataset = self._load_dataset()

        # Shuffle logic for lists
        if shuffle:
            # Create a copy so we don't modify the cached dataset in place
            dataset = list(dataset)
            if seed is not None:
                random.seed(seed)
            random.shuffle(dataset)

        goals = []
        self.last_extracted_extras = []
        count = 0

        for record in dataset:
            if limit and count >= limit:
                break

            goal = self._extract_goal_from_record(
                record, self.goal_field, self.fallback_fields
            )

            if goal:
                extra_data = {}
                if self.extra_fields:
                    extra_data = {
                        field: record.get(field) for field in self.extra_fields
                    }

                # Always save extra data to parallel list
                self.last_extracted_extras.append(extra_data)

                if return_dicts and self.extra_fields:
                    goals.append({"goal": goal, **extra_data})
                else:
                    goals.append(goal)
                count += 1
            else:
                self.logger.warning(
                    f"Could not extract goal from record. "
                    f"Tried fields: {[self.goal_field] + self.fallback_fields}"
                )

        self._metadata["goals_loaded"] = len(goals)
        self.logger.info(f"Extracted {len(goals)} goals from URL dataset")

        return goals

    def get_extra_data(self) -> List[Dict[str, Any]]:
        """Return the extra fields extracted during the last load_goals call."""
        return self.last_extracted_extras

    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata about the loaded dataset."""
        return self._metadata.copy()
