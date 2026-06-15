---
sidebar_label: tracking_logger
title: hackagent.router.tracking_logger
---

LiteLLM callback that captures every ``litellm.completion`` call.

LiteLLM exposes a ``CustomLogger`` base class with hook methods that
fire pre-call, on success, and on failure. We register a single
:class:`HackAgentTrackingLogger` instance on ``litellm.callbacks`` and
attach ``metadata`` to every call so the logger can correlate the I/O
back to the originating HackAgent registration.

The logger only emits structured records to ``hackagent.logger``; it
does not write to the backend storage directly. Downstream sinks (TUI
event bus, dashboard, file logs) can pick the records up from there.

#### ensure\_registered

```python
def ensure_registered() -> bool
```

Register the tracking logger on ``litellm.callbacks`` exactly once.

Idempotent — safe to call from every ``AgentRouter.__init__``.
Returns ``True`` when registration is in effect (either because we
just registered or because we already had).

#### get\_instance

```python
def get_instance() -> Optional[Any]
```

Return the singleton logger instance (mainly for tests).

