# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""File-based dataset provider for loading goals from local files."""

import csv
import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from hackagent.datasets.base import DatasetProvider

logger = logging.getLogger(__name__)


class FileDatasetProvider(DatasetProvider):
    """
    Dataset provider for local files (JSON, JSONL, CSV).

    This provider loads goals from local files in various formats.

    Example:
        # JSON file with array of objects
        provider = FileDatasetProvider({
            "path": "./goals.json",
            "goal_field": "objective",
        })
        goals = provider.load_goals()

        # CSV file
        provider = FileDatasetProvider({
            "path": "./goals.csv",
            "goal_field": "prompt",
        })
        goals = provider.load_goals()

        # Plain text file (one goal per line)
        provider = FileDatasetProvider({
            "path": "./goals.txt",
        })
        goals = provider.load_goals()
    """

    SUPPORTED_FORMATS = {".json", ".jsonl", ".csv", ".txt"}

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the file dataset provider.

        Args:
            config: Configuration dictionary with keys:
                - path (str): Path to the file
                - goal_field (str, optional): Field name for JSON/CSV (default: "goal")
                - encoding (str, optional): File encoding (default: "utf-8")
                - fallback_fields (list, optional): Alternative fields if goal_field not found
        """
        super().__init__(config)

        path_value = config.get("path")
        if not path_value:
            raise ValueError("File 'path' is required in config")
        self.path = Path(path_value)

        self.goal_field = config.get("goal_field", "goal")
        self.encoding = config.get("encoding", "utf-8")
        self.fallback_fields = config.get(
            "fallback_fields", ["input", "prompt", "text", "objective"]
        )

        self._records: Optional[List[Dict[str, Any]]] = None
        self._metadata = {
            "provider": "file",
            "path": str(self.path),
            "goal_field": self.goal_field,
        }

    def _detect_format(self) -> str:
        """Detect the file format from extension."""
        suffix = self.path.suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported file format: {suffix}. "
                f"Supported formats: {self.SUPPORTED_FORMATS}"
            )
        return suffix

    def _load_json(self) -> List[Dict[str, Any]]:
        """Load records from a JSON file."""
        with open(self.path, "r", encoding=self.encoding) as f:
            data = json.load(f)

        # Handle both array and object with data key
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Try common keys for data arrays
            for key in ["data", "samples", "records", "goals", "items"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
            # Single record
            return [data]
        else:
            raise ValueError(f"Unexpected JSON structure in {self.path}")

    def _load_jsonl(self) -> List[Dict[str, Any]]:
        """Load records from a JSON Lines file."""
        records = []
        with open(self.path, "r", encoding=self.encoding) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    self.logger.warning(
                        f"Skipping invalid JSON at line {line_num}: {e}"
                    )
        return records

    def _load_csv(self) -> List[Dict[str, Any]]:
        """Load records from a CSV file."""
        records = []
        with open(self.path, "r", encoding=self.encoding, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(dict(row))
        return records

    def _load_txt(self) -> List[Dict[str, Any]]:
        """Load records from a plain text file (one goal per line)."""
        records = []
        with open(self.path, "r", encoding=self.encoding) as f:
            for line in f:
                line = line.strip()
                if line:
                    # For plain text, the entire line is the goal
                    records.append({"goal": line, "text": line})
        return records

    def _load_records(self) -> List[Dict[str, Any]]:
        """Load records from the file."""
        if self._records is not None:
            return self._records

        if not self.path.exists():
            raise FileNotFoundError(f"Dataset file not found: {self.path}")

        file_format = self._detect_format()
        self.logger.info(f"Loading dataset from {self.path} (format: {file_format})")

        loaders = {
            ".json": self._load_json,
            ".jsonl": self._load_jsonl,
            ".csv": self._load_csv,
            ".txt": self._load_txt,
        }

        self._records = loaders[file_format]()
        self._metadata["total_samples"] = len(self._records)
        self._metadata["format"] = file_format
        self.logger.info(f"Loaded {len(self._records)} records from {self.path}")

        return self._records

    def load_goals(
        self,
        limit: Optional[int] = None,
        shuffle: bool = False,
        seed: Optional[int] = None,
        **kwargs,
    ) -> List[str]:
        """
        Load goals from the file.

        Args:
            limit: Maximum number of goals to return.
            shuffle: Whether to shuffle records before selecting.
            seed: Random seed for shuffling.
            **kwargs: Additional arguments (unused).

        Returns:
            List of goal strings.
        """
        records = self._load_records()

        # Optionally shuffle
        if shuffle:
            records = records.copy()
            if seed is not None:
                random.seed(seed)
            random.shuffle(records)

        goals = []
        count = 0

        for record in records:
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
        self.logger.info(f"Extracted {len(goals)} goals from file")

        return goals

    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata about the loaded dataset."""
        return self._metadata.copy()
