---
sidebar_label: goals
title: hackagent.reporting.goals
---

Goal verdicts and the summaries built from them.

A goal&#x27;s verdict is `jailbroken` if any attempt is a jailbreak; else
`mitigated` if its scope is complete and every attempt is mitigated; else
`unresolved`. A campaign scope is complete when the campaign run and every
attack run in it are `COMPLETED`; one attack run&#x27;s own summary always counts
as complete, because the runner records a goal&#x27;s attempts after that attack
has finished the goal.

#### VERDICT\_CODES

How `/matrix` codes a per-attack verdict.

#### UNKNOWN\_CATEGORY

Category of a goal no attempt labelled, and subcategory of one with none.

#### goal\_verdict

```python
def goal_verdict(*, attempts: int, jailbreak: int, mitigated: int,
                 complete: bool) -> GoalVerdict
```

The verdict of a goal from its attempt counts.

#### attack\_verdict

```python
def attack_verdict(outcome: GoalOutcome) -> AttackVerdict
```

One attack run&#x27;s verdict on a goal: `error` when every attempt errored.

#### is\_complete

```python
def is_complete(status: str, attack_runs: Iterable[AttackRun]) -> bool
```

A campaign scope is complete when it and all its attack runs completed.

#### run\_order

```python
def run_order(runs: Iterable[AttackRun]) -> list[AttackRun]
```

Attack runs in report order: by `created_at`, then `id`.

#### summarize\_goals

```python
def summarize_goals(
    outcomes: Iterable[GoalOutcome],
    complete: bool,
    runs: Sequence[AttackRun] = ()) -> list[GoalSummary]
```

One summary per goal index, ordered by index.

A goal&#x27;s text comes from the most recently created attack run of `runs`
that recorded it, and its labels from the most recently created one that
recorded a category (`created_at`, then `id`; runs not in `runs`
come first).

#### outcome\_counts

```python
def outcome_counts(goals: Iterable[GoalSummary]) -> OutcomeCounts
```

How many of `goals` were recorded, and how many have each verdict.

#### subcategory\_name

```python
def subcategory_name(goal: GoalSummary) -> str
```

The subcategory a goal is grouped under; empty is `Unspecified`.

#### category\_summaries

```python
def category_summaries(goals: Iterable[GoalSummary]) -> list[CategorySummary]
```

Counts per category (sorted), and per subcategory in order of first goal.

#### attack\_outcomes

```python
def attack_outcomes(goals: list[GoalSummary], outcomes: Iterable[GoalOutcome],
                    runs: Sequence[AttackRun]) -> list[GoalSummary]
```

`goals` with each attack run&#x27;s own verdict on them, in run order.

## GoalFilters Objects

```python
@dataclass(frozen=True)
class GoalFilters()
```

The filters of `/goals`; see :func:`~hackagent.reporting.http.goal_filters`.

#### filter\_goals

```python
def filter_goals(goals: Iterable[GoalSummary],
                 filters: GoalFilters) -> list[GoalSummary]
```

The goals that pass every filter, in order.

