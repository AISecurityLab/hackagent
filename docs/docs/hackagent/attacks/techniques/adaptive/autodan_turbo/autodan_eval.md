---
sidebar_label: autodan_eval
title: hackagent.attacks.techniques.adaptive.autodan_turbo.autodan_eval
---

AutoDAN-Turbo evaluation wrapper using the shared LLM-judge pipeline.

## AutoDANTurboEvaluation Objects

```python
class AutoDANTurboEvaluation()
```

Finalize AutoDAN-Turbo outputs.

When `config[&quot;_judge&quot;]` is set, scores come from that judge. Otherwise
success follows the internal AutoDAN score against `break_score`.

#### execute

```python
def execute(input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]
```

Evaluate AutoDAN outputs using LLM judges.

**Arguments**:

- `input_data` - Per-goal attack outputs from lifelong phase.
  

**Returns**:

  Enriched result list with judge outputs, `best_score`, and
  `success` fields.

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

