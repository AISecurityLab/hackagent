---
sidebar_label: evaluation
title: hackagent.attacks.techniques.autodan_turbo.evaluation
---

AutoDAN-Turbo evaluation — multi-judge scoring via BaseEvaluationStep.

## AutoDANTurboEvaluation Objects

```python
class AutoDANTurboEvaluation(BaseEvaluationStep)
```

Run standardized hackagent multi-judge evaluation on attack outputs.

Paper relation: this is an integration-layer extension (not in original
AutoDAN-Turbo paper code) used to align metrics with other techniques.

#### execute

```python
def execute(input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]
```

Evaluate generated responses with configured judges and merge scores.

**Arguments**:

- `input_data` - Per-goal attack outputs from lifelong phase.
  

**Returns**:

  Enriched result list containing judge columns, aggregated
  ``best_score``, and flags like ``judge_success`` while preserving
  ``autodan_score``/``attack_score`` fields.

#### execute

```python
def execute(input_data, config, client, logger)
```

Module-level pipeline entry point used by attack orchestrator.

**Arguments**:

- `input_data` - Lifelong phase outputs to evaluate.
- `config` - Full attack configuration.
- `client` - Authenticated client for judge routing.
- `logger` - Logger instance.
  

**Returns**:

  Evaluated and enriched results list.

