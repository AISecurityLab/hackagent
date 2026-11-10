# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""What each attack run spent: calls by role, target tokens and time.

``call`` trace nodes are labelled with the role that made them: ``target``,
``panel`` (a judge), and anything else (``attacker`` or a helper such as
``on_topic``) is the attacker side. Each goal counts its calls from what it
recorded: its labelled call nodes when it has any, else its target
interaction steps, whose attacker and judge calls are unknown. A run sums its
goals; when any goal's attacker and judge calls are unknown, the run's are
reported as ``None``: not traced, rather than zero.

A goal sample carries the first successful attempt's ordinal and, when every
successful attempt carries an active goal clock, the earliest one; local
scheduling waits are excluded and legacy wall clocks are not substituted.
Token totals are unknown when any target call or attempt lacks usage.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence

from hackagent.reporting.goals import run_order
from hackagent.reporting.rows import AttackRun, Latency
from hackagent.reporting.tallies import INTERACTION, GoalOutcome, GoalUsage

#: Call labels with a role of their own; any other label is the attacker side.
TARGET = "target"
JUDGE = "panel"


def quantile(ordered: Sequence[float], q: float) -> float:
    """Linear-interpolated quantile of an already sorted, non-empty sequence."""
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def latency_summary(latencies: Iterable[Latency]) -> Optional[dict[str, Any]]:
    """Median, p90 and sample count of one run's target latencies."""
    values = sorted(
        float(row.latency_ms) for row in latencies for _ in range(row.count)
    )
    if not values:
        return None
    return {
        "median": quantile(values, 0.5),
        "p90": quantile(values, 0.9),
        "samples": len(values),
    }


def _goal_calls(usage: Iterable[GoalUsage]) -> Optional[dict[str, Any]]:
    """One goal's calls by role, from the source that goal recorded.

    A goal with labelled call nodes counts every role from them (an
    interaction step mirrors a target call node and is not counted again).
    A goal with only interaction steps counts them as its target calls; its
    attacker and judge calls are unknown (None). A goal that recorded
    neither has no source (None) and contributes nothing.
    """
    per_label: dict[str, int] = {}
    for row in usage:
        per_label[row.label] = per_label.get(row.label, 0) + row.calls
    nodes = {label: n for label, n in per_label.items() if label != INTERACTION}
    if nodes:
        return {
            "target": nodes.get(TARGET, 0),
            "attacker": sum(
                n for label, n in nodes.items() if label not in (TARGET, JUDGE)
            ),
            "judge": nodes.get(JUDGE, 0),
        }
    if INTERACTION in per_label:
        return {"target": per_label[INTERACTION], "attacker": None, "judge": None}
    return None


def _calls(per_goal: Iterable[Iterable[GoalUsage]]) -> tuple[dict[str, Any], bool]:
    """A run's calls by role, and whether it traced its call nodes.

    ``target`` sums every goal's target calls (see :func:`_goal_calls`). The
    run's calls are traced when at least one goal recorded labelled call
    nodes and no goal recorded only interaction steps; then ``attacker`` and
    ``judge`` sum the goals' counts. Otherwise some goal's attacker and judge
    calls are unknown, and so are the run's: both are None, not zero.
    """
    counted = [calls for usage in per_goal if (calls := _goal_calls(usage))]
    traced = bool(counted) and all(calls["attacker"] is not None for calls in counted)
    return {
        "target": sum(calls["target"] for calls in counted),
        "attacker": sum(calls["attacker"] for calls in counted) if traced else None,
        "judge": sum(calls["judge"] for calls in counted) if traced else None,
    }, traced


def goal_sample(
    outcome: GoalOutcome, usage: Iterable[GoalUsage]
) -> tuple[dict[str, Any], Optional[tuple[int, int]]]:
    """One goal's sample, and its target ``(prompt, completion)`` tokens when
    its usage is complete (None otherwise)."""
    labels = {row.label: row for row in usage}
    nodes = {label: row for label, row in labels.items() if label != INTERACTION}
    interactions = labels.get(INTERACTION)
    target = nodes.get(TARGET) if nodes else interactions
    source = target
    if source is None or not source.usage_calls:
        source = interactions
    attempts = outcome.attempts
    complete = source is not None and source.usage_calls == source.calls
    if source is not None and complete:
        if source.label == INTERACTION:
            complete = outcome.interaction_attempts == attempts
        else:
            # A batched phase can attach all its goal-scoped calls to one result.
            complete = (
                outcome.target_call_attempts == attempts
                or source.goal_scoped_calls >= attempts
            )
    calls_complete = outcome.labelled_call_attempts == attempts or (
        target is not None and target.goal_scoped_calls >= attempts
    )
    timed = outcome.jailbreak > 0 and outcome.timed_jailbreaks == outcome.jailbreak
    sample = {
        "goal_index": outcome.goal_index,
        "first_jailbreak_attempt": outcome.first_jailbreak_attempt,
        "first_jailbreak_elapsed_s": outcome.min_jailbreak_elapsed_s if timed else None,
        "attempts": attempts,
        "calls": sum(row.calls for row in nodes.values())
        if nodes and calls_complete
        else None,
        "target_tokens": source.prompt_tokens + source.completion_tokens
        if source is not None and complete
        else None,
        "elapsed_s": max(
            (outcome.last_updated_at - outcome.first_created_at).total_seconds(), 0.0
        ),
    }
    tokens = (
        (source.prompt_tokens, source.completion_tokens)
        if source is not None and complete
        else None
    )
    return sample, tokens


def run_cost(
    run: AttackRun,
    outcomes: Sequence[GoalOutcome],
    usage: Iterable[GoalUsage],
    latencies: Iterable[Latency],
) -> dict[str, Any]:
    """One attack run's ``RunCost``, from its rows (which must not be empty)."""
    by_goal: dict[int, list[GoalUsage]] = {}
    for row in usage:
        by_goal.setdefault(row.goal_index, []).append(row)
    calls, traced = _calls(by_goal.values())
    samples = []
    prompt = completion = 0
    known = True
    for outcome in sorted(outcomes, key=lambda row: row.goal_index):
        sample, tokens = goal_sample(outcome, by_goal.get(outcome.goal_index, []))
        samples.append(sample)
        if tokens is None:
            known = False
        else:
            prompt += tokens[0]
            completion += tokens[1]
    started = min(row.first_created_at for row in outcomes)
    finished = max(row.last_updated_at for row in outcomes)
    return {
        "run_id": run.id,
        "attempts": sum(row.attempts for row in outcomes),
        "goals": len(outcomes),
        "elapsed_s": max((finished - started).total_seconds(), 0.0),
        "calls": calls,
        "calls_traced": traced,
        "target_tokens": {"prompt": prompt, "completion": completion}
        if known
        else None,
        "target_latency_ms": latency_summary(latencies),
        "goal_samples": samples,
    }


def campaign_run_costs(
    attack_runs: Iterable[AttackRun],
    outcomes: Iterable[GoalOutcome],
    usage: Iterable[GoalUsage],
    latencies: Iterable[Latency],
) -> dict[str, Any]:
    """``GET /run/{id}/costs``: one ``RunCost`` per attack run that has
    results, in report order."""
    by_run: dict[str, list[GoalOutcome]] = {}
    for outcome in outcomes:
        by_run.setdefault(outcome.run_id, []).append(outcome)
    usage_by_run: dict[str, list[GoalUsage]] = {}
    for row in usage:
        usage_by_run.setdefault(row.run_id, []).append(row)
    latency_by_run: dict[str, list[Latency]] = {}
    for latency in latencies:
        latency_by_run.setdefault(latency.run_id, []).append(latency)
    return {
        "runs": [
            run_cost(
                run,
                by_run[run.id],
                usage_by_run.get(run.id, []),
                latency_by_run.get(run.id, []),
            )
            for run in run_order(attack_runs)
            if run.id in by_run
        ]
    }


__all__ = [
    "JUDGE",
    "TARGET",
    "campaign_run_costs",
    "goal_sample",
    "latency_summary",
    "quantile",
    "run_cost",
]
