---
sidebar_label: remote
title: hackagent.server.storage.remote
---

RemoteBackend — StorageBackend implementation backed by api.hackagent.dev.

This backend centralises all HTTP calls that were previously scattered across
AgentRouter, AttackOrchestrator, Tracker, and StepTracker.  It is instantiated
when an API key is available and selected automatically by HackAgent.__init__.

## RemoteBackend Objects

```python
class RemoteBackend()
```

StorageBackend implementation that talks to api.hackagent.dev.

Wraps all HTTP calls behind the StorageBackend interface so that the rest
of the SDK is entirely decoupled from HTTP concerns.

#### get\_context

```python
def get_context() -> OrganizationContext
```

Fetch org_id and user_id from the first agent (cached after first call).

