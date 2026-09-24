# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""``RunSink`` over a :class:`~hackagent.storage.store.Store`.

Tracking writes result, trace and run rows through this object. Evaluation
metrics passed in are stored as given; ``eval_*`` columns are produced by
:mod:`hackagent.orchestrator.results.mapping` before they reach here.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from hackagent.attacks.types import AttackResult
from hackagent.orchestrator.results.mapping import evaluation_metrics, evaluation_status
from hackagent.storage.store import Store


class StoreSink:
    """Adapt a ``Store`` to the tracking :class:`RunSink` protocol."""

    def __init__(self, store: Store) -> None:
        self.store = store

    def create_result(
        self,
        run_id: UUID,
        goal: str,
        goal_index: int,
        request_payload: Dict[str, Any],
        agent_specific_data: Dict[str, Any],
    ) -> Any:
        return self.store.create_result(
            run_id,
            goal,
            goal_index,
            request_payload,
            agent_specific_data,
        )

    def update_result(
        self,
        result_id: UUID,
        evaluation_status: Optional[str] = None,
        evaluation_notes: Optional[str] = None,
        evaluation_metrics: Optional[Dict[str, Any]] = None,
        agent_specific_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        return self.store.update_result(
            result_id,
            evaluation_status=evaluation_status,
            evaluation_notes=evaluation_notes,
            evaluation_metrics=evaluation_metrics,
            agent_specific_data=agent_specific_data,
        )

    def get_result(self, result_id: UUID) -> Any:
        return self.store.get_result(result_id)

    def create_trace(
        self,
        result_id: UUID,
        sequence: int,
        step_type: str,
        content: Dict[str, Any],
    ) -> Any:
        return self.store.create_trace(result_id, sequence, step_type, content)

    def update_run(
        self,
        run_id: UUID,
        status: Optional[str] = None,
        run_notes: Optional[str] = None,
        run_config: Optional[Dict[str, Any]] = None,
    ) -> Any:
        return self.store.update_run(
            run_id,
            status=status,
            run_notes=run_notes,
            run_config=run_config,
        )

    def get_run(self, run_id: UUID) -> Any:
        return self.store.get_run(run_id)

    def flush(self) -> None:
        flush = getattr(self.store, "flush", None)
        if callable(flush):
            flush()

    def write_verdict(self, result_id: UUID, result: AttackResult) -> Any:
        """Persist the mapped evaluation columns for one judged result."""
        return self.update_result(
            result_id,
            evaluation_status=evaluation_status(result),
            evaluation_notes=(result.verdict.explanation if result.verdict else None),
            evaluation_metrics=evaluation_metrics(result),
        )


__all__ = ["StoreSink"]
