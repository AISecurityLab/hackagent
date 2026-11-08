# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Stored per-goal tallies and the functions that keep them.

Reports never recount results or scan traces. A backend keeps two tables
that mirror :class:`GoalOutcome` and :class:`GoalUsage` column for column, and
updates them in the same transaction as every write that affects them:

* result created or updated: recompute the goal's :class:`GoalOutcome` with
  :func:`goal_outcome` from the light :class:`ResultRow` of every result of
  that (attack run, goal index), keeping the stored trace coverage;
* trace created: apply :func:`add_trace` to the goal's stored rows, given the
  :class:`TraceFlags` of the result's earlier traces;
* result or trace deleted: recompute both rows of the goal from what is left,
  with :func:`goal_outcome`, :func:`trace_coverage` and :func:`goal_usage`
  (or delete them when no result is left);
* attack run deleted: delete its rows.

Timestamps are timezone-aware datetimes. Ids are lowercase canonical UUID
strings; ordering "by ``created_at`` then ``id``" compares those strings,
which is also how Postgres orders ``uuid`` and SQLite orders ``TEXT``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional, Sequence

from hackagent.reporting.buckets import JAILBREAK, result_bucket

#: Label of the usage row that counts a goal's ``interaction`` steps.
INTERACTION = ""


def _text(value: Any) -> Optional[str]:
    return None if value is None or value == "" else str(value)


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _tokens(value: Any) -> Optional[int]:
    number = _number(value)
    return None if number is None else int(number)


def _path(data: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(data, Mapping):
            return None
        data = data.get(key)
    return data


# ── Light input rows ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResultRow:
    """The light columns of one result, which its goal's outcome is computed from.

    Read for every result of one (attack run, goal index)::

        SELECT id, goal, evaluation_status, evaluation_notes,
               agent_specific_data->>'category'                AS category,
               agent_specific_data->>'subcategory'             AS subcategory,
               (agent_specific_data->'attack_metadata'
                  ->>'goal_active_target_elapsed_s')::float     AS active_elapsed_s,
               created_at, updated_at
        FROM result WHERE run_id = %s AND goal_index = %s

    ``category`` and ``subcategory`` are ``None`` when missing or empty.
    ``active_elapsed_s`` is ``None`` unless it is a JSON number.
    :meth:`from_data` builds the row from a result already in memory.
    """

    id: str
    goal: str
    evaluation_status: Optional[str]
    evaluation_notes: Optional[str]
    category: Optional[str]
    subcategory: Optional[str]
    active_elapsed_s: Optional[float]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_data(
        cls,
        *,
        id: str,
        goal: str,
        evaluation_status: Optional[str],
        evaluation_notes: Optional[str],
        agent_specific_data: Optional[Mapping[str, Any]],
        created_at: datetime,
        updated_at: datetime,
    ) -> ResultRow:
        data = agent_specific_data or {}
        return cls(
            id=id,
            goal=goal or "",
            evaluation_status=evaluation_status,
            evaluation_notes=evaluation_notes,
            category=_text(data.get("category")),
            subcategory=_text(data.get("subcategory")),
            active_elapsed_s=_number(
                _path(data, "attack_metadata", "goal_active_target_elapsed_s")
            ),
            created_at=created_at,
            updated_at=updated_at,
        )


@dataclass(frozen=True)
class TraceRow:
    """The light columns of one trace step, which usage and coverage count.

    Read with::

        SELECT result_id, step_type,
               content->>'node'  AS node,
               content->>'label' AS label,
               content->>'scope' AS scope,
               COALESCE((content->'data'->'usage'->>'prompt_tokens')::bigint,
                        (content->'response'->'usage'->>'prompt_tokens')::bigint)
                   AS prompt_tokens,
               COALESCE((content->'data'->'usage'->>'completion_tokens')::bigint,
                        (content->'response'->'usage'->>'completion_tokens')::bigint)
                   AS completion_tokens
        FROM trace WHERE result_id IN (...)

    :meth:`from_content` builds the row from a trace already in memory, which
    is what a backend does when it creates one.
    """

    result_id: str
    step_type: str
    node: Optional[str]
    label: Optional[str]
    scope: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]

    @classmethod
    def from_content(
        cls, result_id: str, step_type: str, content: Optional[Mapping[str, Any]]
    ) -> TraceRow:
        content = content if isinstance(content, Mapping) else {}

        def usage(key: str) -> Optional[int]:
            value = _tokens(_path(content, "data", "usage", key))
            if value is None:
                value = _tokens(_path(content, "response", "usage", key))
            return value

        return cls(
            result_id=result_id,
            step_type=step_type,
            node=_text(content.get("node")),
            label=_text(content.get("label")),
            scope=_text(content.get("scope")),
            prompt_tokens=usage("prompt_tokens"),
            completion_tokens=usage("completion_tokens"),
        )


# ── Stored rows ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TraceCoverage:
    """How many attempts of a goal recorded each kind of trace step."""

    #: Attempts with a ``call`` node that carries a non-empty ``label``.
    labelled_call_attempts: int = 0
    #: Attempts with a ``call`` node labelled ``target``.
    target_call_attempts: int = 0
    #: Attempts with an ``interaction`` step.
    interaction_attempts: int = 0


@dataclass(frozen=True)
class TraceFlags:
    """Which kinds of trace step one attempt has recorded so far."""

    labelled_call: bool = False
    target_call: bool = False
    interaction: bool = False


@dataclass(frozen=True)
class GoalOutcome:
    """Table ``goal_outcome``: one row per (attack run, goal index).

    Primary key ``(run_id, goal_index)``; index
    ``(campaign_run_id, run_id, goal_index)``.

    =========================  ============  ===================================
    column                     type          value
    =========================  ============  ===================================
    campaign_run_id            uuid, null    the attack run's campaign run
    run_id                     uuid          the attack run
    goal_index                 integer
    goal                       text          goal text of the latest attempt
    category                   text          of the latest attempt that has
                                             one, ``''`` when none has
    subcategory                text          of that same attempt, or ``''``
    attempts                   integer       results
    jailbreak                  integer       results per bucket
    mitigated                  integer
    error                      integer
    pending                    integer
    first_jailbreak_attempt    integer, null ordinal (1-based, ``created_at``
                                             then ``id``) of the first jailbreak
    min_jailbreak_elapsed_s    float, null   smallest active goal clock among
                                             the jailbreaks that carry one
    timed_jailbreaks           integer       jailbreaks that carry the clock
    first_created_at           timestamp     MIN(created_at) of the results
    last_updated_at            timestamp     MAX(updated_at) of the results
    labelled_call_attempts     integer       see :class:`TraceCoverage`
    target_call_attempts       integer
    interaction_attempts       integer
    =========================  ============  ===================================

    "Latest" is the greatest (``created_at``, ``id``).
    """

    campaign_run_id: Optional[str]
    run_id: str
    goal_index: int
    goal: str
    category: str
    subcategory: str
    attempts: int
    jailbreak: int
    mitigated: int
    error: int
    pending: int
    first_jailbreak_attempt: Optional[int]
    min_jailbreak_elapsed_s: Optional[float]
    timed_jailbreaks: int
    first_created_at: datetime
    last_updated_at: datetime
    labelled_call_attempts: int = 0
    target_call_attempts: int = 0
    interaction_attempts: int = 0

    @property
    def coverage(self) -> TraceCoverage:
        return TraceCoverage(
            self.labelled_call_attempts,
            self.target_call_attempts,
            self.interaction_attempts,
        )


@dataclass(frozen=True)
class GoalUsage:
    """Table ``goal_usage``: one row per (attack run, goal index, label).

    Primary key ``(run_id, goal_index, label)``; index
    ``(campaign_run_id, run_id, goal_index)``. ``label`` is a ``call`` node's
    label, or ``''`` for ``interaction`` steps (see :func:`usage_label`).

    =================  ==========  ==========================================
    column             type        value
    =================  ==========  ==========================================
    campaign_run_id    uuid, null  the attack run's campaign run
    run_id             uuid        the attack run
    goal_index         integer
    label              text
    calls              integer     steps counted under this label
    goal_scoped_calls  integer     of which ``content.scope = 'goal'``
    prompt_tokens      bigint      sum over the steps that report it
    completion_tokens  bigint      sum over the steps that report it
    usage_calls        integer     steps that report both token counts
    =================  ==========  ==========================================
    """

    campaign_run_id: Optional[str]
    run_id: str
    goal_index: int
    label: str
    calls: int
    goal_scoped_calls: int
    prompt_tokens: int
    completion_tokens: int
    usage_calls: int


# ── Rules ────────────────────────────────────────────────────────────────────


def usage_label(trace: TraceRow) -> Optional[str]:
    """The usage row a trace step counts under, or None when it counts nowhere.

    An ``interaction`` step counts under ``''``; any other step whose
    ``node`` is ``call`` counts under its label. A call node without a label
    names no role and is not counted.
    """
    if trace.step_type == "interaction":
        return INTERACTION
    if trace.node == "call" and trace.label:
        return trace.label
    return None


def trace_flags(traces: Iterable[TraceRow]) -> TraceFlags:
    """What ``traces`` (the steps of one attempt) have recorded."""
    labelled = target = interaction = False
    for trace in traces:
        if trace.node == "call" and trace.label:
            labelled = True
            target = target or trace.label == "target"
        interaction = interaction or trace.step_type == "interaction"
    return TraceFlags(labelled, target, interaction)


def trace_coverage(traces: Iterable[TraceRow]) -> TraceCoverage:
    """Coverage of a goal from every step of every one of its attempts."""
    by_result: dict[str, list[TraceRow]] = {}
    for trace in traces:
        by_result.setdefault(trace.result_id, []).append(trace)
    flags = [trace_flags(steps) for steps in by_result.values()]
    return TraceCoverage(
        labelled_call_attempts=sum(flag.labelled_call for flag in flags),
        target_call_attempts=sum(flag.target_call for flag in flags),
        interaction_attempts=sum(flag.interaction for flag in flags),
    )


def goal_outcome(
    *,
    campaign_run_id: Optional[str],
    run_id: str,
    goal_index: int,
    results: Sequence[ResultRow],
    coverage: TraceCoverage = TraceCoverage(),
) -> Optional[GoalOutcome]:
    """The outcome row of a goal from every one of its results, or None
    when it has none. ``coverage`` is kept as given: results do not change it."""
    if not results:
        return None
    ordered = sorted(results, key=lambda row: (row.created_at, row.id))
    buckets = [
        result_bucket(row.evaluation_status, row.evaluation_notes) for row in ordered
    ]
    latest = ordered[-1]
    labelled = next((row for row in reversed(ordered) if row.category), None)
    jailbreaks = [row for row, bucket in zip(ordered, buckets) if bucket == JAILBREAK]
    clocks = [
        row.active_elapsed_s for row in jailbreaks if row.active_elapsed_s is not None
    ]
    return GoalOutcome(
        campaign_run_id=campaign_run_id,
        run_id=run_id,
        goal_index=goal_index,
        goal=latest.goal,
        category=labelled.category or "" if labelled else "",
        subcategory=labelled.subcategory or "" if labelled else "",
        attempts=len(ordered),
        jailbreak=buckets.count("jailbreak"),
        mitigated=buckets.count("mitigated"),
        error=buckets.count("error"),
        pending=buckets.count("pending"),
        first_jailbreak_attempt=buckets.index(JAILBREAK) + 1
        if JAILBREAK in buckets
        else None,
        min_jailbreak_elapsed_s=min(clocks) if clocks else None,
        timed_jailbreaks=len(clocks),
        first_created_at=min(row.created_at for row in ordered),
        last_updated_at=max(row.updated_at for row in ordered),
        labelled_call_attempts=coverage.labelled_call_attempts,
        target_call_attempts=coverage.target_call_attempts,
        interaction_attempts=coverage.interaction_attempts,
    )


def goal_usage(
    *,
    campaign_run_id: Optional[str],
    run_id: str,
    goal_index: int,
    traces: Iterable[TraceRow],
) -> list[GoalUsage]:
    """The usage rows of a goal from every step of every one of its attempts,
    ordered by label."""
    rows: dict[str, GoalUsage] = {}
    for trace in traces:
        row = _add_usage(
            rows.get(usage_label(trace) or ""),
            trace,
            campaign_run_id=campaign_run_id,
            run_id=run_id,
            goal_index=goal_index,
        )
        if row is not None:
            rows[row.label] = row
    return [rows[label] for label in sorted(rows)]


def _add_usage(
    row: Optional[GoalUsage],
    trace: TraceRow,
    *,
    campaign_run_id: Optional[str],
    run_id: str,
    goal_index: int,
) -> Optional[GoalUsage]:
    label = usage_label(trace)
    if label is None:
        return None
    if row is None:
        row = GoalUsage(campaign_run_id, run_id, goal_index, label, 0, 0, 0, 0, 0)
    return replace(
        row,
        calls=row.calls + 1,
        goal_scoped_calls=row.goal_scoped_calls + (trace.scope == "goal"),
        prompt_tokens=row.prompt_tokens + (trace.prompt_tokens or 0),
        completion_tokens=row.completion_tokens + (trace.completion_tokens or 0),
        usage_calls=row.usage_calls
        + (trace.prompt_tokens is not None and trace.completion_tokens is not None),
    )


def add_trace(
    outcome: GoalOutcome,
    usage: Optional[GoalUsage],
    trace: TraceRow,
    before: TraceFlags,
) -> tuple[GoalOutcome, Optional[GoalUsage]]:
    """Count one new trace step of an attempt of ``outcome``'s goal.

    ``usage`` is the stored row under :func:`usage_label` of ``trace`` (None
    when there is none yet), and ``before`` the :func:`trace_flags` of the
    attempt's earlier steps. Returns the outcome to store and the usage row to
    upsert (None when the step counts under no label).
    """
    after = trace_flags([trace])
    outcome = replace(
        outcome,
        labelled_call_attempts=outcome.labelled_call_attempts
        + (after.labelled_call and not before.labelled_call),
        target_call_attempts=outcome.target_call_attempts
        + (after.target_call and not before.target_call),
        interaction_attempts=outcome.interaction_attempts
        + (after.interaction and not before.interaction),
    )
    return outcome, _add_usage(
        usage,
        trace,
        campaign_run_id=outcome.campaign_run_id,
        run_id=outcome.run_id,
        goal_index=outcome.goal_index,
    )


__all__ = [
    "GoalOutcome",
    "GoalUsage",
    "INTERACTION",
    "ResultRow",
    "TraceCoverage",
    "TraceFlags",
    "TraceRow",
    "add_trace",
    "goal_outcome",
    "goal_usage",
    "trace_coverage",
    "trace_flags",
    "usage_label",
]
