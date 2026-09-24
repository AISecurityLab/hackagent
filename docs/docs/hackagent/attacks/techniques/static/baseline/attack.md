---
sidebar_label: attack
title: hackagent.attacks.techniques.static.baseline.attack
---

Baseline attack implementation.

Sends goals directly to the target model without any transformation,
serving as a control condition for measuring default refusal rates.

## BaselineAttack Objects

```python
class BaselineAttack(BaseAttack)
```

Baseline attack that sends goals directly to the target.

Construct with `(config, ctx)`. `config` is an
:class:`~hackagent.attacks.config.AttackConfig` or a dict merged into
:data:`~hackagent.attacks.techniques.static.baseline.config.DEFAULT_BASELINE_CONFIG`.
`ctx` is a :class:`~hackagent.attacks.ports.RunContext`, passed
positionally or as `ctx=`. Tests build it with `make_ctx()`
(`tests.fakes.context`).

The pipeline is generation-only. `run()` returns rows without a
verdict; `HackAgent.hack` scores them in the shared evaluator.

The legacy constructor `(config_dict, client, agent_router)` is
obsolete for new code. `hackagent.orchestrator.execution.runner` constructs
`(config, ctx)`.

#### get\_effective\_model\_roles

```python
@classmethod
def get_effective_model_roles(
    cls,
    attack_config: Dict[str, Any],
    *,
    goal_labels_by_index: Optional[Dict[int, Dict[str, str]]] = None
) -> List[Dict[str, Any]]
```

Baseline always needs judge models for LLM-judge evaluation.

