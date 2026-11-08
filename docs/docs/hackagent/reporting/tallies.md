---
sidebar_label: tallies
title: hackagent.reporting.tallies
---

Stored per-goal tallies and the functions that keep them.

Reports never recount results or scan traces. A backend keeps two tables
that mirror :class:`GoalOutcome` and :class:`GoalUsage` column for column, and
updates them in the same transaction as every write that affects them:

* result created or updated: recompute the goal&#x27;s :class:`GoalOutcome` with
  :func:`goal_outcome` from the light :class:`ResultRow` of every result of
  that (attack run, goal index), keeping the stored trace coverage;
* trace created: apply :func:`add_trace` to the goal&#x27;s stored rows, given the
  :class:`TraceFlags` of the result&#x27;s earlier traces;
* result or trace deleted: recompute both rows of the goal from what is left,
  with :func:`goal_outcome`, :func:`trace_coverage` and :func:`goal_usage`
  (or delete them when no result is left);
* attack run deleted: delete its rows.

Timestamps are timezone-aware datetimes. Ids are lowercase canonical UUID
strings; ordering &quot;by `created_at` then `id`&quot; compares those strings,
which is also how Postgres orders `uuid` and SQLite orders `TEXT`.

#### INTERACTION

Label of the usage row that counts a goal&#x27;s `interaction` steps.

#### INTERACTION\_STEP

`step_type` of the step the runner records for each exchange with the
target. Both stores keep it as written (`StepKind.INTERACTION`; the
platform&#x27;s `Trace.StepType.INTERACTION`) and every rule compares it
exactly.

## ResultRow Objects

```python
@dataclass(frozen=True)
class ResultRow()
```

The light columns of one result, which its goal&#x27;s outcome is computed from.

Read for every result of one (attack run, goal index)::

    SELECT id, goal, evaluation_status, evaluation_notes,
           agent_specific_data-&gt;&gt;&#x27;category&#x27;                AS category,
           agent_specific_data-&gt;&gt;&#x27;subcategory&#x27;             AS subcategory,
           (agent_specific_data-&gt;&#x27;attack_metadata&#x27;
              -&gt;&gt;&#x27;goal_active_target_elapsed_s&#x27;)::float     AS active_elapsed_s,
           created_at, updated_at
    FROM result WHERE run_id = %s AND goal_index = %s

`category` and `subcategory` are `None` when missing or empty.
`active_elapsed_s` is `None` unless it is a JSON number.
:meth:`from_data` builds the row from a result already in memory.

## TraceRow Objects

```python
@dataclass(frozen=True)
class TraceRow()
```

The light columns of one trace step, which usage and coverage count.

Read with::

    SELECT result_id, step_type,
           content-&gt;&gt;&#x27;node&#x27;  AS node,
           content-&gt;&gt;&#x27;label&#x27; AS label,
           content-&gt;&gt;&#x27;scope&#x27; AS scope,
           COALESCE((content-&gt;&#x27;data&#x27;-&gt;&#x27;usage&#x27;-&gt;&gt;&#x27;prompt_tokens&#x27;)::bigint,
                    (content-&gt;&#x27;response&#x27;-&gt;&#x27;usage&#x27;-&gt;&gt;&#x27;prompt_tokens&#x27;)::bigint)
               AS prompt_tokens,
           COALESCE((content-&gt;&#x27;data&#x27;-&gt;&#x27;usage&#x27;-&gt;&gt;&#x27;completion_tokens&#x27;)::bigint,
                    (content-&gt;&#x27;response&#x27;-&gt;&#x27;usage&#x27;-&gt;&gt;&#x27;completion_tokens&#x27;)::bigint)
               AS completion_tokens
    FROM trace WHERE result_id IN (...)

:meth:`from_content` builds the row from a trace already in memory, which
is what a backend does when it creates one.

## TraceCoverage Objects

```python
@dataclass(frozen=True)
class TraceCoverage()
```

How many attempts of a goal recorded each kind of trace step.

#### labelled\_call\_attempts

Attempts with a `call` node that carries a non-empty `label`.

#### target\_call\_attempts

Attempts with a `call` node labelled `target`.

#### interaction\_attempts

Attempts with an `interaction` step.

## TraceFlags Objects

```python
@dataclass(frozen=True)
class TraceFlags()
```

Which kinds of trace step one attempt has recorded so far.

## GoalOutcome Objects

```python
@dataclass(frozen=True)
class GoalOutcome()
```

Table `goal_outcome`: one row per (attack run, goal index).

Primary key `(run_id, goal_index)`; index
`(campaign_run_id, run_id, goal_index)`.

=========================  ============  ===================================
column                     type          value
=========================  ============  ===================================
campaign_run_id            uuid, null    the attack run&#x27;s campaign run
run_id                     uuid          the attack run
goal_index                 integer
goal                       text          goal text of the latest attempt
category                   text          of the latest attempt that has
                                         one, `''` when none has
subcategory                text          of that same attempt, or `''`
attempts                   integer       results
jailbreak                  integer       results per bucket
mitigated                  integer
error                      integer
pending                    integer
first_jailbreak_attempt    integer, null ordinal (1-based, `created_at`
                                         then `id`) of the first jailbreak
min_jailbreak_elapsed_s    float, null   smallest active goal clock among
                                         the jailbreaks that carry one
timed_jailbreaks           integer       jailbreaks that carry the clock
first_created_at           timestamp     MIN(created_at) of the results
last_updated_at            timestamp     MAX(updated_at) of the results
labelled_call_attempts     integer       see :class:`TraceCoverage`
target_call_attempts       integer
interaction_attempts       integer
=========================  ============  ===================================

&quot;Latest&quot; is the greatest (`created_at`, `id`).

## GoalUsage Objects

```python
@dataclass(frozen=True)
class GoalUsage()
```

Table `goal_usage`: one row per (attack run, goal index, label).

Primary key `(run_id, goal_index, label)`; index
`(campaign_run_id, run_id, goal_index)`. `label` is a `call` node&#x27;s
label, or `''` for `interaction` steps (see :func:`usage_label`).

=================  ==========  ==========================================
column             type        value
=================  ==========  ==========================================
campaign_run_id    uuid, null  the attack run&#x27;s campaign run
run_id             uuid        the attack run
goal_index         integer
label              text
calls              integer     steps counted under this label
goal_scoped_calls  integer     of which `content.scope = 'goal'`
prompt_tokens      bigint      sum over the steps that report it
completion_tokens  bigint      sum over the steps that report it
usage_calls        integer     steps that report both token counts
=================  ==========  ==========================================

#### usage\_label

```python
def usage_label(trace: TraceRow) -> Optional[str]
```

The usage row a trace step counts under, or None when it counts nowhere.

An `interaction` step counts under `''`; any other step whose
`node` is `call` counts under its label. A call node without a label
names no role and is not counted.

#### trace\_flags

```python
def trace_flags(traces: Iterable[TraceRow]) -> TraceFlags
```

What `traces` (the steps of one attempt) have recorded.

#### trace\_coverage

```python
def trace_coverage(traces: Iterable[TraceRow]) -> TraceCoverage
```

Coverage of a goal from every step of every one of its attempts.

#### goal\_outcome

```python
def goal_outcome(
    *,
    campaign_run_id: Optional[str],
    run_id: str,
    goal_index: int,
    results: Sequence[ResultRow],
    coverage: TraceCoverage = TraceCoverage()
) -> Optional[GoalOutcome]
```

The outcome row of a goal from every one of its results, or None
when it has none. `coverage` is kept as given: results do not change it.

#### goal\_usage

```python
def goal_usage(*, campaign_run_id: Optional[str], run_id: str, goal_index: int,
               traces: Iterable[TraceRow]) -> list[GoalUsage]
```

The usage rows of a goal from every step of every one of its attempts,
ordered by label.

#### add\_trace

```python
def add_trace(outcome: GoalOutcome, usage: Optional[GoalUsage],
              trace: TraceRow,
              before: TraceFlags) -> tuple[GoalOutcome, Optional[GoalUsage]]
```

Count one new trace step of an attempt of `outcome`&#x27;s goal.

`usage` is the stored row under :func:`usage_label` of `trace` (None
when there is none yet), and `before` the :func:`trace_flags` of the
attempt&#x27;s earlier steps. Returns the outcome to store and the usage row to
upsert (None when the step counts under no label).

