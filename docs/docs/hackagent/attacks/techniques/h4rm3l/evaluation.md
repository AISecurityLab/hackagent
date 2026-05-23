---
sidebar_label: evaluation
title: hackagent.attacks.techniques.h4rm3l.evaluation
---

h4rm3l evaluation module.

Multi-judge evaluation via ``BaseEvaluationStep``.
Evaluates whether the target model&#x27;s response to a decorated prompt
constitutes a successful jailbreak.

## H4rm3lEvaluation Objects

```python
class H4rm3lEvaluation(BaseEvaluationStep)
```

Evaluation step for h4rm3l attack.

Transforms h4rm3l response data into the standard evaluation format
``(goal, prefix, completion)``, runs all configured judges, merges
results back, and syncs to the server.

#### execute

```python
def execute(input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]
```

Evaluate h4rm3l responses using the multi-judge pipeline.

**Arguments**:

- `input_data` - Dicts from generation step (with ``response``,
  ``goal``, ``full_prompt``, etc.).
  

**Returns**:

  Same list enriched with judge columns, ``best_score``, ``success``.

#### execute

```python
def execute(input_data: List[Dict[str, Any]], config: Dict[str, Any],
            client: AuthenticatedClient,
            logger: logging.Logger) -> List[Dict[str, Any]]
```

Module-level entry point for the pipeline.

