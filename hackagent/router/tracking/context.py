# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Tracking context management.

This module provides the TrackingContext class for managing shared state
across tracking operations. It acts as a lightweight container for tracking
configuration and state that can be passed between components.
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID

from hackagent.client import AuthenticatedClient

if TYPE_CHECKING:
    from .tracker import Context


@dataclass
class TrackingContext:
    """
    Shared context for operation tracking.

    This class encapsulates all the state needed for tracking operations
    and synchronizing with the backend API. It provides a clean interface
    for passing tracking configuration between components.

    When linked to a goal ``Context`` via :meth:`delegate_sequence_to`,
    calls to :meth:`increment_sequence` delegate to the goal context's
    counter.  This ensures that both the StepTracker (pipeline-level)
    and the Tracker (per-goal) produce monotonically increasing,
    non-overlapping sequence numbers on the same Result, preventing
    ``(result_id, sequence)`` collisions on the backend.

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
    _delegate_ctx: Optional["Context"] = field(default=None, repr=False)

    def __post_init__(self):
        """Initialize default logger if not provided."""
        if self.logger is None:
            self.logger = logging.getLogger(__name__)

    def delegate_sequence_to(self, ctx: "Context") -> None:
        """
        Share the sequence counter with a goal's ``Context``.

        After this call, :meth:`increment_sequence` increments the
        *goal* context's counter instead of the local one.  This is
        required when the StepTracker and the Tracker both write traces
        to the same Result: they must share a single monotonic counter
        to avoid ``(result_id, sequence)`` unique-constraint violations.

        Args:
            ctx: Goal-level ``Context`` whose ``sequence_counter`` will
                 be used as the single source of truth.
        """
        self._delegate_ctx = ctx

    @property
    def is_enabled(self) -> bool:
        """
        Check if tracking is enabled for creating traces.

        Trace creation requires client and run_id.
        Result creation additionally requires parent_result_id.

        Returns:
            True if basic tracking is enabled (can create traces), False otherwise
        """
        return bool(self.client is not None and self.run_id is not None)

    def increment_sequence(self) -> int:
        """
        Increment and return the sequence counter.

        If :meth:`delegate_sequence_to` has been called, the *delegated*
        goal context's counter is incremented instead of the local one,
        ensuring a single shared counter for the shared Result.

        Returns:
            The new sequence number
        """
        if self._delegate_ctx is not None:
            self._delegate_ctx.sequence_counter += 1
            return self._delegate_ctx.sequence_counter
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
