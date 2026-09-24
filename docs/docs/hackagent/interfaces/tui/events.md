---
sidebar_label: events
title: hackagent.interfaces.tui.events
---

Structured event bus for the TUI.

Replaces ad-hoc log-string parsing. Attack techniques, trackers, and
adapters emit typed events; TUI widgets subscribe and render them directly.

Events are delivered synchronously on the emitting thread. Subscribers that
need to update Textual widgets should wrap their callback in
`app.call_from_thread` themselves; the bus does not assume a Textual app.

## TUIEvent Objects

```python
@dataclass(frozen=True)
class TUIEvent()
```

A single bus event.

`event_type` is one of the `EVENT_*` constants. `payload` is the
structured data — its shape depends on the event type. `timestamp` is
wall-clock seconds since the epoch, set automatically.

## TUIEventBus Objects

```python
class TUIEventBus()
```

Thread-safe pub/sub event bus.

Subscribers register per event type (or for all events). Emitters call
:meth:`emit` from any thread; subscriber callbacks run synchronously on
the emitting thread. Exceptions raised by subscribers are logged and
swallowed so a misbehaving subscriber cannot break the attack.

#### subscribe

```python
def subscribe(callback: Subscriber, event_type: Optional[str] = None) -> None
```

Register a subscriber.

**Arguments**:

- `callback` - Function called with each matching :class:`TUIEvent`.
- `event_type` - Specific event type to subscribe to. If `None`,
  the subscriber receives every event.

#### unsubscribe

```python
def unsubscribe(callback: Subscriber,
                event_type: Optional[str] = None) -> None
```

Remove a previously registered subscriber. No-op if not found.

#### emit

```python
def emit(event_type: str, **payload: Any) -> None
```

Emit an event to all matching subscribers.

**Arguments**:

- `event_type` - One of the `EVENT_*` constants. Custom types are
  allowed but will only be seen by `subscribe(..., None)`
  catch-all subscribers and by subscribers using the exact
  same string.
- `**payload` - Structured event data; merged into `TUIEvent.payload`.

#### clear

```python
def clear() -> None
```

Remove every subscriber. Useful between attack runs.

