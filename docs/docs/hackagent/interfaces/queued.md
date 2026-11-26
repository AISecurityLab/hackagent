---
sidebar_label: queued
title: hackagent.interfaces.queued
---

Runs queued from the dashboard for a local machine, run here: by
`hackagent run` and by the TUI&#x27;s Queued runs screen, with the same checks.

A queued run is refused (:class:`Refused`) before it is claimed when this
machine cannot run it: a key the server rejects, a run that is not queued
for a local machine or no longer queued, a campaign this version of
HackAgent cannot load, or model keys missing from the environment.

## Refused Objects

```python
class Refused(Exception)
```

Why this machine will not run a queued run; `code` is the exit code
`hackagent run` ends with, `missing` the variables to set.

## Ready Objects

```python
@dataclass
class Ready()
```

A queued run that passed the checks: its id and its campaign, and
what is worth knowing before it starts.

#### connect

```python
def connect(settings: Any) -> Any
```

The remote store, its key checked.

#### queued\_runs

```python
def queued_runs(store: Any) -> list[dict[str, Any]]
```

The runs queued for a local machine, newest first.

#### prepare

```python
def prepare(store: Any, run_id: str, settings: Any) -> Ready
```

The queued run `run_id`, checked; :class:`Refused` when it cannot
run here.

#### execute

```python
def execute(store: Any, ready: Ready, settings: Any) -> Any
```

Claim the run and execute it here; its outcome. Raises
:class:`~hackagent.storage.RunNotClaimable` when another machine was
first.

#### follow\_url

```python
def follow_url(settings: Any, run_id: UUID) -> Optional[str]
```

Where the dashboard shows the run, when it is known.

