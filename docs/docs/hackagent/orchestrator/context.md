---
sidebar_label: context
title: hackagent.orchestrator.context
---

Build the :class:`~hackagent.attacks.ports.RunContext` for one run.

## DirWorkspace Objects

```python
class DirWorkspace()
```

Run-scoped directory and in-memory caches.

#### build\_panel

```python
def build_panel(config: Dict[str, Any], models: LLMFactory) -> Optional[Panel]
```

Build a panel from the run&#x27;s judge specs, or ``None`` when unset.

#### build\_context

```python
def build_context(*,
                  run_id: str,
                  target: LLM,
                  models: LLMFactory,
                  config: Dict[str, Any],
                  sink: StoreSink,
                  attack_type: str,
                  output_dir: str,
                  goal_labels: Optional[Dict[int, Dict[str, str]]] = None,
                  event_bus: Any = None) -> RunContext
```

Assemble the dependency bag a technique receives.

