---
sidebar_label: evaluation
title: hackagent.attacks.techniques.pap.evaluation
---

PAP post-processing module.

This step runs **after** the generation loop, which already includes inline
judge evaluation with early-stopping.  By the time this step executes,
every result dict already contains ``best_score``, ``success``, and the
raw judge columns.

The post-processing step is responsible for:
- Enriching any items still missing scores (e.g. errors).
- Server sync of evaluation data.
- ASR logging per judge.

## PAPEvaluation Objects

```python
class PAPEvaluation(BaseEvaluationStep)
```

Lightweight post-processing for the PAP attack.

Judge evaluation is performed inline during the generation loop.
This step handles server sync, tracker updates, and ASR logging only.

#### execute

```python
def execute(input_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]
```

Post-process PAP results: enrich scores, sync, and log ASR.

**Arguments**:

- `input_data` - Dicts from the generation step.
  

**Returns**:

  Same list, enriched with any missing ``best_score`` / ``success``.

#### execute

```python
def execute(input_data: List[Dict], config: Dict[str, Any],
            client: AuthenticatedClient, logger: logging.Logger) -> List[Dict]
```

Pipeline-compatible function entry point.

