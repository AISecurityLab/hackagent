---
sidebar_label: rows
title: hackagent.reporting.rows
---

The rows a backend reads to answer a report request.

Each docstring gives the query that produces the rows, in Postgres terms
over the platform&#x27;s tables (`run`, `result`, `trace`, `attack`,
`agent`) and the two tally tables of :mod:`hackagent.reporting.tallies`.
Queries only filter, select columns and GROUP BY with plain aggregates;
every rule is applied by :mod:`hackagent.reporting` to the rows.

## CampaignRun Objects

```python
@dataclass(frozen=True)
class CampaignRun()
```

One campaign run: a parent run, with its agent&#x27;s name.

::

    SELECT run.id, run.run_config-&gt;&gt;&#x27;campaign_name&#x27; AS name,
           run.campaign_id, run.agent_id, agent.name AS target, run.status,
           run.executor, run.timestamp AS created_at, &lt;updated_at&gt;,
           run.finished_at, run.revision
    FROM run JOIN agent ON agent.id = run.agent_id
    WHERE run.parent_id IS NULL AND &lt;filters&gt;
    ORDER BY run.timestamp DESC, run.id

`configuration` (`run_config->'campaign_config'`), `audit`
(`run_config->'evaluation_audit'`) and `notes` (`run_notes`) are
read only for :func:`~hackagent.reporting.report.campaign_run_report`.
`notes` may be `''` or `None` for no notes.

## AttackRun Objects

```python
@dataclass(frozen=True)
class AttackRun()
```

One attack run of a campaign run.

::

    SELECT run.id, run.parent_id AS campaign_run, run.status,
           run.timestamp AS created_at, run.attack_id AS attack,
           attack.type AS technique, run.run_notes AS notes,
           run.run_config AS configuration,
           attack.configuration AS attack_configuration
    FROM run LEFT JOIN attack ON attack.id = run.attack_id
    WHERE run.parent_id IN (...)

The summary list reads only the first four columns. For a report the
backend passes `technique` through
:func:`hackagent.storage.records.canonical_attack_type`, sets `family`
to :func:`hackagent.attacks.techniques.registry.attack_family` of it and
`attack_configuration` to
:func:`hackagent.orchestrator.campaign.spec.redacted` of the attack&#x27;s
configuration; without an attack, `technique` is `'Unknown'` and the
other two `None`.

## GoalTotal Objects

```python
@dataclass(frozen=True)
class GoalTotal()
```

A goal&#x27;s attempts across a whole campaign run, per bucket.

::

    SELECT campaign_run_id AS campaign_run, goal_index,
           SUM(attempts), SUM(jailbreak), SUM(mitigated), SUM(error),
           SUM(pending)
    FROM goal_outcome WHERE campaign_run_id IN (...)
    GROUP BY campaign_run_id, goal_index

## Attempt Objects

```python
@dataclass(frozen=True)
class Attempt()
```

One attempt at a goal, on a page of `/attempts`.

::

    SELECT id, run_id, bucket, evaluation_notes AS notes,
           timestamp AS created_at
    FROM result WHERE run_id IN (...) AND goal_index = %s
    ORDER BY created_at, id LIMIT %s OFFSET %s

`notes` may be `''` or `None` for no notes.

## FirstSuccess Objects

```python
@dataclass(frozen=True)
class FirstSuccess()
```

The first jailbreak among a goal&#x27;s attempts and its 1-based position.

::

    SELECT id, timestamp FROM result
    WHERE run_id IN (...) AND goal_index = %s AND bucket = &#x27;jailbreak&#x27;
    ORDER BY timestamp, id LIMIT 1;
    -- position:
    SELECT COUNT(*) FROM result
    WHERE run_id IN (...) AND goal_index = %s
      AND (timestamp, id) &lt;= (%(timestamp)s, %(id)s)

## StructureResult Objects

```python
@dataclass(frozen=True)
class StructureResult()
```

One attempt of a goal in full, for `/structure`.

Every result of one (attack run, goal index), all columns.

## StructureTrace Objects

```python
@dataclass(frozen=True)
class StructureTrace()
```

One trace step of a :class:`StructureResult`, all columns.

## Latency Objects

```python
@dataclass(frozen=True)
class Latency()
```

How many results of an attack run took a given target latency.

::

    SELECT run_id, latency_ms, COUNT(*) AS count FROM result
    WHERE run_id IN (...) AND latency_ms IS NOT NULL
    GROUP BY run_id, latency_ms

