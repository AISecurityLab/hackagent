# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
RemoteBackend — StorageBackend implementation backed by api.hackagent.dev.

This backend centralises all HTTP calls that were previously scattered across
AgentRouter, AttackOrchestrator, Tracker, and StepTracker.  It is instantiated
when an API key is available and selected automatically by HackAgent.__init__.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from hackagent.server.client import AuthenticatedClient
from hackagent.server.api.agent import agent_create, agent_list, agent_partial_update
from hackagent.server.api.organization import organization_me_retrieve
from hackagent.server.api.attack import attack_create, attack_list
from hackagent.server.api.run import (
    run_list,
    run_partial_update,
    run_retrieve,
    run_run_tests_create,
)
from hackagent.server.api.result import (
    result_create,
    result_list,
    result_partial_update,
    result_retrieve,
    result_trace_create,
)
from hackagent.server.api.models import (
    AgentRequest,
    AttackRequest,
    EvaluationStatusEnum,
    PatchedAgentRequest,
    PatchedResultRequest,
    PatchedRunRequest,
    ResultRequest,
    RunRequest,
    StatusEnum,
    StepTypeEnum,
    TraceRequest,
)
from hackagent.server.storage.base import (
    AgentRecord,
    AttackRecord,
    OrganizationContext,
    PaginatedResult,
    ResultRecord,
    RunRecord,
    TraceRecord,
)

logger = logging.getLogger("hackagent.server.storage.remote")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _pick_dt(obj: Any, *names: str) -> datetime:
    """Return first available datetime-like attribute from object, else now."""
    for name in names:
        value = getattr(obj, name, None)
        if value:
            return value
    return _now()


def _coerce_trace_id(raw_id: Any, result_id: UUID, sequence: int) -> UUID:
    """Normalize API trace IDs to UUID for TraceRecord compatibility.

    Remote Trace IDs are integer-based in the current API schema, so int IDs are
    expected and converted deterministically without logging a warning.
    """
    if isinstance(raw_id, UUID):
        return raw_id

    if isinstance(raw_id, str):
        try:
            return UUID(raw_id)
        except ValueError:
            pass

    if isinstance(raw_id, int):
        return uuid.uuid5(uuid.NAMESPACE_URL, f"trace:{result_id}:{sequence}:{raw_id}")

    try:
        logger.warning(
            "RemoteBackend: received non-UUID trace id=%r (type=%s); "
            "using deterministic UUID fallback",
            raw_id,
            type(raw_id).__name__,
        )
    except Exception:
        # Never fail tracing due to logging handler misconfiguration.
        pass
    return uuid.uuid5(uuid.NAMESPACE_URL, f"trace:{result_id}:{sequence}:{raw_id}")


def _to_agent_record(agent) -> AgentRecord:
    """Convert an API Agent model to an AgentRecord."""
    return AgentRecord(
        id=agent.id,
        name=agent.name,
        agent_type=agent.agent_type.value
        if hasattr(agent.agent_type, "value")
        else str(agent.agent_type),
        endpoint=str(agent.endpoint) if agent.endpoint else "",
        metadata=agent.metadata if isinstance(agent.metadata, dict) else {},
        organization=agent.organization,
        owner=str(agent.owner) if agent.owner is not None else "unknown",
        created_at=agent.created_at
        if hasattr(agent, "created_at") and agent.created_at
        else _now(),
        updated_at=agent.updated_at
        if hasattr(agent, "updated_at") and agent.updated_at
        else _now(),
    )


class RemoteBackend:
    """
    StorageBackend implementation that talks to api.hackagent.dev.

    Wraps all HTTP calls behind the StorageBackend interface so that the rest
    of the SDK is entirely decoupled from HTTP concerns.
    """

    def __init__(self, client: AuthenticatedClient) -> None:
        self._client = client
        self._context: Optional[OrganizationContext] = None  # cached

    # ── Context ──────────────────────────────────────────────────────────────

    def get_api_key(self) -> Optional[str]:
        return self._client.token

    def get_context(self) -> OrganizationContext:
        """Fetch org_id and user_id from the first agent (cached after first call)."""
        if self._context is not None:
            return self._context

        response = agent_list.sync_detailed(client=self._client)
        if response.status_code == 200 and response.parsed and response.parsed.results:
            first = response.parsed.results[0]
            self._context = OrganizationContext(
                org_id=first.organization,
                user_id=str(first.owner) if first.owner is not None else "unknown",
            )
            return self._context

        # New accounts may legitimately have zero agents. In that case, resolve
        # the organization directly from the dedicated endpoint and keep user_id
        # as unknown (it is only required for specific adapter flows like ADK).
        org_response = organization_me_retrieve.sync_detailed(client=self._client)
        if org_response.status_code == 200 and org_response.parsed:
            self._context = OrganizationContext(
                org_id=org_response.parsed.id,
                user_id="unknown",
            )
            return self._context

        raise RuntimeError(
            "RemoteBackend: Cannot determine organization context. "
            "No agents exist, and /organization/me lookup failed. "
            f"agent_list_status={response.status_code}, "
            f"agent_list_body={response.content!r}, "
            f"organization_me_status={org_response.status_code}, "
            f"organization_me_body={org_response.content!r}."
        )

    # ── Agent ─────────────────────────────────────────────────────────────────

    def _update_existing_agent(
        self,
        existing: Any,
        agent_type: str,
        endpoint: str,
        metadata: Dict[str, Any],
        overwrite_metadata: bool,
    ) -> AgentRecord:
        """Update an existing agent record, or return it unchanged."""
        if not overwrite_metadata:
            return _to_agent_record(existing)

        patch_kwargs: Dict[str, Any] = {}
        current_meta = existing.metadata if isinstance(existing.metadata, dict) else {}
        merged_meta = {**current_meta, **metadata}
        patch_kwargs["metadata"] = {
            k: v for k, v in merged_meta.items() if v is not None
        }
        patch_kwargs["agent_type"] = agent_type
        patch_kwargs["endpoint"] = endpoint

        body = PatchedAgentRequest(**patch_kwargs)
        resp = agent_partial_update.sync_detailed(
            id=existing.id, client=self._client, body=body
        )
        if resp.status_code < 300 and resp.parsed:
            return _to_agent_record(resp.parsed)
        return _to_agent_record(existing)

    def create_or_update_agent(
        self,
        name: str,
        agent_type: str,
        endpoint: str,
        metadata: Dict[str, Any],
        overwrite_metadata: bool = True,
    ) -> AgentRecord:
        existing = self._find_agent_by_name(name)

        if existing:
            return self._update_existing_agent(
                existing=existing,
                agent_type=agent_type,
                endpoint=endpoint,
                metadata=metadata,
                overwrite_metadata=overwrite_metadata,
            )

        body = AgentRequest(
            name=name,
            endpoint=endpoint,
            agent_type=agent_type,
            metadata={k: v for k, v in metadata.items() if v is not None},
            description=f"Agent managed by hackagent SDK: {name}",
        )
        resp = agent_create.sync_detailed(client=self._client, body=body)
        if resp.status_code == 201 and resp.parsed:
            return _to_agent_record(resp.parsed)

        # Some backend deployments may return 5xx for duplicate names.
        # Retry lookup and convert to update semantics instead of crashing.
        recovered_existing = self._find_agent_by_name(name)
        if recovered_existing:
            logger.warning(
                "RemoteBackend: create for existing agent name '%s' returned %s; "
                "falling back to update path",
                name,
                resp.status_code,
            )
            return self._update_existing_agent(
                existing=recovered_existing,
                agent_type=agent_type,
                endpoint=endpoint,
                metadata=metadata,
                overwrite_metadata=overwrite_metadata,
            )

        raise RuntimeError(
            f"RemoteBackend: Failed to create agent '{name}' "
            f"(status {resp.status_code}, body={resp.content!r})"
        )

    def _find_agent_by_name(self, name: str):
        """Return the first agent matching name in the current org, or None."""
        page = 1
        while True:
            resp = agent_list.sync_detailed(client=self._client, page=page)
            if resp.status_code != 200 or not resp.parsed:
                break
            for a in resp.parsed.results or []:
                if a.name == name:
                    return a
            next_page = getattr(resp.parsed, "next", None)
            if next_page is None:
                next_page = getattr(resp.parsed, "next_", None)
            has_next_page = bool(next_page)
            if not has_next_page:
                break
            page += 1
        return None

    def list_agents(
        self, page: int = 1, page_size: int = 100
    ) -> PaginatedResult[AgentRecord]:
        # Agent endpoint currently supports page but not page_size.
        resp = agent_list.sync_detailed(client=self._client, page=page)
        if resp.status_code == 200 and resp.parsed:
            items = [_to_agent_record(a) for a in (resp.parsed.results or [])]
            return PaginatedResult(items=items, total=resp.parsed.count or len(items))
        return PaginatedResult(items=[], total=0)

    def get_agent(self, agent_id: UUID) -> AgentRecord:
        from hackagent.server.api.agent import agent_retrieve

        resp = agent_retrieve.sync_detailed(id=agent_id, client=self._client)
        if resp.status_code == 200 and resp.parsed:
            return _to_agent_record(resp.parsed)
        raise RuntimeError(f"RemoteBackend: Agent {agent_id} not found")

    def delete_agent(self, agent_id: UUID) -> None:
        from hackagent.server.api.agent import agent_destroy

        agent_destroy.sync_detailed(id=agent_id, client=self._client)

    # ── Attack ────────────────────────────────────────────────────────────────

    def create_attack(
        self,
        attack_type: str,
        agent_id: UUID,
        organization: UUID,
        configuration: Dict[str, Any],
    ) -> AttackRecord:
        body = AttackRequest.model_validate(
            {
                "type": attack_type,
                "agent": str(agent_id),
                "organization": str(organization),
                "configuration": configuration,
            }
        )
        resp = attack_create.sync_detailed(client=self._client, body=body)
        if resp.status_code == 201:
            data = self._parse_json_response(resp)
            attack_id = data.get("id") or str(data.get("pk", ""))
            return AttackRecord(
                id=UUID(attack_id),
                type=attack_type,
                agent_id=agent_id,
                organization=organization,
                configuration=configuration,
                created_at=_now(),
            )
        raise RuntimeError(
            f"RemoteBackend: Failed to create attack record (status {resp.status_code})"
        )

    def list_attacks(
        self, page: int = 1, page_size: int = 100
    ) -> PaginatedResult[AttackRecord]:
        resp = attack_list.sync_detailed(client=self._client, page=page)
        if resp.status_code == 200 and resp.parsed:
            items = []
            for a in resp.parsed.results or []:
                items.append(
                    AttackRecord(
                        id=a.id,
                        type=a.type.value if hasattr(a.type, "value") else str(a.type),
                        agent_id=a.agent,
                        organization=a.organization,
                        configuration=a.configuration
                        if isinstance(a.configuration, dict)
                        else {},
                        created_at=a.created_at
                        if hasattr(a, "created_at") and a.created_at
                        else _now(),
                    )
                )
            return PaginatedResult(items=items, total=resp.parsed.count or len(items))
        return PaginatedResult(items=[], total=0)

    # ── Run ───────────────────────────────────────────────────────────────────

    def create_run(
        self,
        attack_id: UUID,
        agent_id: UUID,
        run_config: Dict[str, Any],
    ) -> RunRecord:
        body = RunRequest(
            attack=str(attack_id),
            agent=str(agent_id),
            run_config=run_config,
        )
        resp = run_run_tests_create.sync_detailed(client=self._client, body=body)
        if resp.status_code in (200, 201):
            data = self._parse_json_response(resp)
            run_id = data.get("id") or str(data.get("pk", ""))
            return RunRecord(
                id=UUID(run_id),
                attack_id=attack_id,
                agent_id=agent_id,
                run_config=run_config,
                status="PENDING",
                run_notes=None,
                created_at=_now(),
                updated_at=_now(),
            )
        raise RuntimeError(
            f"RemoteBackend: Failed to create run record (status {resp.status_code})"
        )

    def update_run(
        self,
        run_id: UUID,
        status: Optional[str] = None,
        run_notes: Optional[str] = None,
    ) -> RunRecord:
        kwargs: Dict[str, Any] = {}
        if status is not None:
            try:
                kwargs["status"] = StatusEnum(status)
            except ValueError:
                kwargs["status"] = status
        if run_notes is not None:
            kwargs["run_notes"] = run_notes
        body = PatchedRunRequest(**kwargs)
        resp = run_partial_update.sync_detailed(
            id=run_id, client=self._client, body=body
        )
        if resp.status_code < 300:
            return RunRecord(
                id=run_id,
                attack_id=UUID("00000000-0000-0000-0000-000000000000"),
                agent_id=UUID("00000000-0000-0000-0000-000000000000"),
                run_config={},
                status=status or "UNKNOWN",
                run_notes=run_notes,
                created_at=_now(),
                updated_at=_now(),
            )
        logger.warning(
            f"RemoteBackend: update_run {run_id} returned {resp.status_code}"
        )
        return RunRecord(
            id=run_id,
            attack_id=UUID("00000000-0000-0000-0000-000000000000"),
            agent_id=UUID("00000000-0000-0000-0000-000000000000"),
            run_config={},
            status=status or "",
            run_notes=run_notes,
            created_at=_now(),
            updated_at=_now(),
        )

    def list_runs(
        self,
        attack_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> PaginatedResult[RunRecord]:
        items: List[RunRecord] = []
        total = 0
        current_page = max(1, int(page))
        remaining = max(1, int(page_size))

        while remaining > 0:
            run_kwargs: Dict[str, Any] = {
                "client": self._client,
                "page": current_page,
                "page_size": remaining,
            }
            if attack_id is not None:
                run_kwargs["attack"] = attack_id

            resp = run_list.sync_detailed(**run_kwargs)
            if resp.status_code != 200 or not resp.parsed:
                break

            page_results = resp.parsed.results or []
            total = resp.parsed.count or total

            for r in page_results:
                items.append(
                    RunRecord(
                        id=r.id,
                        attack_id=r.attack
                        if isinstance(r.attack, UUID)
                        else UUID(str(r.attack)),
                        agent_id=r.agent
                        if isinstance(r.agent, UUID)
                        else UUID(str(r.agent)),
                        run_config=r.run_config
                        if isinstance(r.run_config, dict)
                        else {},
                        status=r.status.value
                        if hasattr(r.status, "value")
                        else str(r.status),
                        run_notes=getattr(r, "run_notes", None),
                        created_at=_pick_dt(r, "timestamp", "created_at"),
                        updated_at=_pick_dt(r, "updated_at", "timestamp"),
                    )
                )

            remaining -= len(page_results)
            next_page = getattr(resp.parsed, "next", None)
            if not isinstance(next_page, str) or not next_page.strip():
                next_page = getattr(resp.parsed, "next_", None)
            has_next_page = isinstance(next_page, str) and bool(next_page.strip())
            if remaining <= 0 or not has_next_page or not page_results:
                break
            current_page += 1

        return PaginatedResult(items=items, total=total or len(items))

    def get_run(self, run_id: UUID) -> RunRecord:
        resp = run_retrieve.sync_detailed(id=run_id, client=self._client)
        if resp.status_code == 200 and resp.parsed:
            r = resp.parsed
            return RunRecord(
                id=r.id,
                attack_id=r.attack
                if isinstance(r.attack, UUID)
                else UUID(str(r.attack)),
                agent_id=r.agent if isinstance(r.agent, UUID) else UUID(str(r.agent)),
                run_config=r.run_config if isinstance(r.run_config, dict) else {},
                status=r.status.value if hasattr(r.status, "value") else str(r.status),
                run_notes=getattr(r, "run_notes", None),
                created_at=_pick_dt(r, "timestamp", "created_at"),
                updated_at=_pick_dt(r, "updated_at", "timestamp"),
            )
        raise RuntimeError(f"RemoteBackend: Run {run_id} not found")

    # ── Result ────────────────────────────────────────────────────────────────

    def create_result(
        self,
        run_id: UUID,
        goal: str,
        goal_index: int,
        request_payload: Dict[str, Any],
        agent_specific_data: Dict[str, Any],
    ) -> ResultRecord:
        body = ResultRequest(
            run=run_id,
            request_payload=request_payload,
            evaluation_status=EvaluationStatusEnum.NOT_EVALUATED,
            agent_specific_data=agent_specific_data,
        )
        resp = result_create.sync_detailed(client=self._client, body=body)
        if resp.status_code == 201 and resp.parsed:
            r = resp.parsed
            return ResultRecord(
                id=r.id,
                run_id=run_id,
                goal=goal,
                goal_index=goal_index,
                evaluation_status=EvaluationStatusEnum.NOT_EVALUATED.value,
                evaluation_notes=None,
                evaluation_metrics={},
                metadata=agent_specific_data,
                created_at=_pick_dt(r, "timestamp", "created_at"),
                updated_at=_pick_dt(r, "updated_at", "timestamp"),
            )
        raise RuntimeError(
            f"RemoteBackend: Failed to create result "
            f"(status {resp.status_code}, body={resp.content!r})"
        )

    def update_result(
        self,
        result_id: UUID,
        evaluation_status: Optional[str] = None,
        evaluation_notes: Optional[str] = None,
        evaluation_metrics: Optional[Dict[str, Any]] = None,
        agent_specific_data: Optional[Dict[str, Any]] = None,
    ) -> ResultRecord:
        kwargs: Dict[str, Any] = {}
        if evaluation_status is not None:
            try:
                kwargs["evaluation_status"] = EvaluationStatusEnum(evaluation_status)
            except ValueError:
                kwargs["evaluation_status"] = evaluation_status
        if evaluation_notes is not None:
            kwargs["evaluation_notes"] = evaluation_notes
        if agent_specific_data is not None:
            kwargs["agent_specific_data"] = agent_specific_data
        body = PatchedResultRequest(**kwargs)
        resp = result_partial_update.sync_detailed(
            id=result_id, client=self._client, body=body
        )
        if resp.status_code >= 300:
            logger.warning(
                f"RemoteBackend: update_result {result_id} returned {resp.status_code}"
            )
        return ResultRecord(
            id=result_id,
            run_id=UUID("00000000-0000-0000-0000-000000000000"),
            goal="",
            goal_index=0,
            evaluation_status=evaluation_status or "",
            evaluation_notes=evaluation_notes,
            evaluation_metrics=evaluation_metrics or {},
            metadata=agent_specific_data or {},
            created_at=_now(),
            updated_at=_now(),
        )

    def list_results(
        self,
        run_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> PaginatedResult[ResultRecord]:
        items: List[ResultRecord] = []
        total = 0
        current_page = max(1, int(page))
        remaining = max(1, int(page_size))

        while remaining > 0:
            result_kwargs: Dict[str, Any] = {
                "client": self._client,
                "page": current_page,
            }
            if run_id is not None:
                result_kwargs["run"] = run_id

            resp = result_list.sync_detailed(**result_kwargs)
            if resp.status_code != 200 or not resp.parsed:
                break

            page_results = resp.parsed.results or []
            total = resp.parsed.count or total

            for r in page_results:
                goal = ""
                goal_index = 0
                if isinstance(r.agent_specific_data, dict):
                    goal = r.agent_specific_data.get("goal", "")
                    goal_index = r.agent_specific_data.get("goal_index", 0)
                items.append(
                    ResultRecord(
                        id=r.id,
                        run_id=r.run if isinstance(r.run, UUID) else UUID(str(r.run)),
                        goal=goal,
                        goal_index=goal_index,
                        evaluation_status=r.evaluation_status.value
                        if hasattr(r.evaluation_status, "value")
                        else str(r.evaluation_status),
                        evaluation_notes=getattr(r, "evaluation_notes", None),
                        evaluation_metrics=getattr(r, "evaluation_metrics", {}) or {},
                        metadata=r.agent_specific_data
                        if isinstance(r.agent_specific_data, dict)
                        else {},
                        created_at=_pick_dt(r, "timestamp", "created_at"),
                        updated_at=_pick_dt(r, "updated_at", "timestamp"),
                    )
                )

            remaining -= len(page_results)
            next_page = getattr(resp.parsed, "next", None)
            if not isinstance(next_page, str) or not next_page.strip():
                next_page = getattr(resp.parsed, "next_", None)
            has_next_page = isinstance(next_page, str) and bool(next_page.strip())
            if remaining <= 0 or not has_next_page or not page_results:
                break
            current_page += 1

        return PaginatedResult(items=items, total=total or len(items))

    def get_result(self, result_id: UUID) -> ResultRecord:
        resp = result_retrieve.sync_detailed(id=result_id, client=self._client)
        if resp.status_code == 200 and resp.parsed:
            r = resp.parsed
            goal = ""
            goal_index = 0
            if isinstance(r.agent_specific_data, dict):
                goal = r.agent_specific_data.get("goal", "")
                goal_index = r.agent_specific_data.get("goal_index", 0)
            return ResultRecord(
                id=r.id,
                run_id=r.run if isinstance(r.run, UUID) else UUID(str(r.run)),
                goal=goal,
                goal_index=goal_index,
                evaluation_status=r.evaluation_status.value
                if hasattr(r.evaluation_status, "value")
                else str(r.evaluation_status),
                evaluation_notes=getattr(r, "evaluation_notes", None),
                evaluation_metrics=getattr(r, "evaluation_metrics", {}) or {},
                metadata=r.agent_specific_data
                if isinstance(r.agent_specific_data, dict)
                else {},
                created_at=_pick_dt(r, "timestamp", "created_at"),
                updated_at=_pick_dt(r, "updated_at", "timestamp"),
            )
        raise RuntimeError(f"RemoteBackend: Result {result_id} not found")

    # ── Trace ─────────────────────────────────────────────────────────────────

    def create_trace(
        self,
        result_id: UUID,
        sequence: int,
        step_type: str,
        content: Dict[str, Any],
    ) -> TraceRecord:
        try:
            step_type_enum = StepTypeEnum(step_type)
        except ValueError:
            step_type_enum = StepTypeEnum.OTHER
        body = TraceRequest(
            sequence=sequence, step_type=step_type_enum, content=content
        )
        resp = result_trace_create.sync_detailed(
            client=self._client, id=result_id, body=body
        )
        if resp.status_code == 201 and resp.parsed:
            return TraceRecord(
                id=_coerce_trace_id(
                    resp.parsed.id, result_id=result_id, sequence=sequence
                ),
                result_id=result_id,
                sequence=sequence,
                step_type=step_type,
                content=content,
                created_at=_now(),
            )
        logger.warning(
            f"RemoteBackend: create_trace for result {result_id} "
            f"returned {resp.status_code}"
        )
        return TraceRecord(
            id=uuid.uuid4(),
            result_id=result_id,
            sequence=sequence,
            step_type=step_type,
            content=content,
            created_at=_now(),
        )

    def list_traces(self, result_id: UUID) -> List[TraceRecord]:
        # Traces are written-only via the API; return empty list for now
        return []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_json_response(self, response) -> Dict[str, Any]:
        """Parse JSON from an httpx response, falling back to parsed attributes."""
        import json

        if response.content:
            try:
                return json.loads(response.content.decode("utf-8", errors="replace"))
            except (json.JSONDecodeError, AttributeError):
                pass
        if hasattr(response, "parsed") and response.parsed:
            if hasattr(response.parsed, "additional_properties"):
                return response.parsed.additional_properties or {}
            if isinstance(response.parsed, dict):
                return response.parsed
        return {}
