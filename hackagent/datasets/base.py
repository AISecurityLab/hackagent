# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Base class for dataset providers."""

import abc
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DatasetProvider(abc.ABC):
    """
    Abstract base class for dataset providers.

    Dataset providers are responsible for loading samples from various sources
    and converting them to goal strings that can be used in HackAgent attacks.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the dataset provider.

        Args:
            config: Provider-specific configuration dictionary.
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abc.abstractmethod
    def load_goals(
        self,
        limit: Optional[int] = None,
        **kwargs,
    ) -> List[str]:
        """
        Load samples and convert them to goal strings.

        Args:
            limit: Maximum number of goals to return. None means all.
            **kwargs: Additional provider-specific arguments.

        Returns:
            List of goal strings for use in attacks.
        """
        pass

    @abc.abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        Return metadata about the loaded dataset.

        Returns:
            Dictionary containing metadata like source, total samples, etc.
        """
        pass

    def _extract_goal_from_record(
        self,
        record: Dict[str, Any],
        goal_field: str,
        fallback_fields: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Extract a goal string from a dataset record.

        Args:
            record: The dataset record dictionary.
            goal_field: Primary field name to extract the goal from.
            fallback_fields: Alternative field names if primary is not found.

        Returns:
            The extracted goal string, or None if not found.
        """
        # Try primary field
        if goal_field in record and record[goal_field]:
            value = record[goal_field]
            return str(value).strip() if value else None

        # Try fallback fields
        if fallback_fields:
            for field in fallback_fields:
                if field in record and record[field]:
                    value = record[field]
                    return str(value).strip() if value else None

        return None
