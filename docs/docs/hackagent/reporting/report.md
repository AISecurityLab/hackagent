---
sidebar_label: report
title: hackagent.reporting.report
---

Campaign run summaries, reports, goal listings, the matrix and comparisons.

Every function takes rows (:mod:`hackagent.reporting.rows`, the stored
:class:`~hackagent.reporting.tallies.GoalOutcome`) and returns the JSON body
of a route, so both servers answer identically.

#### iso

```python
def iso(value: Optional[datetime]) -> Optional[str]
```

How every timestamp is rendered: `datetime.isoformat()`.

#### children

```python
def children(run: CampaignRun,
             attack_runs: Iterable[AttackRun]) -> list[AttackRun]
```

The attack runs of `run`, in report order.

#### campaign\_run\_summary

```python
def campaign_run_summary(run: CampaignRun, attack_runs: Iterable[AttackRun],
                         totals: Iterable[GoalTotal]) -> CampaignRunSummary
```

`GET /run/{id}/summary`: one campaign run&#x27;s `CampaignRunSummary`.

`attack_runs` and `totals` may hold other campaign runs&#x27; rows too.

#### campaign\_run\_summaries

```python
def campaign_run_summaries(
        runs: Sequence[CampaignRun], attack_runs: Iterable[AttackRun],
        totals: Iterable[GoalTotal]) -> list[CampaignRunSummary]
```

The items of a `GET /run/summary` page, in the order of `runs`.

#### is\_previous

```python
def is_previous(current: CampaignRun, candidate: CampaignRun) -> bool
```

Whether `candidate` may be the `previous` run of `current`: a
`COMPLETED` run of the same saved campaign (or, for a run of no saved
campaign, of no saved campaign with the same agent and name), created
before it.

#### pick\_previous

```python
def pick_previous(current: CampaignRun,
                  candidates: Iterable[CampaignRun]) -> Optional[CampaignRun]
```

The most recent run of `candidates` that :func:`is_previous`.

A backend may pass any superset of the matching runs, e.g. the
`COMPLETED` runs of the same campaign (or agent) created before
`current`, newest first, `LIMIT 1` after filtering on the same keys.

#### previous\_summary

```python
def previous_summary(run: CampaignRun, attack_runs: Iterable[AttackRun],
                     totals: Iterable[GoalTotal]) -> dict[str, Any]
```

The `previous` object of a report.

#### scoped\_runs

```python
def scoped_runs(
        run: CampaignRun, attack_runs: Iterable[AttackRun],
        scope_run_id: Optional[str]
) -> tuple[list[AttackRun], list[AttackRun]]
```

`(every attack run, the attack runs in scope)`; raises
:class:`~hackagent.reporting.http.NotFound` for a scope that is not one of
`run`&#x27;s attack runs.

#### campaign\_run\_report

```python
def campaign_run_report(
        run: CampaignRun,
        attack_runs: Iterable[AttackRun],
        outcomes: Iterable[GoalOutcome],
        *,
        scope_run_id: Optional[str] = None,
        previous: Optional[dict[str, Any]] = None) -> dict[str, Any]
```

`GET /run/{id}/report`.

`outcomes` are the stored goal outcomes of `run` (rows of other runs
are ignored); `previous` is :func:`previous_summary` of
:func:`pick_previous`, or None.

#### goal\_listing

```python
def goal_listing(run: CampaignRun,
                 attack_runs: Iterable[AttackRun],
                 outcomes: Iterable[GoalOutcome],
                 filters: GoalFilters,
                 *,
                 scope_run_id: Optional[str] = None) -> list[GoalSummary]
```

Every goal of `GET /run/{id}/goals` that passes `filters`, with its
per-attack outcomes; the server pages the list.

#### goal\_matrix

```python
def goal_matrix(run: CampaignRun, attack_runs: Iterable[AttackRun],
                outcomes: Iterable[GoalOutcome]) -> dict[str, Any]
```

`GET /run/{id}/matrix`: every goal&#x27;s verdict per attack run, columnar.

#### compare\_runs

```python
def compare_runs(current: CampaignRun,
                 current_attack_runs: Iterable[AttackRun],
                 current_outcomes: Iterable[GoalOutcome],
                 baseline: CampaignRun,
                 baseline_attack_runs: Iterable[AttackRun],
                 baseline_outcomes: Iterable[GoalOutcome]) -> dict[str, Any]
```

`GET /run/{id}/compare`: goals matched by exact text, each campaign
run&#x27;s verdicts taken over its whole scope.

