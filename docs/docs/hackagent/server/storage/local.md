---
sidebar_label: local
title: hackagent.server.storage.local
---

LocalBackend — StorageBackend implementation backed by SQLite.

Selected automatically by HackAgent when no API key is available.  All data
is persisted in ~/.local/share/hackagent/hackagent.db with a stable schema
for TUI/SDK access.

Thread safety: a per-instance lock ensures safe concurrent writes from the
goal-batch parallel execution workers.

## LocalBackend Objects

```python
class LocalBackend()
```

SQLite-backed StorageBackend.

All tracking data (agents, attacks, runs, results, traces) is stored in a
single SQLite database so TUI views and the SDK can access the same data.

#### close

```python
def close() -> None
```

Close the underlying SQLite connection.

Call this when the backend is no longer needed to release the file lock.
Particularly important on Windows where open file handles prevent
temporary directory cleanup.

#### flush

```python
def flush() -> None
```

No-op: local writes are synchronous (mirrors RemoteBackend.flush).

#### count\_result\_buckets

```python
def count_result_buckets() -> dict
```

Return {total, jailbreaks, mitigated, error, pending} via SQL.

