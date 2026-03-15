---
sidebar_label: local
title: hackagent.server.storage.local
---

LocalBackend — StorageBackend implementation backed by SQLite.

Selected automatically by HackAgent when no API key is available.  All data
is persisted in ~/.local/share/hackagent/hackagent.db with the same schema
as the remote Django models, enabling identical TUI/SDK behaviour offline.

Thread safety: a per-instance lock ensures safe concurrent writes from the
goal-batch parallel execution workers.

## LocalBackend Objects

```python
class LocalBackend()
```

SQLite-backed StorageBackend.

All tracking data (agents, attacks, runs, results, traces) is stored in a
single SQLite database.  The schema mirrors the remote Django models so that
TUI views and the SDK work identically in both online and offline modes.

