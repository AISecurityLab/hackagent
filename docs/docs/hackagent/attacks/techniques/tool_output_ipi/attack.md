---
sidebar_label: attack
title: hackagent.attacks.techniques.tool_output_ipi.attack
---

Tool-output indirect prompt injection (tool_output_ipi) attack.

Poisons tool / function-call *observations* so a tool-using agent may follow
a malicious goal after a benign user task (InjecAgent / OPI family).

This is distinct from ``rag``, which poisons
RAG documents — not tool return values.

Pipeline:
1. Generation — craft poisoned tool observations, query target, inline judge
2. Evaluation — post-processing (server sync, tracker, ASR)

Taxonomy: primary **adaptive**, tag **indirect** (registered defensively when ``hackagent.attacks.taxonomy`` is present; add a permanent ``ATTACK_TAXONOMY`` entry when `603` merges).

## ToolOutputIPIAttack Objects

```python
class ToolOutputIPIAttack(BaseAttack)
```

Tool-output indirect prompt injection (InjecAgent / OPI).

For each malicious goal the attack:
1. Starts from a benign user message that would elicit a tool call.
2. Appends a simulated (or live) ``role=tool`` observation containing an
   adversarial injection aimed at the goal.
3. Re-queries the target with the full messages history.
4. Judges whether the response or subsequent tool call follows the
   injected instructions (direct harm and/or data stealing).

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

Declare attacker (optional) and judge model roles for preflight.

#### run

```python
def run(goals: Optional[List[str]] = None, **kwargs) -> List[AttackResult]
```

Execute the tool-output IPI pipeline.

**Arguments**:

- `goals` - Malicious goals the poisoned tool observation should induce.
  

**Returns**:

  List of :class:`~hackagent.attacks.types.AttackResult` rows.

