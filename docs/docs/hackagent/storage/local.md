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

#### link\_campaign\_run

```python
def link_campaign_run(campaign_run_id: UUID, campaign_id: UUID) -> None
```

Record that the dashboard launched a campaign run, and from which
saved campaign. The launch stays recorded if the campaign is deleted.

#### delete\_campaign

```python
def delete_campaign(campaign_id: UUID) -> None
```

Delete a saved campaign; the runs launched from it are kept, and
their reports, which name the campaign, change.

#### count\_result\_buckets

```python
def count_result_buckets() -> dict
```

Return \{total, jailbreaks, mitigated, error, pending\} via SQL.

#### report\_campaign\_runs

```python
def report_campaign_runs(*,
                         campaign: Optional[str] = None,
                         agent: Optional[str] = None,
                         status: Optional[str] = None,
                         page: int = 1,
                         page_size: int = 100) -> PaginatedResult[CampaignRun]
```

Campaign runs, newest first (`created_at` desc, then `id`).

#### report\_previous\_candidates

```python
def report_previous_candidates(current: CampaignRun) -> List[CampaignRun]
```

The completed runs of `current`&#x27;s campaign created up to it, newest
first: a superset of its `previous` that the reporting rule narrows.

#### report\_revisions

```python
def report_revisions(campaign_run_ids: List[str]) -> Dict[str, int]
```

The current revision of each campaign run that exists.

#### report\_attack\_runs

```python
def report_attack_runs(campaign_run_ids: List[str],
                       *,
                       full: bool = False) -> List[AttackRun]
```

The attack runs of campaign runs. Without `full` only id, parent,
status and creation are read. With it, `attack_configuration` is the
attack&#x27;s stored configuration, unredacted, and `family` is unset:
the caller completes both.

#### report\_attempts

```python
def report_attempts(
        run_ids: List[str], goal_index: int, *, page: int,
        page_size: int) -> Tuple[List[Attempt], int, Optional[FirstSuccess]]
```

One page of a goal&#x27;s attempts in `created_at`, `id` order, their
count, and the first jailbreak with its position.

#### report\_structure

```python
def report_structure(
        run_id: str,
        goal_index: int) -> Tuple[List[StructureResult], List[StructureTrace]]
```

Every attempt of a goal in one attack run, in full, and their traces.

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

