---
sidebar_label: evaluation
title: hackagent.attacks.techniques.autodan_turbo.evaluation
---

AutoDAN-Turbo scorer-only finalization (no judge stage).

## AutoDANTurboEvaluation Objects

```python
class AutoDANTurboEvaluation(BaseEvaluationStep)
```

Finalize AutoDAN-Turbo outputs using scorer threshold only.

The original attack already produces a continuous 1-10 scorer value
(``autodan_score``). This step standardizes result fields and marks
jailbreak success when ``autodan_score >= break_score``.

#### execute

```python
def execute(input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]
```

Finalize generated responses using scorer threshold only.

**Arguments**:

- `input_data` - Per-goal attack outputs from lifelong phase.
  

**Returns**:

  Enriched result list containing judge columns, aggregated
  `best_score`, and flags like `judge_success` while preserving
  `autodan_score`/`attack_score` fields.

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

