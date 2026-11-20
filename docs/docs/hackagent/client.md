---
sidebar_label: client
title: hackagent.client
---

Facade (depth 2).

`HackAgent` is constructed from :class:`~hackagent.core.settings.Settings`
and reads what past runs recorded: campaigns, runs, results, agents and the
catalogs. Running an attack is a campaign —
:func:`~hackagent.orchestrator.campaign.run_campaign` — and there is no
second way to do it. Interfaces talk only to this module and the public
types re-exported from :mod:`hackagent`.

#### primary\_dataset

```python
def primary_dataset() -> Optional[str]
```

Preset used by the default jailbreak campaign when none is chosen.

#### primary\_attacks

```python
def primary_attacks() -> List[str]
```

Return the jailbreak profile&#x27;s primary technique ids, in profile order.

Only techniques registered with the campaign runner are kept, so a chain
built from this never fails on its first step.

#### presets

```python
def presets() -> Dict[str, Dict[str, Any]]
```

Built-in dataset presets, keyed by name.

#### preset

```python
def preset(name: str) -> Dict[str, Any]
```

Return one preset configuration.

**Raises**:

- `ValueError` - The name is not a known preset.

#### load\_goals

```python
def load_goals(**kwargs: Any) -> List[Any]
```

Load goals through the datasets package.

#### form\_fields

```python
@lru_cache(maxsize=None)
def form_fields(attack_id: str) -> List[Dict[str, Any]]
```

Flatten a technique&#x27;s pydantic JSON schema into form fields.

#### catalog\_entries

```python
@lru_cache(maxsize=1)
def catalog_entries() -> List[Dict[str, Any]]
```

Return every registered technique, sorted by id, with its form fields.

Command lists and TUI forms are generated from this. Each entry carries
the technique&#x27;s label, description, taxonomy category and tags, its
position in the jailbreak profile (`primary_order`) and its
:func:`form_fields`. Cached: the same list is returned on every call.

#### technique\_catalog

```python
def technique_catalog() -> List[Dict[str, Any]]
```

Every technique with its parameter schema and auxiliary-model roles.

Consumers build attack forms from this instead of hardcoding them. The
result is a fresh copy, so callers may mutate it freely.

#### catalog\_by\_id

```python
def catalog_by_id() -> Dict[str, Dict[str, Any]]
```

Return :func:`catalog_entries` keyed by technique id.

#### grouped\_catalog

```python
def grouped_catalog() -> List[tuple[str, str, List[Dict[str, Any]]]]
```

`(category, category_label, entries)` in taxonomy order.

#### plan\_attack

```python
def plan_attack(target: Dict[str, Any], **kwargs: Any) -> Any
```

Choose a technique, goals and parameters for `target`.

#### web\_target

```python
def web_target(url: str, **kwargs: Any) -> tuple[str, Dict[str, Any]]
```

Build the `("web", operational_config)` pair for a live-browser chatbot.

#### ensure\_graphviz

```python
def ensure_graphviz(*, allow_download: bool = False) -> Optional[str]
```

Locate or install the Graphviz `dot` binary used by FC-Attack.

## DoctorReport Objects

```python
@dataclass(frozen=True)
class DoctorReport()
```

Structured diagnostics for `hackagent doctor`.

## HackAgent Objects

```python
class HackAgent()
```

Session over resolved settings and a store, for reading what runs recorded.

The store is opened from `settings`: SQLite in local mode, the platform
API in remote mode. Runs themselves are started with
:func:`~hackagent.orchestrator.campaign.run_campaign`. In local mode, pass
it this session&#x27;s `settings` and `backend` to record into the same
database. In remote mode, set the campaign&#x27;s `execution.storage.backend`
to `remote` and pass only `settings`: a `store` argument would skip
the remote run&#x27;s heartbeat and server-side cancellation. Call
:meth:`close` when done (a remote store flushes its queued writes then).

**Arguments**:

- `settings` - Resolved settings; :meth:`Settings.resolve` is called when
  omitted.
- `backend` - A store object to use instead of the one `settings` selects,
  e.g. a `LocalBackend` on a temporary database. It is not a
  backend name: choose `"local"`/`"remote"` through `settings`.
- `timeout` - HTTP timeout in seconds for the remote store.
- `raise_on_unexpected_status` - Make the remote store&#x27;s HTTP client raise
  `UnexpectedStatus` on undocumented response codes.
  

**Raises**:

- `CredentialError` - In remote mode without a platform API key.
  

**Example**:

  Run a campaign into a local database, then read back its results:
  
    ```python
    from hackagent import HackAgent, Settings
    from hackagent.orchestrator.campaign import run_campaign

    session = HackAgent(Settings.resolve(db_path="./runs.db"))
    try:
        result = run_campaign(
            "campaign.yaml", settings=session.settings, store=session.backend
        )
        for outcome in result.attacks:
            for record in session.results(run_id=outcome.run_id).items:
                print(record.goal, record.evaluation_status)
    finally:
        session.close()
    ```

#### close

```python
def close() -> None
```

Close the store, releasing its connection and flushing queued writes.

#### context

```python
def context() -> Any
```

Return the organization and user the store records under.

#### agents

```python
def agents(*, page: int = 1, page_size: int = 100) -> Any
```

Return one page of recorded target agents.

#### agent

```python
def agent(agent_id: Any) -> Any
```

Return one agent by id (a UUID or its string form).

**Raises**:

- `RuntimeError` - When no such agent exists.

#### attacks

```python
def attacks(*, page: int = 1, page_size: int = 100) -> Any
```

Return one page of recorded attack configurations.

#### runs

```python
def runs(*, attack_id: Any = None, page: int = 1, page_size: int = 100) -> Any
```

Return one page of attack runs, optionally only those of `attack_id`.

#### campaign\_runs

```python
def campaign_runs(*, page: int = 1, page_size: int = 100) -> Any
```

List campaign-level runs, including their audit reports.

#### campaign\_run

```python
def campaign_run(campaign_run_id: Any) -> Any
```

Retrieve one campaign run and its immutable specification/audit.

#### run

```python
def run(run_id: Any) -> Any
```

Return one attack run by id.

**Raises**:

- `RuntimeError` - When no such run exists.

#### results

```python
def results(*, run_id: Any = None, page: int = 1, page_size: int = 100) -> Any
```

Return one page of results, optionally only those of `run_id`.

#### result

```python
def result(result_id: Any) -> Any
```

Return one result by id.

**Raises**:

- `RuntimeError` - When no such result exists.

#### traces

```python
def traces(result_id: Any) -> List[Any]
```

Return a result&#x27;s trace steps, ordered by sequence.

#### delete\_run

```python
def delete_run(run_id: Any) -> None
```

Delete one run. This is a write; reads never call it.

#### delete\_campaign\_run

```python
def delete_campaign_run(campaign_run_id: Any) -> None
```

Delete a completed local campaign execution and its recorded child data.

#### delete\_campaign\_runs

```python
def delete_campaign_runs(campaign_run_ids: List[Any]) -> None
```

Atomically delete selected local executions and their recorded child data.

#### report\_campaign\_runs

```python
def report_campaign_runs(**filters: Any) -> Any
```

A page of campaign runs, newest first (`campaign`, `agent`,
`status`, `page`, `page_size`).

#### report\_campaign\_run

```python
def report_campaign_run(campaign_run_id: str) -> Any
```

One campaign run, or None.

#### report\_previous\_candidates

```python
def report_previous_candidates(current: Any) -> List[Any]
```

Return the earlier completed runs of `current`&#x27;s campaign, newest first.

**Raises**:

- `NotImplementedError` - When the session does not use local storage.

#### report\_revisions

```python
def report_revisions(campaign_run_ids: List[str]) -> Dict[str, int]
```

Return the current report revision of each existing campaign run.

**Raises**:

- `NotImplementedError` - When the session does not use local storage.

#### report\_attack\_runs

```python
def report_attack_runs(campaign_run_ids: List[str],
                       *,
                       full: bool = False) -> List[Any]
```

Return the attack runs of campaign runs; `full` adds configurations.

**Raises**:

- `NotImplementedError` - When the session does not use local storage.

#### report\_goal\_totals

```python
def report_goal_totals(campaign_run_ids: List[str]) -> List[Any]
```

Return each goal&#x27;s attempt and bucket totals per campaign run.

**Raises**:

- `NotImplementedError` - When the session does not use local storage.

#### report\_goal\_outcomes

```python
def report_goal_outcomes(campaign_run_id: str) -> List[Any]
```

Return the per-goal outcome tallies of a campaign run&#x27;s attack runs.

**Raises**:

- `NotImplementedError` - When the session does not use local storage.

#### report\_goal\_usage

```python
def report_goal_usage(campaign_run_id: str) -> List[Any]
```

Return the per-goal call and token tallies of a campaign run.

**Raises**:

- `NotImplementedError` - When the session does not use local storage.

#### report\_judge\_votes

```python
def report_judge_votes(campaign_run_id: str) -> List[Any]
```

Return the per-goal judge vote patterns of a campaign run.

**Raises**:

- `NotImplementedError` - When the session does not use local storage.

#### review\_attempt

```python
def review_attempt(result_id: str, request: Any, *, reviewer: str) -> Any
```

Record a human review of one attempt (a parsed
:class:`hackagent.reporting.ReviewRequest`).

Returns the review and the attempt&#x27;s `run_id`, `goal_index` and
`automated_bucket`.

**Raises**:

- `NotImplementedError` - When the session does not use local storage.
- `hackagent.reporting.http.ReportError` - An unknown result, or a
  review that does not follow the attempt&#x27;s latest one.

#### attempt\_reviews

```python
def attempt_reviews(result_id: str) -> List[Any]
```

Return every review of one attempt, newest first.

**Raises**:

- `NotImplementedError` - When the session does not use local storage.
- `hackagent.reporting.http.NotFound` - An unknown result.

#### report\_latencies

```python
def report_latencies(run_ids: List[str]) -> List[Any]
```

Return the distinct target latencies (ms) recorded per run, with counts.

**Raises**:

- `NotImplementedError` - When the session does not use local storage.

#### report\_attempts

```python
def report_attempts(run_ids: List[str], goal_index: int, *, page: int,
                    page_size: int) -> Any
```

Return one page of a goal&#x27;s attempts, their count and the first jailbreak.

**Raises**:

- `NotImplementedError` - When the session does not use local storage.

#### report\_structure

```python
def report_structure(run_id: str, goal_index: int) -> Any
```

Return every attempt of a goal in one attack run with its traces.

**Raises**:

- `NotImplementedError` - When the session does not use local storage.

#### campaigns

```python
def campaigns(*, page: int = 1, page_size: int = 100) -> Any
```

Return one page of campaigns saved from the dashboard (local storage).

#### campaign

```python
def campaign(campaign_id: Any) -> Any
```

Return one saved campaign by id (local storage).

**Raises**:

- `RuntimeError` - When no such campaign exists.

#### save\_campaign

```python
def save_campaign(*,
                  name: str,
                  description: str,
                  agent_id: Any,
                  spec: Dict[str, Any],
                  campaign_id: Any = None) -> Any
```

Create a saved campaign, or replace the one `campaign_id` names.

#### delete\_campaign

```python
def delete_campaign(campaign_id: Any) -> None
```

Delete a saved campaign; the runs launched from it are kept (local storage).

**Raises**:

- `RuntimeError` - When no such campaign exists.

#### catalog

```python
def catalog() -> List[Dict[str, Any]]
```

Return every registered attack technique; see :func:`catalog_entries`.

#### presets

```python
def presets() -> Dict[str, Dict[str, Any]]
```

Return the built-in dataset presets, keyed by name.

#### load\_goals

```python
def load_goals(**kwargs: Any) -> List[Any]
```

Load goals with :func:`hackagent.datasets.load_goals`&#x27;s arguments.

#### plan\_attack

```python
def plan_attack(target: Dict[str, Any], **kwargs: Any) -> Any
```

Let the LLM planner choose a technique, goals and parameters.

#### check\_connection

```python
def check_connection() -> int
```

Probe the remote API. Local sessions return `0`.

#### ensure\_graphviz

```python
def ensure_graphviz(*, allow_download: bool = False) -> Optional[str]
```

Locate (or download) the Graphviz `dot` binary FC-Attack needs.

#### doctor

```python
def doctor() -> DoctorReport
```

Collect configuration diagnostics, including Graphviz.

