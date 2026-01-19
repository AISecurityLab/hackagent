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

"""HuggingFace dataset provider for loading goals from HuggingFace Hub."""

import logging
from typing import Any, Dict, List, Optional

from hackagent.datasets.base import DatasetProvider

logger = logging.getLogger(__name__)

# Lazy import flag
_datasets_available = None


def _check_datasets_available() -> bool:
    """Check if the datasets library is available."""
    global _datasets_available
    if _datasets_available is None:
        try:
            import datasets  # noqa: F401

            _datasets_available = True
        except ImportError:
            _datasets_available = False
    return _datasets_available


class HuggingFaceDatasetProvider(DatasetProvider):
    """
    Dataset provider for HuggingFace Hub datasets.

    This provider loads datasets from HuggingFace Hub and extracts goal strings
    from specified fields. It supports filtering, splitting, and limiting samples.

    Example:
        provider = HuggingFaceDatasetProvider({
            "path": "ai-safety-institute/AgentHarm",
            "name": "harmful",
            "goal_field": "prompt",
            "split": "test_public",
        })
        goals = provider.load_goals(limit=100)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the HuggingFace dataset provider.

        Args:
            config: Configuration dictionary with keys:
                - path (str): HuggingFace dataset path (e.g., "ai-safety-institute/AgentHarm")
                - goal_field (str): Field name containing the goal/prompt text
                - split (str, optional): Dataset split to use (default: "test")
                - name (str, optional): Dataset configuration name
                - fallback_fields (list, optional): Alternative fields if goal_field not found
                - trust_remote_code (bool, optional): Whether to trust remote code (default: False)
        """
        super().__init__(config)

        if not _check_datasets_available():
            raise ImportError(
                "The 'datasets' library is required for HuggingFace datasets. "
                "Install it with: pip install datasets"
            )

        self.path = config.get("path")
        if not self.path:
            raise ValueError("HuggingFace dataset 'path' is required in config")

        self.goal_field = config.get("goal_field", "input")
        self.split = config.get("split", "test")
        self.name = config.get("name")  # Dataset configuration name
        self.fallback_fields = config.get(
            "fallback_fields", ["input", "prompt", "question", "text"]
        )
        self.trust_remote_code = config.get("trust_remote_code", False)

        self._dataset = None
        self._metadata = {
            "provider": "huggingface",
            "path": self.path,
            "split": self.split,
            "goal_field": self.goal_field,
        }

    def _load_dataset(self):
        """Lazily load the dataset from HuggingFace."""
        if self._dataset is not None:
            return self._dataset

        from datasets import load_dataset

        self.logger.info(
            f"Loading HuggingFace dataset: {self.path} (split: {self.split})"
        )

        load_kwargs = {
            "path": self.path,
            "split": self.split,
            "trust_remote_code": self.trust_remote_code,
        }

        if self.name:
            load_kwargs["name"] = self.name

        try:
            self._dataset = load_dataset(**load_kwargs)
            self._metadata["total_samples"] = len(self._dataset)
            self.logger.info(f"Loaded {len(self._dataset)} samples from {self.path}")
        except Exception as e:
            self.logger.error(f"Failed to load dataset {self.path}: {e}")
            raise

        return self._dataset

    def load_goals(
        self,
        limit: Optional[int] = None,
        shuffle: bool = False,
        seed: Optional[int] = None,
        **kwargs,
    ) -> List[str]:
        """
        Load goals from the HuggingFace dataset.

        Args:
            limit: Maximum number of goals to return.
            shuffle: Whether to shuffle the dataset before selecting.
            seed: Random seed for shuffling.
            **kwargs: Additional arguments (unused).

        Returns:
            List of goal strings.
        """
        dataset = self._load_dataset()

        # Optionally shuffle
        if shuffle:
            dataset = dataset.shuffle(seed=seed)

        goals = []
        count = 0

        for record in dataset:
            if limit and count >= limit:
                break

            goal = self._extract_goal_from_record(
                record,
                self.goal_field,
                self.fallback_fields,
            )

            if goal:
                goals.append(goal)
                count += 1
            else:
                self.logger.warning(
                    f"Could not extract goal from record. "
                    f"Tried fields: {[self.goal_field] + self.fallback_fields}"
                )

        self._metadata["goals_loaded"] = len(goals)
        self.logger.info(f"Extracted {len(goals)} goals from dataset")

        return goals

    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata about the loaded dataset."""
        return self._metadata.copy()
