---
sidebar_label: attack
title: hackagent.attacks.techniques.baseline.attack
---

Baseline attack implementation.

Sends goals directly to the target model without any transformation,
serving as a control condition for measuring default refusal rates.

## BaselineAttack Objects

```python
class BaselineAttack(BaseAttack)
```

Baseline attack that sends goals directly to the target.

No prompt transformation is applied — goals are sent as-is.
This provides a control condition to compare against actual
attack techniques (PAIR, TAP, DrAttack, etc.).

Pipeline stages
---------------
1. **Generation** — sends each goal verbatim to the target model.
2. **Evaluation** — scores responses using the configured evaluator.

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

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: List[str]) -> Dict[str, Any]
```

Execute baseline attack (direct goal submission).

**Arguments**:

- `goals` - List of goal strings to send directly.
  

**Returns**:

  Dictionary with &#x27;evaluated&#x27; and &#x27;summary&#x27; DataFrames.

