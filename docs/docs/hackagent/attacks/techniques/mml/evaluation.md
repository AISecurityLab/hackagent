---
sidebar_label: evaluation
title: hackagent.attacks.techniques.mml.evaluation
---

MML attack evaluation module.

Evaluates attack success using multi-judge LLM evaluation via
``BaseEvaluationStep``, following the same paradigm as FlipAttack/AdvPrefix.

Supports multiple judges (HarmBench, JailbreakBench, Nuanced), merges
their scores, computes ``best_score`` / ``success``, syncs to server,
and logs per-judge ASR.

Result Tracking:
    Uses Tracker (passed via config[&quot;_tracker&quot;]) to add evaluation traces
    per goal and sync evaluation status to server.

## MMLEvaluation Objects

```python
class MMLEvaluation(BaseEvaluationStep)
```

MML evaluation step using the shared multi-judge pipeline.

Transforms MML response data into the standard evaluation
format ``(goal, prefix, completion)``, runs all configured judges,
merges results back, and syncs to the server.

#### execute

```python
def execute(input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]
```

Evaluate MML responses using the multi-judge pipeline.

**Arguments**:

- `input_data` - Dicts from generation step (with ``response``,
  ``goal``, ``text_prompt``, etc.).
  

**Returns**:

  Same list enriched with judge columns, ``best_score``, ``success``.

#### execute

```python
def execute(input_data: List[Dict], config: Dict[str, Any],
            client: AuthenticatedClient, logger: logging.Logger) -> List[Dict]
```

Pipeline-compatible function entry point.

Wraps ``MMLEvaluation`` so that ``attack.py`` can reference
``evaluation.execute`` directly in the pipeline step definition.

