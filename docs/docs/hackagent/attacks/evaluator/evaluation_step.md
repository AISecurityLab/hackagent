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

#### get\_judge\_range

```python
@staticmethod
def get_judge_range(judge_config: Dict[str, Any]) -> str
```

Return &#x27;binary&#x27; or &#x27;decimal&#x27; for the given judge config dict.

Resolution order:
1. Explicit ``range`` field in the judge config.
2. Type-based default from ``JUDGE_DEFAULT_RANGE``.
3. &#x27;binary&#x27; as a safe fallback.

#### score\_range\_maximum

```python
@classmethod
def score_range_maximum(cls, judge_range: str) -> float
```

Return the largest native score for a supported judge range.

#### normalize\_judge\_score

```python
@classmethod
def normalize_judge_score(cls, score: Any, judge_range: str) -> float
```

Map a native judge score onto the shared 0--10 scale.

#### normalized\_jailbreak\_threshold

```python
@classmethod
def normalized_jailbreak_threshold(cls, config: Dict[str, Any]) -> float
```

Return the canonical 0--10 jailbreak threshold.

``jailbreak_threshold`` is intentionally interpreted on the shared
0--10 scale.  Omitting it means 70% (7.0); callers can obtain the
equivalent native threshold through :meth:`native_jailbreak_threshold`.

#### native\_jailbreak\_threshold

```python
@classmethod
def native_jailbreak_threshold(cls, judge_range: str,
                               config: Dict[str, Any]) -> float
```

Convert the canonical threshold to a judge&#x27;s native score range.

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

Return the best normalized 0--10 score across judge columns.

#### prepare\_and\_sync

```python
def prepare_and_sync(evaluated_items: list, run_id: str)
```

Prepare evaluated items for backend sync:
- Add _run_id if missing
- Ensure result_id exists
- Build judge_keys
- Call _sync_to_server (only if not already synced by the attack)

#### get\_statistics

```python
def get_statistics() -> Dict[str, Any]
```

Return a copy of execution statistics.

#### run

```python
def run(input_data: List[Dict[str, Any]],
        *,
        prefix_fn=None,
        completion_fn=None,
        technique_params_key: Optional[str] = None,
        evaluator_prefix: Optional[str] = None,
        pre_eval_hook=None) -> List[Dict[str, Any]]
```

Generic evaluation pipeline for any attack technique.

Replaces per-attack evaluation.py boilerplate. Runs the full pipeline:
judge resolution → row transform → evaluation → merge → enrich →
tracker → sync → ASR logging.

**Arguments**:

- `input_data` - Generation output rows.
- `prefix_fn` - ``(item) -&gt; str`` to build the ``prefix`` eval field.
  Falls back to ``full_prompt``, ``best_prompt``, ``goal``.
- `completion_fn` - ``(item) -&gt; str`` to build the ``completion`` field.
  Falls back to ``response``. Use for attacks like CipherChat that
  store the response in a non-standard key.
- `technique_params_key` - Config key (e.g. ``&#x27;flipattack_params&#x27;``) for
  attack-specific judge defaults.
- `evaluator_prefix` - Label prefix for tracker evaluation traces.
- `pre_eval_hook` - Optional ``(input_data, raw_config) -&gt; None`` called
  before judge evaluation (e.g. to emit decoration traces in h4rm3l).

#### make\_execute

```python
@classmethod
def make_execute(cls,
                 *,
                 prefix_fn=None,
                 completion_fn=None,
                 technique_params_key: Optional[str] = None,
                 evaluator_prefix: Optional[str] = None,
                 pre_eval_hook=None)
```

Factory: return an ``execute(input_data, config, logger, client)`` function.

Designed for use as a ``_get_pipeline_steps()`` function reference,
replacing per-attack ``evaluation.execute`` module imports.

Example::

from hackagent.attacks.evaluator.evaluation_step import BaseEvaluationStep

# in _get_pipeline_steps():
{
&quot;function&quot;: BaseEvaluationStep.make_execute(
prefix_fn=lambda item: item.get(&quot;full_prompt&quot;, &quot;&quot;),
technique_params_key=&quot;flipattack_params&quot;,
),
&quot;step_type_enum&quot;: &quot;EVALUATION&quot;,
&quot;required_args&quot;: [&quot;logger&quot;, &quot;client&quot;, &quot;config&quot;],
}

#### make\_postprocess\_execute

```python
@classmethod
def make_postprocess_execute(cls, attack_label: str)
```

Factory: return an execute function that only runs post-processing.

For attacks whose judges run **inline** during generation (BoN, PAP)
and only need sync/ASR logging in the evaluation step.

