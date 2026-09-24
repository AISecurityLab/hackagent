---
sidebar_label: preflight
title: hackagent.orchestrator.setup.preflight
---

Reachability checks before a run creates records.

Targets come from `config.roles()` (via the technique&#x27;s
`get_effective_model_roles`), the victim model, and the category
classifier when goals are not already labelled.

#### validate\_default\_classifier

```python
def validate_default_classifier(config: Dict[str, Any]) -> None
```

Abort when the implicit local classifier&#x27;s Ollama model is missing.

#### collect\_targets

```python
def collect_targets(config: Dict[str, Any],
                    roles: Optional[List[Dict[str, Any]]],
                    *,
                    target: Optional[Dict[str, Any]] = None,
                    include_classifier: bool = True) -> List[Dict[str, Any]]
```

Deduped model endpoints that preflight will probe.

#### check\_models

```python
def check_models(config: Dict[str, Any],
                 roles: Optional[List[Dict[str, Any]]],
                 *,
                 target: Optional[Dict[str, Any]] = None,
                 include_classifier: bool = True) -> Optional[str]
```

Return an error string when a required model is unreachable.

#### probe\_embedding\_target

```python
def probe_embedding_target(target: Dict[str, Any]) -> Optional[str]
```

Verify an embedding endpoint. `None` means reachable.

#### probe\_model\_target

```python
def probe_model_target(target: Dict[str, Any]) -> Optional[str]
```

Probe one target. `None` means reachable.

#### probe\_router

```python
def probe_router(router: Any, registration_key: str) -> Optional[str]
```

Tiny completion, or `probe_ready` when the adapter has one.

#### target\_from\_agent

```python
def target_from_agent(agent: Any) -> Optional[Dict[str, Any]]
```

Describe the victim already connected on *agent*, when there is one.

