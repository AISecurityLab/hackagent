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

Jailbreak campaign technique ids `hack` can execute, in order.

Both halves count: a migrated technique runs on the campaign runner and
the rest on the legacy pipeline. A technique neither can run is dropped,
so a chain built from this never fails on its first step.

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

Registered techniques, in registry order, with form fields.

Command lists and TUI forms are generated from this. It covers both
halves of the migration — what the legacy pipeline still runs and what
the campaign runner has taken over — because `hack` runs either.

#### technique\_catalog

```python
def technique_catalog() -> List[Dict[str, Any]]
```

Every technique with its parameter schema and auxiliary-model roles.

Consumers build attack forms from this instead of hardcoding them. The
result is a fresh copy, so callers may mutate it freely.

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

Session over settings and a store. Bind a victim with :meth:`target`.

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

#### check\_connection

```python
def check_connection() -> int
```

Probe the remote API. Local sessions return `0`.

#### doctor

```python
def doctor() -> DoctorReport
```

Collect configuration diagnostics, including Graphviz.

