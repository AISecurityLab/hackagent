---
sidebar_label: logging
title: hackagent.core.logging
---

Logger access for library code, and the run&#x27;s log as the one way out.

Library modules only obtain loggers and log text; they never install
handlers. What a campaign does reaches every interface as log records: the
CLI prints them, the TUI shows them in its run view, a run keeps them in its
`run.log`, and the executor relays them to the platform. Each interface is
a :class:`logging.Handler` that shows the lines its own way.

A line says what happened. Which attack and goal it is about comes from
:func:`about`, set by the code that runs them; which kind of line it is,
from the logger it was logged on (:data:`CAMPAIGN_LOGGER`,
:data:`GOALS_LOGGER`, :data:`TRACE_LOGGER`). A step of an attack&#x27;s trace
also carries its fields (:func:`trace_step`), from which it is written.

An interface attaches its handler with :func:`capture`, which hands it only
the records of the run it wraps, at the handler&#x27;s own level. The logger&#x27;s
level is the floor for every handler: the application opens it (the CLI to
DEBUG), and each handler chooses how much of that it shows.

#### PACKAGE\_LOGGER

The package&#x27;s root logger; every library logger descends from it.

#### CAMPAIGN\_LOGGER

The campaign&#x27;s own story: it started, each attack started and finished,
how it ended. A quiet log still shows these lines.

#### GOALS\_LOGGER

One line per goal and attack, saying how the goal ended: what a progress
count reads, with the goal count from :func:`subject_of`.

#### TRACE\_LOGGER

Logger of an attack&#x27;s trace: a record for each node an attack records
(:mod:`hackagent.attacks.techniques.trace`), with the node&#x27;s fields in the
record&#x27;s `trace_step`. Only its DEBUG records quote prompts and
replies, and nothing below INFO leaves the machine.

#### CLIENT\_RETRY\_LOGGERS

Loggers of the model clients that log each retry at INFO, which a run&#x27;s
activity relays: the application opens them to INFO, as the CLI does.

#### get\_logger

```python
def get_logger(name: str) -> logging.Logger
```

Return the logger called `name` without configuring it.

#### trace\_step

```python
def trace_step(record: logging.LogRecord) -> Optional[Mapping[str, Any]]
```

The trace node a :data:`TRACE_LOGGER` record describes, or None.

#### goal\_label

```python
def goal_label(goal: Any, goals: Any = None) -> str
```

`goal 3`, its number zero-padded to the width of the run&#x27;s goal
count (`goal 03` of 20, `goal 003` of 200): an attack&#x27;s lines start
their text at the same place, and `goal 03` never matches goal 13.

#### LEVEL\_WIDTH

Width of the level column: the longest level name, `WARNING`.

#### plain\_line

```python
def plain_line(level: str,
               message: str,
               created: Optional[float] = None) -> str
```

One record as written to a file: date and time, level, message.

#### LINE\_BREAK

What a line break inside a message is written as, to keep it one line.

#### one\_line

```python
def one_line(message: str) -> str
```

`message` with its line breaks shown as :data:`LINE_BREAK`, so a
provider error or a captured warning is one line like every other.

#### trace\_breadcrumb

```python
def trace_breadcrumb(step: Mapping[str, Any]) -> str
```

A trace record as one sentence: attack, goal, the steps it is nested
in, then what happened, joined by `·`.

#### public\_breadcrumb

```python
def public_breadcrumb(step: Mapping[str, Any]) -> str
```

A trace record as :func:`trace_breadcrumb` says it, without what a
model may have written: a decision says what was decided and its numbers
and flags, not why (a reason can quote a program a model wrote, or a
tool call it made); a failed call says it failed, not the error text. For
what leaves the machine; the log keeps the whole sentence.

## PlainFormatter Objects

```python
class PlainFormatter(logging.Formatter)
```

Format a record as :func:`plain_line`; a trace record&#x27;s message is its
:func:`trace_breadcrumb`. Never padded or wrapped.

#### about

```python
@contextmanager
def about(**subject: Any) -> Iterator[None]
```

Name what the code in this context works on, such as ``attack="tap",
goal=3, goals=20``; nested calls add to it. Every record logged inside
names it (:func:`subject_of`), so an interface can say which attack and
goal a line is about without the line carrying it.

#### subject\_of

```python
def subject_of(
        record: Optional[logging.LogRecord] = None) -> Mapping[str, Any]
```

What a record is about: as :func:`capture` stamped it, else what the
current context is about (a handler runs in the context that logged).

#### capture

```python
@contextmanager
def capture(
        handler: logging.Handler,
        level: int = logging.INFO,
        logger: str | Sequence[str] = PACKAGE_LOGGER
) -> Iterator[logging.Handler]
```

Hand `handler` the records of `logger` (and the loggers under it),
or of each of several loggers, logged at `level` or above inside this
block.

Tasks created and threads started with :func:`asyncio.to_thread` inside
the block belong to it, so two runs in one process each reach only their
own handlers.

`level` is the handler&#x27;s own; no other handler is touched. The logger&#x27;s
level is the floor for all of them, so whoever configures logging opens
it as far as its handlers need: the CLI opens the package logger fully
and gives each of its handlers a level.

## \_Opener Objects

```python
class _Opener()
```

Opens loggers while runs need them in a process whose logging nobody
configured, and closes them after the last run.

#### close

```python
def close() -> None
```

Release one opening; the last one closes every logger opened.

#### opened

```python
@contextmanager
def opened(levels: Mapping[str, int]) -> Iterator[bool]
```

Open each logger to its level for the block, if nobody configured
logging: no level on any of them, no handler on the root logger, on them
or on the loggers above them. Then no one else sees what they let
through. Otherwise whoever configured logging
decides, and nothing changes. Yields whether they were opened.

#### RUN\_LOG\_LEVEL

What a run&#x27;s log file holds: the campaign&#x27;s events and lines, and what
the attacks decide, without quoting prompts or replies (those are DEBUG).

#### run\_log

```python
@contextmanager
def run_log(path: str | Path, level: int = RUN_LOG_LEVEL) -> Iterator[Path]
```

Write the run inside the block to `path`, a :class:`PlainFormatter`
line per record at `level` and above, as the CLI writes its log to a
file. Only the block&#x27;s records, even with runs side by side.

