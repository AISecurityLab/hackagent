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
Core tracking functionality.

This module provides the StepTracker class which handles the lifecycle
of operation tracking including trace creation, status updates, and
error handling. It integrates with the HackAgent backend API to maintain
synchronized state.
"""

import json
from contextlib import contextmanager
from typing import Any, Dict, Optional

from hackagent.api.result import result_partial_update, result_trace_create
from hackagent.api.run import run_partial_update
from hackagent.models import (
    EvaluationStatusEnum,
    PatchedResultRequest,
    PatchedRunRequest,
    StatusEnum,
    StepTypeEnum,
    TraceRequest,
)

from .context import TrackingContext


class StepTracker:
    """
    Tracks operation execution and synchronizes with backend API.

    This class manages the complete lifecycle of operation tracking:
    - Creating trace records for each step
    - Handling exceptions and updating error states
    - Managing sequence counters for ordered operations
    - Updating run and result statuses

    The tracker is designed to fail gracefully - if tracking is disabled
    or API calls fail, the underlying operations continue unaffected.

    Attributes:
        context: TrackingContext containing tracking configuration
        logger: Logger instance for tracking operations

    Example:
        >>> context = TrackingContext(client=client, run_id="123", parent_result_id="456")
        >>> tracker = StepTracker(context)
        >>>
        >>> with tracker.track_step("Process Data", "STEP1_PROCESS"):
        ...     result = process_data()
        >>>
        >>> tracker.update_run_status(StatusEnum.COMPLETED)
    """

    def __init__(self, context: TrackingContext):
        """
        Initialize the step tracker.

        Args:
            context: TrackingContext instance with tracking configuration
        """
        self.context = context
        self.logger = context.logger

    @contextmanager
    def track_step(
        self,
        step_name: str,
        step_type: str,
        input_data: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Context manager for tracking a single operation step.

        This context manager handles the complete lifecycle of step tracking:
        1. Creates a trace record at step start
        2. Yields control to the caller
        3. Handles exceptions and updates error states
        4. Ensures proper cleanup

        Args:
            step_name: Human-readable step name
            step_type: Step type identifier (e.g., "STEP1_GENERATE")
            input_data: Optional input data sample for tracking
            config: Optional configuration snapshot for this step

        Yields:
            trace_id: ID of the created trace record (or None if tracking disabled)

        Example:
            >>> with tracker.track_step("Generate Prefixes", "STEP1_GENERATE"):
            ...     prefixes = generate_prefixes(goals)
            ...     # Step automatically tracked

        Raises:
            Re-raises any exception from the tracked code block after
            recording the error state.
        """
        if not self.context.is_enabled:
            # Tracking disabled, just yield and return
            yield None
            return

        trace_id = None
        try:
            # Create trace record at step start
            trace_id = self._create_trace(
                step_name=step_name,
                step_type=step_type,
                input_data=input_data,
                config=config,
            )

            # Yield control to the tracked code block
            yield trace_id

            # Step completed successfully
            self.logger.debug(f"Step '{step_name}' completed successfully")

        except Exception as e:
            # Handle step failure
            self.logger.error(f"Step '{step_name}' failed: {e}", exc_info=True)
            self._handle_step_error(step_name, str(e))
            # Re-raise to allow caller to handle
            raise

    def _create_trace(
        self,
        step_name: str,
        step_type: str,
        input_data: Optional[Dict[str, Any]],
        config: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """
        Create a trace record on the backend API.

        Args:
            step_name: Human-readable step name
            step_type: Step type identifier
            input_data: Optional input data sample
            config: Optional configuration snapshot

        Returns:
            Trace ID if successful, None otherwise
        """
        try:
            sequence = self.context.increment_sequence()

            # Prepare trace content
            trace_content = {
                "step_name": step_name,
                "step_type_identifier": step_type,
            }

            if config is not None:
                trace_content["config_snapshot"] = self._sanitize_config(config)

            if input_data is not None:
                trace_content["input_data_sample"] = input_data

            # Add any additional metadata
            if self.context.metadata:
                trace_content["context_metadata"] = self.context.metadata

            # Create trace request
            trace_request = TraceRequest(
                sequence=sequence,
                step_type=StepTypeEnum.OTHER,
                content=trace_content,
            )

            # Call API
            result_uuid = self.context.get_result_uuid()
            if not result_uuid:
                self.logger.warning(
                    f"Cannot create trace for '{step_name}': invalid result UUID"
                )
                return None

            response = result_trace_create.sync_detailed(
                client=self.context.client,
                id=result_uuid,
                body=trace_request,
            )

            # Parse response
            if response.status_code == 201:
                trace_id = self._extract_trace_id(response, step_name)
                if trace_id:
                    self.logger.info(
                        f"Created trace for '{step_name}' (ID: {trace_id}, seq: {sequence})"
                    )
                    return trace_id
            else:
                self.logger.error(
                    f"Failed to create trace for '{step_name}': status={response.status_code}, body={response.content}"
                )

        except Exception as e:
            self.logger.error(
                f"Exception creating trace for '{step_name}': {e}", exc_info=True
            )

        return None

    def _extract_trace_id(self, response, step_name: str) -> Optional[str]:
        """
        Extract trace ID from API response.

        Args:
            response: API response object
            step_name: Step name for logging

        Returns:
            Trace ID if found, None otherwise
        """
        # Try parsed response first
        if response.parsed and hasattr(response.parsed, "id"):
            return str(response.parsed.id)

        # Try parsing raw content
        try:
            response_data = json.loads(response.content.decode())
            if "id" in response_data:
                return str(response_data["id"])
        except Exception as e:
            self.logger.warning(f"Could not parse trace ID for '{step_name}': {e}")

        return None

    def _sanitize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive information from config before sending to API.

        Args:
            config: Configuration dictionary

        Returns:
            Sanitized configuration dictionary
        """
        sensitive_keys = {"api_key", "token", "secret", "password", "key"}

        sanitized = {}
        for key, value in config.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_config(value)
            else:
                sanitized[key] = value

        return sanitized

    def _handle_step_error(self, step_name: str, error_message: str) -> None:
        """
        Update backend with step error information.

        Args:
            step_name: Name of the failed step
            error_message: Error message
        """
        if not self.context.is_enabled:
            return

        try:
            result_uuid = self.context.get_result_uuid()
            if not result_uuid:
                return

            error_request = PatchedResultRequest(
                evaluation_status=EvaluationStatusEnum.ERROR_TEST_FRAMEWORK,
                evaluation_notes=f"Pipeline failed at '{step_name}': {error_message}",
            )

            result_partial_update.sync_detailed(
                client=self.context.client,
                id=result_uuid,
                body=error_request,
            )

            self.logger.info(f"Updated result with error status for '{step_name}'")

        except Exception as e:
            self.logger.error(f"Failed to update error status: {e}", exc_info=True)

    def update_run_status(self, status: StatusEnum) -> bool:
        """
        Update the run status on the backend.

        Args:
            status: New status to set

        Returns:
            True if update was successful, False otherwise
        """
        if not self.context.is_enabled:
            return False

        try:
            run_uuid = self.context.get_run_uuid()
            if not run_uuid:
                self.logger.warning("Cannot update run status: invalid run UUID")
                return False

            run_request = PatchedRunRequest(status=status)

            response = run_partial_update.sync_detailed(
                client=self.context.client,
                id=run_uuid,
                body=run_request,
            )

            if response.status_code < 300:
                self.logger.info(f"Updated run {self.context.run_id} to {status.value}")
                return True
            else:
                self.logger.error(
                    f"Failed to update run status: status={response.status_code}, body={response.content}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Exception updating run status: {e}", exc_info=True)
            return False

    def update_result_status(
        self,
        evaluation_status: EvaluationStatusEnum,
        evaluation_notes: Optional[str] = None,
        agent_specific_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update the result evaluation status.

        Args:
            evaluation_status: Evaluation status to set
            evaluation_notes: Optional notes about the evaluation
            agent_specific_data: Optional agent-specific result data

        Returns:
            True if update was successful, False otherwise
        """
        if not self.context.is_enabled:
            return False

        try:
            result_uuid = self.context.get_result_uuid()
            if not result_uuid:
                self.logger.warning("Cannot update result status: invalid result UUID")
                return False

            result_request = PatchedResultRequest(
                evaluation_status=evaluation_status,
                evaluation_notes=evaluation_notes,
                agent_specific_data=agent_specific_data,
            )

            response = result_partial_update.sync_detailed(
                client=self.context.client,
                id=result_uuid,
                body=result_request,
            )

            if response.status_code < 300:
                self.logger.info(
                    f"Updated result {self.context.parent_result_id} to {evaluation_status.value}"
                )
                return True
            else:
                self.logger.error(
                    f"Failed to update result status: status={response.status_code}, body={response.content}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Exception updating result status: {e}", exc_info=True)
            return False

    def add_step_metadata(self, key: str, value: Any) -> None:
        """
        Add metadata that will be included in the next trace.

        This allows steps to record additional information like:
        - Item counts (e.g., "prefixes_generated": 150)
        - Processing stats (e.g., "success_rate": 0.85)
        - Warnings (e.g., "empty_results": True)

        Args:
            key: Metadata key
            value: Metadata value (must be JSON-serializable)

        Example:
            >>> tracker.add_step_metadata("items_processed", 100)
            >>> tracker.add_step_metadata("warning", "Some items filtered")
        """
        if "step_metadata" not in self.context.metadata:
            self.context.metadata["step_metadata"] = {}
        self.context.metadata["step_metadata"][key] = value

    def record_progress(self, message: str, **metrics) -> None:
        """
        Record progress information during step execution.

        This is useful for long-running operations to track intermediate
        progress without cluttering logs. Information is added to context
        metadata and will be included in the next trace update.

        Args:
            message: Progress message
            **metrics: Additional metrics as keyword arguments

        Example:
            >>> tracker.record_progress("Processing batch 1/10", items=50, errors=0)
        """
        if "progress_log" not in self.context.metadata:
            self.context.metadata["progress_log"] = []

        progress_entry = {"message": message, **metrics}
        self.context.metadata["progress_log"].append(progress_entry)

        # Keep only last 20 entries to avoid bloat
        if len(self.context.metadata["progress_log"]) > 20:
            self.context.metadata["progress_log"] = self.context.metadata[
                "progress_log"
            ][-20:]
