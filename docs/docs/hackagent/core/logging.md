---
sidebar_label: logging
title: hackagent.core.logging
---

Logger access for library code.

Library modules only obtain loggers; they never install handlers or set
levels. Handler configuration belongs to the application (the CLI does it in
:mod:`hackagent.interfaces.cli.logging_setup`).

#### REPORTED\_AS\_EVENT

`extra=` for a log line whose fact a campaign progress event reports
too. The line still reaches every handler; the run activity relay skips
it, so the platform records the fact once, from the event.

#### TRACE\_LOGGER

Logger of an attack&#x27;s trace: a record for each node an attack records
(:mod:`hackagent.attacks.techniques.trace`), with the node&#x27;s fields in the
record&#x27;s `trace_step`. Its DEBUG records quote prompts and replies, so
it stays on this machine: the run activity relay never reads it.

#### get\_logger

```python
def get_logger(name: str) -> logging.Logger
```

Return the logger called `name` without configuring it.

#### reported\_as\_event

```python
def reported_as_event(record: logging.LogRecord) -> bool
```

Return whether `record` was logged with :data:`REPORTED_AS_EVENT`.

#### trace\_step

```python
def trace_step(record: logging.LogRecord) -> Optional[Mapping[str, Any]]
```

The trace node a :data:`TRACE_LOGGER` record describes, or None.

