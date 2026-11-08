# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Goal verdicts and the summaries built from them.

A goal's verdict is ``jailbroken`` if any attempt is a jailbreak; else
``mitigated`` if its scope is complete and every attempt is mitigated; else
``unresolved``. A campaign scope is complete when the campaign run and every
attack run in it are ``COMPLETED``; one attack run's own summary always counts
as complete, because the runner records a goal's attempts after that attack
has finished the goal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Optional, Sequence, TypedDict

from hackagent.reporting.rows import AttackRun
from hackagent.reporting.tallies import GoalOutcome

GoalVerdict = Literal["jailbroken", "mitigated", "unresolved"]
AttackVerdict = Literal["jailbroken", "mitigated", "unresolved", "error"]

VERDICTS: tuple[GoalVerdict, ...] = ("jailbroken", "mitigated", "unresolved")

#: How ``/matrix`` codes a per-attack verdict.
VERDICT_CODES: dict[AttackVerdict, int] = {
    "unresolved": 0,
    "mitigated": 1,
    "error": 2,
    "jailbroken": 3,
}

#: Category of a goal no attempt labelled, and subcategory of one with none.
UNKNOWN_CATEGORY = "Unknown"
UNSPECIFIED = "Unspecified"


class AttackOutcome(TypedDict):
    run_id: str
    verdict: AttackVerdict
    attempts: int


class _GoalFields(TypedDict):
    index: int
    category: str
    subcategory: str
    category_source: Literal["recorded", "unknown"]
    goal: str
    verdict: GoalVerdict
    attempts: int
    successful_attempts: int
    errors: int
    pending: int
    run_ids: list[str]


class GoalSummary(_GoalFields, total=False):
    attack_outcomes: list[AttackOutcome]


class OutcomeCounts(TypedDict):
    recorded_goals: int
    jailbroken: int
    mitigated: int
    unresolved: int


class SubcategorySummary(OutcomeCounts):
    name: str


class CategorySummary(OutcomeCounts):
    category: str
    subcategories: list[SubcategorySummary]


def goal_verdict(
    *, attempts: int, jailbreak: int, mitigated: int, complete: bool
) -> GoalVerdict:
    """The verdict of a goal from its attempt counts."""
    if jailbreak:
        return "jailbroken"
    if complete and attempts and mitigated == attempts:
        return "mitigated"
    return "unresolved"


def attack_verdict(outcome: GoalOutcome) -> AttackVerdict:
    """One attack run's verdict on a goal: ``error`` when every attempt errored."""
    if outcome.error == outcome.attempts:
        return "error"
    return goal_verdict(
        attempts=outcome.attempts,
        jailbreak=outcome.jailbreak,
        mitigated=outcome.mitigated,
        complete=True,
    )


def is_complete(status: str, attack_runs: Iterable[AttackRun]) -> bool:
    """A campaign scope is complete when it and all its attack runs completed."""
    return status == "COMPLETED" and all(
        run.status == "COMPLETED" for run in attack_runs
    )


def run_order(runs: Iterable[AttackRun]) -> list[AttackRun]:
    """Attack runs in report order: by ``created_at``, then ``id``."""
    return sorted(runs, key=lambda run: (run.created_at, run.id))


def summarize_goals(
    outcomes: Iterable[GoalOutcome],
    complete: bool,
    runs: Sequence[AttackRun] = (),
) -> list[GoalSummary]:
    """One summary per goal index, ordered by index.

    A goal's text comes from the most recently created attack run of ``runs``
    that recorded it, and its labels from the most recently created one that
    recorded a category (``created_at``, then ``id``; runs not in ``runs``
    come first).
    """
    rank = {run.id: index for index, run in enumerate(run_order(runs), start=1)}
    grouped: dict[int, list[GoalOutcome]] = {}
    for outcome in outcomes:
        grouped.setdefault(outcome.goal_index, []).append(outcome)
    goals: list[GoalSummary] = []
    for index, rows in sorted(grouped.items()):
        rows.sort(key=lambda row: (rank.get(row.run_id, 0), row.run_id))
        labelled = next((row for row in reversed(rows) if row.category), None)
        attempts = sum(row.attempts for row in rows)
        jailbreak = sum(row.jailbreak for row in rows)
        goals.append(
            {
                "index": index,
                "category": labelled.category if labelled else UNKNOWN_CATEGORY,
                "subcategory": labelled.subcategory if labelled else "",
                "category_source": "recorded" if labelled else "unknown",
                "goal": rows[-1].goal,
                "verdict": goal_verdict(
                    attempts=attempts,
                    jailbreak=jailbreak,
                    mitigated=sum(row.mitigated for row in rows),
                    complete=complete,
                ),
                "attempts": attempts,
                "successful_attempts": jailbreak,
                "errors": sum(row.error for row in rows),
                "pending": sum(row.pending for row in rows),
                "run_ids": sorted({row.run_id for row in rows}),
            }
        )
    return goals


def outcome_counts(goals: Iterable[GoalSummary]) -> OutcomeCounts:
    """How many of ``goals`` were recorded, and how many have each verdict."""
    verdicts = [goal["verdict"] for goal in goals]
    return {
        "recorded_goals": len(verdicts),
        "jailbroken": verdicts.count("jailbroken"),
        "mitigated": verdicts.count("mitigated"),
        "unresolved": verdicts.count("unresolved"),
    }


def subcategory_name(goal: GoalSummary) -> str:
    """The subcategory a goal is grouped under; empty is ``Unspecified``."""
    return goal["subcategory"] or UNSPECIFIED


def category_summaries(goals: Iterable[GoalSummary]) -> list[CategorySummary]:
    """Counts per category (sorted), and per subcategory in order of first goal."""
    categories: dict[str, list[GoalSummary]] = {}
    for goal in goals:
        categories.setdefault(goal["category"], []).append(goal)
    summaries: list[CategorySummary] = []
    for category, group in sorted(categories.items()):
        subcategories: dict[str, list[GoalSummary]] = {}
        for goal in group:
            subcategories.setdefault(subcategory_name(goal), []).append(goal)
        summaries.append(
            {
                "category": category,
                **outcome_counts(group),
                "subcategories": [
                    {"name": name, **outcome_counts(subgroup)}
                    for name, subgroup in subcategories.items()
                ],
            }
        )
    return summaries


def attack_outcomes(
    goals: list[GoalSummary],
    outcomes: Iterable[GoalOutcome],
    runs: Sequence[AttackRun],
) -> list[GoalSummary]:
    """``goals`` with each attack run's own verdict on them, in run order."""
    by_goal: dict[tuple[str, int], GoalOutcome] = {
        (row.run_id, row.goal_index): row for row in outcomes
    }
    ordered = run_order(runs)
    for goal in goals:
        goal["attack_outcomes"] = [
            {
                "run_id": run.id,
                "verdict": attack_verdict(row),
                "attempts": row.attempts,
            }
            for run in ordered
            if (row := by_goal.get((run.id, goal["index"]))) is not None
        ]
    return goals


@dataclass(frozen=True)
class GoalFilters:
    """The filters of ``/goals``; see :func:`~hackagent.reporting.http.goal_filters`."""

    goal_index: Optional[int] = None
    category: str = ""
    subcategory: str = ""
    search: str = ""
    verdict: Optional[GoalVerdict] = None


def filter_goals(
    goals: Iterable[GoalSummary], filters: GoalFilters
) -> list[GoalSummary]:
    """The goals that pass every filter, in order."""
    search = filters.search.strip().casefold()
    return [
        goal
        for goal in goals
        if (filters.goal_index is None or goal["index"] == filters.goal_index)
        and (not filters.category or goal["category"] == filters.category)
        and (not filters.subcategory or subcategory_name(goal) == filters.subcategory)
        and (not search or search in goal["goal"].casefold())
        and (filters.verdict is None or goal["verdict"] == filters.verdict)
    ]


__all__ = [
    "AttackOutcome",
    "AttackVerdict",
    "CategorySummary",
    "GoalFilters",
    "GoalSummary",
    "GoalVerdict",
    "OutcomeCounts",
    "SubcategorySummary",
    "UNKNOWN_CATEGORY",
    "UNSPECIFIED",
    "VERDICTS",
    "VERDICT_CODES",
    "attack_outcomes",
    "attack_verdict",
    "category_summaries",
    "filter_goals",
    "goal_verdict",
    "is_complete",
    "outcome_counts",
    "run_order",
    "subcategory_name",
    "summarize_goals",
]
