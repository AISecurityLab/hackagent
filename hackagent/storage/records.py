# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Record models returned by every :class:`~hackagent.storage.store.Store`.

They mirror the server-side models, so their fields are part of the wire
and database contract and must not change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Record models (immutable Pydantic BaseModel, mirror the Django model fields)
# ---------------------------------------------------------------------------


class OrganizationContext(BaseModel):
    """Organization and user context resolved by the storage backend."""

    model_config = ConfigDict(frozen=True)

    org_id: UUID
    user_id: str  # "local" for LocalBackend


class AgentRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    agent_type: str
    endpoint: str
    metadata: Dict[str, Any]
    organization: UUID
    owner: str
    created_at: datetime
    updated_at: datetime


#: Attack types written by earlier releases, mapped to canonical attack ids.
_LEGACY_ATTACK_TYPES: Dict[str, str] = {
    "Baseline": "baseline",
    "AdvPrefix": "advprefix",
    "StaticTemplate": "static_template",
    "PAIR": "pair",
    "FlipAttack": "flipattack",
    "TAP": "tap",
    "AutoDANTurbo": "autodan_turbo",
    "MML": "mml",
    "FC": "fc",
    "tFC": "tfc",
}


def canonical_attack_type(value: str) -> str:
    """Map a stored attack type to its canonical id; unknown values pass through."""
    return _LEGACY_ATTACK_TYPES.get(value, value)


class AttackRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    type: str
    agent_id: UUID
    organization: UUID
    configuration: Dict[str, Any]
    created_at: datetime

    @field_validator("type")
    @classmethod
    def _canonical_type(cls, value: str) -> str:
        return canonical_attack_type(value)


class RunRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    attack_id: UUID
    agent_id: UUID
    run_config: Dict[str, Any]
    status: str
    run_notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class ResultRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    run_id: UUID
    goal: str
    goal_index: int
    evaluation_status: str
    evaluation_notes: Optional[str]
    evaluation_metrics: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TraceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    result_id: UUID
    sequence: int
    step_type: str
    content: Dict[str, Any]
    created_at: datetime


class PaginatedResult(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True)

    items: List[T]
    total: int
