# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Campaign run summaries, reports, goal listings, the matrix and comparisons.

Every function takes rows (:mod:`hackagent.reporting.rows`, the stored
:class:`~hackagent.reporting.tallies.GoalOutcome`) and returns the JSON body
of a route, so both servers answer identically.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional, Sequence, TypedDict

from hackagent.reporting.goals import (
    VERDICT_CODES,
    GoalFilters,
    GoalSummary,
    GoalVerdict,
    attack_outcomes,
    attack_verdict,
    category_summaries,
    filter_goals,
    goal_verdict,
    is_complete,
    outcome_counts,
    run_order,
    subcategory_name,
    summarize_goals,
)
from hackagent.reporting.http import ATTACK_RUN_NOT_FOUND, NotFound
from hackagent.reporting.rows import AttackRun, CampaignRun, GoalTotal
from hackagent.reporting.tallies import GoalOutcome


class CampaignRunSummary(TypedDict):
    """One campaign run's row in ``/run/summary``: identity, status, verdicts."""

    id: str
    name: str
    campaign: Optional[str]
    agent: str
    target: str
    status: str
    executor: str
    created_at: str
    updated_at: str
    finished_at: Optional[str]
    attack_runs: int
    recorded_goals: int
    jailbroken: int
    mitigated: int
    unresolved: int
    attempts: int
    revision: int


def iso(value: Optional[datetime]) -> Optional[str]:
    """How every timestamp is rendered: ``datetime.isoformat()``."""
    return value.isoformat() if value is not None else None


def children(run: CampaignRun, attack_runs: Iterable[AttackRun]) -> list[AttackRun]:
    """The attack runs of ``run``, in report order."""
    return run_order(item for item in attack_runs if item.campaign_run == run.id)


def _summary(
    run: CampaignRun,
    attack_runs: int,
    goals: Sequence[GoalSummary],
    attempts: int,
) -> CampaignRunSummary:
    return {
        "id": run.id,
        "name": run.name,
        "campaign": run.campaign,
        "agent": run.agent,
        "target": run.target,
        "status": run.status,
        "executor": run.executor,
        "created_at": iso(run.created_at) or "",
        "updated_at": iso(run.updated_at) or "",
        "finished_at": iso(run.finished_at),
        "attack_runs": attack_runs,
        **outcome_counts(goals),
        "attempts": attempts,
        "revision": run.revision,
    }


def _total_goals(totals: Iterable[GoalTotal], complete: bool) -> list[GoalSummary]:
    """Verdict-only goal summaries from campaign-wide totals."""
    return [
        {  # type: ignore[typeddict-item]
            "index": total.goal_index,
            "verdict": goal_verdict(
                attempts=total.attempts,
                jailbreak=total.jailbreak,
                mitigated=total.mitigated,
                complete=complete,
            ),
        }
        for total in totals
    ]


def campaign_run_summary(
    run: CampaignRun,
    attack_runs: Iterable[AttackRun],
    totals: Iterable[GoalTotal],
) -> CampaignRunSummary:
    """``GET /run/{id}/summary``: one campaign run's ``CampaignRunSummary``.

    ``attack_runs`` and ``totals`` may hold other campaign runs' rows too.
    """
    runs = children(run, attack_runs)
    mine = [total for total in totals if total.campaign_run == run.id]
    return _summary(
        run,
        len(runs),
        _total_goals(mine, is_complete(run.status, runs)),
        sum(total.attempts for total in mine),
    )


def campaign_run_summaries(
    runs: Sequence[CampaignRun],
    attack_runs: Iterable[AttackRun],
    totals: Iterable[GoalTotal],
) -> list[CampaignRunSummary]:
    """The items of a ``GET /run/summary`` page, in the order of ``runs``."""
    attack_runs = list(attack_runs)
    by_run: dict[str, list[GoalTotal]] = {}
    for total in totals:
        by_run.setdefault(total.campaign_run, []).append(total)
    return [
        campaign_run_summary(run, attack_runs, by_run.get(run.id, [])) for run in runs
    ]


def is_previous(current: CampaignRun, candidate: CampaignRun) -> bool:
    """Whether ``candidate`` may be the ``previous`` run of ``current``: a
    ``COMPLETED`` run of the same saved campaign (or, for a run of no saved
    campaign, of no saved campaign with the same agent and name), created
    before it."""
    if candidate.id == current.id or candidate.status != "COMPLETED":
        return False
    if (candidate.created_at, candidate.id) >= (current.created_at, current.id):
        return False
    if current.campaign is not None:
        return candidate.campaign == current.campaign
    return (
        candidate.campaign is None
        and candidate.agent == current.agent
        and candidate.name == current.name
    )


def pick_previous(
    current: CampaignRun, candidates: Iterable[CampaignRun]
) -> Optional[CampaignRun]:
    """The most recent run of ``candidates`` that :func:`is_previous`.

    A backend may pass any superset of the matching runs, e.g. the
    ``COMPLETED`` runs of the same campaign (or agent) created before
    ``current``, newest first, ``LIMIT 1`` after filtering on the same keys.
    """
    matching = [item for item in candidates if is_previous(current, item)]
    return max(matching, key=lambda item: (item.created_at, item.id), default=None)


def previous_summary(
    run: CampaignRun,
    attack_runs: Iterable[AttackRun],
    totals: Iterable[GoalTotal],
) -> dict[str, Any]:
    """The ``previous`` object of a report."""
    summary = campaign_run_summary(run, attack_runs, totals)
    return {
        "id": run.id,
        "created_at": summary["created_at"],
        "recorded_goals": summary["recorded_goals"],
        "jailbroken": summary["jailbroken"],
        "mitigated": summary["mitigated"],
        "unresolved": summary["unresolved"],
    }


def scoped_runs(
    run: CampaignRun, attack_runs: Iterable[AttackRun], scope_run_id: Optional[str]
) -> tuple[list[AttackRun], list[AttackRun]]:
    """``(every attack run, the attack runs in scope)``; raises
    :class:`~hackagent.reporting.http.NotFound` for a scope that is not one of
    ``run``'s attack runs."""
    runs = children(run, attack_runs)
    if scope_run_id is None:
        return runs, runs
    selected = [item for item in runs if item.id == scope_run_id]
    if not selected:
        raise NotFound(ATTACK_RUN_NOT_FOUND)
    return runs, selected


def _of(
    outcomes: Iterable[GoalOutcome], runs: Iterable[AttackRun]
) -> list[GoalOutcome]:
    ids = {run.id for run in runs}
    return [row for row in outcomes if row.run_id in ids]


def campaign_run_report(
    run: CampaignRun,
    attack_runs: Iterable[AttackRun],
    outcomes: Iterable[GoalOutcome],
    *,
    scope_run_id: Optional[str] = None,
    previous: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """``GET /run/{id}/report``.

    ``outcomes`` are the stored goal outcomes of ``run`` (rows of other runs
    are ignored); ``previous`` is :func:`previous_summary` of
    :func:`pick_previous`, or None.
    """
    runs, selected = scoped_runs(run, attack_runs, scope_run_id)
    rows = _of(outcomes, selected)
    complete = scope_run_id is not None or is_complete(run.status, selected)
    goals = summarize_goals(rows, complete, selected)
    attempts = sum(row.attempts for row in rows)

    by_run = {
        item.id: [row for row in rows if row.run_id == item.id] for item in selected
    }
    run_goals = {
        item.id: summarize_goals(by_run[item.id], True, [item]) for item in selected
    }

    techniques: dict[str, list[AttackRun]] = {}
    for item in selected:
        techniques.setdefault(item.technique, []).append(item)
    technique_outcomes = []
    for technique, technique_runs in sorted(techniques.items()):
        technique_rows = _of(rows, technique_runs)
        technique_outcomes.append(
            {
                "technique": technique,
                **outcome_counts(summarize_goals(technique_rows, True, technique_runs)),
                "attempts": sum(row.attempts for row in technique_rows),
            }
        )

    categories = category_summaries(goals)
    labels = {
        goal["index"]: (goal["category"], subcategory_name(goal)) for goal in goals
    }
    attack_categories = []
    for item in selected:
        for category in categories:
            name = category["category"]
            group = [g for g in run_goals[item.id] if labels[g["index"]][0] == name]
            attack_categories.append(
                {
                    "run_id": item.id,
                    "category": name,
                    **outcome_counts(group),
                    "subcategories": [
                        {
                            "name": sub["name"],
                            **outcome_counts(
                                [
                                    g
                                    for g in group
                                    if labels[g["index"]][1] == sub["name"]
                                ]
                            ),
                        }
                        for sub in sorted(
                            category["subcategories"], key=lambda sub: sub["name"]
                        )
                    ],
                }
            )

    in_scope = {item.id for item in selected}
    return {
        **_summary(run, len(selected), goals, attempts),
        "configuration": dict(run.configuration),
        "audit": dict(run.audit) if run.audit is not None else None,
        "notes": run.notes or None,
        "scope_run_id": scope_run_id,
        "runs": [
            {
                "id": item.id,
                "attack_id": item.attack,
                "technique": item.technique,
                "family": item.family,
                "status": item.status,
                "notes": item.notes or None,
                "created_at": iso(item.created_at),
                "configuration": dict(item.configuration),
                "attack_configuration": dict(item.attack_configuration)
                if item.attack_configuration is not None
                else None,
                "outcomes": _summary(
                    run,
                    1,
                    run_goals[item.id],
                    sum(row.attempts for row in by_run[item.id]),
                )
                if item.id in in_scope
                else None,
            }
            for item in runs
        ],
        "technique_outcomes": technique_outcomes,
        "category_outcomes": categories,
        "attack_category_outcomes": attack_categories,
        "previous": previous,
    }


def goal_listing(
    run: CampaignRun,
    attack_runs: Iterable[AttackRun],
    outcomes: Iterable[GoalOutcome],
    filters: GoalFilters,
    *,
    scope_run_id: Optional[str] = None,
) -> list[GoalSummary]:
    """Every goal of ``GET /run/{id}/goals`` that passes ``filters``, with its
    per-attack outcomes; the server pages the list."""
    _, selected = scoped_runs(run, attack_runs, scope_run_id)
    rows = _of(outcomes, selected)
    complete = scope_run_id is not None or is_complete(run.status, selected)
    goals = summarize_goals(rows, complete, selected)
    return filter_goals(attack_outcomes(goals, rows, selected), filters)


def goal_matrix(
    run: CampaignRun,
    attack_runs: Iterable[AttackRun],
    outcomes: Iterable[GoalOutcome],
) -> dict[str, Any]:
    """``GET /run/{id}/matrix``: every goal's verdict per attack run, columnar."""
    runs = children(run, attack_runs)
    rows = _of(outcomes, runs)
    goals = summarize_goals(rows, is_complete(run.status, runs), runs)
    cell = {(row.run_id, row.goal_index): row for row in rows}
    return {
        "runs": [item.id for item in runs],
        "goals": [
            {
                "index": goal["index"],
                "goal": goal["goal"],
                "category": goal["category"],
                "subcategory": goal["subcategory"],
                "verdict": goal["verdict"],
            }
            for goal in goals
        ],
        "cells": [
            [
                VERDICT_CODES[attack_verdict(row)]
                if (row := cell.get((item.id, goal["index"]))) is not None
                else None
                for item in runs
            ]
            for goal in goals
        ],
        "attempts": [
            [
                row.attempts
                if (row := cell.get((item.id, goal["index"]))) is not None
                else None
                for item in runs
            ]
            for goal in goals
        ],
    }


_CHANGE_ORDER = ("regressed", "fixed", "new", "dropped", "unchanged")


def _verdicts_by_text(goals: Iterable[GoalSummary]) -> dict[str, dict[str, Any]]:
    """Goals keyed by text. Indexes sharing a text are one goal: jailbroken if
    any is, mitigated if all are, unresolved otherwise; labelled like the
    lowest index."""
    merged: dict[str, dict[str, Any]] = {}
    for goal in goals:
        entry = merged.setdefault(
            goal["goal"],
            {
                "category": goal["category"],
                "subcategory": goal["subcategory"],
                "verdicts": [],
            },
        )
        entry["verdicts"].append(goal["verdict"])
    for entry in merged.values():
        verdicts = entry.pop("verdicts")
        entry["verdict"] = (
            "jailbroken"
            if "jailbroken" in verdicts
            else "mitigated"
            if all(verdict == "mitigated" for verdict in verdicts)
            else "unresolved"
        )
    return merged


def _change(current: Optional[GoalVerdict], baseline: Optional[GoalVerdict]) -> str:
    if baseline is None:
        return "new"
    if current is None:
        return "dropped"
    if current == "jailbroken" and baseline != "jailbroken":
        return "regressed"
    if baseline == "jailbroken" and current != "jailbroken":
        return "fixed"
    return "unchanged"


def compare_runs(
    current: CampaignRun,
    current_attack_runs: Iterable[AttackRun],
    current_outcomes: Iterable[GoalOutcome],
    baseline: CampaignRun,
    baseline_attack_runs: Iterable[AttackRun],
    baseline_outcomes: Iterable[GoalOutcome],
) -> dict[str, Any]:
    """``GET /run/{id}/compare``: goals matched by exact text, each campaign
    run's verdicts taken over its whole scope."""

    def verdicts(
        run: CampaignRun,
        attack_runs: Iterable[AttackRun],
        outcomes: Iterable[GoalOutcome],
    ) -> dict[str, dict[str, Any]]:
        runs = children(run, attack_runs)
        goals = summarize_goals(
            _of(outcomes, runs), is_complete(run.status, runs), runs
        )
        return _verdicts_by_text(goals)

    now = verdicts(current, current_attack_runs, current_outcomes)
    then = verdicts(baseline, baseline_attack_runs, baseline_outcomes)
    goals = []
    for text in set(now) | set(then):
        labels = now.get(text) or then[text]
        current_verdict = now[text]["verdict"] if text in now else None
        baseline_verdict = then[text]["verdict"] if text in then else None
        goals.append(
            {
                "goal": text,
                "category": labels["category"],
                "subcategory": labels["subcategory"],
                "current": current_verdict,
                "baseline": baseline_verdict,
                "change": _change(current_verdict, baseline_verdict),
            }
        )
    goals.sort(key=lambda goal: (_CHANGE_ORDER.index(goal["change"]), goal["goal"]))

    def head(run: CampaignRun) -> dict[str, Any]:
        return {"id": run.id, "name": run.name, "created_at": iso(run.created_at)}

    return {
        "current": head(current),
        "baseline": head(baseline),
        "counts": {
            change: sum(goal["change"] == change for goal in goals)
            for change in ("regressed", "fixed", "unchanged", "new", "dropped")
        },
        "goals": goals,
    }


__all__ = [
    "CampaignRunSummary",
    "campaign_run_report",
    "campaign_run_summaries",
    "campaign_run_summary",
    "children",
    "compare_runs",
    "goal_listing",
    "goal_matrix",
    "is_previous",
    "iso",
    "pick_previous",
    "previous_summary",
    "scoped_runs",
]
