---
sidebar_label: chain
title: hackagent.orchestrator.chain
---

Sequential attack chains.

``hack_chain`` runs each step through :meth:`HackAgent.hack`. By default a
goal that already succeeded is not retried. The CLI quick scan uses this
instead of reimplementing the jailbreak campaign.

#### hack\_chain

```python
def hack_chain(agent: Any,
               attacks: Optional[list] = None,
               goals: Optional[list] = None,
               run_config_override: Optional[Dict[str, Any]] = None,
               fail_on_run_error: bool = True,
               escalate_only_mitigated: bool = True,
               _tui_event_bus: Optional[Any] = None) -> list
```

Run ``attacks`` in order against a shared pool of goals.

``attacks`` defaults to the jailbreak profile&#x27;s primary techniques.
Each step is executed with ``agent.hack``. See ``HackAgent.hack_chain``.

#### is\_successful\_result

```python
def is_successful_result(row: Dict[str, Any]) -> bool
```

Whether a result row counts as a successful attack for chain escalation.

