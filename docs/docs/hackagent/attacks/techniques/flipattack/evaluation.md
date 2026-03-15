---
sidebar_label: evaluation
title: hackagent.attacks.techniques.flipattack.evaluation
---

FlipAttack evaluation module.

Evaluates attack success using multi-judge LLM evaluation via
`BaseEvaluationStep`, following the same paradigm as AdvPrefix.

Supports multiple judges (HarmBench, JailbreakBench, Nuanced), merges
their scores, computes `best_score` / `success`, syncs to server,
and logs per-judge ASR.

Result Tracking:
    Uses Tracker (passed via config[&quot;_tracker&quot;]) to add evaluation traces
    per goal and sync evaluation status to server.

## FlipAttackEvaluation Objects

```python
class FlipAttackEvaluation(BaseEvaluationStep)
```

FlipAttack evaluation step using the shared multi-judge pipeline.

Transforms FlipAttack response data into the standard evaluation
format `(goal, prefix, completion)`, runs all configured judges,
merges results back, and syncs to the server.

#### execute

```python
def execute(input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]
```

Evaluate FlipAttack responses using the multi-judge pipeline.

**Arguments**:

- `input_data` - Dicts from generation step (with `response`,
  `goal`, `full_prompt`, etc.).
  

**Returns**:

  Same list enriched with judge columns, `best_score`, `success`.

#### execute

```python
def execute(input_data: List[Dict], config: Dict[str, Any],
            client: AuthenticatedClient, logger: logging.Logger) -> List[Dict]
```

Pipeline-compatible function entry point.

Wraps `FlipAttackEvaluation` so that `attack.py` can reference
`evaluation.execute` directly in the pipeline step definition.

