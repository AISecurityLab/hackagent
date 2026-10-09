---
sidebar_label: tracking
title: hackagent.orchestrator.campaign.tracking
---

Persist campaign runs to the HackAgent store.

One :class:`RunTracker` owns the store records of one attack run: the
attack and run rows when it starts, a result row per attempt as soon as
the attempt is judged (with a trace row per search step, then the final
exchange), and the final run status.

#### open\_store

```python
def open_store(storage: StorageSpec) -> Store
```

Open the local database or connect to the remote API.

#### register\_target

```python
def register_target(store: Store, target: ModelConfig) -> UUID
```

Create or update the agent record that runs are attached to.

## RunTracker Objects

```python
class RunTracker()
```

Store records of one attack run.

#### record

```python
def record(attempt: Attempt) -> None
```

Persist one attempt with its evaluation.

