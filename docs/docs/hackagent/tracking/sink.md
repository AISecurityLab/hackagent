---
sidebar_label: sink
title: hackagent.tracking.sink
---

Where a tracker writes run records.

``RunSink`` is local to tracking. Persistence (a ``Store``) implements it
in the orchestrator; this package does not import storage. Method names and
payloads match the existing result, trace and run records so the HTTP and
SQLite schemas stay unchanged.

## RunSink Objects

```python
@runtime_checkable
class RunSink(Protocol)
```

Writes result, trace and run rows for one attack run.

