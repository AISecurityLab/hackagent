# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""A remote store that runs a campaign inside a run the server already made.

The campaign runner registers its target agent, creates the campaign run and
finishes it, as it does for a campaign file. A queued run already has its
agent and its campaign run, and may be executed with a run token that cannot
list or create agents. :class:`AdoptedRunStore` hands the runner those
existing records instead, and holds back the final status so the executor
ends the run once, with a note that says why it ended.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional
from uuid import UUID

from hackagent.core.contracts import RunStatus
from hackagent.storage.records import (
    AgentRecord,
    CampaignRunRecord,
    OrganizationContext,
)
from hackagent.storage.remote import RemoteBackend

_FINAL_STATUSES = frozenset(
    {RunStatus.COMPLETED.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value}
)


class AdoptedRunStore(RemoteBackend):
    """:class:`RemoteBackend` bound to the campaign run ``run_id`` of ``agent_id``.

    Child runs, attacks, results and traces go to the server unchanged.
    """

    def __init__(
        self,
        client: Any,
        *,
        run_id: UUID,
        agent_id: UUID,
        organization_id: UUID,
        user_id: str = "unknown",
    ) -> None:
        super().__init__(client)
        self.run_id = run_id
        self.agent_id = agent_id
        self._adopted_context = OrganizationContext(
            org_id=organization_id, user_id=user_id
        )
        self._record: Optional[CampaignRunRecord] = None
        #: ``(status, note)`` the runner ended the campaign run with, not yet
        #: sent to the server.
        self.final_status: Optional[tuple[str, str]] = None

    @classmethod
    def for_run(cls, client: Any, run: Mapping[str, Any]) -> AdoptedRunStore:
        """The store for ``run``, as the server returns it from a claim."""
        owner = run.get("owner")
        return cls(
            client,
            run_id=UUID(str(run["id"])),
            agent_id=UUID(str(run["agent"])),
            organization_id=UUID(str(run["organization"])),
            user_id=str(owner) if owner is not None else "unknown",
        )

    def get_context(self) -> OrganizationContext:
        return self._adopted_context

    def create_or_update_agent(self, name: str, config: Dict[str, Any]) -> AgentRecord:
        """The run's own agent; nothing is registered."""
        connection = config.get("connection") or {}
        now = datetime.now(timezone.utc)
        return AgentRecord(
            id=self.agent_id,
            name=name,
            agent_type=str(connection.get("type") or ""),
            endpoint=str(connection.get("endpoint") or ""),
            metadata=dict(config),
            organization=self._adopted_context.org_id,
            owner=self._adopted_context.user_id,
            created_at=now,
            updated_at=now,
        )

    def start_campaign(
        self,
        agent_id: UUID,
        spec: Dict[str, Any],
        *,
        claimed_by: Optional[str] = None,
    ) -> CampaignRunRecord:
        """The adopted campaign run; nothing is created."""
        now = datetime.now(timezone.utc)
        self._record = CampaignRunRecord(
            id=self.run_id,
            agent_id=self.agent_id,
            name=str((spec.get("campaign") or {}).get("name") or "Campaign"),
            campaign_config=dict(spec),
            audit=None,
            status=RunStatus.RUNNING.value,
            run_notes=None,
            created_at=now,
            updated_at=now,
        )
        return self._record

    def update_campaign_run(
        self,
        campaign_run_id: UUID,
        status: Optional[str] = None,
        audit: Optional[Dict[str, Any]] = None,
        run_notes: Optional[str] = None,
    ) -> CampaignRunRecord:
        """Send the audit and interim notes; keep a final status for the executor."""
        final = status in _FINAL_STATUSES
        if audit is not None or (run_notes is not None and not final):
            super().update_campaign_run(
                campaign_run_id,
                audit=audit,
                run_notes=None if final else run_notes,
            )
        elif final:
            # Lost result writes surface before the run can end as COMPLETED.
            self.flush()
        if final:
            self.final_status = (str(status), run_notes or "")
        record = self._record or self.start_campaign(self.agent_id, {})
        self._record = record.model_copy(
            update={
                "status": status or record.status,
                "audit": audit if audit is not None else record.audit,
                "run_notes": run_notes if run_notes is not None else record.run_notes,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        return self._record


__all__ = ["AdoptedRunStore"]
