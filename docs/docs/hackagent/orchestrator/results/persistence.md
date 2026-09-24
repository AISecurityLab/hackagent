---
sidebar_label: persistence
title: hackagent.orchestrator.results.persistence
---

`RunSink` over a :class:`~hackagent.storage.store.Store`.

Tracking writes result, trace and run rows through this object. Evaluation
metrics passed in are stored as given; `eval_*` columns are produced by
:mod:`hackagent.orchestrator.results.mapping` before they reach here.

## StoreSink Objects

```python
class StoreSink()
```

Adapt a `Store` to the tracking :class:`RunSink` protocol.

#### write\_verdict

```python
def write_verdict(result_id: UUID, result: AttackResult) -> Any
```

Persist the mapped evaluation columns for one judged result.

