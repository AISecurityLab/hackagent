---
sidebar_label: evaluation
title: hackagent.attacks.techniques.autodan_turbo.evaluation
---

AutoDAN-Turbo evaluation wrapper using the shared LLM-judge pipeline.

## AutoDANTurboEvaluation Objects

```python
class AutoDANTurboEvaluation(BaseEvaluationStep)
```

Finalize AutoDAN-Turbo outputs with the shared multi-judge flow.

AutoDAN generation still produces an internal attack score
(``autodan_score``/``attack_score``), but jailbreak success is always
computed by configured LLM judge(s) via :class:`BaseEvaluationStep`.

#### execute

```python
def execute(input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]
```

Evaluate AutoDAN outputs using LLM judges.

**Arguments**:

- `input_data` - Per-goal attack outputs from lifelong phase.
  

**Returns**:

  Enriched result list with judge outputs, ``best_score``, and
  ``success`` fields.

#### execute

```python
def execute(input_data, config, client, logger)
```

Module-level pipeline entry point used by attack orchestrator.

**Arguments**:

- `input_data` - Lifelong phase outputs to evaluate.
- `config` - Full attack configuration.
- `client` - Authenticated client for result sync.
- `logger` - Logger instance.
  

**Returns**:

  Finalized and enriched results list.

