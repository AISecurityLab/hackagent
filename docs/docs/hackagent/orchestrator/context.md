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

#### DEFAULT\_JUDGE\_AGGREGATION

Panel aggregation when the run config sets no `judge_aggregation`.

#### build\_panel

```python
def build_panel(config: Dict[str, Any], models: LLMFactory) -> Optional[Panel]
```

Build a panel from the run&#x27;s judge specs, or `None` when unset.

`judge_aggregation` picks the :class:`Panel` mode (default
`majority`) and `jailbreak_threshold` its 0..10 threshold. A judge
that cannot be connected fails the run instead of shrinking the panel.

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

