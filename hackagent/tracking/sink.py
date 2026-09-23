# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Where a tracker writes run records.

``RunSink`` is local to tracking. Persistence (a ``Store``) implements it
in the orchestrator; this package does not import storage. Method names and
payloads match the existing result, trace and run records so the HTTP and
SQLite schemas stay unchanged.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class RunSink(Protocol):
    """Writes result, trace and run rows for one attack run."""

    def create_result(
        self,
        run_id: UUID,
        goal: str,
        goal_index: int,
        request_payload: Dict[str, Any],
        agent_specific_data: Dict[str, Any],
    ) -> Any: ...

    def update_result(
        self,
        result_id: UUID,
        evaluation_status: Optional[str] = None,
        evaluation_notes: Optional[str] = None,
        evaluation_metrics: Optional[Dict[str, Any]] = None,
        agent_specific_data: Optional[Dict[str, Any]] = None,
    ) -> Any: ...

    def get_result(self, result_id: UUID) -> Any: ...

    def create_trace(
        self,
        result_id: UUID,
        sequence: int,
        step_type: str,
        content: Dict[str, Any],
    ) -> Any: ...

    def update_run(
        self,
        run_id: UUID,
        status: Optional[str] = None,
        run_notes: Optional[str] = None,
        run_config: Optional[Dict[str, Any]] = None,
    ) -> Any: ...

    def get_run(self, run_id: UUID) -> Any: ...
