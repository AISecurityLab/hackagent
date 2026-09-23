# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The storage protocol that LocalBackend and RemoteBackend implement.

Callers depend on :class:`Store` only, never on a concrete backend.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID

from hackagent.storage.records import (
    OrganizationContext,
    AgentRecord,
    AttackRecord,
    RunRecord,
    ResultRecord,
    TraceRecord,
    PaginatedResult,
)


# ---------------------------------------------------------------------------
# Store protocol
# ---------------------------------------------------------------------------


class Store(Protocol):
    """
    Common interface for storage backends.

    All methods are synchronous.  The protocol uses duck-typing so concrete
    backends do not need to explicitly inherit from this class.
    """

    # ── Context ──────────────────────────────────────────────────────────────
    def get_context(self) -> OrganizationContext:
        """Return the org / user context associated with this backend."""
        ...

    def get_api_key(self) -> Optional[str]:
        """Return the API key used by this backend, or None (local mode)."""
        ...

    # ── Lifecycle ──────────────────────────────────────────────────────────────
    def flush(self) -> None:
        """Block until all deferred writes are persisted (no-op if synchronous)."""
        ...

    def close(self) -> None:
        """Release resources / stop background workers. Idempotent."""
        ...

    # ── Agent ─────────────────────────────────────────────────────────────────
    def create_or_update_agent(
        self,
        name: str,
        agent_type: str,
        endpoint: str,
        metadata: Dict[str, Any],
        overwrite_metadata: bool = True,
    ) -> AgentRecord:
        """Create a new agent or update an existing one with the same name."""
        ...

    def list_agents(
        self, page: int = 1, page_size: int = 100
    ) -> PaginatedResult[AgentRecord]: ...

    def get_agent(self, agent_id: UUID) -> AgentRecord: ...

    def delete_agent(self, agent_id: UUID) -> None: ...

    # ── Attack ────────────────────────────────────────────────────────────────
    def create_attack(
        self,
        attack_type: str,
        agent_id: UUID,
        organization: UUID,
        configuration: Dict[str, Any],
    ) -> AttackRecord: ...

    def list_attacks(
        self, page: int = 1, page_size: int = 100
    ) -> PaginatedResult[AttackRecord]: ...

    # ── Run ───────────────────────────────────────────────────────────────────
    def create_run(
        self,
        attack_id: UUID,
        agent_id: UUID,
        run_config: Dict[str, Any],
    ) -> RunRecord: ...

    def update_run(
        self,
        run_id: UUID,
        status: Optional[str] = None,
        run_notes: Optional[str] = None,
        run_config: Optional[Dict[str, Any]] = None,
    ) -> RunRecord: ...

    def list_runs(
        self,
        attack_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> PaginatedResult[RunRecord]: ...

    def get_run(self, run_id: UUID) -> RunRecord: ...

    def delete_run(self, run_id: UUID) -> None: ...

    def delete_attack(self, attack_id: UUID) -> None: ...

    # ── Result ────────────────────────────────────────────────────────────────
    def create_result(
        self,
        run_id: UUID,
        goal: str,
        goal_index: int,
        request_payload: Dict[str, Any],
        agent_specific_data: Dict[str, Any],
    ) -> ResultRecord: ...

    def update_result(
        self,
        result_id: UUID,
        evaluation_status: Optional[str] = None,
        evaluation_notes: Optional[str] = None,
        evaluation_metrics: Optional[Dict[str, Any]] = None,
        agent_specific_data: Optional[Dict[str, Any]] = None,
    ) -> ResultRecord: ...

    def list_results(
        self,
        run_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> PaginatedResult[ResultRecord]: ...

    def get_result(self, result_id: UUID) -> ResultRecord: ...

    # ── Trace ─────────────────────────────────────────────────────────────────
    def create_trace(
        self,
        result_id: UUID,
        sequence: int,
        step_type: str,
        content: Dict[str, Any],
    ) -> TraceRecord: ...

    def list_traces(self, result_id: UUID) -> List[TraceRecord]: ...

    def count_result_buckets(self) -> Dict[str, int]:
        """Return {total, jailbreaks, mitigated, failed, pending} across all results."""
        ...
