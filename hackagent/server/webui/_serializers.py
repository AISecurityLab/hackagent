# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Render ``LocalBackend`` records in the HackAgent REST wire format.

The bundled web UI is the same single-page app that runs against
``api.hackagent.dev``; its generated client expects Django REST Framework
payloads (snake_case keys, ``{count, next, previous, results}`` pages). These
functions are the offline-mode adapter: they translate the SQLite-backed
records of ``hackagent.storage.records`` into exactly those shapes so the
SPA cannot tell the difference.

Fields the local store has no equivalent for (per-request HTTP metadata,
credits, Auth0 identifiers) are emitted as ``None``/zero rather than omitted —
the generated client dereferences them unconditionally.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from hackagent.storage.records import (
    AgentRecord,
    AttackRecord,
    ResultRecord,
    RunRecord,
    TraceRecord,
)
from hackagent.storage.buckets import (
    ERROR,
    JAILBREAK,
    MITIGATED,
    PENDING,
    result_bucket,
)

#: Identity presented by offline mode. The local store has a single implicit
#: user; the SPA still needs a stable id/username pair to render headers.
LOCAL_USER_ID = "local"
LOCAL_USERNAME = "local"
LOCAL_ORG_NAME = "Local"


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _str(value: Optional[UUID]) -> Optional[str]:
    return str(value) if value is not None else None


def paginate(
    items: List[Dict[str, Any]], total: int, page: int, page_size: int
) -> Dict[str, Any]:
    """Wrap ``items`` in DRF's ``PageNumberPagination`` envelope.

    ``next``/``previous`` are booleans-as-URLs in DRF; the SPA only checks them
    for truthiness to decide whether to request another page, so a sentinel
    string is enough and avoids having to reconstruct absolute URLs.
    """
    has_next = page * page_size < total
    return {
        "count": total,
        "next": "?page=%d" % (page + 1) if has_next else None,
        "previous": "?page=%d" % (page - 1) if page > 1 else None,
        "results": items,
    }


def organization_minimal(org_id: UUID) -> Dict[str, Any]:
    return {"id": str(org_id), "name": LOCAL_ORG_NAME}


def organization(org_id: UUID) -> Dict[str, Any]:
    """Full Organization payload. Credits are meaningless offline: report 0."""
    return {
        "id": str(org_id),
        "name": LOCAL_ORG_NAME,
        "created_at": None,
        "updated_at": None,
        "credits": "0.00",
        "credits_last_updated": None,
    }


def user_profile_minimal(org_id: UUID) -> Dict[str, Any]:
    return {
        "user": LOCAL_USER_ID,
        "username": LOCAL_USERNAME,
        "organization": str(org_id),
    }


def user_profile(org_id: UUID) -> Dict[str, Any]:
    return {
        "id": LOCAL_USER_ID,
        "user": LOCAL_USER_ID,
        "username": LOCAL_USERNAME,
        "email": None,
        "first_name": None,
        "last_name": None,
        "organization": str(org_id),
        "organization_name": LOCAL_ORG_NAME,
        "keycloak_user_id": None,
        "auth0_user_id": None,
        "analytics_consent": None,
    }


def agent(record: AgentRecord) -> Dict[str, Any]:
    return {
        "id": str(record.id),
        "name": record.name,
        "endpoint": record.endpoint,
        "agent_type": record.agent_type,
        "description": (record.metadata or {}).get("description"),
        "metadata": record.metadata,
        "organization": str(record.organization),
        "organization_detail": organization_minimal(record.organization),
        "owner": record.owner,
        "owner_detail": user_profile_minimal(record.organization),
        "created_at": _iso(record.created_at),
        "updated_at": _iso(record.updated_at),
    }


def attack(record: AttackRecord, agent_name: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": str(record.id),
        "type": record.type,
        "agent": str(record.agent_id),
        "agent_name": agent_name,
        "owner": LOCAL_USER_ID,
        "owner_username": LOCAL_USERNAME,
        "organization": str(record.organization),
        "organization_name": LOCAL_ORG_NAME,
        "configuration": record.configuration,
        "created_at": _iso(record.created_at),
        "updated_at": _iso(record.created_at),
    }


def trace(record: TraceRecord) -> Dict[str, Any]:
    return {
        "id": str(record.id),
        "result": str(record.result_id),
        "sequence": record.sequence,
        "step_type": record.step_type,
        "timestamp": _iso(record.created_at),
        "content": record.content,
    }


def result(
    record: ResultRecord, traces: Optional[List[TraceRecord]] = None
) -> Dict[str, Any]:
    """Serialise a result.

    ``traces`` is always present in the wire format (the generated client maps
    over it unconditionally); pass ``None`` for list endpoints, where loading
    every trace would turn one page into hundreds of queries.
    """
    metadata = record.metadata or {}
    return {
        "id": str(record.id),
        "run": str(record.run_id),
        "run_id": str(record.run_id),
        "request_payload": metadata.get("request_payload", {"goal": record.goal}),
        "response_status_code": metadata.get("response_status_code"),
        "response_headers": metadata.get("response_headers"),
        "response_body": metadata.get("response_body"),
        "latency_ms": metadata.get("latency_ms"),
        "detected_tool_calls": metadata.get("detected_tool_calls"),
        "evaluation_status": record.evaluation_status,
        "evaluation_notes": record.evaluation_notes,
        "evaluation_metrics": record.evaluation_metrics,
        "agent_specific_data": metadata,
        "timestamp": _iso(record.created_at),
        "traces": [trace(t) for t in (traces or [])],
    }


def run(
    record: RunRecord,
    agent_name: Optional[str] = None,
    results: Optional[List[Dict[str, Any]]] = None,
    org_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    return {
        "id": str(record.id),
        "agent": str(record.agent_id),
        "agent_name": agent_name,
        "attack": _str(record.attack_id),
        "owner": LOCAL_USER_ID,
        "owner_username": LOCAL_USERNAME,
        "organization": _str(org_id),
        "organization_name": LOCAL_ORG_NAME,
        "run_config": record.run_config,
        "timestamp": _iso(record.created_at),
        "status": record.status,
        "run_notes": record.run_notes,
        # Every local run was executed by this client, by definition.
        "is_client_executed": True,
        "results": results or [],
    }


def run_summary(
    record: RunRecord,
    results: List[ResultRecord],
    agent_name: Optional[str] = None,
    attack_type: Optional[str] = None,
    org_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    """Serialise a run with the per-outcome counts the run list renders."""
    counts = {JAILBREAK: 0, MITIGATED: 0, ERROR: 0, PENDING: 0}
    for item in results:
        counts[result_bucket(item.evaluation_status, item.evaluation_notes)] += 1

    payload = run(record, agent_name=agent_name, org_id=org_id)
    payload.pop("results")
    payload.update(
        {
            "attack_type": attack_type,
            "total_results": len(results),
            "successful_jailbreaks": counts[JAILBREAK],
            "failed_jailbreaks": counts[MITIGATED],
            "errors": counts[ERROR],
            "not_evaluated": counts[PENDING],
        }
    )
    return payload
