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

"""
Tracking context management.

This module provides the TrackingContext class for managing shared state
across tracking operations. It acts as a lightweight container for tracking
configuration and state that can be passed between components.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from uuid import UUID

from hackagent.client import AuthenticatedClient


@dataclass
class TrackingContext:
    """
    Shared context for operation tracking.

    This class encapsulates all the state needed for tracking operations
    and synchronizing with the backend API. It provides a clean interface
    for passing tracking configuration between components.

    Attributes:
        client: Authenticated client for API communication
        run_id: Server-generated run ID for this execution
        parent_result_id: ID of the parent result record
        logger: Logger instance for tracking operations
        enabled: Whether tracking is enabled
        sequence_counter: Counter for trace sequence numbers
        metadata: Additional metadata for tracking

    Example:
        >>> context = TrackingContext(
        ...     client=authenticated_client,
        ...     run_id="run-123",
        ...     parent_result_id="result-456"
        ... )
        >>> if context.is_enabled:
        ...     tracker = StepTracker(context)
    """

    client: Optional[AuthenticatedClient] = None
    run_id: Optional[str] = None
    parent_result_id: Optional[str] = None
    logger: Optional[logging.Logger] = None
    sequence_counter: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize default logger if not provided."""
        if self.logger is None:
            self.logger = logging.getLogger(__name__)

    @property
    def is_enabled(self) -> bool:
        """
        Check if tracking is enabled.

        Tracking is enabled when all required components are available:
        client, run_id, and parent_result_id.

        Returns:
            True if tracking is enabled, False otherwise
        """
        return bool(
            self.client is not None
            and self.run_id is not None
            and self.parent_result_id is not None
        )

    def increment_sequence(self) -> int:
        """
        Increment and return the sequence counter.

        Returns:
            The new sequence number
        """
        self.sequence_counter += 1
        return self.sequence_counter

    def get_run_uuid(self) -> Optional[UUID]:
        """
        Get run_id as UUID.

        Returns:
            UUID instance or None if run_id is not set
        """
        if self.run_id:
            try:
                return UUID(self.run_id)
            except (ValueError, AttributeError):
                self.logger.warning(f"Invalid UUID format for run_id: {self.run_id}")
        return None

    def get_result_uuid(self) -> Optional[UUID]:
        """
        Get parent_result_id as UUID.

        Returns:
            UUID instance or None if parent_result_id is not set
        """
        if self.parent_result_id:
            try:
                return UUID(self.parent_result_id)
            except (ValueError, AttributeError):
                self.logger.warning(
                    f"Invalid UUID format for parent_result_id: {self.parent_result_id}"
                )
        return None

    def add_metadata(self, key: str, value: Any) -> None:
        """
        Add metadata to the context.

        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get metadata from the context.

        Args:
            key: Metadata key
            default: Default value if key not found

        Returns:
            Metadata value or default
        """
        return self.metadata.get(key, default)

    @classmethod
    def create_disabled(cls) -> "TrackingContext":
        """
        Create a disabled tracking context.

        Returns:
            A TrackingContext with all tracking disabled
        """
        return cls(
            client=None,
            run_id=None,
            parent_result_id=None,
        )
