# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The storage protocol that LocalBackend and RemoteBackend implement.

Callers depend on :class:`Store` only, never on a concrete backend.
The backend is chosen explicitly (``Settings.mode`` for
:class:`~hackagent.client.HackAgent`, ``storage.backend`` for a campaign),
never inferred from whether an API key is present.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID

from hackagent.storage.records import (
    OrganizationContext,
    AgentRecord,
    AttackRecord,
    CampaignRunRecord,
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

    def get_api_key(self) -> Optional[str]:
        """Return the API key used by this backend, or None (local mode)."""

    # ── Lifecycle ──────────────────────────────────────────────────────────────
    def flush(self) -> None:
        """Block until all deferred writes are persisted (no-op if synchronous)."""

    def close(self) -> None:
        """Release resources / stop background workers. Idempotent."""

    # ── Agent ─────────────────────────────────────────────────────────────────
    def create_or_update_agent(self, name: str, config: Dict[str, Any]) -> AgentRecord:
        """Create the agent ``name``, or replace the config of the one that
        exists. ``config`` is a dumped ``ModelConfig``; the record's
        ``agent_type`` and ``endpoint`` come from its connection."""

    def list_agents(
        self, page: int = 1, page_size: int = 100
    ) -> PaginatedResult[AgentRecord]:
        """Return one page of the organization's agents.

        Args:
            page: 1-based page number.
            page_size: Agents per page. A backend whose API pages with a fixed
                size may ignore it.

        Returns:
            The page of agents and the total count.
        """

    def get_agent(self, agent_id: UUID) -> AgentRecord:
        """Return the agent ``agent_id``.

        Raises:
            RuntimeError: When no such agent exists.
        """

    def delete_agent(self, agent_id: UUID) -> None:
        """Delete the agent ``agent_id``."""

    # ── Attack ────────────────────────────────────────────────────────────────
    def create_attack(
        self,
        attack_type: str,
        agent_id: UUID,
        organization: UUID,
        configuration: Dict[str, Any],
    ) -> AttackRecord:
        """Record an attack configuration against an agent.

        Args:
            attack_type: Canonical attack id, e.g. ``"pair"``.
            agent_id: The targeted agent.
            organization: The owning organization, from :meth:`get_context`.
            configuration: The attack's configuration as stored for audit.

        Returns:
            The new attack record.

        Raises:
            RuntimeError: When the backend refuses the write.
        """

    def list_attacks(
        self, page: int = 1, page_size: int = 100
    ) -> PaginatedResult[AttackRecord]:
        """Return one page of attacks, newest first where the backend orders."""

    # ── Campaign run ─────────────────────────────────────────────────────────
    def start_campaign(self, agent_id: UUID, spec: Dict[str, Any]) -> CampaignRunRecord:
        """Record a run of the campaign ``spec`` (its recorded form) against
        the agent, already RUNNING. The run is named after the campaign."""

    def update_campaign_run(
        self,
        campaign_run_id: UUID,
        status: Optional[str] = None,
        audit: Optional[Dict[str, Any]] = None,
        run_notes: Optional[str] = None,
    ) -> CampaignRunRecord:
        """Change what was given. ``None`` leaves a field as it is; pass ``""``
        to clear a note an earlier update wrote. A final status (COMPLETED,
        FAILED, CANCELLED) ends the run with ``run_notes`` as its note."""

    def list_campaign_runs(
        self, page: int = 1, page_size: int = 100
    ) -> PaginatedResult[CampaignRunRecord]:
        """Return one page of campaign runs, newest first."""

    def get_campaign_run(self, campaign_run_id: UUID) -> CampaignRunRecord:
        """Return the campaign run ``campaign_run_id``.

        Raises:
            RuntimeError: When no such campaign run exists.
        """

    # ── Run ───────────────────────────────────────────────────────────────────
    def create_run(
        self,
        attack_id: UUID,
        agent_id: UUID,
        run_config: Dict[str, Any],
        campaign_run_id: Optional[UUID] = None,
    ) -> RunRecord:
        """Record one attack run. The remote store creates it as a child of
        ``campaign_run_id``, which it therefore requires."""

    def update_run(
        self,
        run_id: UUID,
        status: Optional[str] = None,
        run_notes: Optional[str] = None,
        run_config: Optional[Dict[str, Any]] = None,
    ) -> RunRecord:
        """Change the given fields of an attack run.

        ``None`` leaves a field unchanged. A final status (COMPLETED, FAILED,
        CANCELLED) ends the run with ``run_notes`` as its note.

        Returns:
            The run as updated. Backends that do not read the row back return
            a record with only the fields that were passed.
        """

    def list_runs(
        self,
        attack_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> PaginatedResult[RunRecord]:
        """Return one page of attack runs, optionally only those of one attack.

        Campaign runs are never listed here; see :meth:`list_campaign_runs`.
        """

    def get_run(self, run_id: UUID) -> RunRecord:
        """Return the attack run ``run_id``.

        Raises:
            RuntimeError: When no such run exists.
        """

    def delete_run(self, run_id: UUID) -> None:
        """Delete an attack run together with its results and traces."""

    def delete_attack(self, attack_id: UUID) -> None:
        """Delete an attack together with its runs, results and traces."""

    # ── Result ────────────────────────────────────────────────────────────────
    def create_result(
        self,
        run_id: UUID,
        goal: str,
        goal_index: int,
        request_payload: Dict[str, Any],
        agent_specific_data: Dict[str, Any],
    ) -> ResultRecord:
        """Record one goal attempt of a run, not yet evaluated.

        Args:
            run_id: The attack run the attempt belongs to.
            goal: The goal text.
            goal_index: Position of the goal in the campaign's goal list.
            request_payload: What was sent to the target.
            agent_specific_data: Adapter-specific response data, stored as the
                result's metadata.

        Returns:
            The new result, with evaluation status ``NOT_EVALUATED``.

        Raises:
            RuntimeError: When the backend refuses the write.
        """

    def update_result(
        self,
        result_id: UUID,
        evaluation_status: Optional[str] = None,
        evaluation_notes: Optional[str] = None,
        evaluation_metrics: Optional[Dict[str, Any]] = None,
        agent_specific_data: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[int] = None,
        response_status_code: Optional[int] = None,
    ) -> ResultRecord:
        """Change the given fields of a result, typically its evaluation.

        ``None`` leaves a field unchanged. A backend may defer the write (see
        :meth:`flush`); the returned record then carries only the fields
        that were passed.

        Args:
            result_id: The result to update.
            evaluation_status: An evaluation status such as
                ``SUCCESSFUL_JAILBREAK`` or ``FAILED_JAILBREAK``.
            evaluation_notes: The judge's explanation.
            evaluation_metrics: Per-judge scores and metrics.
            agent_specific_data: Replaces the result's metadata.
            latency_ms: Target response time in milliseconds.
            response_status_code: HTTP status the target answered with.
        """

    def list_results(
        self,
        run_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> PaginatedResult[ResultRecord]:
        """Return one page of results, optionally only those of one run."""

    def get_result(self, result_id: UUID) -> ResultRecord:
        """Return the result ``result_id``.

        Raises:
            RuntimeError: When no such result exists.
        """

    # ── Trace ─────────────────────────────────────────────────────────────────
    def create_trace(
        self,
        result_id: UUID,
        sequence: int,
        step_type: str,
        content: Dict[str, Any],
    ) -> TraceRecord:
        """Append one step to a result's trace.

        A backend may defer the write (see :meth:`flush`), in which case the
        returned record's id is synthetic.

        Args:
            result_id: The result the step belongs to.
            sequence: Position of the step within the result's trace.
            step_type: Step kind, e.g. ``TOOL_CALL`` or ``OTHER``. The remote
                backend stores a kind its API does not know as ``OTHER``.
            content: The step payload.
        """

    def list_traces(self, result_id: UUID) -> List[TraceRecord]:
        """Return the trace steps of a result, ordered by ``sequence``."""

    def count_result_buckets(self) -> Dict[str, int]:
        """Count all results by reporting bucket.

        Returns:
            A dict with the keys ``total``, ``jailbreaks``, ``mitigated``,
            ``error`` and ``pending``.
        """
