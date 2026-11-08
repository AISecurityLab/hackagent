---
sidebar_label: costs
title: hackagent.reporting.costs
---

What each attack run spent: calls by role, target tokens and time.

`call` trace nodes are labelled with the role that made them: `target`,
`panel` (a judge), and anything else (`attacker` or a helper such as
`on_topic`) is the attacker side. Each goal counts its calls from what it
recorded: its labelled call nodes when it has any, else its target
interaction steps, whose attacker and judge calls are unknown. A run sums its
goals; when any goal&#x27;s attacker and judge calls are unknown, the run&#x27;s are
reported as `None`: not traced, rather than zero.

A goal sample carries the first successful attempt&#x27;s ordinal and, when every
successful attempt carries an active goal clock, the earliest one; local
scheduling waits are excluded and legacy wall clocks are not substituted.
Token totals are unknown when any target call or attempt lacks usage.

#### TARGET

Call labels with a role of their own; any other label is the attacker side.

#### quantile

```python
def quantile(ordered: Sequence[float], q: float) -> float
```

Linear-interpolated quantile of an already sorted, non-empty sequence.

#### latency\_summary

```python
def latency_summary(latencies: Iterable[Latency]) -> Optional[dict[str, Any]]
```

Median, p90 and sample count of one run&#x27;s target latencies.

#### goal\_sample

```python
def goal_sample(
    outcome: GoalOutcome, usage: Iterable[GoalUsage]
) -> tuple[dict[str, Any], Optional[tuple[int, int]]]
```

One goal&#x27;s sample, and its target `(prompt, completion)` tokens when
its usage is complete (None otherwise).

#### run\_cost

```python
def run_cost(run: AttackRun, outcomes: Sequence[GoalOutcome],
             usage: Iterable[GoalUsage],
             latencies: Iterable[Latency]) -> dict[str, Any]
```

One attack run&#x27;s `RunCost`, from its rows (which must not be empty).

#### campaign\_run\_costs

```python
def campaign_run_costs(attack_runs: Iterable[AttackRun],
                       outcomes: Iterable[GoalOutcome],
                       usage: Iterable[GoalUsage],
                       latencies: Iterable[Latency]) -> dict[str, Any]
```

`GET /run/{id}/costs`: one `RunCost` per attack run that has
results, in report order.

