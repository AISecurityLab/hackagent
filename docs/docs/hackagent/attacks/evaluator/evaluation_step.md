---
sidebar_label: evaluation_step
title: hackagent.attacks.evaluator.evaluation_step
---

Base evaluation step for attack pipeline stages.

This module provides ``BaseEvaluationStep``, the shared foundation for all
evaluation pipeline stages across attack techniques (AdvPrefix, FlipAttack, etc.).

It centralises the common logic that was previously duplicated:
- Multi-judge evaluation orchestration
- Judge type inference from model identifiers
- Agent type resolution (string / enum → ``AgentTypeEnum``)
- ``EvaluatorConfig`` construction from raw judge config dicts
- Single evaluator instantiation and execution
- Result merging via lookup keys ``(goal, prefix, completion)``
- Server sync via ``sync_evaluation_to_server``
- Best-score computation across judge columns
- ASR logging

Subclasses only need to implement ``execute()`` and, optionally, override
configuration or data-transformation hooks.

Usage:
    from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep

    class MyEvaluation(BaseEvaluationStep):
        def execute(self, input_data):
            ...

## BaseEvaluationStep Objects

```python
class BaseEvaluationStep()
```

Shared foundation for evaluation pipeline stages.

Provides multi-judge evaluation, result merging, server sync,
best-score computation, and ASR logging.  Subclasses implement
``execute()`` with technique-specific data transformation.

#### \_\_init\_\_

```python
def __init__(config: Dict[str, Any], logger: logging.Logger,
             client: AuthenticatedClient)
```

Extract common tracking context and dependencies.

**Arguments**:

- `config` - Step configuration dictionary (may contain ``_run_id``,
  ``_client``, ``_tracker`` internal keys).
- `logger` - Logger instance.
- `client` - ``AuthenticatedClient`` for backend API calls.

#### infer\_judge\_type

```python
@staticmethod
def infer_judge_type(identifier: Optional[str],
                     default: Optional[str] = None) -> Optional[str]
```

Infer judge evaluator type from a model identifier string.

Checks for known substrings (``harmbench``, ``nuanced``,
``jailbreak``) and returns the matching type key, or *default*.

#### resolve\_agent\_type

```python
def resolve_agent_type(agent_type_value: Any) -> AgentTypeEnum
```

Convert a string, enum, or ``None`` into an ``AgentTypeEnum``.

#### compute\_best\_score

```python
def compute_best_score(item: Dict[str, Any]) -> float
```

Return the best (max) binary score across all judge columns.

#### get\_statistics

```python
def get_statistics() -> Dict[str, Any]
```

Return a copy of execution statistics.

