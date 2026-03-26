---
sidebar_label: evaluation
title: hackagent.attacks.techniques.bon.evaluation
---

Best-of-N (BoN) post-processing module.

This step runs **after** the generation loop, which already includes inline
judge evaluation with early-stopping.  By the time this step executes,
every result dict already contains `best_score`, `success`, and the
raw judge columns (`eval_hb`, `eval_jb`, etc.).

The post-processing step is responsible for:
- Enriching any items that are still missing scores (e.g. errors).
- Tracker integration (per-goal evaluation traces).
- Server sync of evaluation data.
- ASR logging per judge.

It does **not** re-evaluate responses with judges — that is done inline
during generation.

## BoNEvaluation Objects

```python
class BoNEvaluation(BaseEvaluationStep)
```

Lightweight post-processing for the Best-of-N (BoN) attack.

Judge evaluation is performed inline during the generation loop.
This step handles server sync, tracker updates, and ASR logging only.

#### execute

```python
def execute(input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]
```

Post-process BoN results: enrich scores, sync, and log ASR.

**Arguments**:

- `input_data` - Dicts from the generation step, each already containing
  `best_score`, `success`, and judge columns from inline
  evaluation.
  

**Returns**:

  Same list, enriched with any missing `best_score` / `success`.

#### execute

```python
def execute(input_data: List[Dict], config: Dict[str, Any],
            client: AuthenticatedClient, logger: logging.Logger) -> List[Dict]
```

Pipeline-compatible function entry point.

Wraps `BoNEvaluation` so that `attack.py` can reference
`evaluation.execute` directly in the pipeline step definition.

