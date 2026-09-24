---
sidebar_label: client
title: hackagent.client
---

Facade (depth 2).

`HackAgent` is constructed from :class:`~hackagent.core.settings.Settings`
and does not require a target. :meth:`HackAgent.target` binds an endpoint and
returns an object whose :meth:`~Target.hack` and :meth:`~Target.hack_chain`
both accept `on_event`. Interfaces talk only to this module and the public
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

Jailbreak campaign technique ids, in campaign order.

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

Command lists and TUI forms are generated from this. It includes every
registry id, including techniques that are absent from older hand-written
catalogs.

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

Build the `(&quot;web&quot;, operational_config)` pair for a live-browser chatbot.

#### result\_bucket

```python
def result_bucket(status: Optional[str], notes: Optional[str] = None) -> str
```

Classify a result the same way the store does.

Interfaces use this instead of importing storage bucket constants.

#### ensure\_graphviz

```python
def ensure_graphviz(*, allow_download: bool = False) -> Optional[str]
```

Locate or install the Graphviz `dot` binary used by FC-Attack.

## Target Objects

```python
class Target()
```

One victim bound to a :class:`HackAgent` session.

#### hack

```python
def hack(attack_config: Dict[str, Any],
         run_config_override: Optional[Dict[str, Any]] = None,
         fail_on_run_error: bool = True,
         on_event: Optional[Any] = None) -> Any
```

Run one attack. `on_event` receives `(event_type, **payload)`.

#### hack\_chain

```python
def hack_chain(attacks: Optional[list] = None,
               goals: Optional[list] = None,
               run_config_override: Optional[Dict[str, Any]] = None,
               fail_on_run_error: bool = True,
               escalate_only_mitigated: bool = True,
               on_event: Optional[Any] = None) -> list
```

Run a sequence of attacks. `on_event` is forwarded to each step.

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

#### target

```python
def target(endpoint: str,
           agent_type: Union[AgentType, str] = AgentType.UNKNOWN,
           *,
           name: Optional[str] = None,
           guardrails: Any = None,
           metadata: Optional[Dict[str, Any]] = None,
           target_config: Optional[Dict[str, Any]] = None,
           adapter_operational_config: Optional[Dict[str, Any]] = None,
           thinking: Optional[bool] = None) -> Target
```

Bind `endpoint` and return an object with `hack` and `hack_chain`.

#### delete\_run

```python
def delete_run(run_id: Any) -> None
```

Delete one run. This is a write; reads never call it.

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

