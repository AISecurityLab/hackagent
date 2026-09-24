---
sidebar_label: local
title: hackagent.storage.local
---

LocalBackend — Store implementation backed by SQLite.

Selected automatically by HackAgent when no API key is available.  All data
is persisted in ~/.local/share/hackagent/hackagent.db with a stable schema
for TUI/SDK access.

Thread safety: a per-instance lock ensures safe concurrent writes from the
goal-batch parallel execution workers.

## LocalBackend Objects

```python
class LocalBackend()
```

SQLite-backed Store.

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

Return \{total, jailbreaks, mitigated, error, pending\} via SQL.

#### save\_builder\_draft

```python
def save_builder_draft(name: str,
                       canvas: Dict[str, Any],
                       draft_id: Optional[str] = None) -> Dict[str, Any]
```

Insert or update a dashboard attack-builder draft canvas.

**Arguments**:

- `name` - User-facing draft name.
- `canvas` - Canvas dict (node layout plus the underlying config).
- `draft_id` - Existing draft id to overwrite; a new one is created
  when omitted or unknown.
  

**Returns**:

  The stored draft as `{id, name, canvas, created_at, updated_at}`.

#### list\_builder\_drafts

```python
def list_builder_drafts() -> List[Dict[str, Any]]
```

Return all saved builder drafts, most recently updated first.

#### get\_builder\_draft

```python
def get_builder_draft(draft_id: str) -> Optional[Dict[str, Any]]
```

Return one draft by id, or None if it does not exist.

#### delete\_builder\_draft

```python
def delete_builder_draft(draft_id: str) -> None
```

Delete a draft by id. No-op if it does not exist.

