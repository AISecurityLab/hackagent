---
sidebar_label: scheduling
title: hackagent.orchestrator.execution.scheduling
---

Goal batching. One attack instance per worker, log labels via contextvars.

#### schedule

```python
def schedule(goals: Sequence[Goal], *, attack_factory: Callable[[], Any],
             batch_size: int | None, workers: int) -> List[AttackResult]
```

Run *goals*, splitting into batches when `batch_size` is set.

`batch_size` of `None` runs every goal in one `run()` call, which
is the historical default when the caller did not ask for batching.
Each worker builds its own attack instance.

