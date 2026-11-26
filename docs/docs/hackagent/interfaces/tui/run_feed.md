---
sidebar_label: run_feed
title: hackagent.interfaces.tui.run_feed
---

A run&#x27;s log in the TUI, from the run&#x27;s thread to the run view.

Whatever runs a campaign in the app (the builder, or a run queued from the
dashboard) runs it on a thread of its own, its log captured by a
:class:`RunLog` handler. The handler only queues each line; the app drains
the queue on its own thread (:meth:`RunFeed.drain`), so logging never waits
for a repaint. The feed keeps the latest lines, so the run view
(:class:`~hackagent.interfaces.tui.views.campaign.screens.RunScreen`) can be
left and reopened without losing any.

#### RUN\_LINES

How many of a run&#x27;s lines the run view keeps and shows: the latest.

## RunLog Objects

```python
class RunLog(logging.Handler)
```

The run view&#x27;s handler of the run&#x27;s log: each line, written as the CLI
writes it to a file and coloured as a log viewer colours it.

It only queues them for the view, which draws them on its own thread:
the run never waits for the screen.

## RunFeed Objects

```python
class RunFeed()
```

One run&#x27;s lines: queued by its thread, kept, and shown on its run
view when that view is on top.

#### handler

```python
def handler() -> RunLog
```

A handler for the run&#x27;s log, feeding this.

#### showing

```python
def showing(app: Any) -> Any
```

This feed&#x27;s run view, when it is the screen on top.

#### log

```python
def log(app: Any, markup: str) -> None
```

Keep a line, and show it if its run view is on top.

#### note

```python
def note(app: Any, level: int, message: str) -> None
```

A line of the app&#x27;s own, written as a line of the run&#x27;s log.

#### drain

```python
def drain(app: Any, limit: Optional[int] = DRAIN_BATCH) -> None
```

Show what the run&#x27;s log handed over since the last look, at most
`limit` lines (all of them with `None`).

#### watch

```python
def watch(app: Any,
          title: str,
          stop: Callable[[], None],
          context: Optional[str] = None,
          on_close: Optional[Callable[[Any], None]] = None) -> None
```

Open the run view on what the run has produced so far.

