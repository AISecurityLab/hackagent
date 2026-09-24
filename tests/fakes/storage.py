# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Storage doubles.

``in_memory_store`` is a real ``LocalBackend`` on SQLite ``:memory:``.
``RecordingStore`` is a pure fake: it records every call and serves the
records a test seeded, so facade and interface tests never open SQLite.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from hackagent.storage.local import LocalBackend
from hackagent.storage.records import (
    AgentRecord,
    AttackRecord,
    OrganizationContext,
    PaginatedResult,
    ResultRecord,
    RunRecord,
    TraceRecord,
)


def in_memory_store() -> LocalBackend:
    """Return a ``LocalBackend`` backed by an in-memory SQLite database."""
    return LocalBackend(db_path=":memory:")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RecordingStore:
    """Store double that records calls and returns seeded records."""

    def __init__(self) -> None:
        self.calls: List[tuple] = []
        self.closed = False
        self.context = OrganizationContext(org_id=uuid4(), user_id="local")
        self.agents: Dict[UUID, AgentRecord] = {}
        self.attacks: Dict[UUID, AttackRecord] = {}
        self.runs: Dict[UUID, RunRecord] = {}
        self.results: Dict[UUID, ResultRecord] = {}
        self.traces: Dict[UUID, List[TraceRecord]] = {}

    def call_names(self) -> List[str]:
        return [name for name, _args, _kwargs in self.calls]

    def _note(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((name, args, kwargs))

    def get_context(self) -> OrganizationContext:
        self._note("get_context")
        return self.context

    def get_api_key(self) -> Optional[str]:
        self._note("get_api_key")
        return None

    def flush(self) -> None:
        self._note("flush")

    def close(self) -> None:
        self._note("close")
        self.closed = True

    def create_or_update_agent(
        self,
        name: str,
        agent_type: str,
        endpoint: str,
        metadata: Dict[str, Any],
        overwrite_metadata: bool = True,
    ) -> AgentRecord:
        self._note(
            "create_or_update_agent",
            name,
            agent_type,
            endpoint,
            metadata,
            overwrite_metadata=overwrite_metadata,
        )
        now = _now()
        record = AgentRecord(
            id=uuid4(),
            name=name,
            agent_type=agent_type,
            endpoint=endpoint,
            metadata=dict(metadata),
            organization=self.context.org_id,
            owner=self.context.user_id,
            created_at=now,
            updated_at=now,
        )
        self.agents[record.id] = record
        return record

    def list_agents(
        self, page: int = 1, page_size: int = 100
    ) -> PaginatedResult[AgentRecord]:
        return self._page("list_agents", list(self.agents.values()), page, page_size)

    def get_agent(self, agent_id: UUID) -> AgentRecord:
        self._note("get_agent", agent_id)
        try:
            return self.agents[agent_id]
        except KeyError as exc:
            raise RuntimeError(f"agent {agent_id} not found") from exc

    def delete_agent(self, agent_id: UUID) -> None:
        self._note("delete_agent", agent_id)
        self.agents.pop(agent_id, None)

    def create_attack(
        self,
        attack_type: str,
        agent_id: UUID,
        organization: UUID,
        configuration: Dict[str, Any],
    ) -> AttackRecord:
        self._note("create_attack", attack_type, agent_id, organization, configuration)
        record = AttackRecord(
            id=uuid4(),
            type=attack_type,
            agent_id=agent_id,
            organization=organization,
            configuration=dict(configuration),
            created_at=_now(),
        )
        self.attacks[record.id] = record
        return record

    def list_attacks(
        self, page: int = 1, page_size: int = 100
    ) -> PaginatedResult[AttackRecord]:
        return self._page("list_attacks", list(self.attacks.values()), page, page_size)

    def create_run(
        self,
        attack_id: UUID,
        agent_id: UUID,
        run_config: Dict[str, Any],
    ) -> RunRecord:
        self._note("create_run", attack_id, agent_id, run_config)
        now = _now()
        record = RunRecord(
            id=uuid4(),
            attack_id=attack_id,
            agent_id=agent_id,
            run_config=dict(run_config),
            status="completed",
            run_notes=None,
            created_at=now,
            updated_at=now,
        )
        self.runs[record.id] = record
        return record

    def update_run(
        self,
        run_id: UUID,
        status: Optional[str] = None,
        run_notes: Optional[str] = None,
        run_config: Optional[Dict[str, Any]] = None,
    ) -> RunRecord:
        self._note("update_run", run_id, status=status)
        record = self.get_run(run_id)
        updated = record.model_copy(
            update={
                "status": status or record.status,
                "run_notes": run_notes if run_notes is not None else record.run_notes,
                "run_config": run_config or record.run_config,
                "updated_at": _now(),
            }
        )
        self.runs[run_id] = updated
        return updated

    def list_runs(
        self,
        attack_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> PaginatedResult[RunRecord]:
        items = list(self.runs.values())
        if attack_id is not None:
            items = [item for item in items if item.attack_id == attack_id]
        return self._page("list_runs", items, page, page_size, attack_id=attack_id)

    def get_run(self, run_id: UUID) -> RunRecord:
        self._note("get_run", run_id)
        try:
            return self.runs[run_id]
        except KeyError as exc:
            raise RuntimeError(f"run {run_id} not found") from exc

    def delete_run(self, run_id: UUID) -> None:
        self._note("delete_run", run_id)
        if run_id not in self.runs:
            raise RuntimeError(f"run {run_id} not found")
        del self.runs[run_id]
        gone = [item.id for item in self.results.values() if item.run_id == run_id]
        for result_id in gone:
            self.results.pop(result_id, None)
            self.traces.pop(result_id, None)

    def delete_attack(self, attack_id: UUID) -> None:
        self._note("delete_attack", attack_id)
        self.attacks.pop(attack_id, None)

    def create_result(
        self,
        run_id: UUID,
        goal: str,
        goal_index: int,
        request_payload: Dict[str, Any],
        agent_specific_data: Dict[str, Any],
    ) -> ResultRecord:
        self._note("create_result", run_id, goal, goal_index)
        now = _now()
        record = ResultRecord(
            id=uuid4(),
            run_id=run_id,
            goal=goal,
            goal_index=goal_index,
            evaluation_status="NOT_EVALUATED",
            evaluation_notes=None,
            evaluation_metrics={},
            metadata={
                "request_payload": request_payload,
                **dict(agent_specific_data),
            },
            created_at=now,
            updated_at=now,
        )
        self.results[record.id] = record
        return record

    def update_result(
        self,
        result_id: UUID,
        evaluation_status: Optional[str] = None,
        evaluation_notes: Optional[str] = None,
        evaluation_metrics: Optional[Dict[str, Any]] = None,
        agent_specific_data: Optional[Dict[str, Any]] = None,
    ) -> ResultRecord:
        self._note("update_result", result_id, evaluation_status=evaluation_status)
        record = self.get_result(result_id)
        metadata = dict(record.metadata)
        if agent_specific_data:
            metadata.update(agent_specific_data)
        updated = record.model_copy(
            update={
                "evaluation_status": evaluation_status or record.evaluation_status,
                "evaluation_notes": (
                    evaluation_notes
                    if evaluation_notes is not None
                    else record.evaluation_notes
                ),
                "evaluation_metrics": evaluation_metrics or record.evaluation_metrics,
                "metadata": metadata,
                "updated_at": _now(),
            }
        )
        self.results[result_id] = updated
        return updated

    def list_results(
        self,
        run_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> PaginatedResult[ResultRecord]:
        items = list(self.results.values())
        if run_id is not None:
            items = [item for item in items if item.run_id == run_id]
        return self._page("list_results", items, page, page_size, run_id=run_id)

    def get_result(self, result_id: UUID) -> ResultRecord:
        self._note("get_result", result_id)
        try:
            return self.results[result_id]
        except KeyError as exc:
            raise RuntimeError(f"result {result_id} not found") from exc

    def create_trace(
        self,
        result_id: UUID,
        sequence: int,
        step_type: str,
        content: Dict[str, Any],
    ) -> TraceRecord:
        self._note("create_trace", result_id, sequence, step_type)
        record = TraceRecord(
            id=uuid4(),
            result_id=result_id,
            sequence=sequence,
            step_type=step_type,
            content=dict(content),
            created_at=_now(),
        )
        self.traces.setdefault(result_id, []).append(record)
        return record

    def list_traces(self, result_id: UUID) -> List[TraceRecord]:
        self._note("list_traces", result_id)
        return list(self.traces.get(result_id, []))

    def count_result_buckets(self) -> Dict[str, int]:
        self._note("count_result_buckets")
        return {
            "total": len(self.results),
            "jailbreaks": 0,
            "mitigated": 0,
            "failed": 0,
            "pending": len(self.results),
        }

    def _page(self, name: str, items: list, page: int, page_size: int, **extra: Any):
        self._note(name, page=page, page_size=page_size, **extra)
        start = (page - 1) * page_size
        return PaginatedResult(items=items[start : start + page_size], total=len(items))
