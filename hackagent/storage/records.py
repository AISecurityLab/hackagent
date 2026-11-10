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
    """A target agent that runs are attached to.

    ``metadata`` is the agent's model config (a dumped ``ModelConfig``);
    ``agent_type`` and ``endpoint`` are copied from its connection. ``owner`` is
    ``"local"`` in local storage.
    """

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
    """An attack configuration recorded against an agent.

    ``type`` is normalised to the canonical attack id on load, so records
    written by earlier releases (``"PAIR"``, ``"AdvPrefix"``) read as
    ``"pair"``, ``"advprefix"``.
    """

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


class CampaignRunRecord(BaseModel):
    """One execution of a declarative campaign.

    The campaign owns its immutable specification and judge audit. Individual
    attack runs link back to this record through ``campaign_run_id``.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    agent_id: UUID
    name: str
    campaign_config: Dict[str, Any]
    audit: Optional[Dict[str, Any]]
    status: str
    run_notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    #: The saved campaign it was launched from, when the dashboard launched it.
    campaign_id: Optional[UUID] = None
    #: The dashboard launched it, in the ``hackagent web`` process. Kept when
    #: the saved campaign is deleted and ``campaign_id`` cleared.
    launched: bool = False


class CampaignRecord(BaseModel):
    """A campaign saved from the dashboard: a spec without target and execution.

    The target comes from the agent's config when the campaign is launched.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    description: str
    agent_id: UUID
    spec: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class RunRecord(BaseModel):
    """One attack run: a single technique executed against an agent.

    ``campaign_run_id`` links it to the campaign run it belongs to. ``status``
    is a ``RunStatus`` value.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID
    campaign_run_id: Optional[UUID] = None
    attack_id: UUID
    agent_id: UUID
    run_config: Dict[str, Any]
    status: str
    run_notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class ResultRecord(BaseModel):
    """One attempt at one goal within a run, with its evaluation.

    ``evaluation_status`` is an ``EvalStatus`` value, ``NOT_EVALUATED`` until
    the judges have scored the attempt.
    """

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
    """One step of a result's trace, ordered within the result by ``sequence``."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    result_id: UUID
    sequence: int
    step_type: str
    content: Dict[str, Any]
    created_at: datetime


class PaginatedResult(BaseModel, Generic[T]):
    """One page of records and the total number of records across all pages."""

    model_config = ConfigDict(frozen=True)

    items: List[T]
    total: int
