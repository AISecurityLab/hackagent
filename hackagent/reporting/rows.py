# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The rows a backend reads to answer a report request.

Each docstring gives the query that produces the rows, in Postgres terms
over the platform's tables (``run``, ``result``, ``trace``, ``attack``,
``agent``) and the two tally tables of :mod:`hackagent.reporting.tallies`.
Queries only filter, select columns and GROUP BY with plain aggregates;
every rule is applied by :mod:`hackagent.reporting` to the rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional

TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})


@dataclass(frozen=True)
class CampaignRun:
    """One campaign run: a parent run, with its agent's name.

    ::

        SELECT run.id, run.run_config->>'campaign_name' AS name,
               run.campaign_id, run.agent_id, agent.name AS target, run.status,
               run.executor, run.timestamp AS created_at, <updated_at>,
               run.finished_at, run.revision
        FROM run JOIN agent ON agent.id = run.agent_id
        WHERE run.parent_id IS NULL AND <filters>
        ORDER BY run.timestamp DESC, run.id

    ``configuration`` (``run_config->'campaign_config'``), ``audit``
    (``run_config->'evaluation_audit'``) and ``notes`` (``run_notes``) are
    read only for :func:`~hackagent.reporting.report.campaign_run_report`.
    ``notes`` may be ``''`` or ``None`` for no notes.
    """

    id: str
    name: str
    campaign: Optional[str]
    agent: str
    target: str
    status: str
    executor: str
    created_at: datetime
    updated_at: datetime
    finished_at: Optional[datetime]
    revision: int = 0
    configuration: Mapping[str, Any] = field(default_factory=dict)
    audit: Optional[Mapping[str, Any]] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class AttackRun:
    """One attack run of a campaign run.

    ::

        SELECT run.id, run.parent_id AS campaign_run, run.status,
               run.timestamp AS created_at, run.attack_id AS attack,
               attack.type AS technique, run.run_notes AS notes,
               run.run_config AS configuration,
               attack.configuration AS attack_configuration
        FROM run LEFT JOIN attack ON attack.id = run.attack_id
        WHERE run.parent_id IN (...)

    The summary list reads only the first four columns. For a report the
    backend passes ``technique`` through
    :func:`hackagent.storage.records.canonical_attack_type`, sets ``family``
    to :func:`hackagent.attacks.techniques.registry.attack_family` of it and
    ``attack_configuration`` to
    :func:`hackagent.orchestrator.campaign.spec.redacted` of the attack's
    configuration; without an attack, ``technique`` is ``'Unknown'`` and the
    other two ``None``.
    """

    id: str
    campaign_run: str
    status: str
    created_at: datetime
    attack: Optional[str] = None
    technique: str = "Unknown"
    family: Optional[str] = None
    notes: Optional[str] = None
    configuration: Mapping[str, Any] = field(default_factory=dict)
    attack_configuration: Optional[Mapping[str, Any]] = None


@dataclass(frozen=True)
class GoalTotal:
    """A goal's attempts across a whole campaign run, per bucket.

    ::

        SELECT campaign_run_id AS campaign_run, goal_index,
               SUM(attempts), SUM(jailbreak), SUM(mitigated), SUM(error),
               SUM(pending)
        FROM goal_outcome WHERE campaign_run_id IN (...)
        GROUP BY campaign_run_id, goal_index
    """

    campaign_run: str
    goal_index: int
    attempts: int
    jailbreak: int
    mitigated: int
    error: int
    pending: int


@dataclass(frozen=True)
class Attempt:
    """One attempt at a goal, on a page of ``/attempts``.

    ::

        SELECT id, run_id, bucket, evaluation_notes AS notes,
               timestamp AS created_at
        FROM result WHERE run_id IN (...) AND goal_index = %s
        ORDER BY created_at, id LIMIT %s OFFSET %s

    ``notes`` may be ``''`` or ``None`` for no notes.
    """

    id: str
    run_id: str
    bucket: str
    notes: Optional[str]
    created_at: datetime


@dataclass(frozen=True)
class FirstSuccess:
    """The first jailbreak among a goal's attempts and its 1-based position.

    ::

        SELECT id, timestamp FROM result
        WHERE run_id IN (...) AND goal_index = %s AND bucket = 'jailbreak'
        ORDER BY timestamp, id LIMIT 1;
        -- position:
        SELECT COUNT(*) FROM result
        WHERE run_id IN (...) AND goal_index = %s
          AND (timestamp, id) <= (%(timestamp)s, %(id)s)
    """

    id: str
    position: int


@dataclass(frozen=True)
class StructureResult:
    """One attempt of a goal in full, for ``/structure``.

    Every result of one (attack run, goal index), all columns.
    """

    id: str
    run_id: str
    evaluation_status: Optional[str]
    evaluation_notes: Optional[str]
    request_payload: Optional[Mapping[str, Any]]
    agent_specific_data: Optional[Mapping[str, Any]]
    created_at: datetime


@dataclass(frozen=True)
class StructureTrace:
    """One trace step of a :class:`StructureResult`, all columns."""

    id: str
    result_id: str
    sequence: int
    step_type: str
    content: Any
    timestamp: datetime


@dataclass(frozen=True)
class Latency:
    """How many results of an attack run took a given target latency.

    ::

        SELECT run_id, latency_ms, COUNT(*) AS count FROM result
        WHERE run_id IN (...) AND latency_ms IS NOT NULL
        GROUP BY run_id, latency_ms
    """

    run_id: str
    latency_ms: float
    count: int = 1


__all__ = [
    "AttackRun",
    "Attempt",
    "CampaignRun",
    "FirstSuccess",
    "GoalTotal",
    "Latency",
    "StructureResult",
    "StructureTrace",
    "TERMINAL_STATUSES",
]
