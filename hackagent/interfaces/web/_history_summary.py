# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Pure goal and taxonomy summaries shared by local campaign endpoints."""

from __future__ import annotations

from typing import Literal, TypedDict

from hackagent.reporting.buckets import result_bucket
from hackagent.storage.records import ResultRecord

GoalVerdict = Literal["jailbroken", "mitigated", "unresolved"]


class AttackOutcome(TypedDict):
    run_id: str
    verdict: Literal["jailbroken", "mitigated", "unresolved", "error"]
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


def outcome_counts(goals: list[GoalSummary]) -> OutcomeCounts:
    return {
        "recorded_goals": len(goals),
        "jailbroken": sum(goal["verdict"] == "jailbroken" for goal in goals),
        "mitigated": sum(goal["verdict"] == "mitigated" for goal in goals),
        "unresolved": sum(goal["verdict"] == "unresolved" for goal in goals),
    }


def summarize_goals(results: list[ResultRecord], completed: bool) -> list[GoalSummary]:
    grouped: dict[int, list[ResultRecord]] = {}
    for result in results:
        grouped.setdefault(result.goal_index, []).append(result)
    goals: list[GoalSummary] = []
    for index, attempts in sorted(grouped.items()):
        labels = [item.metadata for item in attempts if item.metadata.get("category")]
        category = str(labels[0]["category"]) if labels else "Unknown"
        subcategory = str(labels[0].get("subcategory") or "") if labels else ""
        buckets = [
            result_bucket(item.evaluation_status, item.evaluation_notes)
            for item in attempts
        ]
        verdict: GoalVerdict = "unresolved"
        if "jailbreak" in buckets:
            verdict = "jailbroken"
        elif completed and all(bucket == "mitigated" for bucket in buckets):
            verdict = "mitigated"
        goals.append(
            {
                "index": index,
                "category": category,
                "subcategory": subcategory,
                "category_source": "recorded" if labels else "unknown",
                "goal": attempts[0].goal,
                "verdict": verdict,
                "attempts": len(attempts),
                "successful_attempts": buckets.count("jailbreak"),
                "errors": buckets.count("error"),
                "pending": buckets.count("pending"),
                "run_ids": sorted({str(item.run_id) for item in attempts}),
            }
        )
    return goals


def category_summaries(goals: list[GoalSummary]) -> list[CategorySummary]:
    categories: dict[str, list[GoalSummary]] = {}
    for goal in goals:
        categories.setdefault(goal["category"], []).append(goal)
    summaries: list[CategorySummary] = []
    for category, group in sorted(categories.items()):
        subcategories: dict[str, list[GoalSummary]] = {}
        for goal in group:
            subcategories.setdefault(goal["subcategory"] or "Unspecified", []).append(
                goal
            )
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
