---
sidebar_label: base
title: hackagent.server.storage.base
---

StorageBackend Protocol and record models.

LocalBackend (SQLite) implements
the StorageBackend protocol, providing identical interfaces so that all
callers — AgentRouter, Tracker, StepTracker, AttackOrchestrator, TUI — are
fully decoupled from where data is actually persisted.

Usage:
    from hackagent.server.storage.base import StorageBackend, AgentRecord, RunRecord

The selection of which backend to instantiate lives solely in agent.py.

## OrganizationContext Objects

```python
class OrganizationContext(BaseModel)
```

Organization and user context resolved by the storage backend.

#### user\_id

&quot;local&quot; for LocalBackend

## StorageBackend Objects

```python
class StorageBackend(Protocol)
```

Common interface for storage backends.

All methods are synchronous.  The protocol uses duck-typing so concrete
backends do not need to explicitly inherit from this class.

#### get\_context

```python
def get_context() -> OrganizationContext
```

Return the org / user context associated with this backend.

#### get\_api\_key

```python
def get_api_key() -> Optional[str]
```

Return the API key used by this backend, or None (local mode).

#### flush

```python
def flush() -> None
```

Block until all deferred writes are persisted (no-op if synchronous).

#### close

```python
def close() -> None
```

Release resources / stop background workers. Idempotent.

#### create\_or\_update\_agent

```python
def create_or_update_agent(name: str,
                           agent_type: str,
                           endpoint: str,
                           metadata: Dict[str, Any],
                           overwrite_metadata: bool = True) -> AgentRecord
```

Create a new agent or update an existing one with the same name.

#### count\_result\_buckets

```python
def count_result_buckets() -> Dict[str, int]
```

Return {total, jailbreaks, mitigated, failed, pending} across all results.

