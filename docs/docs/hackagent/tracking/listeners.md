---
sidebar_label: listeners
title: hackagent.tracking.listeners
---

Fan tracker events out to interfaces.

Interfaces subscribe with a listener. Tracking does not import them.

## EventListener Objects

```python
@runtime_checkable
class EventListener(Protocol)
```

One subscriber. ``kind`` is the event name; ``payload`` is its data.

## BusListener Objects

```python
class BusListener()
```

Adapt an object with ``emit(kind, **payload)`` (the TUI bus).

## Fanout Objects

```python
class Fanout()
```

Deliver each event to every listener. One failure does not stop the rest.

