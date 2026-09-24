---
sidebar_label: runner
title: hackagent.orchestrator.runner
---

One attack run.

validate → defaults → preflight → goals → register the target and create
records → build context → schedule → judge unjudged results once → finalise
and flush.

A verdict an attack already produced is final. Re-judging every result is
opt-in via :attr:`hackagent.orchestrator.run_spec.RunSpec.rejudge`.

#### run

```python
def run(agent: Any,
        attack_config: Dict[str, Any],
        run_config_override: Optional[Dict[str, Any]] = None,
        fail_on_run_error: bool = True,
        _tui_event_bus: Optional[Any] = None) -> List[Dict[str, Any]]
```

Execute one attack against ``agent`` and return result rows.

#### judge\_unjudged

```python
def judge_unjudged(results: List[AttackResult],
                   judge: Any,
                   *,
                   rejudge: bool = False) -> List[AttackResult]
```

Score results that have no verdict.

An attack-produced verdict is kept. ``rejudge=True`` scores every result
that has a response, including ones that already carry a verdict.

