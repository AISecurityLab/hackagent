---
sidebar_label: local
title: hackagent.storage.local
---

LocalBackend: the :class:`~hackagent.storage.store.Store` backed by SQLite.

Used when the local backend is selected (the default; see
:attr:`hackagent.core.settings.Settings.mode`). All data is persisted in
`~/.local/share/hackagent/hackagent.db` unless another path is given, with
a stable schema that the TUI, the web dashboard and the SDK all read. Besides
the Store protocol it keeps per-goal tallies and a revision counter per
campaign run, updated in the transaction of every write, so the reporting
reads (`report_*`) never recount results. Human reviews of attempts are
kept in `attempt_reviews`, append-only, and count in the tallies.

Thread safety: a per-instance lock serialises access to the one connection,
so goal-batch workers may write concurrently.

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

#### get\_api\_key

```python
def get_api_key() -> Optional[str]
```

Return None: local storage has no API key.

#### get\_context

```python
def get_context() -> OrganizationContext
```

Return the local organization context, creating it on first use.

The organization id is generated once and kept in the database, so every
record written by this database shares it. `user_id` is `"local"`.

#### create\_or\_update\_agent

```python
def create_or_update_agent(name: str, config: Dict[str, Any]) -> AgentRecord
```

Insert the agent `name`, or replace the config of the existing one.

Agent names are unique in the local database. `agent_type` and
`endpoint` are taken from `config["connection"]`.

#### list\_agents

```python
def list_agents(page: int = 1,
                page_size: int = 100) -> PaginatedResult[AgentRecord]
```

Return one page of agents, newest first.

#### get\_agent

```python
def get_agent(agent_id: UUID) -> AgentRecord
```

Return the agent `agent_id`.

**Raises**:

- `RuntimeError` - When no such agent exists.

#### delete\_agent

```python
def delete_agent(agent_id: UUID) -> None
```

Delete the agent row; a missing agent is not an error.

#### create\_attack

```python
def create_attack(attack_type: str, agent_id: UUID, organization: UUID,
                  configuration: Dict[str, Any]) -> AttackRecord
```

Insert an attack row and return it.

#### list\_attacks

```python
def list_attacks(page: int = 1,
                 page_size: int = 100) -> PaginatedResult[AttackRecord]
```

Return one page of attacks, newest first.

#### start\_campaign

```python
def start_campaign(agent_id: UUID, spec: Dict[str, Any]) -> CampaignRunRecord
```

Insert a RUNNING campaign run for `spec`.

The run is named after `spec["campaign"]["name"]`, or `"Campaign"`.

#### update\_campaign\_run

```python
def update_campaign_run(campaign_run_id: UUID,
                        status: Optional[str] = None,
                        audit: Optional[Dict[str, Any]] = None,
                        run_notes: Optional[str] = None) -> CampaignRunRecord
```

Change the given fields of a campaign run and return it.

`None` leaves a field unchanged. Every update counts as a new report
revision of the campaign run.

**Raises**:

- `RuntimeError` - When no such campaign run exists.

#### list\_campaign\_runs

```python
def list_campaign_runs(
        page: int = 1,
        page_size: int = 100) -> PaginatedResult[CampaignRunRecord]
```

Return one page of campaign runs, newest first.

#### get\_campaign\_run

```python
def get_campaign_run(campaign_run_id: UUID) -> CampaignRunRecord
```

Return the campaign run `campaign_run_id`.

**Raises**:

- `RuntimeError` - When no such campaign run exists.

#### link\_campaign\_run

```python
def link_campaign_run(campaign_run_id: UUID, campaign_id: UUID) -> None
```

Record that the dashboard launched a campaign run, and from which
saved campaign. The launch stays recorded if the campaign is deleted.

#### create\_campaign

```python
def create_campaign(name: str, description: str, agent_id: UUID,
                    spec: Dict[str, Any]) -> CampaignRecord
```

Save a dashboard campaign and return it.

#### update\_campaign

```python
def update_campaign(campaign_id: UUID, name: str, description: str,
                    agent_id: UUID, spec: Dict[str, Any]) -> CampaignRecord
```

Replace a saved campaign&#x27;s name, description, agent and spec.

**Raises**:

- `RuntimeError` - When no such campaign exists.

#### get\_campaign

```python
def get_campaign(campaign_id: UUID) -> CampaignRecord
```

Return the saved campaign `campaign_id`.

**Raises**:

- `RuntimeError` - When no such campaign exists.

#### list\_campaigns

```python
def list_campaigns(page: int = 1,
                   page_size: int = 100) -> PaginatedResult[CampaignRecord]
```

Return one page of saved campaigns, most recently updated first.

#### delete\_campaign

```python
def delete_campaign(campaign_id: UUID) -> None
```

Delete a saved campaign; the runs launched from it are kept, and
their reports, which name the campaign, change.

#### create\_run

```python
def create_run(attack_id: UUID,
               agent_id: UUID,
               run_config: Dict[str, Any],
               campaign_run_id: Optional[UUID] = None) -> RunRecord
```

Insert a PENDING attack run, linked to `campaign_run_id` if given.

Unlike the remote backend, a run without a campaign run is allowed.

#### update\_run

```python
def update_run(run_id: UUID,
               status: Optional[str] = None,
               run_notes: Optional[str] = None,
               run_config: Optional[Dict[str, Any]] = None) -> RunRecord
```

Change the given fields of an attack run and return it.

`None` leaves a field unchanged. When the run does not exist, a
placeholder record carrying only the passed fields is returned.

#### list\_runs

```python
def list_runs(attack_id: Optional[UUID] = None,
              page: int = 1,
              page_size: int = 100) -> PaginatedResult[RunRecord]
```

Return one page of attack runs, newest first, optionally of one attack.

#### get\_run

```python
def get_run(run_id: UUID) -> RunRecord
```

Return the attack run `run_id`.

**Raises**:

- `RuntimeError` - When no such run exists.

#### delete\_campaign\_run

```python
def delete_campaign_run(campaign_run_id: UUID) -> None
```

Delete one campaign run; see :meth:`delete_campaign_runs`.

#### delete\_campaign\_runs

```python
def delete_campaign_runs(campaign_run_ids: List[UUID]) -> None
```

Delete campaign runs with their attack runs, results, traces and tallies.

All deletions happen in one transaction.

**Arguments**:

- `campaign_run_ids` - The campaign runs to delete; duplicates are ignored.
  

**Raises**:

- `ValueError` - When the list is empty, or a campaign run or one of its
  attack runs has not reached a final status.
- `RuntimeError` - When one of the campaign runs does not exist.

#### delete\_run

```python
def delete_run(run_id: UUID) -> None
```

Delete an attack run with its results, traces and per-goal tallies.

#### delete\_attack

```python
def delete_attack(attack_id: UUID) -> None
```

Delete an attack with its runs, results, traces and per-goal tallies.

#### count\_result\_buckets

```python
def count_result_buckets() -> dict
```

Count all results by reporting bucket, human reviews applied.

**Returns**:

  A dict with the keys `total`, `jailbreaks`, `mitigated`,
  `error` and `pending`.

#### create\_result

```python
def create_result(run_id: UUID, goal: str, goal_index: int,
                  request_payload: Dict[str, Any],
                  agent_specific_data: Dict[str, Any]) -> ResultRecord
```

Insert an unevaluated result and update its goal&#x27;s tally.

The returned record&#x27;s metadata merges `request_payload` and
`agent_specific_data` and keeps the payload under `request_payload`.

#### update\_result

```python
def update_result(result_id: UUID,
                  evaluation_status: Optional[str] = None,
                  evaluation_notes: Optional[str] = None,
                  evaluation_metrics: Optional[Dict[str, Any]] = None,
                  agent_specific_data: Optional[Dict[str, Any]] = None,
                  latency_ms: Optional[int] = None,
                  response_status_code: Optional[int] = None) -> ResultRecord
```

Change the given fields of a result and update its goal&#x27;s tally.

`latency_ms` and `response_status_code` have no columns locally and
are merged into the metadata. When the result does not exist, a
placeholder record carrying only the passed fields is returned.

#### list\_results

```python
def list_results(run_id: Optional[UUID] = None,
                 page: int = 1,
                 page_size: int = 100) -> PaginatedResult[ResultRecord]
```

Return one page of results, newest first, optionally of one run.

#### get\_result

```python
def get_result(result_id: UUID) -> ResultRecord
```

Return the result `result_id`.

**Raises**:

- `RuntimeError` - When no such result exists.

#### create\_trace

```python
def create_trace(result_id: UUID, sequence: int, step_type: str,
                 content: Dict[str, Any]) -> TraceRecord
```

Insert a trace step and add it to its goal&#x27;s usage tally.

#### list\_traces

```python
def list_traces(result_id: UUID) -> List[TraceRecord]
```

Return the trace steps of a result, ordered by `sequence`.

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

#### report\_campaign\_run

```python
def report_campaign_run(campaign_run_id: str) -> Optional[CampaignRun]
```

Return the campaign run `campaign_run_id` as a report row, or None.

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

#### report\_goal\_totals

```python
def report_goal_totals(campaign_run_ids: List[str]) -> List[GoalTotal]
```

Return each goal&#x27;s attempt and bucket totals per campaign run.

Summed over the campaign run&#x27;s attack runs, from the stored tallies.

#### report\_goal\_outcomes

```python
def report_goal_outcomes(campaign_run_id: str) -> List[GoalOutcome]
```

Return the per-goal outcome tallies of a campaign run&#x27;s attack runs.

#### report\_goal\_usage

```python
def report_goal_usage(campaign_run_id: str) -> List[GoalUsage]
```

Return the per-goal call and token tallies of a campaign run.

One row per attack run, goal and call label.

#### report\_judge\_votes

```python
def report_judge_votes(campaign_run_id: str) -> List[GoalJudgeVotes]
```

Return the per-goal judge vote patterns of a campaign run.

#### report\_latencies

```python
def report_latencies(run_ids: List[str]) -> List[Latency]
```

Return the distinct target latencies recorded per run.

Each row is one run and latency (milliseconds) with how many results
recorded it.

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

#### review\_attempt

```python
def review_attempt(result_id: str, request: ReviewRequest, *,
                   reviewer: str) -> Tuple[Review, Dict[str, Any]]
```

Record a human review of the result `result_id`.

The review must follow the latest one (`check_review`); it is
appended, the goal&#x27;s tallies are recomputed and its campaign run&#x27;s
revision is bumped, in one transaction. Returns the review and the
attempt&#x27;s `run_id`, `goal_index` and `automated_bucket`.

**Raises**:

- `NotFound` - no such result.
- `Conflict` - another review was recorded after the expected one.
- `BadRequest` - a withdrawal when no review is active.

#### list\_attempt\_reviews

```python
def list_attempt_reviews(result_id: str) -> List[Review]
```

Every review of the result `result_id`, newest first.

**Raises**:

- `NotFound` - no such result.

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

