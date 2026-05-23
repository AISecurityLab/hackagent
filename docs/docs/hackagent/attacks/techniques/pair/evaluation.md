---
sidebar_label: evaluation
title: hackagent.attacks.techniques.pair.evaluation
---

Evaluation module for the PAIR attack.

Wraps PAIR&#x27;s scorer-based evaluation into the shared
``BaseEvaluationStep`` framework for consistency with other attacks.

PAIR scoring is performed inline during the iterative refinement loop
(see ``PAIRAttack._score_response``). This module provides a class-based
entry point so that external callers (e.g. reporting, dashboard) can
instantiate ``PAIREvaluation`` the same way they instantiate evaluators
for other techniques.

## PAIREvaluation Objects

```python
class PAIREvaluation(BaseEvaluationStep)
```

Evaluation step for the PAIR attack.

Extends ``BaseEvaluationStep`` to expose PAIR&#x27;s inline scorer results
through the shared evaluation framework.

Because PAIR scoring happens inside the iterative refinement loop,
``execute()`` enriches pre-scored results with ``best_score`` and
``success`` fields to match the standard evaluation output contract.

#### execute

```python
def execute(input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]
```

Enrich PAIR results with standard evaluation fields.

PAIR results already contain ``best_score`` and ``is_success``
from inline scoring. This method normalises the fields so that
downstream consumers (reporting, dashboard) find the same keys
as for other attacks.

**Arguments**:

- `input_data` - List of per-goal result dicts from the PAIR loop.
  

**Returns**:

  Same list with ``success`` and ``evaluation_notes`` added.

